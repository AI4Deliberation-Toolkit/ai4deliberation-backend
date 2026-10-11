import json
import types
from unittest import mock

from asgiref.sync import iscoroutinefunction
from django.test import TestCase, override_settings

from ai4deliberation_backend.urls import build_urlpatterns
from tests.gateway.support import capture_logs


def urlconf(stub_enabled):
    """A fresh URLconf module built with the flag set as given (override_settings clears the URL caches)."""
    module = types.ModuleType(f'urls_with_stub_{stub_enabled}')
    with override_settings(GATEWAY_ENABLE_STUB=stub_enabled):
        module.urlpatterns = build_urlpatterns()
    return module


class StubMountTests(TestCase):
    def setUp(self):
        self.enterContext(capture_logs('django.request'))  # keeps the expected 404/4xx warnings out of the output

    def post_echo(self):
        return self.client.post('/stub/echo', '{"input": {}}', content_type='application/json')

    def test_not_mounted_without_the_flag(self):
        with override_settings(ROOT_URLCONF=urlconf(False)):
            self.assertEqual(self.post_echo().status_code, 404)

    def test_mounted_with_the_flag(self):
        with override_settings(ROOT_URLCONF=urlconf(True), GATEWAY_STUB_KEY=''):
            self.assertEqual(self.post_echo().status_code, 200)


@override_settings(GATEWAY_STUB_KEY='')
class StubBehaviourTests(TestCase):
    def setUp(self):
        self.enterContext(capture_logs('django.request'))
        overrider = override_settings(ROOT_URLCONF=urlconf(True))
        overrider.enable()
        self.addCleanup(overrider.disable)

    async def echo(self, payload=None, *, headers=None, raw=None):
        body = raw if raw is not None else json.dumps({'input': payload or {}})
        return await self.async_client.post('/stub/echo', body, content_type='application/json', headers=headers or {})

    async def test_echo(self):
        response = await self.echo({'echo': {'nested': [1, 2]}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'output': {'echo': {'nested': [1, 2]}},
                                           'metadata': {'tool_version': 'stub-1', 'model_id': 'none'}})

    async def test_echo_defaults_to_null(self):
        self.assertEqual((await self.echo({})).json()['output'], {'echo': None})

    async def test_delay_is_capped_and_validated(self):
        with mock.patch('gateway.stub._pause', new_callable=mock.AsyncMock) as pause:
            for delay in (2.5, 500, True, -1, 'x'):
                await self.echo({'delay_s': delay})
        self.assertEqual([c.args[0] for c in pause.await_args_list], [2.5, 60])

    async def test_status(self):
        response = await self.echo({'status': 503})
        self.assertEqual((response.status_code, response.json()), (503, {'error': 'stub error'}))
        for ignored in (200, 600, '500', True):
            with self.subTest(status=ignored):
                self.assertEqual((await self.echo({'status': ignored})).status_code, 200)

    async def test_stub_key(self):
        with override_settings(GATEWAY_STUB_KEY='right-key'):
            self.assertEqual((await self.echo()).status_code, 401)
            self.assertEqual((await self.echo(headers={'X-API-Key': 'wrong'})).status_code, 401)
            self.assertEqual((await self.echo(headers={'X-API-Key': 'right-key'})).status_code, 200)

    async def test_post_only_and_echo_only(self):
        self.assertEqual((await self.async_client.get('/stub/echo')).status_code, 405)
        response = await self.async_client.post('/stub/other', '{"input": {}}', content_type='application/json')
        self.assertEqual(response.status_code, 404)

    async def test_bad_body_is_400(self):
        for raw in ('not json', '[]', '{"input": 3}', '{}'):
            with self.subTest(raw=raw):
                self.assertEqual((await self.echo(raw=raw)).status_code, 400)

    def test_view_is_async(self):
        from gateway.stub import stub_view
        self.assertTrue(iscoroutinefunction(stub_view))
