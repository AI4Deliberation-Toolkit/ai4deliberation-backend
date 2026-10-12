"""lib.sh: base-backup selection, schedule and retention (spec §5.3)."""
import calendar
from datetime import datetime, timezone

from tests.pod.support import PodTestCase

# backup_label from a real `pg_basebackup -Ft -z -X stream` of Postgres 17.
BACKUP_LABEL = """\
START WAL LOCATION: 0/600028 (file 000000010000000000000006)
CHECKPOINT LOCATION: 0/600080
BACKUP METHOD: streamed
BACKUP FROM: primary
START TIME: 2026-10-12 20:05:24 UTC
LABEL: pg_basebackup base backup
START TIMELINE: 1
"""
NOW = calendar.timegm((2026, 10, 14, 12, 0, 0))
HOUR = 3600


def stamp(seconds_ago):
    """Backup folder name for a backup taken `seconds_ago` before NOW."""
    return datetime.fromtimestamp(NOW - seconds_ago, timezone.utc).strftime('%Y%m%dT%H%M%SZ')


class SelectionTests(PodTestCase):
    def test_complete_backups_newest_first(self):
        self.pod.add_backup('20261010T100000Z')
        self.pod.add_backup('20261012T100000Z')
        self.pod.add_backup('20261013T100000Z', complete=False)
        out = self.lib(f'complete_backups "{self.pod.backup}/base"')
        self.assertEqual(
            out.stdout.splitlines(),
            [f'{self.pod.backup}/base/20261012T100000Z', f'{self.pod.backup}/base/20261010T100000Z'],
        )

    def test_folders_not_named_by_a_stamp_are_ignored(self):
        self.pod.add_backup('20261010T100000Z')
        self.pod.add_backup('zz-copy')
        out = self.lib(f'complete_backups "{self.pod.backup}/base"')
        self.assertEqual(out.stdout.splitlines(), [f'{self.pod.backup}/base/20261010T100000Z'])

    def test_read_stamp(self):
        good, bad = self.pod.root / 'good', self.pod.root / 'bad'
        good.write_text('20261012T200524Z\n')
        bad.write_text('yesterday\n')
        out = self.lib(f'read_stamp "{good}"; read_stamp "{bad}"; read_stamp "{self.pod.root}/missing"')
        self.assertEqual(out.stdout, '20261012T200524Z\n')

    def test_newest_complete_backup(self):
        self.pod.add_backup('20261010T100000Z')
        self.pod.add_backup('20261013T100000Z', complete=False)
        out = self.lib(f'newest_complete_backup "{self.pod.backup}/base"')
        self.assertEqual(out.stdout.strip(), f'{self.pod.backup}/base/20261010T100000Z')

    def test_no_backups(self):
        self.assertEqual(self.lib(f'newest_complete_backup "{self.pod.backup}/base"').stdout, '')

    def test_start_wal_from_backup_label(self):
        out = self.lib(f"start_wal_from_label <<'EOF'\n{BACKUP_LABEL}EOF")
        self.assertEqual(out.stdout.strip(), '000000010000000000000006')

    def test_stamp_to_epoch(self):
        expected = calendar.timegm((2026, 10, 12, 20, 5, 24))
        self.assertEqual(self.lib('stamp_to_epoch 20261012T200524Z').stdout.strip(), str(expected))


class ScheduleTests(PodTestCase):
    def due(self, last_cycle=None, force=0):
        flag = self.pod.state / 'needs-base-backup'
        last = self.pod.backup / 'status' / 'last-cycle'
        if last_cycle is not None:
            last.parent.mkdir(exist_ok=True)
            last.write_text(stamp(last_cycle) + '\n')
        return self.lib(f'base_backup_due "{self.pod.backup}/base" "{flag}" "{last}" {NOW} {force}').stdout.strip()

    def test_first_check_runs_the_daily_cycle(self):
        self.assertEqual(self.due(), 'daily')

    def test_day_old_cycle_runs_the_daily_cycle(self):
        self.pod.add_backup(stamp(HOUR))
        self.assertEqual(self.due(last_cycle=24 * HOUR), 'daily')

    def test_restores_dont_postpone_the_daily_cycle(self):
        # Each restore takes a fresh base backup; the daily cycle still comes a day after the last one.
        self.pod.add_backup(stamp(HOUR))
        self.assertEqual(self.due(last_cycle=25 * HOUR), 'daily')

    def test_recent_cycle_and_backup_need_nothing(self):
        self.pod.add_backup(stamp(HOUR))
        self.assertEqual(self.due(last_cycle=23 * HOUR), 'none')

    def test_flag_takes_a_base_backup_now(self):
        self.pod.add_backup(stamp(HOUR))
        (self.pod.state / 'needs-base-backup').touch()
        self.assertEqual(self.due(last_cycle=HOUR), 'base')

    def test_no_complete_backup_takes_one_now(self):
        self.pod.add_backup(stamp(HOUR), complete=False)
        self.assertEqual(self.due(last_cycle=HOUR), 'base')

    def test_failed_daily_base_backup_is_retried(self):
        self.pod.add_backup(stamp(25 * HOUR))
        self.assertEqual(self.due(last_cycle=HOUR), 'base')

    def test_unreadable_last_cycle_counts_as_never(self):
        self.pod.add_backup(stamp(HOUR))
        last = self.pod.backup / 'status' / 'last-cycle'
        last.parent.mkdir(exist_ok=True)
        last.write_text('garbage\n')
        self.assertEqual(self.due(), 'daily')

    def test_force_runs_the_daily_cycle(self):
        self.pod.add_backup(stamp(HOUR))
        self.assertEqual(self.due(last_cycle=HOUR, force=1), 'daily')


