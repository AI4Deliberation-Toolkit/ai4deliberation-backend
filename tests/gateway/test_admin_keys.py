import re

from asgiref.sync import async_to_sync
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.contrib.sessions.models import Session
from django.test import TestCase

from gateway.keys import averify_key, hash_key, issue_key
from gateway.logging_filters import GATEWAY_KEY_PATTERN
from gateway.models import ApiKey, Platform


class ApiKeyAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('admin', 'admin@example.org', 'pw')
        self.client.force_login(self.admin)
        self.platform = Platform.objects.create(name='WP site', slug='wp-site')

    def issue(self):
        response = self.client.post('/admin/gateway/apikey/add/', {'platform': self.platform.pk, 'label': 'production'})
        match = re.search(GATEWAY_KEY_PATTERN, response.content.decode())
        return response, match.group(0) if match else None

    def test_issued_key_is_shown_once_on_its_own_page(self):
        response, key = self.issue()
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(key)
        self.assertTemplateUsed(response, 'admin/gateway/apikey/issued.html')
        self.assertIn('no-store', response['Cache-Control'])
        api_key = ApiKey.objects.get()
        self.assertEqual(api_key.key_hash, hash_key(key))
        self.assertEqual(api_key.label, 'production')

    def test_issued_key_is_not_in_messages_session_cookies_or_admin_log(self):
        response, key = self.issue()
        self.assertFalse(any(key in str(m) for m in get_messages(response.wsgi_request)))
        for session in Session.objects.all():
            self.assertNotIn(key, str(session.get_decoded()))
        for morsel in list(response.cookies.values()) + list(self.client.cookies.values()):
            self.assertNotIn(key, morsel.value)
        for entry in LogEntry.objects.all():
            self.assertNotIn(key, entry.object_repr + entry.change_message)

    def test_key_never_appears_again(self):
        _, key = self.issue()
        api_key = ApiKey.objects.get()
        for url in ('/admin/gateway/apikey/', f'/admin/gateway/apikey/{api_key.pk}/change/'):
            with self.subTest(url=url):
                content = self.client.get(url).content.decode()
                self.assertNotIn(key, content)
                self.assertNotIn(key[12:], content)

    def test_revoke_action(self):
        key, api_key = issue_key(self.platform)
        self.client.post('/admin/gateway/apikey/', {'action': 'revoke_keys', '_selected_action': [api_key.pk]})
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.revoked_at)
        self.assertIsNone(async_to_sync(averify_key)(key))

    def test_label_stays_editable(self):
        _, api_key = issue_key(self.platform, label='old')
        response = self.client.post(f'/admin/gateway/apikey/{api_key.pk}/change/', {'label': 'renamed'})
        self.assertEqual(response.status_code, 302)
        api_key.refresh_from_db()
        self.assertEqual(api_key.label, 'renamed')

    def test_keys_cannot_be_deleted(self):
        _, api_key = issue_key(self.platform)
        with self.assertLogs('django.request', 'WARNING'):
            status = self.client.get(f'/admin/gateway/apikey/{api_key.pk}/delete/').status_code
        self.assertEqual(status, 403)

    def test_platform_admin_lists_platforms(self):
        response = self.client.get('/admin/gateway/platform/')
        self.assertContains(response, 'WP site')


class ApiKeyAdminViewOnlyTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user('viewer', 'v@example.org', 'pw', is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_apikey'))
        self.client.force_login(user)
        self.platform = Platform.objects.create(name='WP site', slug='wp-site')
        self.key, self.api_key = issue_key(self.platform)

    def test_view_only_staff_cannot_revoke(self):
        self.client.post('/admin/gateway/apikey/', {'action': 'revoke_keys', '_selected_action': [self.api_key.pk]})
        self.api_key.refresh_from_db()
        self.assertIsNone(self.api_key.revoked_at)
        self.assertIsNotNone(async_to_sync(averify_key)(self.key))

    def test_revoke_action_not_offered_to_view_only_staff(self):
        response = self.client.get('/admin/gateway/apikey/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'revoke_keys')
