"""The gateway's HTTP API, mounted at /api/v1/ (spec §4.2)."""
from asgiref.sync import sync_to_async
from django.db import DatabaseError, connection
from ninja import NinjaAPI

from gateway.errors import install_error_handlers
from gateway.schemas import Health

api = NinjaAPI(
    title='AI4Deliberation Unified API',
    version='1',
    description='Opt-in gateway that calls partner AI tools on behalf of platforms, in one envelope.',
    urls_namespace='gateway',
    docs_url='/docs',
    openapi_url='/openapi.json',
)
install_error_handlers(api)


def _ping_database() -> None:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')


@api.get('/health', auth=None, response={200: Health, 503: Health}, tags=['health'])
async def health(request):
    """Liveness plus a trivial database query. Never calls tools."""
    try:
        await sync_to_async(_ping_database)()
    except DatabaseError:
        return 503, {'status': 'error', 'database': 'error'}
    return 200, {'status': 'ok', 'database': 'ok'}
