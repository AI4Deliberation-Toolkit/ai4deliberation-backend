"""The unified route's core: lookup → adapter → call → wrap (spec §6.4).

The outcome goes on request.call_record; the request-ID middleware writes the CallLog row.
"""
import contextlib
import logging
import time

import httpx
from cryptography.fernet import InvalidToken
from django.http import HttpResponse

from gateway import http
from gateway.adapters import ADAPTERS
from gateway.adapters.base import Adapter, Outbound, Result, ToolError
from gateway.calllog import CallRecord, logged_metadata, new_record
from gateway.errors import (
    INTERNAL, INVALID_REQUEST, METHOD_NOT_ALLOWED, OPERATION_NOT_FOUND, TOOL_AUTH_FAILED, TOOL_BAD_RESPONSE,
    TOOL_ERROR, TOOL_NOT_FOUND, TOOL_TIMEOUT, TOOL_UNREACHABLE, GatewayError,
)
from gateway.logging_filters import register_sensitive_header
from gateway.models import Tool
from gateway.schemas import Envelope

logger = logging.getLogger(__name__)

TOOL_BODY_TEXT_LIMIT = 4096


async def invoke(request, tool_id: str, operation: str, envelope: Envelope) -> dict:
    record = request.call_record = new_record(request, tool_id, operation)
    with _recording_errors(record, tool_id):
        tool, adapter = await _find_tool(tool_id, operation, read=False)
        outbound = adapter.build_request(tool, operation, envelope)
        tool_response = await _send(request, tool, outbound, record, read=False)
        result = _parse(adapter, tool, operation, tool_response)
    return _wrap(request, record, result, tool_id, operation, envelope.session_id)


async def invoke_read(request, tool_id: str, operation: str, response: HttpResponse) -> dict | HttpResponse:
    """A read call (GET): the query string is the input. `response` is Ninja's temporal response,
    which carries the tool's ETag on a 200."""
    record = request.call_record = new_record(request, tool_id, operation)
    if_none_match = request.headers.get('If-None-Match')
    with _recording_errors(record, tool_id):
        params = _read_params(request)
        tool, adapter = await _find_tool(tool_id, operation, read=True)
        outbound = adapter.build_read_request(tool, operation, params)
        tool_response = await _send(request, tool, outbound, record, read=True)
        etag = tool_response.headers.get('ETag')
        if tool_response.status_code == 304:  # before the adapter, which would call it a tool error
            if if_none_match is None:
                raise GatewayError(TOOL_BAD_RESPONSE)
            not_modified = HttpResponse(status=304)
            if etag is not None:
                not_modified['ETag'] = etag
            record.error_code = record.error_source = None
            return not_modified
        result = _parse(adapter, tool, operation, tool_response)
    if etag is not None:
        response['ETag'] = etag  # unchanged, so a cached ETag stays valid in direct mode too
    return _wrap(request, record, result, tool_id, operation, None)


@contextlib.contextmanager
def _recording_errors(record: CallRecord, tool_id: str):
    """Put the error on the record, and the tool ID on the error. Anything unexpected keeps the
    record's defaults (INTERNAL). The middleware stores the status sent."""
    try:
        yield
    except GatewayError as exc:
        exc.tool_id = tool_id
        record.error_code, record.error_source = exc.code, 'gateway'
        raise
    except ToolError as exc:
        exc.tool_id = tool_id
        record.error_code, record.error_source = TOOL_ERROR, 'tool'
        raise


def _read_params(request) -> dict[str, str]:
    # Names only in the message: query values are input, never echoed.
    repeated = sorted(name for name, values in request.GET.lists() if len(values) > 1)
    if repeated:
        raise GatewayError(INVALID_REQUEST, f'Repeated query parameter(s): {", ".join(repeated)}. '
                                            'Give each parameter once.')
    return dict(request.GET.items())


