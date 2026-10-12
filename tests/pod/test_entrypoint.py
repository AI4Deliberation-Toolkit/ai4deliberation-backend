"""Guards on the boot script (spec §4). Its behaviour is covered by the local drill (spec §9.2)."""
from django.test import SimpleTestCase

from tests.pod.support import pod_code


class EntrypointTests(SimpleTestCase):
    def setUp(self):
        self.text = pod_code('entrypoint.sh')

    def test_one_megabyte_wal_segments_and_initdb_auth(self):
        self.assertIn('--wal-segsize=1 --auth-local=peer --auth-host=scram-sha-256', self.text)

    def test_restore_command_points_at_restore_wal(self):
        self.assertIn('restore_command = \'%s %%f %%p\'', self.text)
        self.assertIn('"$POD_DIR/restore-wal.sh"', self.text)

    def test_archiving_modes_of_the_temporary_starts(self):
        # Normal start: on (off would let a checkpoint delete WAL still waiting to be archived).
        # Restore: on but blocked (off would never archive segments the new timeline finished).
        # Fresh init: off.
        self.assertEqual(self.text.count('temp_pg_start wait on '), 1)
        self.assertEqual(self.text.count('temp_pg_start nowait blocked '), 1)
        self.assertEqual(self.text.count('temp_pg_start wait off '), 1)
        self.assertIn('blocked) opts+=" -c archive_mode=on -c archive_command=false"', self.text)

    def test_restore_checks_role_and_database(self):
        body = self.text[self.text.index('restore_cluster() {'):]
        self.assertIn('check_role_and_database', body[:body.index('\n}')])
        self.assertIn("SELECT count(*) FROM pg_database WHERE datname = :'db';", self.text)

    def test_stale_pid_files_are_removed(self):
        self.assertIn('rm -f "$PGDATA/postmaster.pid"', self.text)
        self.assertIn('rm -f "$SUPERVISORD_PIDFILE"', self.text)

    def test_password_is_applied_with_psql_variables(self):
        self.assertIn('ALTER ROLE :"usr" PASSWORD :\'pw\';', self.text)
        self.assertIn('-v pw="$POSTGRES_PASSWORD"', self.text)

    def test_hands_over_to_supervisord(self):
        self.assertTrue(self.text.rstrip().endswith('exec supervisord -n -c /usr/src/app/docker/pod/supervisord.conf'))

    def test_restore_path_picks_the_decompressor_by_extension(self):
        # A later encrypted format adds an extension; nothing may assume .gz is the only one (spec §8).
        for text in (self.text, pod_code('restore-wal.sh')):
            self.assertNotIn('gzip -d', text)
            self.assertNotIn('gunzip', text)
            self.assertNotIn('tar -xz', text)
