import io
from unittest import mock

import httpx
from cryptography.fernet import Fernet
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from gateway.models import Tool


class CheckToolsTests(TestCase):
    def setUp(self):
        self.replies = {}  # host → status code, or 'connect-error'
        self.seen = []

        def handler(request):
            self.seen.append(request)
            reply = self.replies[request.url.host]
            if reply == 'connect-error':
                raise httpx.ConnectError('refused', request=request)
            return httpx.Response(reply)

        transport = httpx.MockTransport(handler)
        patcher = mock.patch('gateway.http.build_sync_client',
                             side_effect=lambda timeout: httpx.Client(transport=transport, timeout=timeout))
        self.build_sync_client = patcher.start()
        self.addCleanup(patcher.stop)

    def add_tool(self, tool_id, reply, *, health_path='/health', enabled=True, tool_key=None, key_header='X-API-Key'):
        host = f'{tool_id}.example.org'
        self.replies[host] = reply
        tool = Tool(tool_id=tool_id, name=tool_id, base_url=f'https://{host}', depth='native', adapter='native',
                    operations=['run'], health_path=health_path, enabled=enabled, key_header=key_header)
        if tool_key:
            tool.set_tool_key(tool_key)
        tool.save()

    def run_command(self):
        out = io.StringIO()
        try:
            call_command('check_tools', stdout=out)
            code = 0
        except CommandError as exc:
            code = exc.returncode
        return out.getvalue().splitlines(), code

    def test_all_ok(self):
        self.add_tool('alpha', 200)
        self.assertEqual(self.run_command(), (['alpha: ok'], 0))
        self.build_sync_client.assert_called_with(timeout=10)

    def test_outcomes_and_exit_code(self):
        self.add_tool('alpha', 200)
        self.add_tool('beta', 401)
        self.add_tool('gamma', 403)
        self.add_tool('delta', 503)
        self.add_tool('epsilon', 'connect-error')
        self.add_tool('zeta', 200, health_path='')
        lines, code = self.run_command()
        self.assertEqual(lines, [
            'alpha: ok',
            'beta: AUTH (likely key drift)',
            'delta: DOWN (503)',
            'epsilon: DOWN (ConnectError)',
            'gamma: AUTH (likely key drift)',
            'zeta: no health_path',
        ])
        self.assertEqual(code, 1)

    def test_no_health_path_alone_does_not_fail(self):
        self.add_tool('zeta', 200, health_path='')
        self.assertEqual(self.run_command(), (['zeta: no health_path'], 0))

    def test_disabled_tools_are_skipped(self):
        self.add_tool('alpha', 200, enabled=False)
        self.assertEqual(self.run_command(), ([], 0))

    def test_sends_the_tool_key_and_keeps_the_query(self):
        self.add_tool('toolkit', 200, health_path='/api/topics?language=el', tool_key='tk-1',
                      key_header='X-Toolkit-Key')
        self.run_command()
        request = self.seen[0]
        self.assertEqual(str(request.url), 'https://toolkit.example.org/api/topics?language=el')
        self.assertEqual(request.headers['X-Toolkit-Key'], 'tk-1')

    def test_undecryptable_key_fails_without_calling_the_tool(self):
        # Spec §9.2: a key the configured GATEWAY_ENCRYPTION_KEYS cannot read makes the command exit non-zero.
        with override_settings(GATEWAY_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            self.add_tool('alpha', 200, tool_key='tk-1')
        with override_settings(GATEWAY_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            lines, code = self.run_command()
        self.assertEqual(lines, ['alpha: KEY ERROR (tool key cannot be decrypted)'])
        self.assertEqual(code, 1)
        self.assertEqual(self.seen, [])

    def test_undecryptable_key_fails_even_without_a_health_path(self):
        with override_settings(GATEWAY_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            self.add_tool('alpha', 200, health_path='', tool_key='tk-1')
        with override_settings(GATEWAY_ENCRYPTION_KEYS=[Fernet.generate_key().decode()]):
            lines, code = self.run_command()
        self.assertEqual(lines, ['alpha: KEY ERROR (tool key cannot be decrypted)'])
        self.assertEqual(code, 1)
