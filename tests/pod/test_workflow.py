"""Guards on the GitHub Actions workflow that builds the pod image (spec §10.1)."""
from django.test import SimpleTestCase

from tests.pod.support import ROOT


class PodImageWorkflowTests(SimpleTestCase):
    def setUp(self):
        self.text = (ROOT / '.github' / 'workflows' / 'pod-image.yml').read_text(encoding='utf-8')

    def test_runs_on_main_and_by_hand(self):
        self.assertIn('branches: [main]', self.text)
        self.assertIn('workflow_dispatch:', self.text)

    def test_tests_gate_the_build(self):
        self.assertIn('run: python manage.py test', self.text)
        self.assertIn('needs: test', self.text)

    def test_builds_the_pod_dockerfile(self):
        self.assertIn('file: docker/pod/Dockerfile', self.text)

    def test_pushes_short_sha_and_latest_to_ghcr_with_the_workflow_token(self):
        self.assertIn('ghcr.io/${GITHUB_REPOSITORY_OWNER,,}/ai4deliberation-backend-pod', self.text)
        self.assertIn('tag=${GITHUB_SHA::7}', self.text)
        self.assertIn(':${{ steps.image.outputs.tag }}', self.text)
        self.assertIn(':latest', self.text)
        self.assertIn('password: ${{ secrets.GITHUB_TOKEN }}', self.text)
        self.assertIn('packages: write', self.text)

    def test_image_links_to_the_repo_and_licence(self):
        self.assertIn('org.opencontainers.image.source=https://github.com/${{ github.repository }}', self.text)
        self.assertIn('org.opencontainers.image.licenses=EUPL-1.2', self.text)
