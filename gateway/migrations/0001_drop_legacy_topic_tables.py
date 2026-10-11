"""Drop the tables the removed topic_extraction app left behind (spec §3.5).

Safe on a fresh database. Irreversible by design (no backup, decided 2026-10-10).
"""
from django.db import migrations

# Children before parents, so SQLite needs no CASCADE.
LEGACY_TABLES = (
    'topic_extraction_articleembedding',
    'topic_extraction_articletopic',
    'topic_extraction_topic',
)
# ai_tools never had models; it's listed only for completeness.
LEGACY_APPS = ('topic_extraction', 'ai_tools')


def drop_legacy_topic_tables(apps, schema_editor):
    connection = schema_editor.connection
    cascade = ' CASCADE' if connection.vendor == 'postgresql' else ''
    with connection.cursor() as cursor:
        for table in LEGACY_TABLES:
            cursor.execute(f'DROP TABLE IF EXISTS {schema_editor.quote_name(table)}{cascade}')
        cursor.execute('DELETE FROM django_migrations WHERE app IN (%s, %s)', LEGACY_APPS)
    # The historical model, never the live one: cascades come from the historical registry,
    # which is why auth (Permission) and admin (LogEntry.content_type → NULL) are dependencies.
    ContentType = apps.get_model('contenttypes', 'ContentType')
    ContentType.objects.using(connection.alias).filter(app_label__in=LEGACY_APPS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('admin', '0003_logentry_add_action_flag_choices'),
    ]

    operations = [
        migrations.RunPython(drop_legacy_topic_tables, migrations.RunPython.noop),
    ]
