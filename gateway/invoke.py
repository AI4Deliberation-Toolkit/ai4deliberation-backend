"""The unified route's core: lookup → adapter → call → wrap (spec §6.4)."""
import logging

import httpx
from cryptography.fernet import InvalidToken

from gateway import http
from gateway.adapters import ADAPTERS
from gateway.adapters.base import Result, ToolError
from gateway.errors import (
    INTERNAL, OPERATION_NOT_FOUND, TOOL_AUTH_FAILED, TOOL_NOT_FOUND, TOOL_TIMEOUT, TOOL_UNREACHABLE, GatewayError,
)
from gateway.logging_filters import register_sensitive_header
from gateway.models import Tool
from gateway.schemas import Envelope

logger = logging.getLogger(__name__)

TOOL_BODY_TEXT_LIMIT = 4096


async def invoke(request, tool_id: str, operation: str, envelope: Envelope) -> dict:
    try:
        result = await _call_tool(request, tool_id, operation, envelope)
    except (GatewayError, ToolError) as exc:
        exc.tool_id = tool_id
        raise
    return {
        'output': result.output,
        # The gateway's own fields win: a tool can't override them.
        'metadata': {**result.metadata, 'request_id': request.request_id, 'tool_id': tool_id,
                     'operation': operation, 'session_id': envelope.session_id},
    }


async def _call_tool(request, tool_id: str, operation: str, envelope: Envelope) -> Result:
    try:
        tool = await Tool.objects.aget(tool_id=tool_id, enabled=True)
    except Tool.DoesNotExist:
        raise GatewayError(TOOL_NOT_FOUND) from None
    if operation not in tool.operations:
        raise GatewayError(OPERATION_NOT_FOUND)
    adapter = ADAPTERS[tool.adapter]
    outbound = adapter.build_request(tool, operation, envelope)
    headers = _outbound_headers(request, tool)
    try:
        response = await http.get_client().request(
            outbound.method, tool.base_url + outbound.path, params=outbound.params, json=outbound.json,
            headers=headers, timeout=tool.timeout_seconds, follow_redirects=False,
        )
    except httpx.TimeoutException:
        raise GatewayError(TOOL_TIMEOUT) from None
    except httpx.TransportError:  # connect, DNS, TLS
        raise GatewayError(TOOL_UNREACHABLE) from None
    if response.status_code in (401, 403):  # before the adapter sees it
        raise GatewayError(TOOL_AUTH_FAILED)
    try:
        return adapter.parse_response(tool, operation, response.status_code, _json_or_none(response))
    except ToolError as exc:
        if exc.body is None:
            exc.body = response.text[:TOOL_BODY_TEXT_LIMIT]
        raise


def _outbound_headers(request, tool: Tool) -> dict[str, str]:
    """Exactly these headers reach the tool. Nothing else from the incoming request is forwarded,
    so X-Gateway-Key can never leak to a tool."""
    headers = {
        'Content-Type': 'application/json',
        'X-Request-Id': request.request_id,
        'X-Gateway-Caller': request.auth.platform.slug,
    }
    user_context = request.headers.get('X-User-Context')
    if user_context is not None:
        headers['X-User-Context'] = user_context  # forwarded unchanged; never stored or logged
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
