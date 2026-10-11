import logging
import sys

from django.conf import settings
from django.test import SimpleTestCase

from gateway.logging_filters import REDACTED, RedactingFilter, redact_text, register_sensitive_header

KEY = 'gw_ABCDEFGH_' + 'a1' * 32


def filtered(msg, args=(), **attrs):
    record = logging.LogRecord('test', logging.INFO, __file__, 1, msg, args, None)
    for name, value in attrs.items():
        setattr(record, name, value)
    RedactingFilter().filter(record)
    return record


class RedactionTests(SimpleTestCase):
    def test_gateway_key_pattern_in_message(self):
        message = filtered(f'calling with {KEY}').getMessage()
        self.assertNotIn(KEY, message)
        self.assertIn(REDACTED, message)

    def test_gateway_key_pattern_in_args(self):
        self.assertNotIn(KEY, filtered('value %s', (KEY,)).getMessage())

    def test_header_values_in_text(self):
        cases = {
            'X-API-Key: s3cret-value': 's3cret-value',
            'x-gateway-key=abc123': 'abc123',
            'Authorization: Bearer tok123': 'tok123',
            "{'X-Api-Key': 'quoted-secret'}": 'quoted-secret',
            'X-User-Context: user-42-context': 'user-42-context',
        }
        for text, secret in cases.items():
            with self.subTest(text=text):
                self.assertNotIn(secret, filtered(text).getMessage())

    def test_dict_args(self):
        record = filtered('%(headers)s', ({'headers': {'X-API-Key': 'dict-secret'}},))
        self.assertNotIn('dict-secret', record.getMessage())

    def test_dict_valued_attributes(self):
        record = filtered('outbound', headers={'Authorization': 'Bearer t0k', 'Accept': 'application/json'})
        self.assertEqual(record.headers, {'Authorization': REDACTED, 'Accept': 'application/json'})

    def test_registered_tool_header(self):
        register_sensitive_header('X-Toolkit-Token')
        self.assertNotIn('tool-secret', filtered('X-Toolkit-Token: tool-secret').getMessage())
        self.assertNotIn('tool-secret', redact_text('x-toolkit-token=tool-secret'))

    def test_exception_text(self):
        try:
            raise ValueError(f'bad key {KEY}')
        except ValueError:
            record = filtered('failed', exc_info=sys.exc_info())
        self.assertNotIn(KEY, record.exc_text)
        self.assertIn('ValueError', record.exc_text)

    def test_ordinary_text_is_untouched(self):
        text = 'tool topic-toolkit answered 201 in 812 ms'
        self.assertEqual(filtered(text).getMessage(), text)


class LoggingConfigTests(SimpleTestCase):
    def test_every_handler_has_the_redaction_filter(self):
        for name, handler in settings.LOGGING['handlers'].items():
            with self.subTest(handler=name):
                self.assertIn('redact_secrets', handler.get('filters', []))
        root_filters = [f for h in logging.getLogger().handlers for f in h.filters]
        self.assertTrue(any(isinstance(f, RedactingFilter) for f in root_filters))

    def test_httpx_and_httpcore_are_pinned_to_warning(self):
        for name in ('httpx', 'httpcore'):
            with self.subTest(logger=name):
                self.assertEqual(logging.getLogger(name).getEffectiveLevel(), logging.WARNING)

    def test_access_logger_writes_info_to_stdout(self):
        self.assertEqual(logging.getLogger('gateway.access').getEffectiveLevel(), logging.INFO)
        self.assertEqual(settings.LOGGING['handlers']['console']['stream'], 'ext://sys.stdout')
