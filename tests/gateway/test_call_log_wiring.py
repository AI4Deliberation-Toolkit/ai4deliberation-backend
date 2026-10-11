import json
from unittest import mock

import httpx
from django.db import DatabaseError
from django.test import override_settings

from gateway.adapters import ADAPTERS
from gateway.models import CallLog
from tests.gateway.support import UNKNOWN_KEY, BrokenAdapter, GatewayTestCase, load_fixture, reply_json


class CallLogRowTests(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_toolkit_tool()

    async def row(self):
        return await CallLog.objects.aget()

    async def test_success_row(self):
        fixture = load_fixture('extract_201.json')
        self.tool_reply = reply_json(201, fixture)
        body = json.dumps({'input': load_fixture('extract_request.json')})
        response = await self.call('topic-toolkit', 'extract', body)
        row = await self.row()
        self.assertEqual(str(row.request_id), response['X-Request-Id'])
        self.assertEqual((row.platform_id, row.key_prefix, row.tool_id, row.operation),
                         (self.platform.pk, self.api_key.prefix, 'topic-toolkit', 'extract'))
        self.assertEqual((row.status, row.error_code, row.error_source, row.tool_status), (200, None, None, 201))
        self.assertEqual(row.request_bytes, len(body.encode()))
        self.assertEqual(row.response_bytes, len(httpx.Response(201, json=fixture).content))
        self.assertEqual((row.taxonomy_version, row.tool_version, row.model_id), ('2026-05-21-1', None, None))
        self.assertIsNotNone(row.tool_duration_ms)
        self.assertGreaterEqual(row.duration_ms, row.tool_duration_ms)

    async def test_lookup_failure_row(self):
        await self.call('nope', 'echo')
        row = await self.row()
        self.assertEqual((row.tool_id, row.status, row.error_code, row.error_source),
                         ('nope', 404, 'TOOL_NOT_FOUND', 'gateway'))
        self.assertEqual((row.tool_status, row.tool_duration_ms, row.response_bytes), (None, None, None))

    async def test_timeout_row(self):
        def reply(request):
            raise httpx.ReadTimeout('timed out', request=request)

        self.tool_reply = reply
        await self.call('topic-toolkit', 'extract')
        row = await self.row()
        self.assertEqual((row.status, row.error_code, row.error_source, row.tool_status),
                         (504, 'TOOL_TIMEOUT', 'gateway', None))
        self.assertIsNotNone(row.tool_duration_ms)
        self.assertIsNone(row.response_bytes)

    async def test_tool_error_row(self):
        self.tool_reply = reply_json(500, load_fixture('extract_500.json'))
        await self.call('topic-toolkit', 'extract')
        row = await self.row()
        self.assertEqual((row.status, row.error_code, row.error_source, row.tool_status), (502, 'TOOL_ERROR', 'tool', 500))

    async def test_tool_auth_failed_row(self):
        self.tool_reply = reply_json(401, {})
        await self.call('topic-toolkit', 'extract')
        row = await self.row()
        self.assertEqual((row.status, row.error_code, row.tool_status), (502, 'TOOL_AUTH_FAILED', 401))

    async def test_internal_error_row(self):
        with mock.patch.dict(ADAPTERS, {'topic_toolkit': BrokenAdapter()}):
            with self.assertLogs('gateway.errors', 'ERROR'):
                await self.call('topic-toolkit', 'extract')
        row = await self.row()
        self.assertEqual((row.status, row.error_code, row.error_source), (500, 'INTERNAL', 'gateway'))

    async def test_unauthenticated_calls_write_no_row(self):
        await self.call('topic-toolkit', 'extract', key=None)
        await self.call('topic-toolkit', 'extract', key=UNKNOWN_KEY)
        self.assertEqual(await CallLog.objects.acount(), 0)

    async def test_authenticated_request_rejected_before_the_view_gets_a_row(self):
        # Ninja rejects this before invoke runs; the middleware still writes the row (spec §8.1, §14).
        await self.call('topic-toolkit', 'extract', {'input': [1]})
        row = await self.row()
        self.assertEqual((row.tool_id, row.operation, row.status, row.error_code, row.error_source),
                         ('topic-toolkit', 'extract', 422, 'INVALID_REQUEST', 'gateway'))
        self.assertEqual((row.tool_status, row.tool_duration_ms, row.response_bytes), (None, None, None))

    async def test_overlong_path_segment_is_cut_to_the_column_width(self):
        await self.call('x' * 70, 'extract')
        row = await self.row()
        self.assertEqual((row.tool_id, row.status, row.error_code), ('x' * 64, 422, 'INVALID_REQUEST'))

    async def test_oversized_body_gets_a_413_row(self):
        body = json.dumps({'input': {'text': 'x' * 500}})
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=100):
            response = await self.call('topic-toolkit', 'extract', body)
        self.assertEqual(response.status_code, 413)
        row = await self.row()
        self.assertEqual((row.status, row.error_code, row.request_bytes), (413, 'REQUEST_TOO_LARGE', len(body.encode())))
        self.assertEqual(self.tool_requests, [])

    async def test_write_failure_does_not_change_the_response(self):
        self.tool_reply = reply_json(201, load_fixture('extract_201.json'))
        with mock.patch.object(CallLog.objects, 'acreate', side_effect=DatabaseError('db down')):
            with self.assertLogs('gateway.calllog', 'WARNING'):
                response = await self.call('topic-toolkit', 'extract')
        self.assertEqual(response.status_code, 200)


class AccessLineTests(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_stub_tool()

    async def test_one_line_per_unified_call(self):
        with self.assertLogs('gateway.access', 'INFO') as logs:
            response = await self.call('stub', 'echo')
        self.assertEqual(len(logs.records), 1)
        request_id, platform, tool_id, operation, status, duration = logs.records[0].getMessage().split(' ')
        self.assertEqual((request_id, platform, tool_id, operation, status),
                         (response['X-Request-Id'], 'wp-site', 'stub', 'echo', '200'))
        self.assertGreaterEqual(int(duration), 0)

    async def test_unauthenticated_calls_get_a_line_too(self):
        with self.assertLogs('gateway.access', 'INFO') as logs:
            await self.call('stub', 'echo', key=None)
        _, platform, _, _, status, _ = logs.records[0].getMessage().split(' ')
        self.assertEqual((platform, status), ('-', '401'))

    async def test_path_segments_are_percent_encoded_in_the_line(self):
        # Unauthenticated callers control these segments: they must not forge or split a line.
        with self.assertLogs('gateway.access', 'INFO') as logs:
            await self.call('a%0AFAKE%20wp-site%20stub%20echo%20200%201', 'e%20x', key=None)
        message = logs.records[0].getMessage()
        self.assertNotIn('\n', message)
        fields = message.split(' ')
        self.assertEqual(len(fields), 6)
        self.assertEqual(fields[2:4], ['a%0AFAKE%20wp-site%20stub%20echo%20200%201', 'e%20x'])

    async def test_long_segments_are_cut_to_64_before_encoding(self):
        with self.assertLogs('gateway.access', 'INFO') as logs:
            await self.call('x' * 70, 'y' * 63 + '%20z', key=None)
        fields = logs.records[0].getMessage().split(' ')
        self.assertEqual((fields[2], fields[3]), ('x' * 64, 'y' * 63 + '%20'))

    async def test_other_routes_get_no_line(self):
        with self.assertNoLogs('gateway.access', 'INFO'):
            await self.async_client.get('/api/v1/health')
