"""archive-wal.sh and restore-wal.sh against temporary directories (spec §4.4, §5.2)."""
import gzip
import os
import subprocess

from tests.pod.support import POD_DIR, PodTestCase

SEGMENT = '000000010000000000000006'


class WalScriptTestCase(PodTestCase):
    def run_script(self, name, *args, **env):
        return subprocess.run(
            [str(POD_DIR / name), *args], capture_output=True, text=True, timeout=30,
            env={'PATH': os.environ['PATH'], **self.pod.env(**env)},
        )

    def archived(self, name=SEGMENT):
        return self.pod.backup / 'wal' / f'{name}.gz'


class ArchiveTests(WalScriptTestCase):
    def setUp(self):
        super().setUp()
        self.pod.set_owner('pod-a')
        self.segment = self.pod.root / SEGMENT
        self.segment.write_bytes(b'\x00wal bytes\x01' * 100)

    def archive(self, pod='pod-a'):
        return self.run_script('archive-wal.sh', str(self.segment), SEGMENT, RUNPOD_POD_ID=pod)

    def test_archives_compressed(self):
        self.assertEqual(self.archive().returncode, 0)
        self.assertEqual(gzip.decompress(self.archived().read_bytes()), self.segment.read_bytes())
        self.assertEqual(sorted(p.name for p in (self.pod.backup / 'wal').iterdir()), [f'{SEGMENT}.gz'])

    def test_same_file_again_succeeds(self):
        self.archive()
        self.assertEqual(self.archive().returncode, 0)

    def test_different_file_with_the_same_name_fails(self):
        self.archive()
        self.segment.write_bytes(b'other bytes')
        out = self.archive()
        self.assertEqual(out.returncode, 1)
        self.assertIn(f'ARCHIVE ERROR {SEGMENT}: a different file', out.stderr)

    def test_damaged_archived_copy_is_replaced(self):
        self.archived().write_bytes(b'not gzip at all')
        out = self.archive()
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(f'replacing the damaged archived copy of {SEGMENT}', out.stdout)
        self.assertEqual(gzip.decompress(self.archived().read_bytes()), self.segment.read_bytes())

    def test_foreign_owner_writes_nothing(self):
        out = self.archive(pod='pod-b')
        self.assertEqual(out.returncode, 1)
        self.assertIn('OWNER FENCE', out.stderr)
        self.assertFalse(self.archived().exists())

    def test_missing_owner_writes_nothing(self):
        (self.pod.backup / 'OWNER').unlink()
        self.assertEqual(self.archive().returncode, 1)
        self.assertFalse(self.archived().exists())

    def test_unwritable_volume_fails_and_leaves_no_temp_file(self):
        (self.pod.backup / 'wal').rmdir()
        self.assertEqual(self.archive().returncode, 1)


class RestoreTests(WalScriptTestCase):
    def restore(self, name=SEGMENT):
        dest = self.pod.root / 'RECOVERYXLOG'
        return self.run_script('restore-wal.sh', name, str(dest)), dest

    def test_missing_file_is_the_quiet_end_of_the_archive(self):
        out, dest = self.restore()
        self.assertEqual((out.returncode, out.stderr), (1, ''))
        self.assertFalse(dest.exists())
        self.assertFalse((self.pod.state / 'restore-corrupt').exists())

    def test_restores_the_file(self):
        self.archived().write_bytes(gzip.compress(b'segment'))
        out, dest = self.restore()
        self.assertEqual(out.returncode, 0)
        self.assertEqual(dest.read_bytes(), b'segment')

    def test_restores_a_history_file(self):
        self.archived('00000002.history').write_bytes(gzip.compress(b'1\t0/A00000\tno recovery target\n'))
        out, dest = self.restore('00000002.history')
        self.assertEqual(out.returncode, 0)

    def test_truncated_file_is_flagged_corrupt(self):
        self.archived().write_bytes(gzip.compress(b'segment' * 1000)[:40])
        out, dest = self.restore()
        self.assertEqual(out.returncode, 1)
        self.assertIn(f'RESTORE ERROR corrupt {SEGMENT}', out.stderr)
        self.assertTrue((self.pod.state / 'restore-corrupt').exists())
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_name('RECOVERYXLOG.tmp').exists())
