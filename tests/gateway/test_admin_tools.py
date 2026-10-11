from django.contrib.auth import get_user_model
from django.test import TestCase

from gateway.models import Tool

KEY = 'sentinel-tool-key-123'


def form_data(**overrides):
    data = {
        'tool_id': 'topic-toolkit', 'name': 'Topic toolkit', 'description': '', 'docs_url': '',
        'base_url': 'https://toolkit.example.org', 'depth': 'adapted', 'adapter': 'topic_toolkit',
        'operations': '["extract"]', 'key_header': 'X-API-Key', 'timeout_seconds': '30',
        'health_path': '/api/topics?language=el', 'enabled': 'on', 'new_tool_key': '',
    }
    data.update(overrides)
    return data


class ToolAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser('admin', 'admin@example.org', 'pw'))

    def add(self, **overrides):
        return self.client.post('/admin/gateway/tool/add/', form_data(**overrides), follow=True)

    def change(self, tool, **overrides):
        return self.client.post(f'/admin/gateway/tool/{tool.pk}/change/', form_data(**overrides), follow=True)

    def test_add_with_key_stores_it_encrypted(self):
        self.add(new_tool_key=KEY)
        tool = Tool.objects.get()
        self.assertEqual(tool.get_tool_key(), KEY)
        self.assertNotIn(KEY, tool.tool_key)

    def test_admin_never_renders_the_key(self):
        self.add(new_tool_key=KEY)
        tool = Tool.objects.get()
        for url in ('/admin/gateway/tool/', f'/admin/gateway/tool/{tool.pk}/change/'):
            with self.subTest(url=url):
                content = self.client.get(url).content.decode()
                self.assertNotIn(KEY, content)
                self.assertNotIn(tool.tool_key, content)  # nor the ciphertext

    def test_list_shows_set_or_not_set(self):
        self.add(new_tool_key=KEY)
        self.assertContains(self.client.get('/admin/gateway/tool/'), '<td class="field-key_status">set</td>', html=True)
        self.change(Tool.objects.get(), clear_tool_key='on')
        self.assertContains(self.client.get('/admin/gateway/tool/'), '<td class="field-key_status">not set</td>',
                            html=True)

    def test_blank_key_keeps_the_existing_one(self):
        self.add(new_tool_key=KEY)
        tool = Tool.objects.get()
        self.change(tool, name='Renamed')
        tool.refresh_from_db()
        self.assertEqual((tool.name, tool.get_tool_key()), ('Renamed', KEY))

    def test_clear_checkbox_removes_the_key(self):
        self.add(new_tool_key=KEY)
        tool = Tool.objects.get()
        self.change(tool, clear_tool_key='on')
        tool.refresh_from_db()
        self.assertIsNone(tool.get_tool_key())

    def test_new_key_and_clear_together_is_an_error(self):
        response = self.add(new_tool_key=KEY, clear_tool_key='on')
        self.assertContains(response, 'Either set a new key or clear it')
        self.assertFalse(Tool.objects.exists())

    def test_plain_http_off_loopback_warns_but_saves(self):
        response = self.add(base_url='http://toolkit.example.org')
        self.assertTrue(Tool.objects.exists())
        self.assertContains(response, 'travels unencrypted')

    def test_https_does_not_warn(self):
        self.assertNotContains(self.add(), 'travels unencrypted')

    def test_model_validation_shows_on_the_form(self):
        response = self.add(depth='passthrough')
        self.assertContains(response, 'Pass-through is reserved')
        self.assertFalse(Tool.objects.exists())
