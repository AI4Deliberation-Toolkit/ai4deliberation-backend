import httpx
from asgiref.sync import sync_to_async

from gateway.models import Tool
from tests.gateway.support import GatewayTestCase, assert_gateway_error, capture_logs, load_fixture, reply_json

ETAG = '"v1-el"'
TOOLKIT_ETAG = '"2026-05-21-1-el"'


class ReadRouteTests(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_reader_stub_tool(tool_key='stub-secret')

    async def test_native_read_success(self):
        self.tool_reply = reply_json(200, {'output': {'q': 'x'}, 'metadata': {'tool_version': 'stub-1'}})
        response = await self.read('stub', 'query', {'a': '1', 'b': 'two words'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'output': {'q': 'x'}, 'metadata': {
            'tool_version': 'stub-1', 'request_id': response['X-Request-Id'], 'tool_id': 'stub',
            'operation': 'query', 'session_id': None}})
        sent = self.tool_requests[0]
        self.assertEqual((sent.method, sent.url.path, dict(sent.url.params)),
                         ('GET', '/stub/query', {'a': '1', 'b': 'two words'}))

    async def test_gateway_headers_on_reads(self):
        response = await self.read('stub', 'query')
        sent = self.tool_requests[0].headers
        self.assertEqual((sent['X-Request-Id'], sent['X-Gateway-Caller'], sent['X-API-Key']),
                         (response['X-Request-Id'], 'wp-site', 'stub-secret'))
        self.assertNotIn('X-Gateway-Key', sent)

    async def test_reads_ask_for_an_uncompressed_answer(self):  # Review Focus 1
        await self.read('stub', 'query')
        await self.call('stub', 'echo')
        read, write = self.tool_requests
        self.assertEqual(read.headers['Accept-Encoding'], 'identity')
        self.assertIn('gzip', write.headers['Accept-Encoding'])  # writes keep httpx's default

    async def test_get_sends_no_body_and_no_content_type(self):  # Review Focus 3
        with capture_logs('django.request'):
            await self.async_client.generic('GET', '/api/v1/tools/stub/query', b'{"input": {}}',
                                            content_type='application/json', headers={'X-Gateway-Key': self.key})
        sent = self.tool_requests[0]
        self.assertEqual(sent.content, b'')
        self.assertNotIn('Content-Type', sent.headers)

    async def test_if_none_match_goes_out_and_etag_comes_back_unchanged(self):
        self.tool_reply = lambda request: httpx.Response(200, json={'output': {}}, headers={'ETag': ETAG})
        response = await self.read('stub', 'query', headers={'If-None-Match': ETAG})
        self.assertEqual(self.tool_requests[0].headers['If-None-Match'], ETAG)
        self.assertEqual(response['ETag'], ETAG)

    async def test_no_etag_from_the_tool_means_no_etag_header(self):
        response = await self.read('stub', 'query')
        self.assertNotIn('ETag', response)
        self.tool_reply = lambda request: httpx.Response(304)
        response = await self.read('stub', 'query', headers={'If-None-Match': ETAG})
        self.assertEqual(response.status_code, 304)
        self.assertNotIn('ETag', response)

    async def test_304_passes_through_with_its_etag_and_no_body(self):
        self.tool_reply = lambda request: httpx.Response(304, headers={'ETag': ETAG})
        response = await self.read('stub', 'query', headers={'If-None-Match': ETAG})
        self.assertEqual((response.status_code, response.content, response['ETag']), (304, b'', ETAG))

    async def test_304_without_if_none_match_is_a_bad_response(self):
        self.tool_reply = lambda request: httpx.Response(304, headers={'ETag': ETAG})
        assert_gateway_error(self, await self.read('stub', 'query'), 502, 'TOOL_BAD_RESPONSE')

    async def test_repeated_parameter_is_422_before_any_tool_call(self):
        for tool_id in ('stub', 'no-such-tool'):
            with self.subTest(tool_id=tool_id):
                response = await self.read(tool_id, 'query', {'a': ['1', '2'], 'b': '3'})
                error = assert_gateway_error(self, response, 422, 'INVALID_REQUEST')
                self.assertIn('a', error['message'])
        self.assertEqual(self.tool_requests, [])

    async def test_get_on_a_write_operation_is_405(self):
        response = await self.read('stub', 'echo')
        assert_gateway_error(self, response, 405, 'METHOD_NOT_ALLOWED')
        self.assertEqual(response['Allow'], 'POST')
        self.assertEqual(self.tool_requests, [])

    async def test_post_on_a_read_operation_is_405(self):
        response = await self.call('stub', 'query')
        assert_gateway_error(self, response, 405, 'METHOD_NOT_ALLOWED')
        self.assertEqual(response['Allow'], 'GET')
        self.assertEqual(self.tool_requests, [])

    async def test_unknown_tool_and_operation_are_404(self):
        assert_gateway_error(self, await self.read('nope', 'query'), 404, 'TOOL_NOT_FOUND')
        assert_gateway_error(self, await self.read('stub', 'nope'), 404, 'OPERATION_NOT_FOUND')

    async def test_no_key_is_401(self):
        assert_gateway_error(self, await self.read('stub', 'query', key=None), 401, 'UNAUTHORIZED')

    async def test_tool_404_is_mirrored(self):
        self.tool_reply = reply_json(404, {'detail': 'Not found.'})
        error = assert_gateway_error(self, await self.read('stub', 'query'), 404, 'TOOL_ERROR', source='tool')
        self.assertEqual(error['tool_body'], {'detail': 'Not found.'})

    async def test_read_answers_are_never_cacheable(self):  # Review Focus 2
        replies = {
            '200': lambda r: httpx.Response(200, json={'output': {}}, headers={'Cache-Control': 'public, max-age=300'}),
            '304': lambda r: httpx.Response(304, headers={'Cache-Control': 'public, max-age=300'}),
            '404': reply_json(404, {}),
            '502': reply_json(500, {}),
        }
        for name, reply in replies.items():
            with self.subTest(reply=name):
                self.tool_reply = reply
                response = await self.read('stub', 'query', headers={'If-None-Match': ETAG})
                self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual((await self.read('stub', 'query', key=None))['Cache-Control'], 'no-store')

    async def test_writes_carry_no_conditional_headers(self):  # Review Focus 4
        self.tool_reply = lambda request: httpx.Response(200, json={'output': {}}, headers={'ETag': ETAG})
        response = await self.call('stub', 'echo', headers={'If-None-Match': ETAG})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('If-None-Match', self.tool_requests[0].headers)
        for name in ('ETag', 'Cache-Control'):
            self.assertNotIn(name, response)

    async def test_a_304_on_a_write_is_unchanged(self):
        self.tool_reply = lambda request: httpx.Response(304)
        assert_gateway_error(self, await self.call('stub', 'echo'), 502, 'TOOL_ERROR', source='tool')

    async def test_reads_use_the_tool_timeout(self):
        await sync_to_async(Tool.objects.filter(tool_id='stub').update)(timeout_seconds=7)
        await self.read('stub', 'query')
        self.assertEqual(self.tool_requests[0].extensions['timeout']['read'], 7)


class ToolkitReadTests(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_toolkit_tool(operations=['extract', 'taxonomy', 'article-topics', 'similar-articles'])

    def taxonomy_reply(self, request):
        if request.headers.get('If-None-Match') == TOOLKIT_ETAG:
            return httpx.Response(304, headers={'ETag': TOOLKIT_ETAG})
        return httpx.Response(200, json=load_fixture('taxonomy_200.json'),
                              headers={'ETag': TOOLKIT_ETAG, 'Cache-Control': 'public, max-age=300'})

    async def test_taxonomy_round_trip(self):
        self.tool_reply = self.taxonomy_reply
        first = await self.read('topic-toolkit', 'taxonomy', {'language': 'el'})
        self.assertEqual((first.status_code, first['ETag'], first['Cache-Control']), (200, TOOLKIT_ETAG, 'no-store'))
        self.assertEqual(first.json()['output'], load_fixture('taxonomy_200.json'))
        self.assertEqual(first.json()['metadata']['taxonomy_version'], '2026-05-21-1')
        self.assertEqual(str(self.tool_requests[0].url), 'https://toolkit.example.org/api/topics?language=el')
        second = await self.read('topic-toolkit', 'taxonomy', {'language': 'el'},
                                 headers={'If-None-Match': first['ETag']})
        self.assertEqual((second.status_code, second.content, second['ETag']), (304, b'', TOOLKIT_ETAG))

    async def test_article_topics_404_is_mirrored(self):
        self.tool_reply = reply_json(404, load_fixture('article_topics_404.json'))
        response = await self.read('topic-toolkit', 'article-topics', {'article_id': 'missing'})
        error = assert_gateway_error(self, response, 404, 'TOOL_ERROR', source='tool')
        self.assertEqual(error['tool_body'], load_fixture('article_topics_404.json'))

    async def test_path_values_never_change_the_tool_path(self):
        self.tool_reply = reply_json(200, load_fixture('article_topics_200.json'))
        await self.read('topic-toolkit', 'article-topics', {'article_id': '../../extract-conversation'})
        self.assertEqual(self.tool_requests[0].url.raw_path, b'/api/topics/article/..%2F..%2Fextract-conversation')
        response = await self.read('topic-toolkit', 'article-topics', {'article_id': '..'})
        assert_gateway_error(self, response, 422, 'INVALID_REQUEST')
        self.assertEqual(len(self.tool_requests), 1)

    async def test_extract_is_still_a_write(self):
        response = await self.read('topic-toolkit', 'extract')
        self.assertEqual((response.status_code, response['Allow']), (405, 'POST'))
