"""Guards on the pod image: files, Dockerfile, licence (spec §3.1, §3.2, §10.3)."""
import os
import subprocess

from django.test import SimpleTestCase

from tests.pod.support import POD_DIR, ROOT, pod_code

IMAGE_SCRIPTS = (
    'entrypoint.sh', 'app-start.sh', 'archive-wal.sh', 'restore-wal.sh', 'backup-loop.sh',
    'backup-status', 'backup-reset', 'gateway-manage',
)
HOST_SCRIPTS = ('drill.sh',)  # run by hand on a machine with Docker
SHELL_FILES = (*IMAGE_SCRIPTS, 'lib.sh', *HOST_SCRIPTS)
OTHER_FILES = ('Dockerfile', 'supervisord.conf', 'postgresql.pod.conf')


class FilesTests(SimpleTestCase):
    def test_pod_files_exist(self):
        for name in (*SHELL_FILES, *OTHER_FILES):
            with self.subTest(name=name):
                self.assertTrue((POD_DIR / name).is_file())

    def test_shell_files_parse(self):
        for name in SHELL_FILES:
            with self.subTest(name=name):
                result = subprocess.run(['bash', '-n', str(POD_DIR / name)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_scripts_are_executable_in_the_repo(self):
        for name in (*IMAGE_SCRIPTS, *HOST_SCRIPTS):
            with self.subTest(name=name):
                self.assertTrue(os.access(POD_DIR / name, os.X_OK))


class DockerfileTests(SimpleTestCase):
    def setUp(self):
        self.text = pod_code('Dockerfile')

    def test_base_image_is_bookworm(self):
        # PGDG's postgresql-17 for bookworm needs libicu72, which trixie doesn't ship.
        self.assertIn('FROM python:3.12-slim-bookworm', self.text)

    def test_no_default_cluster(self):
        self.assertIn('create_main_cluster = false', self.text)
        self.assertLess(
            self.text.index('create_main_cluster'), self.text.index('--no-install-recommends postgresql-17'),
        )

    def test_makes_every_image_script_executable(self):
        chmod = self.text[self.text.index('chmod +x'):self.text.index('ln -s')]
        for name in IMAGE_SCRIPTS:
            with self.subTest(name=name):
                self.assertIn(f'docker/pod/{name}', chmod)

    def test_helpers_are_on_the_path(self):
        for name in ('backup-status', 'backup-reset', 'gateway-manage'):
            with self.subTest(name=name):
                self.assertIn(f'/usr/local/bin/{name}', self.text)

    def test_entrypoint_and_port(self):
        self.assertIn('ENTRYPOINT ["/usr/src/app/docker/pod/entrypoint.sh"]', self.text)
        self.assertIn('EXPOSE 8000', self.text)
        self.assertNotRegex(self.text, r'(?m)^CMD')

    def test_no_unused_packages(self):
        # apt reads the PGDG key as a plain .asc through signed-by; gnupg is never used.
        self.assertNotIn('gnupg', self.text)


class LicenceTests(SimpleTestCase):
    def test_eupl_licence_ships_in_the_image(self):
        self.assertIn('EUROPEAN UNION PUBLIC LICENCE v. 1.2', (ROOT / 'LICENSE').read_text(encoding='utf-8'))
        ignored = (ROOT / '.dockerignore').read_text(encoding='utf-8').splitlines()
        self.assertNotIn('LICENSE', ignored)
