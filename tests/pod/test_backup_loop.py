"""Guards on the backup loop (spec §5.3). Its behaviour is covered by the local drill (spec §9.2)."""
import re

from django.core.management import get_commands
from django.test import SimpleTestCase

from tests.pod.support import pod_code

SCRIPTS = (
    'entrypoint.sh', 'app-start.sh', 'archive-wal.sh', 'restore-wal.sh', 'backup-loop.sh',
    'backup-status', 'backup-reset', 'gateway-manage',
)


class BackupLoopTests(SimpleTestCase):
    def setUp(self):
        self.text = pod_code('backup-loop.sh')

    def test_base_backup_command(self):
        self.assertIn('pg_basebackup -U postgres -Ft -z -X stream -c fast', self.text)

    def test_complete_is_written_last_after_an_integrity_check(self):
        self.assertLess(self.text.index('gzip -t "$dest/base.tar.gz"'), self.text.index('"$dest/COMPLETE.tmp"'))
        self.assertLess(self.text.index('sync -d'), self.text.index('"$dest/COMPLETE.tmp"'))

    def test_every_write_step_passes_the_owner_fence(self):
        for function in ('take_base_backup', 'take_dump', 'apply_retention', 'write_status'):
            body = self.text[self.text.index(f'{function}() {{'):]
            with self.subTest(function=function):
                self.assertIn('owner_fence', body[:body.index('\n}')])

    def test_wal_cleanup_keeps_history_files_and_strips_the_extension(self):
        self.assertIn('pg_archivecleanup -b -x ".$ARCHIVE_FORMAT"', self.text)

    def test_daily_cycle_records_its_time_on_the_volume(self):
        self.assertIn('write_status last-cycle', self.text)
        self.assertIn('"$BACKUP_DIR/status/last-cycle"', self.text)

    def test_retention_keeps_backups_younger_than_the_keep_age(self):
        self.assertIn('"$KEEP_BASE_BACKUPS" "$KEEP_BASE_BACKUP_SECONDS"', self.text)

    def test_purges_call_logs_daily(self):
        self.assertIn('gateway-manage" purge_call_logs', self.text)

    def test_scripts_only_call_existing_management_commands(self):
        called = set()
        for name in SCRIPTS:
            called |= set(re.findall(r'(?:manage\.py|gateway-manage)"?\s+([a-z_]+)', pod_code(name)))
        self.assertIn('purge_call_logs', called)
        self.assertEqual(sorted(called - set(get_commands())), [])
