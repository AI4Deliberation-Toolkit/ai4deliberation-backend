"""Shared helpers for the gateway tests."""
import contextlib
import json
import logging
from pathlib import Path
from unittest import mock

import httpx
from asgiref.sync import sync_to_async
from django.test import TestCase

from gateway.adapters.base import Adapter
from gateway.keys import issue_key
from gateway.models import Platform, Tool

FIXTURES = Path(__file__).resolve().parent.parent / 'fixtures'


UNKNOWN_KEY = 'gw_AAAAAAAA_' + '0' * 64


def reply_json(status, body):
    return lambda request: httpx.Response(status, json=body)


class BrokenAdapter(Adapter):
    def build_request(self, tool, operation, envelope):
        raise RuntimeError('adapter bug with details')


def load_fixture(name, tool='topic_toolkit'):
    return json.loads((FIXTURES / tool / name).read_text(encoding='utf-8'))


def assert_gateway_error(test, response, status, code, source='gateway'):
    """Assert the one error shape (spec §7) and return the `error` object."""
    test.assertEqual(response.status_code, status, response.content)
    error = response.json()['error']
    test.assertEqual(error['code'], code)
    test.assertEqual(error['source'], source)
    test.assertEqual(error['request_id'], response['X-Request-Id'])
    return error


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@contextlib.contextmanager
def capture_logs(name):
    """Like assertLogs, but doesn't fail when nothing is logged: yields the captured records."""
    logger = logging.getLogger(name)
    handler = _ListHandler()
    saved = logger.handlers, logger.propagate
    logger.handlers, logger.propagate = [handler], False
    try:
        yield handler.records
    finally:
        logger.handlers, logger.propagate = saved


_OWN_KEY = object()


class GatewayTestCase(TestCase):
    """A platform with a key, plus a MockTransport standing in for every tool. No test touches the network."""

    def setUp(self):
        super().setUp()
        self.platform = Platform.objects.create(name='WP site', slug='wp-site')
        self.key, self.api_key = issue_key(self.platform, label='tests')
        # Keep the per-request access line out of the suite output; assertLogs still sees it.
        access_logger = logging.getLogger('gateway.access')
        propagate, access_logger.propagate = access_logger.propagate, False
        self.addCleanup(setattr, access_logger, 'propagate', propagate)
        self.tool_requests: list[httpx.Request] = []
        self.tool_reply = lambda request: httpx.Response(200, json={'output': {}, 'metadata': {}})

        def handler(request):
            self.tool_requests.append(request)
            return self.tool_reply(request)

        transport = httpx.MockTransport(handler)
        patcher = mock.patch('gateway.http.get_client', side_effect=lambda: httpx.AsyncClient(transport=transport))
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_tool(self, *, tool_key=None, **fields) -> Tool:
        tool = Tool(**fields)
        if tool_key is not None:
            tool.set_tool_key(tool_key)
        tool.save()
        return tool

    def make_stub_tool(self, **fields) -> Tool:
        return self.make_tool(**{
            'tool_id': 'stub', 'name': 'Stub', 'base_url': 'http://127.0.0.1:8000/stub',
            'depth': 'native', 'adapter': 'native', 'operations': ['echo'], **fields,
        })

    def make_toolkit_tool(self, **fields) -> Tool:
        return self.make_tool(**{
            'tool_id': 'topic-toolkit', 'name': 'Topic toolkit', 'base_url': 'https://toolkit.example.org',
            'depth': 'adapted', 'adapter': 'topic_toolkit', 'operations': ['extract'], **fields,
        })

    def make_kg_rag_tool(self, **fields) -> Tool:
        return self.make_tool(**{
            'tool_id': 'kg-rag', 'name': 'KG chatbot', 'base_url': 'https://kg.example.org',
            'depth': 'adapted', 'adapter': 'kg_rag', 'operations': ['ask'], 'timeout_seconds': 90, **fields,
        })

    def make_reader_stub_tool(self, **fields) -> Tool:
        return self.make_stub_tool(operations=['echo', 'query'], read_operations=['query'], **fields)

    # Async tests can't use the sync ORM directly.
    async def amake_stub_tool(self, **fields) -> Tool:
        return await sync_to_async(self.make_stub_tool)(**fields)

    async def amake_reader_stub_tool(self, **fields) -> Tool:
        return await sync_to_async(self.make_reader_stub_tool)(**fields)

    async def amake_kg_rag_tool(self, **fields) -> Tool:
        return await sync_to_async(self.make_kg_rag_tool)(**fields)

    async def amake_toolkit_tool(self, **fields) -> Tool:
        return await sync_to_async(self.make_toolkit_tool)(**fields)

    async def call(self, tool_id, operation, body=None, *, key=_OWN_KEY, headers=None,
                   content_type='application/json'):
        request_headers = dict(headers or {})
        key = self.key if key is _OWN_KEY else key
        if key is not None:
            request_headers['X-Gateway-Key'] = key
        data = body if isinstance(body, str) else json.dumps({'input': {}} if body is None else body)
        with capture_logs('django.request') as records:
            response = await self.async_client.post(f'/api/v1/tools/{tool_id}/{operation}', data,
                                                    content_type=content_type, headers=request_headers)
        # Django logs one django.request line per 4xx/5xx: assert it, and keep it out of the suite output.
        self.assertEqual(len(records), int(response.status_code >= 400), [r.getMessage() for r in records])
        return response

    async def read(self, tool_id, operation, params=None, *, key=_OWN_KEY, headers=None, quiet_request_log=True):
        """A GET on the unified route. A list value in `params` repeats the parameter.

        With quiet_request_log=False, django.request records reach the test's own assertLogs, and their
        count isn't checked.
        """
        request_headers = dict(headers or {})
        key = self.key if key is _OWN_KEY else key
        if key is not None:
            request_headers['X-Gateway-Key'] = key
        capture = capture_logs('django.request') if quiet_request_log else contextlib.nullcontext()
        with capture as records:
            response = await self.async_client.get(f'/api/v1/tools/{tool_id}/{operation}', params or {},
                                                   headers=request_headers)
        if quiet_request_log:
            self.assertEqual(len(records), int(response.status_code >= 400), [r.getMessage() for r in records])
        return response
