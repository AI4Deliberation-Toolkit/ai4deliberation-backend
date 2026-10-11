"""One error shape for every matched /api/v1/ route (spec §7)."""
import logging

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from ninja.errors import AuthenticationError, HttpError, ValidationError

logger = logging.getLogger(__name__)

UNAUTHORIZED = 'UNAUTHORIZED'
TOOL_NOT_FOUND = 'TOOL_NOT_FOUND'
OPERATION_NOT_FOUND = 'OPERATION_NOT_FOUND'
INVALID_REQUEST = 'INVALID_REQUEST'
REQUEST_TOO_LARGE = 'REQUEST_TOO_LARGE'
TOOL_TIMEOUT = 'TOOL_TIMEOUT'
TOOL_UNREACHABLE = 'TOOL_UNREACHABLE'
TOOL_AUTH_FAILED = 'TOOL_AUTH_FAILED'
TOOL_BAD_RESPONSE = 'TOOL_BAD_RESPONSE'
TOOL_ERROR = 'TOOL_ERROR'
INTERNAL = 'INTERNAL'

# TOOL_ERROR is deliberately absent from STATUS and MESSAGES: it is raised only via the adapter's
# ToolError (source `tool`), whose status comes from `tool_error_status` (added in a later task).
STATUS = {
    UNAUTHORIZED: 401,
    TOOL_NOT_FOUND: 404,
    OPERATION_NOT_FOUND: 404,
    INVALID_REQUEST: 422,
    REQUEST_TOO_LARGE: 413,
    TOOL_TIMEOUT: 504,
    TOOL_UNREACHABLE: 502,
    TOOL_AUTH_FAILED: 502,  # deliberately not 401: the caller's key was fine
    TOOL_BAD_RESPONSE: 502,
    INTERNAL: 500,
}

MESSAGES = {
    UNAUTHORIZED: 'Missing or invalid gateway key.',  # one message: no hint which check failed
    TOOL_NOT_FOUND: 'Unknown tool.',
    OPERATION_NOT_FOUND: 'Unknown operation for this tool.',
    INVALID_REQUEST: 'Invalid request.',
    REQUEST_TOO_LARGE: 'Request body is too large.',
    TOOL_TIMEOUT: 'The tool did not answer in time.',
    TOOL_UNREACHABLE: 'The tool could not be reached.',
    TOOL_AUTH_FAILED: "The tool rejected the gateway's credentials.",
    TOOL_BAD_RESPONSE: 'The tool returned a response the gateway could not read.',
    INTERNAL: 'Internal gateway error.',
}


class GatewayError(Exception):
    """An error the gateway itself reports (`source: gateway`)."""

    def __init__(self, code: str, message: str | None = None, *, tool_id: str | None = None):
        self.code = code
        self.status = STATUS[code]
        self.message = message or MESSAGES[code]
        self.tool_id = tool_id
        super().__init__(self.message)


def error_response(request, code, message, status, *, source='gateway', tool_id=None, tool_status=None,
                   tool_body=None) -> JsonResponse:
    error = {
        'source': source,
        'code': code,
        'message': message,
        'request_id': getattr(request, 'request_id', None),
    }
    if tool_id is not None:
        error['tool_id'] = tool_id
    if source == 'tool':
        error['tool_status'] = tool_status
        error['tool_body'] = tool_body
    return JsonResponse({'error': error}, status=status)


def _on_gateway_error(request, exc: GatewayError):
    return error_response(request, exc.code, exc.message, exc.status, tool_id=exc.tool_id)


def _on_authentication_error(request, exc):
    return error_response(request, UNAUTHORIZED, MESSAGES[UNAUTHORIZED], STATUS[UNAUTHORIZED])


def _describe(error: dict) -> str:
    location = '.'.join(str(part) for part in error.get('loc', [])[1:])  # drop 'body' / 'path'
    return f"{location}: {error.get('msg')}" if location else str(error.get('msg'))


def _on_validation_error(request, exc: ValidationError):
    # Ninja already strips input values from these errors, so nothing from the body is echoed.
    message = '; '.join(_describe(e) for e in exc.errors) or MESSAGES[INVALID_REQUEST]
    return error_response(request, INVALID_REQUEST, message, STATUS[INVALID_REQUEST])


def _on_http_error(request, exc: HttpError):
    if exc.status_code == 400:  # Ninja: "Cannot parse request body"
        return error_response(request, INVALID_REQUEST, 'Request body is not valid JSON.', STATUS[INVALID_REQUEST])
    logger.warning('Unexpected Ninja HttpError %s (request_id=%s)', exc.status_code, getattr(request, 'request_id', None))
    return error_response(request, INTERNAL, MESSAGES[INTERNAL], STATUS[INTERNAL])


def _on_request_too_large(request, exc: RequestDataTooBig):
    # Without this, Django's RequestDataTooBig reaches _on_unexpected: a 500 plus a traceback per request.
    message = f'Request body is larger than the gateway accepts ({settings.DATA_UPLOAD_MAX_MEMORY_SIZE} bytes).'
    return error_response(request, REQUEST_TOO_LARGE, message, STATUS[REQUEST_TOO_LARGE])


def _on_unexpected(request, exc: Exception):
    # Required: with DEBUG=False Ninja's default re-raises, which gives Django's HTML 500.
    logger.error('Unhandled error (request_id=%s)', getattr(request, 'request_id', None),
                 exc_info=(type(exc), exc, exc.__traceback__))
    return error_response(request, INTERNAL, MESSAGES[INTERNAL], STATUS[INTERNAL])


def install_error_handlers(api) -> None:
    api.add_exception_handler(GatewayError, _on_gateway_error)
    api.add_exception_handler(AuthenticationError, _on_authentication_error)
    api.add_exception_handler(ValidationError, _on_validation_error)
    api.add_exception_handler(HttpError, _on_http_error)
    api.add_exception_handler(RequestDataTooBig, _on_request_too_large)
    api.add_exception_handler(Exception, _on_unexpected)
