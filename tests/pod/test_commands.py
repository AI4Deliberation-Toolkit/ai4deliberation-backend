"""The SSH helper commands: backup-reset and gateway-manage (spec §3.1, §7.4)."""
import os
import subprocess
import sys

from tests.pod.support import POD_DIR, PodTestCase, run_bash


class BackupResetTests(PodTestCase):
    def reset(self, *args, pidfile=None):
        pidfile = pidfile or self.pod.root / 'no-supervisord.pid'
        return subprocess.run(
            [str(POD_DIR / 'backup-reset'), *args], capture_output=True, text=True, timeout=30,
            env={'PATH': os.environ['PATH'], **self.pod.env(SUPERVISORD_PIDFILE=str(pidfile))},
        )

    def test_needs_confirmation(self):
        out = self.reset()
        self.assertEqual(out.returncode, 2)
        self.assertTrue(self.pod.backup.exists())

    def test_moves_the_folder_aside(self):
        self.pod.set_owner('pod-a')
        out = self.reset('--yes')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(self.pod.backup.exists())
        aside = [p for p in self.pod.volume.iterdir() if p.name.endswith('.aside')]
        self.assertEqual(len(aside), 1)
        self.assertRegex(aside[0].name, r'^gateway-backup\.\d{8}T\d{6}Z\.aside$')
        self.assertEqual((aside[0] / 'OWNER').read_text(), 'pod-a\n')

    def test_refuses_while_the_gateway_runs(self):
        pidfile = self.pod.root / 'supervisord.pid'
        pidfile.write_text(str(os.getpid()))  # a live process stands in for supervisord
        out = self.reset('--yes', pidfile=pidfile)
        self.assertEqual(out.returncode, 1)
        self.assertIn('the gateway is running', out.stderr)
        self.assertTrue(self.pod.backup.exists())


class GatewayManageTests(PodTestCase):
    def test_runs_manage_py_with_the_env_file(self):
        env_file = self.pod.root / 'gateway-pod.env'
        run_bash(
            f'write_env_file "{env_file}" DJANGO_SETTINGS_MODULE',
            env={'DJANGO_SETTINGS_MODULE': 'ai4deliberation_backend.settings'},
        )
        out = subprocess.run(
            [str(POD_DIR / 'gateway-manage'), 'check'], capture_output=True, text=True, timeout=60,
            # The interpreter running the tests first on PATH, as `python` is in the image.
            env={'PATH': f'{os.path.dirname(sys.executable)}:{os.environ["PATH"]}', 'GATEWAY_POD_ENV_FILE': str(env_file)},
            cwd='/',
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('System check identified no issues', out.stdout)
