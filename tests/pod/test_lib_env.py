"""lib.sh: refusals and the environment (spec §4.1, §4.3)."""
import os
import signal
import subprocess
import time

from tests.pod.support import LIB, PodTestCase, run_bash

AWKWARD = 'a$b(c)!d\'e"f g\\h'


class RefuseTests(PodTestCase):
    def test_refusal_logs_one_block_stays_alive_and_exits_on_sigterm(self):
        proc = subprocess.Popen(
            ['bash', '-c', f'source "{LIB}"; refuse "volume missing" "Refusals"'],
            stdout=subprocess.PIPE, text=True, env={'PATH': os.environ['PATH']},
        )
        try:
            lines = [proc.stdout.readline() for _ in range(5)]
            self.assertIn('GATEWAY POD REFUSED: volume missing\n', lines)
            self.assertIn('Runbook: docker/pod/README.md, section "Refusals"\n', lines)
            time.sleep(0.5)
            self.assertIsNone(proc.poll(), 'refuse() must not exit on its own')
            proc.send_signal(signal.SIGTERM)
            self.assertEqual(proc.wait(timeout=3), 0)
        finally:
            proc.kill()
            proc.stdout.close()


class DefaultsTests(PodTestCase):
    def test_defaults(self):
        out = self.lib('apply_defaults; echo "$DJANGO_SETTINGS_MODULE $POSTGRES_HOST $POSTGRES_PORT $GUNICORN_WORKERS"')
        self.assertEqual(out.stdout.strip(), 'ai4deliberation_backend.settings.staging 127.0.0.1 5432 2')

    def test_operator_values_win(self):
        out = self.lib('apply_defaults; echo "$POSTGRES_PORT $GUNICORN_WORKERS"', POSTGRES_PORT='5433', GUNICORN_WORKERS='4')
        self.assertEqual(out.stdout.strip(), '5433 4')

    def test_backup_dir_defaults_to_the_volume(self):
        out = run_bash('echo "$BACKUP_DIR"')
        self.assertEqual(out.stdout.strip(), '/workspace/gateway-backup')

    def test_missing_required_variables_are_listed(self):
        out = self.lib('missing_required_env', SECRET_KEY='s', POSTGRES_DB='', POSTGRES_USER='u', RUNPOD_POD_ID='p')
        self.assertEqual(out.stdout, 'GATEWAY_ENCRYPTION_KEYS POSTGRES_DB POSTGRES_PASSWORD')

    def test_nothing_missing(self):
        env = dict.fromkeys(
            ('SECRET_KEY', 'GATEWAY_ENCRYPTION_KEYS', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'RUNPOD_POD_ID'), 'x',
        )
        self.assertEqual(self.lib('missing_required_env', **env).stdout, '')


class HostnameTests(PodTestCase):
    SHOW = 'derive_hosts; echo "$ALLOWED_HOSTS|$CSRF_TRUSTED_ORIGINS"'

    def test_unset_values_are_derived_from_the_pod_id(self):
        out = self.lib(self.SHOW, RUNPOD_POD_ID='abc123')
        self.assertEqual(
            out.stdout.strip(),
            'abc123-8000.proxy.runpod.net,127.0.0.1,localhost|https://abc123-8000.proxy.runpod.net',
        )

    def test_empty_values_count_as_unset(self):
        out = self.lib(self.SHOW, RUNPOD_POD_ID='abc123', ALLOWED_HOSTS='', CSRF_TRUSTED_ORIGINS='')
        self.assertTrue(out.stdout.startswith('abc123-8000.proxy.runpod.net,'))

    def test_operator_values_win(self):
        out = self.lib(self.SHOW, RUNPOD_POD_ID='abc123', ALLOWED_HOSTS='gw.example.org,127.0.0.1,localhost')
        self.assertEqual(
            out.stdout.strip(), 'gw.example.org,127.0.0.1,localhost|https://abc123-8000.proxy.runpod.net',
        )

    def test_both_set_needs_no_pod_id(self):
        out = self.lib(self.SHOW, ALLOWED_HOSTS='gw.example.org', CSRF_TRUSTED_ORIGINS='https://gw.example.org')
        self.assertEqual(out.stdout.strip(), 'gw.example.org|https://gw.example.org')

    def test_neither_value_nor_pod_id_fails(self):
        self.assertEqual(self.lib('derive_hosts', check=False).returncode, 1)


class EnvFileTests(PodTestCase):
    def test_values_round_trip_through_the_env_file(self):
        path = self.pod.root / 'gateway-pod.env'
        self.lib(f'write_env_file "{path}" POSTGRES_PASSWORD SECRET_KEY UNSET_ONE', POSTGRES_PASSWORD=AWKWARD, SECRET_KEY='plain')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('UNSET_ONE', path.read_text())
        out = subprocess.run(
            ['bash', '-c', f'source "{path}"; printf "%s|%s" "$POSTGRES_PASSWORD" "$SECRET_KEY"'],
            capture_output=True, text=True, env={'PATH': os.environ['PATH']}, check=True,
        )
        self.assertEqual(out.stdout, f'{AWKWARD}|plain')

    def test_render_pg_conf_fills_in_the_port(self):
        template = self.pod.root / 'pg.conf'
        template.write_text("listen_addresses = '127.0.0.1'\nport = ${POSTGRES_PORT}\n")
        out = self.lib(f'render_pg_conf "{template}"', POSTGRES_PORT='5433')
        self.assertEqual(out.stdout, "listen_addresses = '127.0.0.1'\nport = 5433\n")


class PostgresEnvTests(PodTestCase):
    def test_postgres_gets_an_allow_list_not_the_secrets(self):
        out = self.lib(
            'postgres_env_cmd; "${POSTGRES_ENV[@]}" env',
            RUNPOD_POD_ID='pod-a', SECRET_KEY='s', POSTGRES_PASSWORD='p', GATEWAY_ENCRYPTION_KEYS='k',
        )
        names = {line.split('=', 1)[0] for line in out.stdout.splitlines()}
        self.assertEqual(names, {'PATH', 'PGDATA', 'LANG', 'PGPORT', 'RUNPOD_POD_ID', 'BACKUP_DIR'})
        self.assertIn('RUNPOD_POD_ID=pod-a', out.stdout.splitlines())

    def test_client_tools_use_the_server_port(self):
        out = self.lib('postgres_env_cmd; "${POSTGRES_ENV[@]}" env', POSTGRES_PORT='5433')
        self.assertIn('PGPORT=5433', out.stdout.splitlines())


class VolumeTests(PodTestCase):
    def test_a_plain_directory_is_not_a_volume(self):
        self.assertNotEqual(self.lib('volume_ready', check=False).returncode, 0)

    def test_a_mount_point_with_a_writable_backup_dir_is_ready(self):
        # '/' is a mount point everywhere the tests run.
        self.assertEqual(self.lib('volume_ready', VOLUME_MOUNT='/').returncode, 0)
