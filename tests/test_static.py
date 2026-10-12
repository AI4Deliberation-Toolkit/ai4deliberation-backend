"""Static files come from the app itself: the pod has no nginx (spec §7.1)."""
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from servestatic.middleware import ServeStaticMiddleware

from tests.test_deploy_config import _requirements

ROOT = Path(__file__).resolve().parent.parent
SERVESTATIC = 'servestatic.middleware.ServeStaticMiddleware'


class ServeStaticTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.static_root = Path(tmp.name)
        css = self.static_root / 'admin' / 'css' / 'base.css'
        css.parent.mkdir(parents=True)
        css.write_text('body { margin: 0 }')

    def test_middleware_comes_right_after_security_middleware(self):
        middleware = settings.MIDDLEWARE
        self.assertEqual(
            middleware.index(SERVESTATIC),
            middleware.index('django.middleware.security.SecurityMiddleware') + 1,
        )

    def test_middleware_is_async_capable(self):
        # A sync-only middleware would push every ASGI request through one thread (spec §7.1).
        self.assertTrue(ServeStaticMiddleware.async_capable)

    def test_whitenoise_is_not_used(self):
        self.assertNotIn('whitenoise', _requirements())
        self.assertFalse([m for m in settings.MIDDLEWARE if 'whitenoise' in m])

    def test_servestatic_is_pinned(self):
        text = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
        self.assertRegex(text, r'(?m)^servestatic==\d+\.\d+\.\d+$')

    def test_collected_files_are_served(self):
        with override_settings(STATIC_ROOT=str(self.static_root)):
            response = self.client.get('/static/admin/css/base.css')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/css'))

    async def test_collected_files_are_served_under_asgi(self):
        with override_settings(STATIC_ROOT=str(self.static_root)):
            response = await self.async_client.get('/static/admin/css/base.css')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join([chunk async for chunk in response.streaming_content]), b'body { margin: 0 }')

    def test_unknown_static_file_is_404(self):
        with override_settings(STATIC_ROOT=str(self.static_root)), self.assertLogs('django.request', 'WARNING'):
            response = self.client.get('/static/admin/css/nope.css')
        self.assertEqual(response.status_code, 404)
