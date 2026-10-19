import json  # a plain JsonResponse has no .json(); only test-client responses do

from django.test import RequestFactory, SimpleTestCase

from gateway.errors import METHOD_NOT_ALLOWED, GatewayError, _on_gateway_error


class MethodNotAllowedTests(SimpleTestCase):
    def test_405_with_allow_header_in_the_gateway_shape(self):
        request = RequestFactory().get('/x')
        request.request_id = 'rid'
        response = _on_gateway_error(request, GatewayError(METHOD_NOT_ALLOWED, 'Use POST for this operation.',
                                                           tool_id='stub', headers={'Allow': 'POST'}))
        self.assertEqual((response.status_code, response['Allow']), (405, 'POST'))
        self.assertEqual(json.loads(response.content)['error'], {'source': 'gateway', 'code': 'METHOD_NOT_ALLOWED',
                                                    'message': 'Use POST for this operation.', 'request_id': 'rid',
                                                    'tool_id': 'stub'})

    def test_other_errors_carry_no_extra_headers(self):
        request = RequestFactory().get('/x')
        response = _on_gateway_error(request, GatewayError('TOOL_NOT_FOUND'))
        self.assertNotIn('Allow', response)
