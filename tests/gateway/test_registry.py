from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ValidationError
from unittest import mock

from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings

from gateway.checks import encryption_keys_check, unknown_adapter_check
from gateway.crypto import decrypt, encrypt
from gateway.logging_filters import redact_text
from gateway.models import Tool

OLD_KEY = Fernet.generate_key().decode()
NEW_KEY = Fernet.generate_key().decode()


def toolkit_fields(**overrides):
    fields = {
        'tool_id': 'topic-toolkit', 'name': 'Topic toolkit', 'base_url': 'https://toolkit.example.org',
        'depth': 'adapted', 'adapter': 'topic_toolkit', 'operations': ['extract'],
    }
    fields.update(overrides)
    return fields


STUB = dict(tool_id='stub', name='Stub', base_url='http://127.0.0.1:8000/stub', depth='native', adapter='native')


class ToolValidationTests(TestCase):
    def assertRefused(self, field, **overrides):
        with self.assertRaises(ValidationError) as caught:
            Tool.objects.create(**toolkit_fields(**overrides))
        self.assertIn(field, caught.exception.message_dict)
        self.assertFalse(Tool.objects.exists())

    def test_valid_toolkit_and_stub(self):
        Tool.objects.create(**toolkit_fields(health_path='/api/topics?language=el'))
        Tool.objects.create(tool_id='stub', name='Stub', base_url='http://127.0.0.1:8000/stub', depth='native',
                            adapter='native', operations=['echo'])
        self.assertEqual(Tool.objects.count(), 2)

    def test_passthrough_is_refused(self):
        self.assertRefused('depth', depth='passthrough')

    def test_native_iff_native_adapter(self):
        self.assertRefused('adapter', depth='native')  # native depth, toolkit adapter
        self.assertRefused('adapter', adapter='native', operations=['echo'])  # adapted depth, native adapter

    def test_unknown_adapter_is_refused(self):
        self.assertRefused('adapter', adapter='nope')

    def test_base_url_rules(self):
        for bad in ('ftp://toolkit.example.org', 'https://toolkit.example.org/', 'https://toolkit.example.org?x=1',
                    'https://toolkit.example.org#frag', 'https://user:pw@toolkit.example.org', 'toolkit.example.org',
                    '/relative', 'http://[::1', 'http://[bad]'):
            with self.subTest(base_url=bad):
                self.assertRefused('base_url', base_url=bad)

    def test_plain_http_off_loopback_is_allowed_but_flagged(self):
        flagged = Tool.objects.create(**toolkit_fields(base_url='http://toolkit.example.org'))
        self.assertTrue(flagged.uses_plain_http_off_loopback)
        for url in ('http://127.0.0.1:8000/stub', 'http://localhost:9000', 'https://toolkit.example.org'):
            with self.subTest(url=url):
                self.assertFalse(Tool(base_url=url).uses_plain_http_off_loopback)

    def test_operations_rules(self):
        for bad in ([], 'extract', ['Extract Now'], ['extract', 'extract'], ['summarise'], [1], ['x' * 65]):
            with self.subTest(operations=bad):
                self.assertRefused('operations', operations=bad)

    def test_native_tools_accept_any_operation_slug(self):
        Tool.objects.create(tool_id='stub', name='Stub', base_url='http://127.0.0.1:8000/stub', depth='native',
                            adapter='native', operations=['echo', 'summarise_v2'])
        self.assertEqual(Tool.objects.get(tool_id='stub').operations, ['echo', 'summarise_v2'])

    def test_health_path_must_start_with_a_slash(self):
        self.assertRefused('health_path', health_path='api/topics')

    def test_key_header_rules(self):
        for bad in ('X API Key', 'X-Request-Id', 'x-gateway-key', 'Content-Type', ''):
            with self.subTest(key_header=bad):
                self.assertRefused('key_header', key_header=bad)

    def test_timeout_bounds(self):
        for bad in (0, 291):
            with self.subTest(timeout_seconds=bad):
                self.assertRefused('timeout_seconds', timeout_seconds=bad)

    def test_native_read_operations_are_a_subset_of_operations(self):
        tool = Tool.objects.create(**STUB, operations=['echo', 'query'], read_operations=['query'])
        self.assertEqual(tool.read_operation_names(), ['query'])
        Tool.objects.all().delete()
        for bad in (['other'], 'query', ['query', 'query'], [1]):
            with self.subTest(read_operations=bad):
                with self.assertRaises(ValidationError) as caught:
                    Tool.objects.create(**STUB, operations=['echo', 'query'], read_operations=bad)
                self.assertIn('read_operations', caught.exception.message_dict)

    def test_adapted_tools_leave_read_operations_empty(self):
        self.assertRefused('read_operations', read_operations=['extract'])

    def test_read_operation_names_keep_the_operations_order(self):
        tool = Tool(**STUB, operations=['b', 'echo', 'a'], read_operations=['a', 'b'])
        self.assertEqual(tool.read_operation_names(), ['b', 'a'])
        self.assertEqual(Tool(**toolkit_fields()).read_operation_names(), [])

    def test_saving_registers_the_key_header_for_redaction(self):
        # A header name no other test registers (the registry is process-wide).
        self.assertIn('abc123', redact_text('X-Registry-Test-Token: abc123'))
        Tool.objects.create(**toolkit_fields(key_header='X-Registry-Test-Token'))
        self.assertNotIn('abc123', redact_text('X-Registry-Test-Token: abc123'))


