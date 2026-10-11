import json
from unittest import mock

import httpx
from cryptography.fernet import Fernet
from django.test import override_settings

from gateway.adapters import ADAPTERS
from gateway.adapters.base import Adapter
from tests.gateway.support import GatewayTestCase, assert_gateway_error, load_fixture

UNKNOWN_KEY = 'gw_AAAAAAAA_' + '0' * 64


def reply_json(status, body):
    return lambda request: httpx.Response(status, json=body)


class BrokenAdapter(Adapter):
    def build_request(self, tool, operation, envelope):
        raise RuntimeError('adapter bug with details')


class OrderTests(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_stub_tool()

    async def test_no_key_is_401_even_with_a_malformed_body(self):
        assert_gateway_error(self, await self.call('stub', 'echo', {'input': [1]}, key=None), 401, 'UNAUTHORIZED')

    async def test_wrong_key_is_401(self):
        assert_gateway_error(self, await self.call('stub', 'echo', key=UNKNOWN_KEY), 401, 'UNAUTHORIZED')

    async def test_malformed_envelope_is_422_even_for_an_unknown_tool(self):
        assert_gateway_error(self, await self.call('no-such-tool', 'echo', {'input': [1]}), 422, 'INVALID_REQUEST')

    async def test_unknown_top_level_field_is_422(self):
        response = await self.call('stub', 'echo', {'input': {}, 'inputs': {}})
        assert_gateway_error(self, response, 422, 'INVALID_REQUEST')

    async def test_unparseable_json_is_422(self):
        assert_gateway_error(self, await self.call('stub', 'echo', '{"input": '), 422, 'INVALID_REQUEST')
        response = await self.call('stub', 'echo', 'hello', content_type='text/plain')
        assert_gateway_error(self, response, 422, 'INVALID_REQUEST')

    async def test_path_segments_must_be_slugs(self):
        for tool_id in ('bad.id', 'x' * 65):
            with self.subTest(tool_id=tool_id):
                assert_gateway_error(self, await self.call(tool_id, 'echo'), 422, 'INVALID_REQUEST')
        self.assertEqual(self.tool_requests, [])


class LookupTests(GatewayTestCase):
    async def test_unknown_tool(self):
        error = assert_gateway_error(self, await self.call('nope', 'echo'), 404, 'TOOL_NOT_FOUND')
        self.assertEqual(error['tool_id'], 'nope')

    async def test_disabled_tool(self):
        await self.amake_stub_tool(enabled=False)
        assert_gateway_error(self, await self.call('stub', 'echo'), 404, 'TOOL_NOT_FOUND')
        self.assertEqual(self.tool_requests, [])

    async def test_unknown_operation(self):
        await self.amake_stub_tool()
        assert_gateway_error(self, await self.call('stub', 'summarise'), 404, 'OPERATION_NOT_FOUND')

    async def test_adapter_rejects_bad_options(self):
        await self.amake_toolkit_tool()
        for options in ({'include_labels': 'true'}, {'colour': True}):
            with self.subTest(options=options):
                response = await self.call('topic-toolkit', 'extract', {'input': {}, 'options': options})
                error = assert_gateway_error(self, response, 422, 'INVALID_REQUEST')
                self.assertIn(next(iter(options)), error['message'])
        self.assertEqual(self.tool_requests, [])


class SuccessTests(GatewayTestCase):
    async def test_native_success(self):
        await self.amake_stub_tool()
        self.tool_reply = reply_json(200, {'output': {'echo': 'hi'},
                                           'metadata': {'tool_version': 'stub-1', 'model_id': 'none'}})
        response = await self.call('stub', 'echo', {'input': {'echo': 'hi'}, 'session_id': 'sess-1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'output': {'echo': 'hi'},
            'metadata': {'tool_version': 'stub-1', 'model_id': 'none', 'request_id': response['X-Request-Id'],
                         'tool_id': 'stub', 'operation': 'echo', 'session_id': 'sess-1'},
        })
        sent = self.tool_requests[0]
        self.assertEqual((sent.method, str(sent.url)), ('POST', 'http://127.0.0.1:8000/stub/echo'))
        self.assertEqual(json.loads(sent.content), {'input': {'echo': 'hi'}, 'options': {}, 'session_id': 'sess-1'})

    async def test_tool_cannot_override_gateway_metadata(self):
        await self.amake_stub_tool()
        self.tool_reply = reply_json(200, {'output': {}, 'metadata': {
            'request_id': 'forged', 'tool_id': 'other', 'operation': 'x', 'session_id': 'forged'}})
        response = await self.call('stub', 'echo')
        metadata = response.json()['metadata']
        self.assertEqual(
            (metadata['request_id'], metadata['tool_id'], metadata['operation'], metadata['session_id']),
            (response['X-Request-Id'], 'stub', 'echo', None),
        )

    async def test_toolkit_success(self):
        await self.amake_toolkit_tool()
        self.tool_reply = reply_json(201, load_fixture('extract_201_labels.json'))
        body = {'input': load_fixture('extract_request.json'), 'options': {'include_labels': True}}
        response = await self.call('topic-toolkit', 'extract', body)
        self.assertEqual(response.status_code, 200)  # the toolkit's 201 becomes 200
        self.assertEqual(response.json()['output'], load_fixture('extract_201_labels.json'))
        self.assertEqual(response.json()['metadata']['taxonomy_version'], '2026-05-21-1')
        sent = self.tool_requests[0]
        self.assertEqual(str(sent.url), 'https://toolkit.example.org/api/topics/extract-conversation?include_labels=true')
        self.assertEqual(json.loads(sent.content), load_fixture('extract_request.json'))

    async def test_each_call_uses_the_tool_timeout(self):
        await self.amake_stub_tool(timeout_seconds=7)
        await self.call('stub', 'echo')
        self.assertEqual(self.tool_requests[0].extensions['timeout']['read'], 7)


class ToolOutcomeTests(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_toolkit_tool()

    async def extract(self):
        return await self.call('topic-toolkit', 'extract')

    async def test_tool_4xx_is_mirrored(self):
        self.tool_reply = reply_json(400, load_fixture('extract_400.json'))
        error = assert_gateway_error(self, await self.extract(), 400, 'TOOL_ERROR', source='tool')
        self.assertEqual((error['tool_id'], error['tool_status'], error['tool_body']),
                         ('topic-toolkit', 400, load_fixture('extract_400.json')))

    async def test_tool_5xx_becomes_502(self):
        self.tool_reply = reply_json(500, load_fixture('extract_500.json'))
        error = assert_gateway_error(self, await self.extract(), 502, 'TOOL_ERROR', source='tool')
        self.assertEqual((error['tool_status'], error['tool_body']), (500, load_fixture('extract_500.json')))

    async def test_non_json_error_body_is_text_truncated_to_4kb(self):
        self.tool_reply = lambda request: httpx.Response(503, text='x' * 5000)
        error = assert_gateway_error(self, await self.extract(), 502, 'TOOL_ERROR', source='tool')
        self.assertEqual(error['tool_body'], 'x' * 4096)

    async def test_tool_401_and_403_are_tool_auth_failed(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.tool_reply = reply_json(status, {'detail': 'bad key'})
                error = assert_gateway_error(self, await self.extract(), 502, 'TOOL_AUTH_FAILED')
                self.assertNotIn('tool_body', error)

    async def test_timeout_is_504(self):
        def reply(request):
            raise httpx.ReadTimeout('timed out', request=request)

        self.tool_reply = reply
        assert_gateway_error(self, await self.extract(), 504, 'TOOL_TIMEOUT')

    async def test_transport_error_is_502_unreachable(self):
        def reply(request):
            raise httpx.ConnectError('refused', request=request)

        self.tool_reply = reply
        assert_gateway_error(self, await self.extract(), 502, 'TOOL_UNREACHABLE')

    async def test_non_json_success_is_bad_response(self):
        replies = {
            'text': lambda request: httpx.Response(201, text='created'),
            'empty': lambda request: httpx.Response(201),
            'list': reply_json(201, ['a list']),
            # httpx.Response(json=None) sends an empty body, so build a real JSON null by hand.
            'null': lambda request: httpx.Response(201, content=b'null', headers={'Content-Type': 'application/json'}),
        }
        for name, reply in replies.items():
            with self.subTest(reply=name):
                self.tool_reply = reply
                assert_gateway_error(self, await self.extract(), 502, 'TOOL_BAD_RESPONSE')

    async def test_redirect_is_not_followed(self):
        self.tool_reply = lambda request: httpx.Response(302, headers={'Location': 'https://elsewhere.example.org/x'})
        error = assert_gateway_error(self, await self.extract(), 502, 'TOOL_ERROR', source='tool')
        self.assertEqual(error['tool_status'], 302)
        self.assertEqual([r.url.host for r in self.tool_requests], ['toolkit.example.org'])

    async def test_unexpected_adapter_failure_is_a_generic_500(self):
        with mock.patch.dict(ADAPTERS, {'topic_toolkit': BrokenAdapter()}):
            with self.assertLogs('gateway.errors', 'ERROR') as logs:
                response = await self.extract()
        assert_gateway_error(self, response, 500, 'INTERNAL')
        self.assertNotIn('adapter bug', response.content.decode())
        self.assertIn('Unhandled error', logs.output[0])


class HeaderTests(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_toolkit_tool(tool_key='tool-secret-key', key_header='X-Toolkit-Key')
        self.tool_reply = reply_json(201, load_fixture('extract_201.json'))

    async def test_exactly_the_gateway_headers_are_forwarded(self):
        response = await self.call('topic-toolkit', 'extract', headers={
            'X-User-Context': 'ctx-123', 'X-Custom-Thing': 'nope',
            'Authorization': 'Bearer platform-token', 'Cookie': 'session=abc',
        })
        self.assertEqual(response.status_code, 200)
        sent = self.tool_requests[0]
        self.assertEqual(sent.headers['X-Toolkit-Key'], 'tool-secret-key')
        self.assertEqual(sent.headers['X-Request-Id'], response['X-Request-Id'])
        self.assertEqual(sent.headers['X-Gateway-Caller'], 'wp-site')
        self.assertEqual(sent.headers['X-User-Context'], 'ctx-123')
        self.assertEqual(sent.headers['Content-Type'], 'application/json')
        for name in ('X-Gateway-Key', 'X-Custom-Thing', 'Authorization', 'Cookie'):
            with self.subTest(header=name):
                self.assertNotIn(name, sent.headers)
        self.assertNotIn(self.key, str(sent.headers.raw) + sent.content.decode())

    async def test_no_user_context_when_none_was_sent(self):
        await self.call('topic-toolkit', 'extract')
        self.assertNotIn('X-User-Context', self.tool_requests[0].headers)

    async def test_open_tool_gets_no_key_header(self):
        await self.amake_stub_tool()
        await self.call('stub', 'echo')
        sent = self.tool_requests[0].headers
        self.assertNotIn('X-API-Key', sent)
        self.assertNotIn('X-Toolkit-Key', sent)

    async def test_undecryptable_tool_key_is_internal_error(self):
        with override_settings(GATEWAY_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            with self.assertLogs('gateway.invoke', 'WARNING') as logs:
                response = await self.call('topic-toolkit', 'extract')
        assert_gateway_error(self, response, 500, 'INTERNAL')
        self.assertIn('topic-toolkit', logs.output[0])
        self.assertEqual(self.tool_requests, [])