async def _find_tool(tool_id: str, operation: str, *, read: bool) -> tuple[Tool, Adapter]:
    try:
        tool = await Tool.objects.aget(tool_id=tool_id, enabled=True)
    except Tool.DoesNotExist:
        raise GatewayError(TOOL_NOT_FOUND) from None
    if operation not in tool.operations:
        raise GatewayError(OPERATION_NOT_FOUND)
    if read != (operation in tool.read_operation_names()):
        allowed = 'POST' if read else 'GET'
        raise GatewayError(METHOD_NOT_ALLOWED, f'Use {allowed} for this operation.', headers={'Allow': allowed})
    return tool, ADAPTERS[tool.adapter]


async def _send(request, tool: Tool, outbound: Outbound, record: CallRecord, *, read: bool) -> httpx.Response:
    headers = _outbound_headers(request, tool, read=read)
    tool_started = time.perf_counter()
    try:
        response = await http.get_client().request(
            outbound.method, tool.base_url + outbound.path, params=outbound.params, json=outbound.json,
            headers=headers, timeout=tool.timeout_seconds, follow_redirects=False,
        )
    except httpx.TimeoutException:
        raise GatewayError(TOOL_TIMEOUT) from None
    except httpx.DecodingError:  # e.g. a Content-Encoding the body doesn't match; raised before a response exists
        raise GatewayError(TOOL_BAD_RESPONSE) from None
    except httpx.TransportError:  # connect, DNS, TLS
        raise GatewayError(TOOL_UNREACHABLE) from None
    finally:
        record.tool_duration_ms = _ms_since(tool_started)
    record.tool_status = response.status_code
    record.response_bytes = len(response.content)
    if response.status_code in (401, 403):  # before the adapter sees it
        raise GatewayError(TOOL_AUTH_FAILED)
    return response


def _parse(adapter: Adapter, tool: Tool, operation: str, response: httpx.Response) -> Result:
    try:
        return adapter.parse_response(tool, operation, response.status_code, _json_or_none(response))
    except ToolError as exc:
        if exc.body is None:
            exc.body = response.text[:TOOL_BODY_TEXT_LIMIT]
        raise


def _wrap(request, record: CallRecord, result: Result, tool_id: str, operation: str, session_id) -> dict:
    for name, value in logged_metadata(result.metadata).items():
        setattr(record, name, value)
    response = {
        'output': result.output,
        # The gateway's own fields win: a tool can't override them.
        'metadata': {**result.metadata, 'request_id': request.request_id, 'tool_id': tool_id,
                     'operation': operation, 'session_id': session_id},
    }
    record.error_code = record.error_source = None  # last: a failure above leaves INTERNAL in the row
    return response


def _outbound_headers(request, tool: Tool, *, read: bool) -> dict[str, str | bytes]:
    """Exactly these headers reach the tool. Nothing else from the incoming request is forwarded,
    so X-Gateway-Key can never leak to a tool."""
    headers = {
        'X-Request-Id': request.request_id,
        'X-Gateway-Caller': request.auth.platform.slug,
    }
    if read:
        # No body, so no Content-Type. Uncompressed: a proxy that compresses (Cloudflare, in front of
        # Runpod) turns a strong ETag weak, and a weak one never matches the tool's If-None-Match check.
        headers['Accept-Encoding'] = 'identity'
        if_none_match = request.headers.get('If-None-Match')
        if if_none_match is not None:  # raw bytes, as for X-User-Context below
            headers['If-None-Match'] = if_none_match.encode('latin-1')
    else:
        headers['Content-Type'] = 'application/json'
    user_context = request.headers.get('X-User-Context')
    if user_context is not None:
        # Forwarded unchanged; never stored or logged. Django decoded the header bytes as latin-1, so
        # encoding back gives the original bytes, which httpx sends verbatim (a str must be ASCII).
        headers['X-User-Context'] = user_context.encode('latin-1')
    try:
        key = tool.get_tool_key()
    except InvalidToken:
        logger.warning('The tool key of %s cannot be decrypted with GATEWAY_ENCRYPTION_KEYS', tool.tool_id)
        raise GatewayError(INTERNAL) from None
    if key:
        register_sensitive_header(tool.key_header)
        headers[tool.key_header] = key
    return headers


def _json_or_none(response: httpx.Response):
    try:
        return response.json()
    except ValueError:  # not JSON, including empty or undecodable bodies
        return None


def _ms_since(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
