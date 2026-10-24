import json

import httpx

from gateway.adapters.kg_rag import NOT_ANSWERED
from gateway.models import CallLog
from tests.gateway.support import GatewayTestCase, assert_gateway_error, load_fixture, reply_json


def fixture(name):
    return load_fixture(name, 'kg_rag')


class KgRagRouteTests(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_kg_rag_tool(tool_key='rag-key')

    async def test_greek_question_and_answer_survive_unchanged(self):
        ask_request, ask_200 = fixture('ask_request.json'), fixture('ask_200.json')
        self.tool_reply = reply_json(200, ask_200)
        response = await self.call('kg-rag', 'ask', {'input': ask_request, 'session_id': 'sess-1'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {
            'output': {k: ask_200[k] for k in ('answer', 'sparql_generated', 'raw_data_count')},
            'metadata': {'request_id': response['X-Request-Id'], 'tool_id': 'kg-rag', 'operation': 'ask',
                         'session_id': 'sess-1'},
        })
        (sent,) = self.tool_requests
        self.assertEqual((sent.method, str(sent.url)), ('POST', 'https://kg.example.org/ask'))
        self.assertEqual(json.loads(sent.content), {**ask_request, 'history': []})
        self.assertEqual(sent.headers['X-API-Key'], 'rag-key')
        self.assertEqual(sent.extensions['timeout']['read'], 90)

    async def test_not_answered_is_a_502_from_the_tool(self):
        body = fixture('ask_200_not_answered.json')
        self.tool_reply = reply_json(200, body)
        response = await self.call('kg-rag', 'ask', {'input': {'question': 'q'}})
        error = assert_gateway_error(self, response, 502, 'TOOL_ERROR', source='tool')
        self.assertEqual((error['message'], error['tool_id'], error['tool_status'], error['tool_body']),
                         (NOT_ANSWERED, 'kg-rag', 200, body))
        row = await CallLog.objects.aget()
        self.assertEqual((row.status, row.error_code, row.error_source, row.tool_status),
                         (502, 'TOOL_ERROR', 'tool', 200))

    async def test_rag_500_comes_back_in_tool_body(self):
        body = fixture('ask_500.json')
        self.tool_reply = reply_json(500, body)
        error = assert_gateway_error(self, await self.call('kg-rag', 'ask', {'input': {'question': 'q'}}),
                                     502, 'TOOL_ERROR', source='tool')
        self.assertEqual(error['tool_body'], body)
        self.tool_reply = lambda request: httpx.Response(500, text='Internal Server Error')
        error = assert_gateway_error(self, await self.call('kg-rag', 'ask', {'input': {'question': 'q'}}),
                                     502, 'TOOL_ERROR', source='tool')
        self.assertEqual(error['tool_body'], 'Internal Server Error')

    async def test_proxy_error_page_is_a_502_tool_error(self):
        self.tool_reply = lambda request: httpx.Response(
            524, text='<html>' + 'x' * 5000, headers={'Content-Type': 'text/html'})
        error = assert_gateway_error(self, await self.call('kg-rag', 'ask', {'input': {'question': 'q'}}),
                                     502, 'TOOL_ERROR', source='tool')
        self.assertEqual(error['tool_status'], 524)
        self.assertEqual(len(error['tool_body']), 4096)

    async def test_unreadable_success_is_bad_response(self):
        replies = [
            lambda request: httpx.Response(200, text='ok'),
            lambda request: httpx.Response(200),
            lambda request: httpx.Response(200, content=b'{"answer": "\xff"}',
                                           headers={'Content-Type': 'application/json'}),
            reply_json(200, {'answer': 'a'}),
        ]
        for i, reply in enumerate(replies):
            with self.subTest(reply=i):
                self.tool_reply = reply
                response = await self.call('kg-rag', 'ask', {'input': {'question': 'q'}})
                assert_gateway_error(self, response, 502, 'TOOL_BAD_RESPONSE')

    async def test_refused_input_never_reaches_the_rag(self):
        response = await self.call('kg-rag', 'ask', {'input': {'question': 'q', 'wp_user_id': '7'}})
        assert_gateway_error(self, response, 422, 'INVALID_REQUEST')
        self.assertEqual(self.tool_requests, [])
        row = await CallLog.objects.aget()
        self.assertEqual((row.status, row.error_code, row.tool_status, row.tool_duration_ms),
                         (422, 'INVALID_REQUEST', None, None))

    async def test_lone_surrogate_is_422_not_500(self):
        bodies = [
            {'input': {'question': 'a\ud800'}},
            {'input': {'question': 'q', 'history': [['\udfff', 'b']]}},
            {'input': {'question': 'q', '\udfff': 1}},
        ]
        for body in bodies:
            with self.subTest(body=body):
                assert_gateway_error(self, await self.call('kg-rag', 'ask', body), 422, 'INVALID_REQUEST')
        self.assertEqual(self.tool_requests, [])

    async def test_get_is_405_with_allow_post(self):
        response = await self.read('kg-rag', 'ask')
        assert_gateway_error(self, response, 405, 'METHOD_NOT_ALLOWED')
        self.assertEqual(response['Allow'], 'POST')
