"""Request ID for every request (spec §3.7); access line and CallLog row for unified calls (spec §8.1).

The middleware sees every request to the unified route, including those Ninja rejects before the
view (401, 422, 413), with request.auth already set when auth passed. So it is the single place
that writes both, and the stored status is always the status sent (499 if the client disconnected first).
"""
import asyncio
import logging
import time
import uuid
from urllib.parse import quote

from asgiref.sync import async_to_sync, iscoroutinefunction
from django.utils.decorators import sync_and_async_middleware

from gateway.calllog import new_record, write_call_log
from gateway.errors import CLIENT_DISCONNECTED, INTERNAL, INVALID_REQUEST, REQUEST_TOO_LARGE

access_logger = logging.getLogger('gateway.access')
UNIFIED_ROUTE = 'gateway:call_tool'
# Authenticated requests Ninja rejects before the view: status sent → error code stored.
_REJECTED_BEFORE_VIEW = {413: REQUEST_TOO_LARGE, 422: INVALID_REQUEST}
# nginx's convention for "the client closed the connection before the response": stored and
# logged, never sent (there is no one left to send it to).
CLIENT_DISCONNECTED_STATUS = 499


@sync_and_async_middleware
def request_id_middleware(get_response):
    """Generate a UUID4 per request; never accept a caller-supplied one (deferred-decisions #10)."""
    if iscoroutinefunction(get_response):
        async def middleware(request):
            started = _start(request)
            try:
                response = await get_response(request)
            except asyncio.CancelledError:
                # Django's ASGIHandler cancels the request task on http.disconnect: still log the call.
                record = _log_call(request, _unified_match(request), CLIENT_DISCONNECTED_STATUS, started)
                if record is not None:
                    record.error_code, record.error_source = CLIENT_DISCONNECTED, 'gateway'
                    await write_call_log(record)
                raise
            record = _finish(request, response, started)
            if record is not None:
                await write_call_log(record)  # shielded: a client disconnect doesn't cancel it
            return response
    else:
        def middleware(request):
            started = _start(request)
            response = get_response(request)
            record = _finish(request, response, started)
            if record is not None:
                async_to_sync(write_call_log)(record)
            return response
    return middleware


def _start(request) -> float:
    request.request_id = str(uuid.uuid4())
    return time.perf_counter()


def _loggable(segment: str) -> str:
    """Path segments are caller-controlled and unvalidated here: cut and percent-encode so they can't
    forge or split a log line. Valid slugs come out unchanged."""
    return quote(segment[:64], safe='')


def _finish(request, response, started: float):
    """Set the headers, then log the call. Return the CallRecord to store, if any."""
    response['X-Request-Id'] = request.request_id
    match = _unified_match(request)
    if match is not None and request.method == 'GET':
        # Every read answer, errors included (they come from Ninja's handlers, outside the view):
        # it is for one authenticated caller, so no proxy or browser may store it.
        response['Cache-Control'] = 'no-store'
    return _log_call(request, match, response.status_code, started)


def _unified_match(request):
    """The request's ResolverMatch if it resolved to the unified route (either method), else None."""
    match = getattr(request, 'resolver_match', None)
    return match if match is not None and match.view_name == UNIFIED_ROUTE else None


def _log_call(request, match, status: int, started: float):
    """For the unified route (`match` not None), write the access line with this status.
    Return the CallRecord to store, if any."""
    if match is None:
        return None
    duration_ms = int((time.perf_counter() - started) * 1000)
    api_key = getattr(request, 'auth', None)  # set by Ninja only after successful auth
    tool_id, operation = match.kwargs.get('tool_id', ''), match.kwargs.get('operation', '')
    access_logger.info('%s %s %s %s %s %d', request.request_id, api_key.platform.slug if api_key else '-',
                       _loggable(tool_id), _loggable(operation), status, duration_ms)
    if api_key is None:
        return None  # unauthenticated: the access line only, never a row (spec §8.1)
    record = getattr(request, 'call_record', None)
    if record is None:  # Ninja rejected it before invoke ran
        record = new_record(request, tool_id, operation)
        record.error_code = _REJECTED_BEFORE_VIEW.get(status, INTERNAL)
    record.status = status
    record.duration_ms = duration_ms
    return record
