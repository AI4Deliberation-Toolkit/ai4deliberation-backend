from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from gateway.models import CallLog


class Command(BaseCommand):
    help = ('Delete CallLog rows older than CALL_LOG_RETENTION_DAYS (default 180). '
            'To keep older evidence, export first: python manage.py dumpdata gateway.CallLog')

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.CALL_LOG_RETENTION_DAYS)
        deleted, _ = CallLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(f'Deleted {deleted} call log row(s) older than {cutoff:%Y-%m-%d %H:%M} UTC.')
