"""The gateway's HTTP API, mounted at /api/v1/ (spec §4.2)."""
from asgiref.sync import sync_to_async
from django.db import DatabaseError, connection
from ninja import NinjaAPI, Path
from ninja.responses import codes_4xx, codes_5xx

from gateway.auth import GatewayKeyAuth
from gateway.errors import TOOL_NOT_FOUND, GatewayError, install_error_handlers
from gateway.invoke import invoke
from gateway.models import SLUG_PATTERN, Tool
from gateway.schemas import CatalogueEntry, Envelope, ErrorResponse, Health, UnifiedResponse

ERRORS = {codes_4xx: ErrorResponse, codes_5xx: ErrorResponse}

api = NinjaAPI(
    title='AI4Deliberation Unified API',
    version='1',
    description=(
        'Opt-in gateway that calls partner AI tools on behalf of platforms, in one envelope. '
        'Send your platform key in X-Gateway-Key. Errors share one shape: {"error": {source, code, message, '
        'request_id, …}}. On 502 or 504, a platform that holds its own key for a tool (reachability "direct" '
        'or "open") may fall back to calling the tool directly.'
    ),
    urls_namespace='gateway',
    docs_url='/docs',
    openapi_url='/openapi.json',
    auth=GatewayKeyAuth(),
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


@api.post('/tools/{tool_id}/{operation}', url_name='call_tool', response={200: UnifiedResponse, **ERRORS},
          tags=['tools'])
async def call_tool(
    request,
    envelope: Envelope,
    tool_id: str = Path(..., pattern=SLUG_PATTERN, max_length=64),
    operation: str = Path(..., pattern=SLUG_PATTERN, max_length=64),
):
    """Call one operation of a registered tool. `input` and `output` stay in the tool's own format.

    Ninja runs auth first, then envelope validation, then this view.
    """
    return await invoke(request, tool_id, operation, envelope)


def _catalogue_entry(tool: Tool) -> dict:
    # Never base_url, key_header or any key.
    return {
        'tool_id': tool.tool_id, 'name': tool.name, 'description': tool.description, 'docs_url': tool.docs_url,
        'operations': list(tool.operations), 'read_operations': tool.read_operation_names(), 'depth': tool.depth,
        'reachability': tool.reachability,
    }


@api.get('/tools', response={200: list[CatalogueEntry], **ERRORS}, tags=['catalogue'])
async def list_tools(request):
    """Enabled tools."""
    return [_catalogue_entry(tool) async for tool in Tool.objects.filter(enabled=True).order_by('tool_id')]


@api.get('/tools/{tool_id}', response={200: CatalogueEntry, **ERRORS}, tags=['catalogue'])
async def get_tool(request, tool_id: str = Path(..., pattern=SLUG_PATTERN, max_length=64)):
    try:
        tool = await Tool.objects.aget(tool_id=tool_id, enabled=True)
    except Tool.DoesNotExist:
        raise GatewayError(TOOL_NOT_FOUND, tool_id=tool_id) from None
    return _catalogue_entry(tool)
