"""Guards on the deploy files: ASGI workers, a portable DB wait, bounded container logs."""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from tests.test_dependency_fence import _requirement_names

ROOT = Path(__file__).resolve().parent.parent


def _compose_services():
    """Split docker-compose-staging.yml's `services:` section into {name: block text}."""
    text = (ROOT / 'docker-compose-staging.yml').read_text(encoding='utf-8')
    services = text.split('\nvolumes:')[0]
    blocks = re.split(r'\n  (?=[a-z][\w-]*:\n)', services)[1:]
    return {block.split(':', 1)[0]: block for block in blocks}


def _requirements():
    return set(_requirement_names((ROOT / 'requirements.txt').read_text(encoding='utf-8')))


class DeployConfigTests(SimpleTestCase):
    def test_compose_lists_the_three_services(self):
        self.assertEqual(sorted(_compose_services()), ['db', 'nginx', 'web'])

    def test_web_runs_asgi_under_uvicorn_workers(self):
        web = _compose_services()['web']
        self.assertIn('-k uvicorn_worker.UvicornWorker', web)
        self.assertIn('ai4deliberation_backend.asgi:application', web)
        self.assertNotIn('wsgi:application', web)

    def test_every_service_caps_its_container_logs(self):
        for name, block in _compose_services().items():
            with self.subTest(service=name):
                self.assertIn('driver: json-file', block)
                self.assertIn('max-size: "10m"', block)
                self.assertIn('max-file: "5"', block)

    def test_entrypoint_waits_on_configurable_db_host(self):
        script = (ROOT / 'docker' / 'web' / 'entrypoint.sh').read_text(encoding='utf-8')
        self.assertIn('nc -z "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}"', script)

    def test_web_gets_the_env_file_so_the_entrypoint_sees_postgres_settings(self):
        self.assertRegex(_compose_services()['web'], r'env_file:\n\s+- \.env\n')

    def test_drf_and_simplejwt_are_gone(self):
        names = _requirements()
        self.assertNotIn('djangorestframework', names)
        self.assertNotIn('djangorestframework-simplejwt', names)
        self.assertNotIn('rest_framework', settings.INSTALLED_APPS)

    def test_gateway_runtime_packages_are_listed(self):
        names = _requirements()
        for package in ('django-ninja', 'httpx', 'cryptography', 'uvicorn', 'uvicorn-worker'):
            with self.subTest(package=package):
                self.assertIn(package, names)
