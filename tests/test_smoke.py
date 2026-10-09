from django.conf import settings
from django.test import TestCase


class SmokeTests(TestCase):
    def test_admin_login_page_renders(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)

    def test_removed_nlp_endpoints_are_gone(self):
        removed = [
            '/api/topics',
            '/api/topics/extract-conversation',
            '/api/topics/article/1',
            '/api/articles/wp/1/similar',
            '/api/categorize-text/',
        ]
        for path in removed:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_removed_apps_are_not_installed(self):
        for app in ('ai_tools', 'topic_extraction'):
            with self.subTest(app=app):
                self.assertNotIn(app, settings.INSTALLED_APPS)
