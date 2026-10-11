from django.test import TestCase, override_settings
from django.urls import path
from django.utils import timezone
from ninja import NinjaAPI, Schema

from gateway.auth import GatewayKeyAuth
from gateway.errors import install_error_handlers
from gateway.keys import issue_key
from gateway.models import ApiKey, Platform
from tests.gateway.support import assert_gateway_error

# A test-only router: no protected production route exists until Phase B.
protected_api = NinjaAPI(urls_namespace='auth-test', auth=GatewayKeyAuth())
install_error_handlers(protected_api)


class Payload(Schema):
    input: dict


@protected_api.post('/protected')
async def protected(request, payload: Payload):
    return {'platform': request.auth.platform.slug, 'prefix': request.auth.prefix}


urlpatterns = [path('auth-test/', protected_api.urls)]


@override_settings(ROOT_URLCONF='tests.gateway.test_auth')
class GatewayKeyAuthTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name='WP site', slug='wp-site')
        self.key, self.api_key = issue_key(self.platform)

    async def post(self, body='{"input": {}}', key=None):
        headers = {'X-Gateway-Key': key} if key is not None else {}
        return await self.async_client.post('/auth-test/protected', body, content_type='application/json',
                                            headers=headers)

    async def rejected(self, **kwargs):
        with self.assertLogs('django.request', 'WARNING'):
            return await self.post(**kwargs)

    async def test_valid_key_sets_request_auth(self):
        response = await self.post(key=self.key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'platform': 'wp-site', 'prefix': self.api_key.prefix})

    async def test_missing_key(self):
        assert_gateway_error(self, await self.rejected(), 401, 'UNAUTHORIZED')

    async def test_auth_runs_before_body_validation(self):
        assert_gateway_error(self, await self.rejected(body='{"input": [1]}'), 401, 'UNAUTHORIZED')
        assert_gateway_error(self, await self.rejected(body='not json'), 401, 'UNAUTHORIZED')

    async def test_valid_key_with_malformed_body_is_422(self):
        with self.assertLogs('django.request', 'WARNING'):
            response = await self.post(body='{"input": [1]}', key=self.key)
        assert_gateway_error(self, response, 422, 'INVALID_REQUEST')

    async def test_wrong_and_malformed_keys(self):
        for key in ('gw_AAAAAAAA_' + '0' * 64, 'nonsense'):
            with self.subTest(key=key):
                assert_gateway_error(self, await self.rejected(key=key), 401, 'UNAUTHORIZED')

    async def test_revoked_key(self):
        await ApiKey.objects.filter(pk=self.api_key.pk).aupdate(revoked_at=timezone.now())
        assert_gateway_error(self, await self.rejected(key=self.key), 401, 'UNAUTHORIZED')

    async def test_inactive_platform(self):
        await Platform.objects.filter(pk=self.platform.pk).aupdate(is_active=False)
        assert_gateway_error(self, await self.rejected(key=self.key), 401, 'UNAUTHORIZED')

    async def test_failures_give_no_hint_which_check_failed(self):
        missing = (await self.rejected()).json()['error']['message']
        await ApiKey.objects.filter(pk=self.api_key.pk).aupdate(revoked_at=timezone.now())
        revoked = (await self.rejected(key=self.key)).json()['error']['message']
        self.assertEqual(missing, revoked)


class ProductionApiAuthTests(TestCase):
    def test_health_and_docs_stay_open(self):
        self.assertEqual(self.client.get('/api/v1/health').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/openapi.json').status_code, 200)
