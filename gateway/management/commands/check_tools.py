import httpx
from cryptography.fernet import InvalidToken
from django.core.management.base import BaseCommand, CommandError

from gateway import http
from gateway.logging_filters import register_sensitive_header
from gateway.models import Tool

HEALTH_TIMEOUT_SECONDS = 10
NOT_FAILURES = ('ok', 'no health_path')


class Command(BaseCommand):
    help = ('GET {base_url}{health_path} for every enabled tool, with its key. '
            'Exits non-zero if any tool is AUTH or DOWN (cron-friendly).')

    def handle(self, *args, **options):
        failures = 0
        with http.build_sync_client(timeout=HEALTH_TIMEOUT_SECONDS) as client:
            for tool in Tool.objects.filter(enabled=True).order_by('tool_id'):
                outcome = self._check(client, tool)
                self.stdout.write(f'{tool.tool_id}: {outcome}')
                if outcome not in NOT_FAILURES:
                    failures += 1
        if failures:
            raise CommandError(f'{failures} tool(s) not ok', returncode=1)

    def _check(self, client, tool):
        if not tool.health_path:
            return 'no health_path'
        headers = {}
        try:
            key = tool.get_tool_key()
        except InvalidToken:
            return 'KEY ERROR (tool key cannot be decrypted)'
        if key:
            register_sensitive_header(tool.key_header)
            headers[tool.key_header] = key
        try:
            response = client.get(tool.base_url + tool.health_path, headers=headers)
        except httpx.HTTPError as exc:
            return f'DOWN ({type(exc).__name__})'
        if response.status_code in (401, 403):
            return 'AUTH (likely key drift)'
        if response.is_success:
            return 'ok'
        return f'DOWN ({response.status_code})'
