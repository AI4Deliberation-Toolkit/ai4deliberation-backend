"""Request ID for every request (spec §3.7)."""
import uuid

from asgiref.sync import iscoroutinefunction
from django.utils.decorators import sync_and_async_middleware


@sync_and_async_middleware
def request_id_middleware(get_response):
    """Generate a UUID4 per request; never accept a caller-supplied one (deferred-decisions #10)."""
    if iscoroutinefunction(get_response):
        async def middleware(request):
            request.request_id = str(uuid.uuid4())
            response = await get_response(request)
            response['X-Request-Id'] = request.request_id
            return response
    else:
        def middleware(request):
            request.request_id = str(uuid.uuid4())
            response = get_response(request)
            response['X-Request-Id'] = request.request_id
            return response
    return middleware
