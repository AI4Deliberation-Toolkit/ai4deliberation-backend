"""In-process stub tool (spec §9.1): a native tool for tests and staging smoke checks, not a PoC tool.

Async on purpose: the gateway calls itself, and a sync view would hold the worker's thread during the self-call.
"""
import asyncio
import hmac
import json

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

MAX_DELAY_S = 60
METADATA = {'tool_version': 'stub-1', 'model_id': 'none'}
QUERY_ETAG = '"stub-1"'
# echo is a write (POST), query a read (GET).
METHODS = {'echo': 'POST', 'query': 'GET'}


async def _pause(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
async def stub_view(request, operation):
    expected_key = settings.GATEWAY_STUB_KEY
    if expected_key and not hmac.compare_digest(request.headers.get('X-API-Key', '').encode(), expected_key.encode()):
        return JsonResponse({'error': 'invalid stub key'}, status=401)
    if operation not in METHODS:
        return JsonResponse({'error': 'unknown operation'}, status=404)
    if request.method != METHODS[operation]:
        return JsonResponse({'error': 'method not allowed'}, status=405)
    if operation == 'query':
        return _query(request)
    try:
        payload = json.loads(request.body)['input']
        if not isinstance(payload, dict):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'error': 'expected the native envelope: {"input": {...}}'}, status=400)

    delay = payload.get('delay_s')
    if _is_number(delay) and delay > 0:
        await _pause(min(delay, MAX_DELAY_S))
    status = payload.get('status')
    if _is_number(status) and isinstance(status, int) and 400 <= status <= 599:
        return JsonResponse({'error': 'stub error'}, status=status)
    return JsonResponse({'output': {'echo': payload.get('echo')}, 'metadata': METADATA})


def _query(request):
    """Echo the query string, with a fixed ETag, so the gateway's conditional path can be smoke-tested."""
    if request.headers.get('If-None-Match') == QUERY_ETAG:
        response = HttpResponse(status=304)
    else:
        response = JsonResponse({'output': {'query': request.GET.dict()}, 'metadata': METADATA})
    response['ETag'] = QUERY_ETAG
    return response
