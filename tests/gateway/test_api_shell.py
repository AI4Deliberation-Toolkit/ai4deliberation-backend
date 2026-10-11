import uuid
from unittest import mock

from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import path
from ninja import NinjaAPI, Schema
from ninja.security import APIKeyHeader

from gateway.errors import TOOL_NOT_FOUND, GatewayError, install_error_handlers
from tests.gateway.support import assert_gateway_error


class NeverAuth(APIKeyHeader):
    param_name = 'X-Test-Key'

    def authenticate(self, request, key):
        return None  # Ninja then raises its own AuthenticationError


# A test-only API exercising the error handlers; no production route raises these yet.
shell_api = NinjaAPI(urls_namespace='shell-test')
install_error_handlers(shell_api)


class Payload(Schema):
    input: dict


@shell_api.post('/body')
async def body_route(request, payload: Payload):
    return {'ok': True}


@shell_api.get('/gateway-error')
async def gateway_error_route(request):
    raise GatewayError(TOOL_NOT_FOUND, tool_id='nope')


@shell_api.get('/crash')
async def crash_route(request):
    raise RuntimeError('secret detail')


@shell_api.get('/locked', auth=NeverAuth())
async def locked_route(request):
    return {'ok': True}


urlpatterns = [path('shell/', shell_api.urls)]


@override_settings(ROOT_URLCONF='tests.gateway.test_api_shell')
class ErrorHandlerTests(TestCase):
    async def test_gateway_error_shape(self):
        response = await self.async_client.get('/shell/gateway-error')
        error = assert_gateway_error(self, response, 404, 'TOOL_NOT_FOUND')
        self.assertEqual(error['tool_id'], 'nope')
        self.assertNotIn('tool_status', error)
        self.assertNotIn('tool_body', error)

    async def test_validation_error_is_invalid_request(self):
        response = await self.async_client.post('/shell/body', '{"input": [1]}', content_type='application/json')
        error = assert_gateway_error(self, response, 422, 'INVALID_REQUEST')
        self.assertIn('payload.input', error['message'])

    async def test_unparseable_body_is_invalid_request(self):
        for body, content_type in (('{"input": ', 'application/json'), ('plain', 'text/plain'), ('', 'application/json')):
            with self.subTest(body=body, content_type=content_type):
                response = await self.async_client.post('/shell/body', body, content_type=content_type)
                assert_gateway_error(self, response, 422, 'INVALID_REQUEST')

    async def test_oversized_body_is_413_without_a_traceback(self):
        body = '{"input": {"text": "' + 'x' * 200 + '"}}'
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=100):
            with self.assertNoLogs('gateway.errors', 'ERROR'):
                response = await self.async_client.post('/shell/body', body, content_type='application/json')
        error = assert_gateway_error(self, response, 413, 'REQUEST_TOO_LARGE')
        self.assertIn('100 bytes', error['message'])

    async def test_ninja_authentication_error_is_unauthorized(self):
        assert_gateway_error(self, await self.async_client.get('/shell/locked'), 401, 'UNAUTHORIZED')

    async def test_unexpected_exception_is_a_generic_internal_error(self):
        with self.assertLogs('gateway.errors', 'ERROR') as logs:
            response = await self.async_client.get('/shell/crash')
        error = assert_gateway_error(self, response, 500, 'INTERNAL')
        self.assertNotIn('secret detail', response.content.decode())
        self.assertEqual(error['message'], 'Internal gateway error.')
        self.assertIs(logs.records[0].exc_info[0], RuntimeError)  # traceback is logged server-side


class RequestIdTests(TestCase):
    def test_every_response_carries_a_fresh_uuid4(self):
        ids = []
        for path in ('/admin/login/', '/nope', '/api/v1/health'):
            response = self.client.get(path)
            request_id = uuid.UUID(response['X-Request-Id'])
            self.assertEqual(request_id.version, 4)
            ids.append(request_id)
        self.assertEqual(len(set(ids)), 3)

    async def test_async_requests_carry_one_too(self):
        response = await self.async_client.get('/api/v1/health')
        self.assertEqual(uuid.UUID(response['X-Request-Id']).version, 4)

    def test_caller_supplied_request_id_is_ignored(self):
        response = self.client.get('/api/v1/health', headers={'X-Request-Id': 'caller-chosen'})
        self.assertNotEqual(response['X-Request-Id'], 'caller-chosen')


class HealthTests(TestCase):
    async def test_health_ok_without_a_key(self):
        response = await self.async_client.get('/api/v1/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'database': 'ok'})

    async def test_health_reports_a_database_error(self):
        with mock.patch('gateway.api._ping_database', side_effect=OperationalError('down')):
            response = await self.async_client.get('/api/v1/health')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'error', 'database': 'error'})

    def test_docs_and_openapi_are_served_without_a_key(self):
        self.assertEqual(self.client.get('/api/v1/openapi.json').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/docs').status_code, 200)
