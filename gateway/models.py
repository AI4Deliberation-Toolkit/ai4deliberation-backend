import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from gateway.crypto import decrypt, encrypt
from gateway.logging_filters import register_sensitive_header

# Tool IDs and operations are URL segments: the routes validate them with SLUG_PATTERN,
# the registry with _SLUG_RE (same character set, used with fullmatch).
SLUG_PATTERN = r'^[-a-zA-Z0-9_]+$'
_SLUG_RE = re.compile(r'[-a-zA-Z0-9_]+')
_HEADER_RE = re.compile(r'[A-Za-z0-9-]+')
# Headers the gateway sets itself on every outbound call (spec §6.4 step 4).
_GATEWAY_HEADERS = frozenset({'content-type', 'x-request-id', 'x-gateway-caller', 'x-user-context', 'x-gateway-key'})
_LOOPBACK_HOSTS = frozenset({'localhost', '127.0.0.1', '::1'})
# nginx's proxy_read_timeout is 300 s, and it must exceed every tool timeout.
MAX_TIMEOUT_SECONDS = 290


class Platform(models.Model):
    """A platform (e.g. the WP site) that calls tools through the gateway."""

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=64, unique=True)
    contact = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ApiKey(models.Model):
    """A platform key. Only the prefix and the SHA-256 of the whole key are stored."""

    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name='api_keys')
    prefix = models.CharField(max_length=8, unique=True, editable=False)
    key_hash = models.CharField(max_length=64, editable=False)
    label = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'API key'

    def __str__(self):
        return f'gw_{self.prefix}_…'


