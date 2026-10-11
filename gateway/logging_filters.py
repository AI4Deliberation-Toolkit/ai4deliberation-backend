"""Masks secrets in log records before any handler writes them (spec §8.3).

The primary control is pinning httpx/httpcore to WARNING (settings.LOGGING). This filter is
belt and braces for the realistic leak path: an exception message or f-string holding a key.

Imported by LOGGING before Django's apps load: never import models here.
"""
import functools
import logging
import re

REDACTED = '[REDACTED]'

# The platform key format (spec §3.6); gateway.keys validates against it too.
GATEWAY_KEY_PATTERN = r'gw_[A-Z2-7]{8}_[0-9a-f]{64}'
_GATEWAY_KEY_RE = re.compile(GATEWAY_KEY_PATTERN)

_BASE_HEADERS = frozenset({'x-gateway-key', 'x-api-key', 'authorization', 'x-user-context'})
_tool_headers: set[str] = set()


def register_sensitive_header(name: str) -> None:
    """Mask this header's values from now on (every tool's key_header is registered before use)."""
    _tool_headers.add(name.lower())


def _sensitive_headers() -> frozenset[str]:
    return _BASE_HEADERS | frozenset(_tool_headers)


@functools.lru_cache(maxsize=16)
def _header_value_re(names: frozenset[str]) -> re.Pattern:
    alternatives = '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(
        rf'''(?i)(?<![\w-])({alternatives})(["']?\s*[:=]\s*["']?)(?:(?:bearer|basic|token)\s+)?[^\s"',;}}]+'''
    )


def redact_text(text: str) -> str:
    text = _GATEWAY_KEY_RE.sub(REDACTED, text)
    return _header_value_re(_sensitive_headers()).sub(rf'\g<1>\g<2>{REDACTED}', text)


def _redact_dict(values: dict) -> dict:
    headers = _sensitive_headers()
    return {
        key: REDACTED if isinstance(key, str) and key.lower() in headers else _redact(value)
        for key, value in values.items()
    }


def _redact(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return _redact_dict(value)
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact(v) for v in value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    redacted = redact_text(text)
    return redacted if redacted != text else value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(record.msg)
        if isinstance(record.args, dict):
            record.args = _redact_dict(record.args)
        elif record.args:
            record.args = tuple(_redact(arg) for arg in record.args)
        for name, value in list(vars(record).items()):
            if name not in ('msg', 'args') and isinstance(value, dict):
                setattr(record, name, _redact_dict(value))
        if record.exc_info and not record.exc_text:
            record.exc_text = redact_text(logging.Formatter().formatException(record.exc_info))
        return True
