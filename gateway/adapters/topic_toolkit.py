"""The AI4D topic toolkit, as of commit 5bcee4b (spec §6.3)."""
from gateway.adapters.base import Adapter, Outbound, Result, ToolError
from gateway.errors import INVALID_REQUEST, TOOL_BAD_RESPONSE, GatewayError

EXTRACT_PATH = '/api/topics/extract-conversation'
# Envelope options → the toolkit's query parameters; both off by default, as in the toolkit.
EXTRACT_OPTIONS = ('include_labels', 'include_raw')


class TopicToolkitAdapter(Adapter):
    operations = {'extract'}
    read_operations = frozenset()

    def build_request(self, tool, operation, envelope):
        unknown = sorted(set(envelope.options) - set(EXTRACT_OPTIONS))
        if unknown:
            raise GatewayError(INVALID_REQUEST, f'Unknown option(s) for extract: {", ".join(unknown)}. '
                                                f'Allowed: {", ".join(EXTRACT_OPTIONS)}.')
        params = {}
        for name in EXTRACT_OPTIONS:
            value = envelope.options.get(name, False)
            if not isinstance(value, bool):
                raise GatewayError(INVALID_REQUEST, f'Option {name} must be true or false.')
            if value:
                params[name] = 'true'
        # `input` goes as-is: the toolkit validates its own fields (article_id, platform, article, …).
        return Outbound(method='POST', path=EXTRACT_PATH, params=params, json=envelope.input)

    def parse_response(self, tool, operation, status, body):
        if not 200 <= status < 300:  # the toolkit answers 201; the gateway answers 200
            raise ToolError(status, body)
        if not isinstance(body, dict):
            raise GatewayError(TOOL_BAD_RESPONSE, 'The toolkit did not answer with a JSON object.')
        # The toolkit reports no tool version or model ID. Its `backend` is an extractor mode,
        # not a model ID, so it stays in the output only.
        metadata = {}
        if isinstance(body.get('taxonomy_version'), str):
            metadata['taxonomy_version'] = body['taxonomy_version']
        return Result(output=body, metadata=metadata)
