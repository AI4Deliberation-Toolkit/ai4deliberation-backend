import logging

import httpx

from gateway.models import CallLog
from tests.gateway.support import GatewayTestCase, reply_json

BODY = 'SENTINEL-BODY-5f1c'
CONTEXT = 'SENTINEL-USER-CONTEXT-8a2e'
TOOL_KEY = 'SENTINEL-TOOL-KEY-c39d'
METADATA = 'SENTINEL-METADATA-77b0'
ERROR_BODY = 'SENTINEL-ERROR-BODY-e41a'
CLIENT_IP = '203.0.113.77'
QUERY = 'SENTINEL-QUERY-9d3b'
INM = 'SENTINEL-IF-NONE-MATCH-41f0'


class PrivacyChecks:
    """The sentinel checks, shared as a mixin: subclassing PrivacyTests would run its tests twice."""

    def setUp(self):
        super().setUp()
        # GatewayTestCase silences gateway.access; here the root capture must see it too.
        access_logger = logging.getLogger('gateway.access')
        base_scope = self.async_client._base_scope
        self.async_client._base_scope = lambda **request: {**base_scope(**request), 'client': [CLIENT_IP, 54321]}
        access_logger.propagate = True  # the base class's cleanup restores the original value

    def secrets(self):
        return (BODY, CONTEXT, TOOL_KEY, self.key, self.key[12:], CLIENT_IP)

    async def stored_text(self):
        rows = [row async for row in CallLog.objects.all()]
        return ' '.join(str(getattr(row, field.attname)) for row in rows for field in CallLog._meta.fields)

    @staticmethod
    def logged_text(logs):
        return '\n'.join(logs.output + [repr(vars(record)) for record in logs.records])

    def assert_absent(self, needles, *haystacks):
        for needle in needles:
            for haystack in haystacks:
                with self.subTest(needle=needle):
                    self.assertNotIn(needle, haystack)


class PrivacyTests(PrivacyChecks, GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_stub_tool(tool_key=TOOL_KEY)

    async def test_success_path_stores_and_logs_no_content(self):
        self.tool_reply = lambda request: httpx.Response(200, json={
            'output': {'echo': BODY}, 'metadata': {'tool_version': 'stub-1', 'note': METADATA}})
        with self.assertLogs(level='DEBUG') as logs:
            response = await self.call('stub', 'echo', {'input': {'text': BODY}},
                                       headers={'X-User-Context': CONTEXT})
        self.assertEqual(response.status_code, 200)
        # The sentinels really flowed: to the tool and back to the caller.
        self.assertEqual(self.tool_requests[0].headers['X-User-Context'], CONTEXT)
        self.assertEqual(response.json()['metadata']['note'], METADATA)  # unknown metadata still reaches the caller
        self.assertTrue(any(r.name == 'gateway.access' for r in logs.records))  # the access line was captured
        self.assert_absent((*self.secrets(), METADATA), await self.stored_text(), self.logged_text(logs))
        row = await CallLog.objects.aget()
        self.assertEqual(row.tool_version, 'stub-1')

    async def test_tool_error_body_goes_to_the_caller_only(self):
        self.tool_reply = lambda request: httpx.Response(500, json={'error': ERROR_BODY})
        with self.assertLogs(level='DEBUG') as logs:
            response = await self.call('stub', 'echo', {'input': {'text': BODY}},
                                       headers={'X-User-Context': CONTEXT})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['error']['tool_body'], {'error': ERROR_BODY})
        self.assert_absent((*self.secrets(), ERROR_BODY), await self.stored_text(), self.logged_text(logs))

    async def test_timeout_path(self):
        def reply(request):
            raise httpx.ReadTimeout('timed out', request=request)

        self.tool_reply = reply
        with self.assertLogs(level='DEBUG') as logs:
            await self.call('stub', 'echo', {'input': {'text': BODY}},
                            headers={'X-User-Context': CONTEXT})
        self.assert_absent(self.secrets(), await self.stored_text(), self.logged_text(logs))

    async def test_unauthenticated_calls_write_no_row_and_log_no_key(self):
        wrong_key = 'gw_ZZZZZZZZ_' + 'f' * 64
        with self.assertLogs(level='DEBUG') as logs:
            await self.call('stub', 'echo', {'input': {'text': BODY}}, key=wrong_key)
        self.assertEqual(await CallLog.objects.acount(), 0)
        self.assert_absent((wrong_key, BODY, CLIENT_IP), self.logged_text(logs))


