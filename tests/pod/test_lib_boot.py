"""lib.sh: the boot decision table (spec §4.2) and the volume owner rule (spec §4.3 rule 3)."""
from tests.pod.support import PodTestCase


class BootDecisionTests(PodTestCase):
    def decide(self):
        return self.lib('boot_decision').stdout.strip()

    def test_existing_cluster_is_a_normal_start(self):
        self.pod.init_cluster()
        self.assertEqual(self.decide(), 'normal')

    def test_existing_cluster_wins_over_backups(self):
        self.pod.init_cluster()
        self.pod.add_backup('20261012T100000Z')
        self.assertEqual(self.decide(), 'normal')

    def test_interrupted_cluster_with_backups_is_restored(self):
        self.pod.init_cluster()
        (self.pod.state / 'cluster-in-progress').touch()
        self.pod.add_backup('20261012T100000Z')
        self.assertEqual(self.decide(), 'restore')

    def test_interrupted_cluster_without_backups_is_initialised_again(self):
        self.pod.init_cluster()
        (self.pod.state / 'cluster-in-progress').touch()
        self.assertEqual(self.decide(), 'fresh')

    def test_empty_disk_with_a_complete_backup_is_restored(self):
        self.pod.add_backup('20261012T100000Z')
        self.pod.add_wal('000000010000000000000002.gz')
        self.assertEqual(self.decide(), 'restore')

    def test_empty_disk_and_empty_volume_is_a_fresh_init(self):
        self.assertEqual(self.decide(), 'fresh')

    def test_incomplete_backup_alone_is_a_fresh_init(self):
        self.pod.add_backup('20261012T100000Z', complete=False)
        self.assertEqual(self.decide(), 'fresh')

    def test_archive_without_a_base_backup_is_refused(self):
        self.pod.add_wal('000000010000000000000001.gz')
        self.assertEqual(self.decide(), 'refuse-no-base')

    def test_archive_with_only_an_incomplete_backup_is_refused(self):
        self.pod.add_backup('20261012T100000Z', complete=False)
        self.pod.add_wal('000000010000000000000001.gz')
        self.assertEqual(self.decide(), 'refuse-no-base')


class OwnerDecisionTests(PodTestCase):
    def decide(self, owner, pod, takeover):
        return self.lib(f'owner_decision "{owner}" "{pod}" "{takeover}"').stdout.strip()

    def test_table(self):
        cases = [
            ('', 'pod-a', '', 'claim'),
            ('pod-a', 'pod-a', '', 'continue'),
            ('pod-a', 'pod-a', 'pod-z', 'continue'),
            ('pod-a', 'pod-b', '', 'refuse'),
            ('pod-a', 'pod-b', 'pod-a', 'takeover'),
            ('pod-a', 'pod-b', 'pod-c', 'refuse'),
            ('pod-a', '', '', 'refuse'),
        ]
        for owner, pod, takeover, expected in cases:
            with self.subTest(owner=owner, pod=pod, takeover=takeover):
                self.assertEqual(self.decide(owner, pod, takeover), expected)


class OwnerCheckTests(PodTestCase):
    def owner(self):
        return (self.pod.backup / 'OWNER').read_text().strip()

    def test_first_boot_claims_the_folder(self):
        self.lib('owner_check', RUNPOD_POD_ID='pod-a')
        self.assertEqual(self.owner(), 'pod-a')

    def test_foreign_owner_is_refused_and_kept(self):
        self.pod.set_owner('pod-a')
        self.assertEqual(self.lib('owner_check', check=False, RUNPOD_POD_ID='pod-b').returncode, 1)
        self.assertEqual(self.owner(), 'pod-a')

    def test_takeover_rewrites_the_owner_and_logs_it(self):
        self.pod.set_owner('pod-a')
        out = self.lib('owner_check', RUNPOD_POD_ID='pod-b', BACKUP_TAKEOVER='pod-a')
        self.assertEqual(self.owner(), 'pod-b')
        self.assertIn('taken over from pod pod-a', out.stdout)

    def test_leftover_takeover_is_harmless_after_the_takeover(self):
        self.pod.set_owner('pod-b')
        self.lib('owner_check', RUNPOD_POD_ID='pod-b', BACKUP_TAKEOVER='pod-a')
        self.assertEqual(self.owner(), 'pod-b')


class OwnerFenceTests(PodTestCase):
    def test_own_folder_passes(self):
        self.pod.set_owner('pod-a')
        self.assertEqual(self.lib('owner_fence', RUNPOD_POD_ID='pod-a').returncode, 0)

    def test_foreign_folder_fails_with_a_log_line(self):
        self.pod.set_owner('pod-b')
        out = self.lib('owner_fence', check=False, RUNPOD_POD_ID='pod-a')
        self.assertEqual(out.returncode, 1)
        self.assertIn("OWNER FENCE: backup folder belongs to 'pod-b', this pod is 'pod-a'", out.stderr)

    def test_missing_owner_fails(self):
        self.assertEqual(self.lib('owner_fence', check=False, RUNPOD_POD_ID='pod-a').returncode, 1)
