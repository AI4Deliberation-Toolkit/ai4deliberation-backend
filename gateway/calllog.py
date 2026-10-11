"""Building and writing CallLog rows; the metadata allow-list (spec §8.1)."""
import asyncio
import logging
from dataclasses import asdict, dataclass

from django.core.exceptions import RequestDataTooBig

from gateway.errors import INTERNAL
from gateway.models import CallLog

logger = logging.getLogger(__name__)

# Only these tool metadata fields reach the log; the rest still reach the caller.
LOGGED_METADATA = ('tool_version', 'model_id', 'taxonomy_version')
_MAX_METADATA_LENGTH = 100


@dataclass
class CallRecord:
    request_id: str
    platform_id: int
    key_prefix: str
    tool_id: str
    operation: str
    request_bytes: int
    # Until invoke says otherwise, the call is an internal error.
    status: int = 500
    error_code: str | None = INTERNAL
    error_source: str | None = 'gateway'
    tool_status: int | None = None
    duration_ms: int = 0
    tool_duration_ms: int | None = None
    response_bytes: int | None = None
    tool_version: str | None = None
    model_id: str | None = None
    taxonomy_version: str | None = None


def logged_metadata(metadata: dict) -> dict[str, str]:
    return {
        name: value[:_MAX_METADATA_LENGTH]
        for name in LOGGED_METADATA
        if isinstance(value := metadata.get(name), str)
    }


async def write_call_log(record: CallRecord) -> None:
    """Write the row, even if the client disconnects meanwhile. Never raises: the response must not change."""
    try:
        await asyncio.shield(CallLog.objects.acreate(**asdict(record)))
    except Exception as exc:
        logger.warning('Call log row not written (request_id=%s): %s', record.request_id, type(exc).__name__)


def new_record(request, tool_id: str, operation: str) -> CallRecord:
    """A record for an authenticated call to the unified route (`request.auth` must be set)."""
    return CallRecord(
        request_id=request.request_id, platform_id=request.auth.platform_id, key_prefix=request.auth.prefix,
        # Path segments Ninja rejected can be longer than the 64-char columns.
        tool_id=tool_id[:64], operation=operation[:64], request_bytes=_request_bytes(request),
    )


def _request_bytes(request) -> int:
    try:
        return len(request.body)
    except RequestDataTooBig:  # over DATA_UPLOAD_MAX_MEMORY_SIZE: never read it
        return int(request.META.get('CONTENT_LENGTH') or 0)
