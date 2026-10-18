import importlib
import os
from unittest import mock

from cryptography.fernet import Fernet
from decouple import Config, RepositoryEmpty, UndefinedValueError
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from ai4deliberation_backend.settings import settings as base

CI_KEY = 'l5OuvDtJGhPdISI1hEgB_Y9kTItb2AaqCF5qa-MO2oM='
SECOND_KEY = 'fptFnIu8wSj3xFAyQfVkR4zryBp2Md99CCp7VD9yR94='

REQUIRED = {
    'SECRET_KEY': 'test-secret',
    'POSTGRES_USER': 'u',
    'POSTGRES_PASSWORD': 'p',
    'POSTGRES_PORT': '5432',
    'ALLOWED_HOSTS': 'gw.example.org, 127.0.0.1,localhost',
    'GATEWAY_ENCRYPTION_KEYS': CI_KEY,
}
OPTIONAL = (
    'DEBUG', 'POSTGRES_DB', 'POSTGRES_HOST', 'CORS_ALLOWED_ORIGINS', 'CSRF_TRUSTED_ORIGINS',
    'GATEWAY_ENABLE_STUB', 'USE_X_FORWARDED_HOST',
)

# Environment variables only: a stray .env file in the repo root can't leak into the values
# staging reads itself. Values it inherits from the base settings are read once, at import.
ENV_ONLY = Config(RepositoryEmpty())


def load_staging(**overrides):
    """Import the staging settings module under a controlled environment.

    An override of None unsets that variable; optional variables are unset unless overridden.
    """
    env = {**REQUIRED, **{k: v for k, v in overrides.items() if v is not None}}
    with mock.patch.dict(os.environ, env), mock.patch('decouple.config', ENV_ONLY):
        for name in (*OPTIONAL, *overrides):
            if overrides.get(name) is None:
                os.environ.pop(name, None)
        module = importlib.import_module('ai4deliberation_backend.settings.staging')
        return importlib.reload(module)


class StagingSettingsTests(SimpleTestCase):
    def test_debug_is_off_by_default(self):
        self.assertIs(load_staging().DEBUG, False)

    def test_debug_can_be_turned_on(self):
        self.assertIs(load_staging(DEBUG='true').DEBUG, True)

    def test_allowed_hosts_come_from_the_environment(self):
        self.assertEqual(load_staging().ALLOWED_HOSTS, ['gw.example.org', '127.0.0.1', 'localhost'])

    def test_allowed_hosts_are_required(self):
        with self.assertRaises(UndefinedValueError):
            load_staging(ALLOWED_HOSTS=None)

    def test_empty_allowed_hosts_are_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            load_staging(ALLOWED_HOSTS='')

    def test_blank_only_allowed_hosts_are_rejected_like_empty(self):
        with self.assertRaises(ImproperlyConfigured):
            load_staging(ALLOWED_HOSTS=' , ')

    def test_cors_is_closed_by_default(self):
        staging = load_staging()
        self.assertIs(staging.CORS_ALLOW_ALL_ORIGINS, False)
        self.assertEqual(staging.CORS_ALLOWED_ORIGINS, [])

    def test_cors_origins_come_from_the_environment(self):
        staging = load_staging(CORS_ALLOWED_ORIGINS='https://a.example.org,https://b.example.org')
        self.assertEqual(staging.CORS_ALLOWED_ORIGINS, ['https://a.example.org', 'https://b.example.org'])

    def test_csrf_trusted_origins_are_empty_by_default(self):
        self.assertEqual(load_staging().CSRF_TRUSTED_ORIGINS, [])

    def test_csrf_trusted_origins_come_from_the_environment(self):
        # TLS ends at Cloudflare, so admin login needs the https origin trusted explicitly.
        staging = load_staging(CSRF_TRUSTED_ORIGINS='https://ai4deliberation-back-dev.konnekt-able.com')
        self.assertEqual(staging.CSRF_TRUSTED_ORIGINS, ['https://ai4deliberation-back-dev.konnekt-able.com'])

    def test_forwarded_host_is_ignored_by_default(self):
        # Staging's nginx passes the public Host through; only the pod's proxy needs this.
        self.assertIs(load_staging().USE_X_FORWARDED_HOST, False)

    def test_forwarded_host_can_be_turned_on(self):
        self.assertIs(load_staging(USE_X_FORWARDED_HOST='true').USE_X_FORWARDED_HOST, True)

    def test_database_name_and_host_default_to_the_current_deploy(self):
        db = load_staging().DATABASES['default']
        self.assertEqual((db['NAME'], db['HOST']), ('postgres', 'db'))

    def test_database_name_and_host_come_from_the_environment(self):
        db = load_staging(POSTGRES_DB='gateway', POSTGRES_HOST='pg.internal').DATABASES['default']
        self.assertEqual((db['NAME'], db['HOST']), ('gateway', 'pg.internal'))

    def test_encryption_keys_are_required(self):
        with self.assertRaises(UndefinedValueError):
            load_staging(GATEWAY_ENCRYPTION_KEYS=None)

    def test_encryption_keys_are_a_list_first_one_encrypts(self):
        staging = load_staging(GATEWAY_ENCRYPTION_KEYS=f'{SECOND_KEY},{CI_KEY}')
        self.assertEqual(staging.GATEWAY_ENCRYPTION_KEYS, [SECOND_KEY, CI_KEY])

    def test_stub_is_off_by_default(self):
        self.assertIs(load_staging().GATEWAY_ENABLE_STUB, False)

    def test_retention_defaults_to_180_days(self):
        self.assertEqual(load_staging().CALL_LOG_RETENTION_DAYS, 180)


