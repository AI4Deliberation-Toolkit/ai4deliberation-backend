from asgiref.sync import sync_to_async

from gateway.models import Tool
from tests.gateway.support import GatewayTestCase, assert_gateway_error, capture_logs


class CatalogueTests(GatewayTestCase):
    def setUp(self):
        super().setUp()
        self.make_toolkit_tool(description='Topic extraction', docs_url='https://docs.example.org/toolkit')
        self.make_stub_tool(tool_key='stub-secret', gateway_only=True)
        self.make_tool(tool_id='direct-tool', name='Direct', base_url='https://direct.example.org', depth='native',
                       adapter='native', operations=['run'], tool_key='direct-secret')
        self.make_tool(tool_id='retired', name='Retired', base_url='https://retired.example.org', depth='native',
                       adapter='native', operations=['run'], enabled=False)

    async def get(self, path):
        with capture_logs('django.request'):  # keeps the 404 warning out of the suite output
            return await self.async_client.get(path, headers={'X-Gateway-Key': self.key})

    async def test_key_required(self):
        for path in ('/api/v1/tools', '/api/v1/tools/stub'):
            with self.subTest(path=path):
                with capture_logs('django.request'):
                    response = await self.async_client.get(path)
                assert_gateway_error(self, response, 401, 'UNAUTHORIZED')

    async def test_lists_enabled_tools_only(self):
        response = await self.get('/api/v1/tools')
        self.assertEqual(response.status_code, 200)
        entries = response.json()
        self.assertEqual([e['tool_id'] for e in entries], ['direct-tool', 'stub', 'topic-toolkit'])
        self.assertEqual(entries[2], {
            'tool_id': 'topic-toolkit', 'name': 'Topic toolkit', 'description': 'Topic extraction',
            'docs_url': 'https://docs.example.org/toolkit', 'operations': ['extract'], 'read_operations': [],
            'depth': 'adapted', 'reachability': 'open',
        })

    async def test_native_read_operations_are_listed(self):
        await sync_to_async(Tool.objects.filter(tool_id='stub').update)(operations=['echo', 'query'],
                                                                         read_operations=['query'])
        entry = (await self.get('/api/v1/tools/stub')).json()
        self.assertEqual((entry['operations'], entry['read_operations']), (['echo', 'query'], ['query']))

    async def test_reachability(self):
        entries = (await self.get('/api/v1/tools')).json()
        self.assertEqual({e['tool_id']: e['reachability'] for e in entries},
                         {'direct-tool': 'direct', 'stub': 'gateway_only', 'topic-toolkit': 'open'})

    async def test_never_exposes_base_urls_or_keys(self):
        content = (await self.get('/api/v1/tools')).content.decode() + (await self.get('/api/v1/tools/stub')).content.decode()
        for secret in ('https://toolkit.example.org', '127.0.0.1', 'direct.example.org', 'stub-secret',
                       'direct-secret', 'X-API-Key', 'base_url', 'tool_key', 'key_header'):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, content)

    async def test_single_entry(self):
        response = await self.get('/api/v1/tools/stub')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()['depth'], response.json()['reachability']), ('native', 'gateway_only'))

    async def test_unknown_and_disabled_tools_are_404(self):
        for tool_id in ('nope', 'retired'):
            with self.subTest(tool_id=tool_id):
                error = assert_gateway_error(self, await self.get(f'/api/v1/tools/{tool_id}'), 404, 'TOOL_NOT_FOUND')
                self.assertEqual(error['tool_id'], tool_id)

    def test_openapi_documents_the_routes_and_the_key(self):
        schema = self.client.get('/api/v1/openapi.json').json()
        self.assertEqual(schema['components']['securitySchemes']['GatewayKeyAuth'],
                         {'type': 'apiKey', 'in': 'header', 'name': 'X-Gateway-Key'})
        for path in ('/api/v1/health', '/api/v1/tools', '/api/v1/tools/{tool_id}', '/api/v1/tools/{tool_id}/{operation}'):
            with self.subTest(path=path):
                self.assertIn(path, schema['paths'])