class RetentionTests(PodTestCase):
    def test_keeps_newest_three_complete_and_young_incomplete(self):
        complete = [stamp(h * HOUR) for h in (1, 25, 49, 73, 97)]
        for s in complete:
            self.pod.add_backup(s)
        self.pod.add_backup(stamp(30 * HOUR), complete=False)
        self.pod.add_backup(stamp(2 * HOUR), complete=False)
        out = self.lib(f'backups_to_delete "{self.pod.backup}/base" 3 {72 * HOUR} {NOW}')
        base = self.pod.backup / 'base'
        self.assertEqual(
            sorted(out.stdout.splitlines()),
            sorted([f'{base}/{complete[3]}', f'{base}/{complete[4]}', f'{base}/{stamp(30 * HOUR)}']),
        )

    def test_keeps_every_backup_younger_than_the_keep_age(self):
        # Several restores in a day each take a base backup; the recovery window stays ~3 days.
        young = [stamp(h * HOUR) for h in (1, 2, 3, 4, 30, 70)]
        old = [stamp(h * HOUR) for h in (80, 100)]
        for s in young + old:
            self.pod.add_backup(s)
        out = self.lib(f'backups_to_delete "{self.pod.backup}/base" 3 {72 * HOUR} {NOW}')
        base = self.pod.backup / 'base'
        self.assertEqual(sorted(out.stdout.splitlines()), sorted(f'{base}/{s}' for s in old))

    def test_keep_age_zero_keeps_only_the_newest_three(self):
        stamps = [stamp(h * HOUR) for h in (1, 2, 3, 4, 5)]
        for s in stamps:
            self.pod.add_backup(s)
        out = self.lib(f'backups_to_delete "{self.pod.backup}/base" 3 0 {NOW}')
        base = self.pod.backup / 'base'
        self.assertEqual(sorted(out.stdout.splitlines()), sorted(f'{base}/{s}' for s in stamps[3:]))

    def test_keep_age_defaults_to_three_days(self):
        self.assertEqual(self.lib('echo $KEEP_BASE_BACKUP_SECONDS').stdout.strip(), str(72 * HOUR))
        self.assertEqual(self.lib('echo $KEEP_BASE_BACKUP_SECONDS', BACKUP_KEEP_SECONDS='0').stdout.strip(), '0')

    def test_keeps_newest_seven_dumps(self):
        dumps = self.pod.backup / 'dumps'
        names = [f'gateway-{stamp(d * 24 * HOUR)}.dump' for d in range(9)]
        for name in names:
            (dumps / name).write_bytes(b'')
        (dumps / 'gateway-x.dump.tmp').write_bytes(b'')
        out = self.lib(f'dumps_to_delete "{dumps}" 7')
        self.assertEqual(sorted(out.stdout.splitlines()), sorted(f'{dumps}/{n}' for n in names[7:]))

    def test_wal_cutoff_is_the_lowest_start_segment(self):
        dirs = [
            self.pod.add_backup('20261012T100000Z', '000000010000000000000006'),
            self.pod.add_backup('20261011T100000Z', '000000020000000000000009'),
            self.pod.add_backup('20261010T100000Z', '000000010000000000000003'),
        ]
        out = self.lib('wal_cutoff ' + ' '.join(f'"{d}"' for d in dirs))
        self.assertEqual(out.stdout.strip(), '000000010000000000000003')

    def test_wal_cutoff_after_point_in_time_recovery_ignores_the_timeline(self):
        # After a manual PITR to an older backup, the newest backup sits on a higher timeline
        # with the lowest segment number; the cut-off must not delete what it needs.
        dirs = [
            self.pod.add_backup('20261012T100000Z', '000000030000000000000004'),
            self.pod.add_backup('20261011T100000Z', '00000002000000000000000C'),
            self.pod.add_backup('20261010T100000Z', '00000002000000000000000F'),
        ]
        out = self.lib('wal_cutoff ' + ' '.join(f'"{d}"' for d in dirs))
        self.assertEqual(out.stdout.strip(), '000000030000000000000004')