class ToolKeyTests(TestCase):
    def test_key_is_encrypted_at_rest(self):
        tool = Tool(**toolkit_fields())
        tool.set_tool_key('sentinel-tool-key-123')
        tool.save()
        raw = Tool.objects.values_list('tool_key', flat=True).get()
        self.assertNotIn('sentinel-tool-key-123', raw)
        self.assertEqual(Tool.objects.get().get_tool_key(), 'sentinel-tool-key-123')

    def test_no_key(self):
        tool = Tool.objects.create(**toolkit_fields())
        self.assertIsNone(tool.get_tool_key())
        self.assertFalse(tool.has_tool_key)

    def test_clear_key(self):
        tool = Tool(**toolkit_fields())
        tool.set_tool_key('k')
        tool.clear_tool_key()
        self.assertIsNone(tool.get_tool_key())

    def test_reachability(self):
        open_tool = Tool(**toolkit_fields())
        self.assertEqual(open_tool.reachability, 'open')
        direct = Tool(**toolkit_fields())
        direct.set_tool_key('k')
        self.assertEqual(direct.reachability, 'direct')
        gateway_only = Tool(**toolkit_fields(gateway_only=True))
        gateway_only.set_tool_key('k')
        self.assertEqual(gateway_only.reachability, 'gateway_only')


class CryptoTests(SimpleTestCase):
    def test_round_trip(self):
        token = encrypt('secret')
        self.assertNotIn('secret', token)
        self.assertEqual(decrypt(token), 'secret')

    def test_rotation_keeps_old_tokens_readable(self):
        with override_settings(GATEWAY_ENCRYPTION_KEYS=[OLD_KEY]):
            token = encrypt('secret')
        with override_settings(GATEWAY_ENCRYPTION_KEYS=[NEW_KEY, OLD_KEY]):
            self.assertEqual(decrypt(token), 'secret')
        with override_settings(GATEWAY_ENCRYPTION_KEYS=[NEW_KEY]):
            with self.assertRaises(InvalidToken):
                decrypt(token)


class EncryptionKeysCheckTests(SimpleTestCase):
    def test_valid_keys_pass(self):
        with override_settings(GATEWAY_ENCRYPTION_KEYS=[NEW_KEY, OLD_KEY]):
            self.assertEqual(encryption_keys_check(None), [])

    def test_malformed_or_missing_keys_fail(self):
        for keys in ([], ['not-a-fernet-key'], [NEW_KEY, 'short']):
            with self.subTest(keys=keys):
                with override_settings(GATEWAY_ENCRYPTION_KEYS=keys):
                    errors = encryption_keys_check(None)
                self.assertEqual([e.id for e in errors], ['gateway.E001'])
                self.assertNotIn(NEW_KEY, errors[0].msg + (errors[0].hint or ''))


class UnknownAdapterCheckTests(TestCase):
    def test_flags_rows_whose_adapter_is_gone(self):
        Tool.objects.create(**toolkit_fields())
        self.assertEqual(unknown_adapter_check(None, databases=['default']), [])
        Tool.objects.update(adapter='removed-adapter')
        warnings = unknown_adapter_check(None, databases=['default'])
        self.assertEqual([w.id for w in warnings], ['gateway.W001'])
        self.assertIn('topic-toolkit', warnings[0].msg)

    def test_skipped_without_a_database_or_before_migrate(self):
        self.assertEqual(unknown_adapter_check(None), [])
        with mock.patch('gateway.models.Tool.objects') as objects:
            objects.exclude.side_effect = DatabaseError('no such table: gateway_tool')
            self.assertEqual(unknown_adapter_check(None, databases=['default']), [])
