import asyncio
import io
import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone

from gateway.calllog import CallRecord, logged_metadata, write_call_log
from gateway.models import CallLog, Platform


def make_record(platform, **fields):
    return CallRecord(request_id=str(uuid.uuid4()), platform_id=platform.pk, key_prefix='ABCDEFGH',
                      tool_id='stub', operation='echo', request_bytes=12, **fields)


class LoggedMetadataTests(TestCase):
    def test_only_allow_listed_strings_are_kept(self):
        metadata = {'tool_version': 'v1', 'model_id': 'm', 'taxonomy_version': 't', 'note': 'dropped',
                    'request_id': 'dropped'}
        self.assertEqual(logged_metadata(metadata), {'tool_version': 'v1', 'model_id': 'm', 'taxonomy_version': 't'})

    def test_non_strings_are_dropped_and_long_values_truncated(self):
        self.assertEqual(logged_metadata({'tool_version': {'nested': 'x'}, 'model_id': 'm' * 150}),
                         {'model_id': 'm' * 100})


class WriteCallLogTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name='WP site', slug='wp-site')

    async def test_writes_a_row(self):
        record = make_record(self.platform, status=200, error_code=None, error_source=None, duration_ms=12)
        await write_call_log(record)
        row = await CallLog.objects.aget()
        self.assertEqual((str(row.request_id), row.status, row.error_code), (record.request_id, 200, None))

    async def test_defaults_record_an_internal_error(self):
        await write_call_log(make_record(self.platform))
        row = await CallLog.objects.aget()
        self.assertEqual((row.status, row.error_code, row.error_source), (500, 'INTERNAL', 'gateway'))

    async def test_write_failure_logs_a_warning_and_never_raises(self):
        with mock.patch.object(CallLog.objects, 'acreate', side_effect=DatabaseError('db down')):
            with self.assertLogs('gateway.calllog', 'WARNING') as logs:
                await write_call_log(make_record(self.platform))
        self.assertIn('DatabaseError', logs.output[0])

    async def test_failure_after_the_caller_was_cancelled_is_still_our_warning(self):
        # The shielded insert outlives its cancelled caller; its failure must not become asyncio's
        # "Task exception was never retrieved".
        started, release = asyncio.Event(), asyncio.Event()

        async def failing_insert(**fields):
            started.set()
            await release.wait()
            raise DatabaseError('db down')

        record = make_record(self.platform)
        with mock.patch.object(CallLog.objects, 'acreate', failing_insert):
            with self.assertLogs('gateway.calllog', 'WARNING') as logs:
                caller = asyncio.ensure_future(write_call_log(record))
                await started.wait()
                caller.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await caller
                release.set()
                for _ in range(100):  # let the shielded insert run to its end
                    if logs.records:
                        break
                    await asyncio.sleep(0)
        self.assertEqual(logs.output, [
            f'WARNING:gateway.calllog:Call log row not written (request_id={record.request_id}): DatabaseError'])


class PurgeCallLogsTests(TestCase):
    def setUp(self):
        self.platform = Platform.objects.create(name='WP site', slug='wp-site')

    def row(self, days_old):
        row = CallLog.objects.create(request_id=uuid.uuid4(), platform=self.platform, key_prefix='ABCDEFGH',
                                     tool_id='stub', operation='echo', status=200, duration_ms=5, request_bytes=10)
        CallLog.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(days=days_old))
        return row

    def test_deletes_only_rows_past_retention(self):
        keep, drop = self.row(179), self.row(181)
        out = io.StringIO()
        call_command('purge_call_logs', stdout=out)
        self.assertEqual(list(CallLog.objects.values_list('pk', flat=True)), [keep.pk])
        self.assertIn('Deleted 1', out.getvalue())

    @override_settings(CALL_LOG_RETENTION_DAYS=30)
    def test_retention_comes_from_settings(self):
        self.row(29)
        self.row(31)
        call_command('purge_call_logs', stdout=io.StringIO())
        self.assertEqual(CallLog.objects.count(), 1)


class CallLogAdminTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_superuser('admin', 'admin@example.org', 'pw'))
        self.platform = Platform.objects.create(name='WP site', slug='wp-site')
        self.row = CallLog.objects.create(request_id=uuid.uuid4(), platform=self.platform, key_prefix='ABCDEFGH',
                                          tool_id='stub', operation='echo', status=200, duration_ms=5,
                                          request_bytes=10)

    def test_list_and_view_only(self):
        self.assertContains(self.client.get('/admin/gateway/calllog/'), str(self.row.request_id))
        self.assertEqual(self.client.get('/admin/gateway/calllog/add/').status_code, 403)
        change_url = f'/admin/gateway/calllog/{self.row.pk}/change/'
        self.assertEqual(self.client.get(change_url).status_code, 200)  # view-only page
        self.assertEqual(self.client.post(change_url, {'status': 500}).status_code, 403)
        self.assertEqual(self.client.get(f'/admin/gateway/calllog/{self.row.pk}/delete/').status_code, 403)
