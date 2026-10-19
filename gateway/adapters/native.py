"""Native tools speak the unified envelope themselves (spec §6.2)."""
from gateway.adapters.base import Adapter, Outbound, Result, ToolError
from gateway.errors import TOOL_BAD_RESPONSE, GatewayError


class NativeAdapter(Adapter):
    operations = None
    read_operations = None

    def build_request(self, tool, operation, envelope):
        return Outbound(method='POST', path=f'/{operation}', json=envelope.model_dump())

    def build_read_request(self, tool, operation, params):
        return Outbound(method='GET', path=f'/{operation}', params=dict(params))

    def parse_response(self, tool, operation, status, body):
        if not 200 <= status < 300:
            raise ToolError(status, body)
        if not isinstance(body, dict) or not isinstance(body.get('output'), dict):
            raise GatewayError(TOOL_BAD_RESPONSE, 'A native tool must answer {"output": {...}, "metadata": {...}}.')
        metadata = body.get('metadata')
        if metadata is None:  # a missing key or a JSON null; anything else must be an object
            metadata = {}
        if not isinstance(metadata, dict):
            raise GatewayError(TOOL_BAD_RESPONSE, "A native tool's metadata must be an object.")
        return Result(output=body['output'], metadata=metadata)
