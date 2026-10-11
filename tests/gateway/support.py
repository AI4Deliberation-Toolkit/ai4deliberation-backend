"""Shared helpers for the gateway tests."""
import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / 'fixtures'


def load_fixture(name):
    return json.loads((FIXTURES / 'topic_toolkit' / name).read_text(encoding='utf-8'))


def assert_gateway_error(test, response, status, code, source='gateway'):
    """Assert the one error shape (spec §7) and return the `error` object."""
    test.assertEqual(response.status_code, status, response.content)
    error = response.json()['error']
    test.assertEqual(error['code'], code)
    test.assertEqual(error['source'], source)
    test.assertEqual(error['request_id'], response['X-Request-Id'])
    return error
