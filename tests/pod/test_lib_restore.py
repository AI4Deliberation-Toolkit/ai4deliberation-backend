"""lib.sh: restore completeness check and archive formats (spec §4.4, §8)."""
import gzip
import io
import tarfile

from tests.pod.support import PodTestCase


class SegmentTests(PodTestCase):
    def test_lsn_to_segment_with_1mb_segments(self):
        cases = {
            '0/A00000': '000000000000000A',
            '0/1FFFFF': '0000000000000001',
            '0/0': '0000000000000000',
            '1/0': '0000000100000000',
            '2/3500028': '0000000200000035',
        }
        for lsn, suffix in cases.items():
            with self.subTest(lsn=lsn):
                self.assertEqual(self.lib(f'lsn_segment_suffix {lsn}').stdout.strip(), suffix)


class CompletenessTests(PodTestCase):
    def history(self, text):
        path = self.pod.root / 'history'
        path.write_text(text)
        return path

    def check(self, history):
        return self.lib(f'restore_complete "{self.pod.backup}/wal" "{history}"', check=False)

    def test_archive_ending_at_the_switch_segment_is_complete(self):
        for n in range(6, 11):
            self.pod.add_wal(f'0000000100000000000000{n:02X}.gz')
        self.pod.add_wal('00000002000000000000000A.gz')
        self.pod.add_wal('00000001000000000000000A.partial.gz')
        self.pod.add_wal('000000010000000000000006.00000028.backup.gz')
        history = self.history('1\t0/A3F2B8\tno recovery target specified\n')
        self.assertEqual(self.check(history).returncode, 0)

    def test_parent_segment_past_the_switch_means_recovery_stopped_early(self):
        for n in (6, 7, 9, 10):  # 8 is missing: recovery ended in 7
            self.pod.add_wal(f'0000000100000000000000{n:02X}.gz')
        history = self.history('1\t0/800000\tno recovery target specified\n')
        out = self.check(history)
        self.assertEqual(out.returncode, 1)
        self.assertIn('000000010000000000000009.gz', out.stderr)
        self.assertIn('00000001000000000000000A.gz', out.stderr)

    def test_uses_the_last_line_for_a_second_restore(self):
        self.pod.add_wal('000000010000000000000030.gz')  # old timeline 1 past its switch: not checked
        self.pod.add_wal('000000020000000000000014.gz')
        history = self.history('1\t0/A3F2B8\tno recovery target specified\n\n2\t0/14000A0\tno recovery target specified\n')
        self.assertEqual(self.check(history).returncode, 0)

    def test_planned_stop_switch_at_a_segment_boundary_is_complete(self):
        # The shutdown WAL switch puts the switch point at the start of a segment that was never archived.
        for n in range(6, 9):
            self.pod.add_wal(f'0000000100000000000000{n:02X}.gz')
        self.assertEqual(self.check(self.history('1\t0/900000\tno recovery target specified\n')).returncode, 0)

    def test_archived_parent_segment_at_a_boundary_switch_was_never_replayed(self):
        for n in range(6, 10):
            self.pod.add_wal(f'0000000100000000000000{n:02X}.gz')
        out = self.check(self.history('1\t0/900000\tno recovery target specified\n'))
        self.assertEqual(out.returncode, 1)
        self.assertIn('000000010000000000000009.gz', out.stderr)

    def test_late_segments_in_any_readable_format_count(self):
        self.pod.add_wal('000000010000000000000006.gz')
        self.pod.add_wal('00000001000000000000000C.gz.age')
        history = self.history('1\t0/800000\tno recovery target specified\n')
        out = self.lib(
            f'ARCHIVE_FORMATS="gz gz.age"; restore_complete "{self.pod.backup}/wal" "{history}"', check=False,
        )
        self.assertEqual(out.returncode, 1)
        self.assertIn('00000001000000000000000C.gz.age', out.stderr)

    def test_history_without_entries_fails(self):
        self.assertEqual(self.check(self.history('')).returncode, 1)


class FormatTests(PodTestCase):
    def test_archived_file_finds_a_known_format(self):
        path = self.pod.add_wal('000000010000000000000006.gz')
        out = self.lib(f'archived_file "{self.pod.backup}/wal" 000000010000000000000006')
        self.assertEqual(out.stdout.strip(), str(path))

    def test_archived_file_missing(self):
        out = self.lib(f'archived_file "{self.pod.backup}/wal" 000000010000000000000006', check=False)
        self.assertEqual(out.returncode, 1)

    def test_decompress_picks_the_tool_by_extension(self):
        path = self.pod.add_wal('x.gz', gzip.compress(b'segment bytes'))
        self.assertEqual(self.lib(f'decompress "{path}"').stdout, 'segment bytes')

    def test_decompress_rejects_an_unknown_format(self):
        path = self.pod.add_wal('x.gz.age', b'...')
        out = self.lib(f'decompress "{path}"', check=False)
        self.assertEqual(out.returncode, 2)
        self.assertIn('unknown archive format', out.stderr)

    def test_extract_tar(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            data = b'17\n'
            info = tarfile.TarInfo('PG_VERSION')
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        archive = self.pod.root / 'base.tar.gz'
        archive.write_bytes(buffer.getvalue())
        target = self.pod.root / 'out'
        target.mkdir()
        self.lib(f'extract_tar "{archive}" "{target}"')
        self.assertEqual((target / 'PG_VERSION').read_text(), '17\n')

    def test_extract_tar_rejects_an_unknown_format(self):
        self.assertEqual(self.lib('extract_tar x.tar.age /tmp', check=False).returncode, 2)
