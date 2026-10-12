"""Guards on the Postgres settings, supervisord and the app start (spec §3.3, §5.1, §6, §7.2)."""
import configparser
import re

from django.test import SimpleTestCase

from tests.pod.support import pod_code, pod_file


def supervisord():
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(pod_file('supervisord.conf'))
    return parser


class PostgresConfTests(SimpleTestCase):
    def test_archiving_settings(self):
        text = pod_file('postgresql.pod.conf')
        for line in (
            "listen_addresses = '127.0.0.1'",
            'port = ${POSTGRES_PORT}',
            'max_connections = 50',
            'wal_level = replica',
            'archive_mode = on',
            "archive_command = '/usr/src/app/docker/pod/archive-wal.sh %p %f'",
            'archive_timeout = 60',
            'wal_recycle = off',
        ):
            with self.subTest(line=line):
                self.assertRegex(text, rf'(?m)^{re.escape(line)}$')


class SupervisordTests(SimpleTestCase):
    def test_start_order(self):
        conf = supervisord()
        priorities = [conf.getint(f'program:{name}', 'priority') for name in ('postgres', 'backup', 'app')]
        self.assertEqual(priorities, sorted(priorities))
        self.assertEqual(len(set(priorities)), 3)

    def test_stop_settings_fit_the_15_second_window(self):
        conf = supervisord()
        self.assertEqual(conf.get('program:postgres', 'stopsignal'), 'INT')
        self.assertEqual(
            [conf.getint(f'program:{name}', 'stopwaitsecs') for name in ('postgres', 'backup', 'app')],
            [8, 1, 4],
        )
        self.assertEqual(conf.get('program:backup', 'killasgroup'), 'true')
        self.assertEqual(conf.get('program:backup', 'stopasgroup'), 'true')

    def test_postgres_runs_with_the_env_allow_list(self):
        command = supervisord().get('program:postgres', 'command')
        self.assertIn('postgres_env_cmd', command)
        self.assertIn('exec "${POSTGRES_ENV[@]}" gosu postgres postgres', command)

    def test_supervisord_runs_in_the_foreground(self):
        conf = supervisord()
        self.assertEqual(conf.get('supervisord', 'nodaemon'), 'true')
        self.assertEqual(conf.get('supervisord', 'pidfile'), '/run/supervisord.pid')

    def test_supervisorctl_works_over_a_local_socket(self):
        conf = supervisord()
        self.assertEqual(conf.get('unix_http_server', 'file'), '/run/supervisor.sock')
        self.assertEqual(conf.get('supervisorctl', 'serverurl'), 'unix:///run/supervisor.sock')


class AppStartTests(SimpleTestCase):
    def test_gunicorn_runs_asgi_with_a_3_second_graceful_timeout(self):
        text = pod_code('app-start.sh')
        self.assertIn('-k uvicorn_worker.UvicornWorker', text)
        self.assertIn('ai4deliberation_backend.asgi:application', text)
        self.assertIn('--graceful-timeout 3', text)
        self.assertNotIn('--access-logfile', text)

    def test_migrates_and_collects_static_files_first(self):
        text = pod_code('app-start.sh')
        self.assertLess(text.index('manage.py migrate --noinput'), text.index('exec gunicorn'))
        self.assertLess(text.index('manage.py collectstatic --noinput --clear'), text.index('exec gunicorn'))
