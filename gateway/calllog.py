"""Building and writing CallLog rows; the metadata allow-list (spec §8.1)."""
import asyncio
import logging
from dataclasses import asdict, dataclass

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