class ReadPrivacyTests(PrivacyChecks, GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_reader_stub_tool(tool_key=TOOL_KEY)

    async def read_and_capture(self, params, reply):
        self.tool_reply = reply
        with self.assertLogs(level='DEBUG') as logs:
            response = await self.read('stub', 'query', params, quiet_request_log=False,
                                       headers={'If-None-Match': INM, 'X-User-Context': CONTEXT})
        return response, logs

    async def test_read_success_stores_and_logs_no_query_values(self):
        response, logs = await self.read_and_capture({'text': QUERY}, reply_json(200, {'output': {'echo': QUERY}}))
        self.assertEqual(response.status_code, 200)
        sent = self.tool_requests[0]
        self.assertEqual((sent.url.params['text'], sent.headers['If-None-Match']), (QUERY, INM))  # it really flowed
        self.assert_absent((*self.secrets(), QUERY, INM), await self.stored_text(), self.logged_text(logs))

    async def test_mirrored_tool_error_logs_no_query_values(self):
        response, logs = await self.read_and_capture({'text': QUERY}, reply_json(404, {'detail': ERROR_BODY}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(any(r.name == 'django.request' for r in logs.records))  # the record was seen
        self.assert_absent((*self.secrets(), QUERY, INM, ERROR_BODY), await self.stored_text(), self.logged_text(logs))

    async def test_repeated_parameter_422_logs_no_query_values(self):
        response, logs = await self.read_and_capture({'text': [QUERY, QUERY]}, reply_json(200, {'output': {}}))
        self.assertEqual(response.status_code, 422)
        self.assertTrue(any(r.name == 'django.request' for r in logs.records))
        self.assert_absent((*self.secrets(), QUERY, INM), await self.stored_text(), self.logged_text(logs))


QUESTION = 'SENTINEL-QUESTION-2c81'
HISTORY = 'SENTINEL-HISTORY-6d05'
ANSWER = 'SENTINEL-ANSWER-a93f'
SPARQL = 'SENTINEL-SPARQL-17be'
DETAIL = 'SENTINEL-DETAIL-f5c2'


class KgRagPrivacyTests(PrivacyChecks, GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_kg_rag_tool(tool_key=TOOL_KEY)

    async def ask_and_capture(self, input, reply):
        self.tool_reply = reply
        with self.assertLogs(level='DEBUG') as logs:
            response = await self.call('kg-rag', 'ask', {'input': input}, quiet_request_log=False,
                                       headers={'X-User-Context': CONTEXT})
        return response, logs

    async def assert_nothing_leaked(self, logs):
        self.assert_absent((*self.secrets(), QUESTION, HISTORY, ANSWER, SPARQL, DETAIL),
                           await self.stored_text(), self.logged_text(logs))

    @staticmethod
    def default_input():
        return {'question': QUESTION, 'history': [[HISTORY, HISTORY]]}

    async def test_success_stores_and_logs_no_content(self):
        response, logs = await self.ask_and_capture(self.default_input(), reply_json(200, {
            'answer': ANSWER, 'sparql_generated': SPARQL, 'raw_data_count': 1, 'success': True}))
        self.assertEqual(response.status_code, 200)
        sent = self.tool_requests[0].content.decode()  # it really flowed
        self.assertIn(QUESTION, sent)
        self.assertIn(HISTORY, sent)
        self.assertEqual(response.json()['output']['answer'], ANSWER)
        await self.assert_nothing_leaked(logs)

    async def test_not_answered_stores_and_logs_no_content(self):
        response, logs = await self.ask_and_capture(self.default_input(), reply_json(200, {
            'answer': ANSWER, 'sparql_generated': SPARQL, 'success': False}))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['error']['tool_body']['answer'], ANSWER)
        self.assertTrue(any(r.name == 'django.request' for r in logs.records))
        await self.assert_nothing_leaked(logs)

    async def test_unknown_key_value_is_not_logged(self):
        response, logs = await self.ask_and_capture({'question': QUESTION, 'nickname': HISTORY},
                                                    reply_json(200, {'answer': ANSWER, 'success': True}))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.tool_requests, [])
        self.assertTrue(any(r.name == 'django.request' for r in logs.records))
        await self.assert_nothing_leaked(logs)

    async def test_too_long_question_is_not_logged(self):
        response, logs = await self.ask_and_capture(
            {'question': QUESTION + 'x' * 4000, 'history': [[HISTORY, HISTORY]]},
            reply_json(200, {'answer': ANSWER, 'success': True}))
        self.assertEqual(response.status_code, 422)
        self.assertTrue(any(r.name == 'django.request' for r in logs.records))
        await self.assert_nothing_leaked(logs)

    async def test_rag_500_detail_is_not_logged(self):
        response, logs = await self.ask_and_capture(self.default_input(), reply_json(500, {'detail': DETAIL}))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['error']['tool_body'], {'detail': DETAIL})
        self.assertTrue(any(r.name == 'django.request' for r in logs.records))
        await self.assert_nothing_leaked(logs)

    async def test_timeout_stores_and_logs_no_content(self):
        def reply(request):
            raise httpx.ReadTimeout('timed out', request=request)

        response, logs = await self.ask_and_capture(self.default_input(), reply)
        self.assertEqual(response.status_code, 504)
        self.assertTrue(any(r.name == 'django.request' for r in logs.records))
        await self.assert_nothing_leaked(logs)