class Tool(models.Model):
    """A registered tool. Changing base_url moves the tool without a redeploy (spec §5)."""

    class Depth(models.TextChoices):
        NATIVE = 'native'
        ADAPTED = 'adapted'
        PASSTHROUGH = 'passthrough'  # reserved; refused in v0

    tool_id = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    docs_url = models.URLField(blank=True)
    base_url = models.CharField(max_length=500, help_text='http(s) URL, no trailing slash, no query string.')
    depth = models.CharField(max_length=16, choices=Depth.choices)
    # Validated against gateway.adapters.ADAPTERS in clean(), not `choices`: a new adapter needs no migration.
    adapter = models.CharField(max_length=64)
    operations = models.JSONField(default=list, help_text='JSON list of operation slugs, e.g. ["extract"].')
    read_operations = models.JSONField(
        default=list, blank=True,
        help_text='Native tools only: JSON list of the operations that are read calls (GET), e.g. ["query"]. '
                  'Adapted tools: leave empty; the adapter declares them.',
    )
    tool_key = models.TextField(blank=True, default='', editable=False)  # MultiFernet token, never plaintext
    key_header = models.CharField(max_length=100, default='X-API-Key')
    gateway_only = models.BooleanField(default=False)
    timeout_seconds = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(MAX_TIMEOUT_SECONDS)],
    )
    health_path = models.CharField(max_length=500, blank=True, help_text='Starts with "/"; may include a query.')
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tool_id']

    def __str__(self):
        return self.tool_id

    def save(self, *args, **kwargs):
        self.full_clean()  # the same rules for admin and code paths
        register_sensitive_header(self.key_header)
        super().save(*args, **kwargs)

    def clean(self):
        from gateway.adapters import ADAPTERS  # adapters import Ninja; keep that out of model loading

        if self.read_operations is None:  # a cleared admin field; blank=True lets it past clean_fields
            self.read_operations = []
        errors = {}
        adapter = ADAPTERS.get(self.adapter)
        if adapter is None:
            errors['adapter'] = f'Unknown adapter. Choose one of: {", ".join(sorted(ADAPTERS))}.'
        if self.depth == self.Depth.PASSTHROUGH:
            errors['depth'] = 'Pass-through is reserved and not built in v0.'
        elif (self.depth == self.Depth.NATIVE) != (self.adapter == 'native'):
            errors.setdefault('adapter', 'Native tools use the "native" adapter, and only native tools do.')
        for field, error in (
            ('operations', self._operations_error(adapter)),
            ('read_operations', self._read_operations_error(adapter)),
            ('base_url', self._base_url_error()),
            ('health_path', self._health_path_error()),
            ('key_header', self._key_header_error()),
        ):
            if error:
                errors[field] = error
        if errors:
            raise ValidationError(errors)

    def _operations_error(self, adapter):
        ops = self.operations
        if (not isinstance(ops, list) or not ops
                or not all(isinstance(op, str) and len(op) <= 64 and _SLUG_RE.fullmatch(op) for op in ops)):
            return 'A non-empty JSON list of operation slugs (letters, digits, "-" and "_"; at most 64 characters).'
        if len(set(ops)) != len(ops):
            return 'Operations must not repeat.'
        if adapter is not None and adapter.operations is not None:
            unsupported = sorted(set(ops) - adapter.operations)
            if unsupported:
                return f'Not supported by the {self.adapter} adapter: {", ".join(unsupported)}.'
        return None

    def _read_operations_error(self, adapter):
        reads = self.read_operations
        if not isinstance(reads, list) or not all(isinstance(op, str) and _SLUG_RE.fullmatch(op) for op in reads):
            return 'A JSON list of operation slugs.'
        if len(set(reads)) != len(reads):
            return 'Read operations must not repeat.'
        if not set(reads) <= set(self.operations if isinstance(self.operations, list) else []):
            return 'Each read operation must also be in operations.'
        if reads and adapter is not None and adapter.read_operations is not None:
            return 'Adapted tools: the adapter declares its read operations; leave this empty.'
        return None

    def read_operation_names(self) -> list[str]:
        """The operations called with GET, in `operations` order."""
        from gateway.adapters import ADAPTERS

        adapter = ADAPTERS.get(self.adapter)
        if adapter is None:  # a row saved before its adapter left the code: keep the catalogue up
            return []
        declared = adapter.read_operations
        reads = set(self.read_operations) if declared is None else declared
        return [op for op in self.operations if op in reads]

    def _base_url_error(self):
        try:
            parts = urlsplit(self.base_url)
            hostname = parts.hostname  # also raises ValueError for e.g. "http://[bad]"
        except ValueError:
            return 'Use an absolute http:// or https:// URL.'
        if parts.scheme not in ('http', 'https') or not hostname:
            return 'Use an absolute http:// or https:// URL.'
        if parts.username or parts.password:
            return 'Put credentials in the tool key, not in the URL.'
        if '?' in self.base_url or '#' in self.base_url:
            return 'No query string or fragment.'
        if self.base_url.endswith('/'):
            return 'No trailing slash: paths are appended to it.'
        return None

    def _health_path_error(self):
        if self.health_path and not self.health_path.startswith('/'):
            return 'Start with "/": it is appended to base_url.'
        return None

    def _key_header_error(self):
        if not _HEADER_RE.fullmatch(self.key_header or ''):
            return 'Use a header name: letters, digits and "-".'
        if self.key_header.lower() in _GATEWAY_HEADERS:
            return 'The gateway sets this header itself; pick another.'
        return None

    @property
    def uses_plain_http_off_loopback(self) -> bool:
        """True when the tool key would travel unencrypted (admin shows a warning; allowed)."""
        parts = urlsplit(self.base_url)
        return parts.scheme == 'http' and parts.hostname not in _LOOPBACK_HOSTS

    @property
    def has_tool_key(self) -> bool:
        return bool(self.tool_key)

    def set_tool_key(self, plaintext: str) -> None:
        self.tool_key = encrypt(plaintext)

    def clear_tool_key(self) -> None:
        self.tool_key = ''

    def get_tool_key(self) -> str | None:
        """Decrypt at call time only. Raises InvalidToken if GATEWAY_ENCRYPTION_KEYS can't read it."""
        return decrypt(self.tool_key) if self.tool_key else None

    @property
    def reachability(self) -> str:
        if not self.tool_key:
            return 'open'
        return 'gateway_only' if self.gateway_only else 'direct'


class CallLog(models.Model):
    """One row per authenticated call to the unified route, written by the middleware: metadata only (spec §8.1).

    Never stored: bodies, tool_body, X-User-Context, any key, client IP.
    """

    request_id = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name='calls')
    key_prefix = models.CharField(max_length=8)
    tool_id = models.CharField(max_length=64)
    operation = models.CharField(max_length=64)
    status = models.PositiveSmallIntegerField()
    error_code = models.CharField(max_length=32, null=True, blank=True)
    error_source = models.CharField(max_length=16, null=True, blank=True)
    tool_status = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField()
    tool_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    request_bytes = models.PositiveIntegerField(help_text='Size of the incoming request body.')
    response_bytes = models.PositiveIntegerField(
        null=True, blank=True, help_text="Size of the tool's response body; empty when the tool never answered.",
    )
    tool_version = models.CharField(max_length=100, null=True, blank=True)
    model_id = models.CharField(max_length=100, null=True, blank=True)
    taxonomy_version = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'call log entry'
        verbose_name_plural = 'call log'

    def __str__(self):
        return f'{self.request_id} {self.tool_id}/{self.operation} {self.status}'
