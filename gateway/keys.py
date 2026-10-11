"""Platform API keys: format, hashing, verification (spec §3.6).

Keys are high-entropy random strings, so a fast hash (SHA-256) is right; a password hash isn't needed.
"""
import base64
import hashlib
import hmac
import re
import secrets

from gateway.logging_filters import GATEWAY_KEY_PATTERN
from gateway.models import ApiKey

_KEY_RE = re.compile(GATEWAY_KEY_PATTERN)


def generate_key() -> tuple[str, str]:
    """Return (prefix, key): `gw_<8 base32 chars>_<64 hex chars>`.

    Hex, not token_urlsafe, for the secret: urlsafe output contains `_`, which made the format ambiguous.
    """
    prefix = base64.b32encode(secrets.token_bytes(5)).decode('ascii')
    return prefix, f'gw_{prefix}_{secrets.token_hex(32)}'


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode('ascii')).hexdigest()


def assign_new_key(api_key: ApiKey) -> str:
    """Give an unsaved ApiKey a fresh prefix and hash; return the plaintext key (shown once, never stored)."""
    prefix, key = generate_key()
    api_key.prefix = prefix
    api_key.key_hash = hash_key(key)
    return key


def issue_key(platform, label: str = '') -> tuple[str, ApiKey]:
    api_key = ApiKey(platform=platform, label=label)
    key = assign_new_key(api_key)
    api_key.save()
    return key, api_key


async def averify_key(key: str | None) -> ApiKey | None:
    """The ApiKey (with its platform loaded) for a valid, unrevoked key of an active platform; else None."""
    if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
        return None
    try:
        api_key = await ApiKey.objects.select_related('platform').aget(prefix=key[3:11])
    except ApiKey.DoesNotExist:
        return None
    if not hmac.compare_digest(api_key.key_hash, hash_key(key)):
        return None
    if api_key.revoked_at is not None or not api_key.platform.is_active:
        return None
    return api_key