class BaseSettingsTests(SimpleTestCase):
    def test_dev_encryption_key_is_a_valid_fernet_key(self):
        self.assertEqual(len(base.GATEWAY_ENCRYPTION_KEYS), 1)
        Fernet(base.GATEWAY_ENCRYPTION_KEYS[0])

    def test_gateway_defaults(self):
        self.assertEqual(base.CALL_LOG_RETENTION_DAYS, 180)
        self.assertIsInstance(base.GATEWAY_ENABLE_STUB, bool)
        self.assertIsInstance(base.GATEWAY_STUB_KEY, str)

    def test_body_limit_is_10_mb(self):
        self.assertEqual(base.DATA_UPLOAD_MAX_MEMORY_SIZE, 10 * 1024 * 1024)


PROXY_HOST = 'abc123-8000.proxy.runpod.net'


@override_settings(USE_X_FORWARDED_HOST=True, ALLOWED_HOSTS=[PROXY_HOST, '127.0.0.1', 'localhost'])
class ForwardedHostTests(TestCase):
    """Runpod's proxy sends the pod's internal address as Host and the public one as X-Forwarded-Host."""

    def test_a_request_through_the_runpod_proxy_is_accepted(self):
        response = self.client.get('/api/v1/health', HTTP_HOST='100.65.32.20:60828', HTTP_X_FORWARDED_HOST=PROXY_HOST)
        self.assertEqual(response.status_code, 200)

    def test_a_forwarded_host_not_in_allowed_hosts_is_still_rejected(self):
        with self.assertLogs('django.security.DisallowedHost', 'ERROR'):
            response = self.client.get('/api/v1/health', HTTP_HOST=PROXY_HOST, HTTP_X_FORWARDED_HOST='evil.example.org')
        self.assertEqual(response.status_code, 400)


@override_settings(DEBUG=False)
class DebugOffTests(TestCase):
    def test_unknown_urls_are_a_plain_404(self):
        for path in ('/nope', '/api/v1/nope', '/passthrough/topic-toolkit/extract'):
            with self.subTest(path=path), self.assertLogs('django.request', 'WARNING'):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(b'URLconf', response.content)
                self.assertNotIn(b'Traceback', response.content)
