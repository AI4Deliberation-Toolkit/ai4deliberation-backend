"""The AI4D topic toolkit, as of commit 5bcee4b (spec §6.3)."""
from urllib.parse import quote

from gateway.adapters.base import Adapter, Outbound, Result, ToolError
from gateway.errors import INVALID_REQUEST, TOOL_BAD_RESPONSE, GatewayError

EXTRACT_PATH = '/api/topics/extract-conversation'
# Envelope options → the toolkit's query parameters; both off by default, as in the toolkit.
EXTRACT_OPTIONS = ('include_labels', 'include_raw')
# Read operation → (toolkit path, required path parameters, optional query parameters). The toolkit
# checks the values itself (language, k, topic_slug); its 400 comes back mirrored.
READS = {
    'taxonomy': ('/api/topics', (), ('language',)),
    'article-topics': ('/api/topics/article/{article_id}', ('article_id',), ('include_labels', 'include_raw')),
    'similar-articles': ('/api/articles/{platform}/{article_id}/similar', ('platform', 'article_id'),
                         ('k', 'topic_slug')),
}
# true/false query flags: only true is forwarded, as for extract's options.
READ_FLAGS = frozenset({'include_labels', 'include_raw'})
# Where each operation's body carries the taxonomy version.
VERSION_KEYS = {'extract': 'taxonomy_version', 'taxonomy': 'version', 'article-topics': 'taxonomy_version'}


def path_segment(name: str, value: str) -> str:
    """A caller value as exactly one path segment, so it can't change which toolkit endpoint is called.

    Dot segments are refused, not encoded: httpx would normalise them away.
    """
    if value in ('', '.', '..'):
        raise GatewayError(INVALID_REQUEST, f'{name} must not be empty, "." or "..".')
    return quote(value, safe='')


class TopicToolkitAdapter(Adapter):
    operations = {'extract', *READS}
    read_operations = frozenset(READS)

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

    def build_read_request(self, tool, operation, params):
        template, path_names, query_names = READS[operation]
        allowed = (*path_names, *query_names)
        unknown = sorted(set(params) - set(allowed))
        if unknown:
            raise GatewayError(INVALID_REQUEST, f'Unknown parameter(s) for {operation}: {", ".join(unknown)}. '
                                                f'Allowed: {", ".join(allowed)}.')
        missing = [name for name in path_names if name not in params]
        if missing:
            raise GatewayError(INVALID_REQUEST,
                               f'Missing required parameter(s) for {operation}: {", ".join(missing)}.')
        path = template.format(**{name: path_segment(name, params[name]) for name in path_names})
        query = {}
        for name in query_names:
            if name not in params:
                continue
            if name in READ_FLAGS:
                if params[name] not in ('true', 'false'):
                    raise GatewayError(INVALID_REQUEST, f'Parameter {name} must be true or false.')
                if params[name] == 'true':
                    query[name] = 'true'
            else:
                query[name] = params[name]
        return Outbound(method='GET', path=path, params=query)

    def parse_response(self, tool, operation, status, body):
        if not 200 <= status < 300:  # the toolkit answers 201; the gateway answers 200
            raise ToolError(status, body)
        if not isinstance(body, dict):
            raise GatewayError(TOOL_BAD_RESPONSE, 'The toolkit did not answer with a JSON object.')
        # The toolkit reports no tool version or model ID. Its `backend` is an extractor mode,
        # not a model ID, so it stays in the output only.
        metadata = {}
        version_key = VERSION_KEYS.get(operation)
        if version_key and isinstance(body.get(version_key), str):
            metadata['taxonomy_version'] = body[version_key]
        return Result(output=body, metadata=metadata)
