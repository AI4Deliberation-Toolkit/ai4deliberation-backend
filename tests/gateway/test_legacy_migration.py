import importlib

from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase

MIGRATION = 'gateway.migrations.0001_drop_legacy_topic_tables'


def run_drop_legacy_topic_tables():
    """Run the migration's function against the historical app registry, as `migrate` would."""
    module = importlib.import_module(MIGRATION)
    state = MigrationLoader(connection).project_state(('gateway', '0001_drop_legacy_topic_tables'))
    module.drop_legacy_topic_tables(state.apps, connection.schema_editor())


def legacy_tables():
    return sorted(t for t in connection.introspection.table_names() if t.startswith('topic_extraction_'))


def legacy_migration_rows():
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app IN ('topic_extraction', 'ai_tools')")
        return cursor.fetchone()[0]


class DropLegacyTopicTablesTests(TestCase):
    def test_noop_on_a_fresh_database(self):
        content_types = ContentType.objects.count()
        run_drop_legacy_topic_tables()
        self.assertEqual(legacy_tables(), [])
        self.assertEqual(ContentType.objects.count(), content_types)

    def test_drops_tables_and_bookkeeping_rows(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE topic_extraction_topic (id integer PRIMARY KEY)')
            cursor.execute('CREATE TABLE topic_extraction_articletopic (id integer PRIMARY KEY)')
            cursor.execute(
                'CREATE TABLE topic_extraction_articleembedding '
                '(id integer PRIMARY KEY, topic_id integer REFERENCES topic_extraction_topic(id))'
            )
            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) "
                "VALUES ('topic_extraction', '0001_initial', CURRENT_TIMESTAMP)"
            )
        stale = ContentType.objects.create(app_label='topic_extraction', model='topic')
        permission = Permission.objects.create(content_type=stale, codename='view_topic', name='Can view topic')
        user = get_user_model().objects.create_superuser('admin', 'admin@example.org', 'pw')
        entry = LogEntry.objects.create(
            user=user, content_type=stale, object_id='1', object_repr='topic', action_flag=ADDITION,
        )

        run_drop_legacy_topic_tables()

        self.assertEqual(legacy_tables(), [])
        self.assertEqual(legacy_migration_rows(), 0)
        self.assertFalse(ContentType.objects.filter(app_label='topic_extraction').exists())
        self.assertFalse(Permission.objects.filter(pk=permission.pk).exists())
        entry.refresh_from_db()
        self.assertIsNone(entry.content_type_id)
        # TestCase checks deferred FK constraints at teardown: a dangling LogEntry FK would fail here.
