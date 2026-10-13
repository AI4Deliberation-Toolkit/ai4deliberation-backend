"""The runbook covers what the pod can print and offers (spec §11)."""
import re

from django.test import SimpleTestCase

from tests.pod.support import POD_DIR, pod_code


class RunbookTests(SimpleTestCase):
    def setUp(self):
        self.text = (POD_DIR / 'README.md').read_text(encoding='utf-8')

    def test_every_refusal_reason_is_explained(self):
        entrypoint = pod_code('entrypoint.sh')
        literals = re.findall(r'(?:refuse|FAILURE=)\s*["\']([^"\'$(]+)', entrypoint)
        reasons = {literal.rstrip(' :\\\'"') for literal in literals} - {''}
        self.assertGreater(len(reasons), 10)
        for reason in sorted(reasons):
            with self.subTest(reason=reason):
                self.assertIn(reason, self.text)

    def test_restoring_the_newest_dump_is_spelled_out(self):
        # Runbook §6.3: the app is stopped while the dump replaces the fresh database.
        section = self.text[self.text.index('**Use the newest dump instead**'):self.text.index('## 7. Drills')]
        stop = section.index('supervisorctl stop app')
        restore = section.index('pg_restore --no-owner --role=gateway --clean --if-exists -d gateway')
        self.assertLess(stop, restore)
        self.assertLess(restore, section.index('supervisorctl start app'))

    def test_names_the_helper_commands(self):
        for command in ('backup-status', 'backup-reset --yes', 'gateway-manage createsuperuser', 'supervisorctl', 'BACKUP_TAKEOVER'):
            with self.subTest(command=command):
                self.assertIn(command, self.text)
