from django.core.checks import Error, Tags, Warning, register
from django.db import DatabaseError

from gateway import crypto


@register()
def encryption_keys_check(app_configs, **kwargs):
    """Fail `check` and `migrate` (and so the container entrypoint) on unusable encryption keys."""
    try:
        crypto._fernet()
    except (ValueError, TypeError):
        return [Error(
            'GATEWAY_ENCRYPTION_KEYS must hold one or more valid Fernet keys, comma-separated.',
            hint='Generate one with: python -c "from cryptography.fernet import Fernet; '
                 'print(Fernet.generate_key().decode())"',
            id='gateway.E001',
        )]
    return []


@register(Tags.database)
def unknown_adapter_check(app_configs, databases=None, **kwargs):
    """Warn at `migrate` (so at every container boot) about registry rows whose adapter is no longer in the code.

    Such a row can't be saved, but one saved before its adapter was removed stays: its calls fail.
    """
    if not databases:
        return []
    from gateway.adapters import ADAPTERS
    from gateway.models import Tool

    try:
        stale = list(Tool.objects.exclude(adapter__in=list(ADAPTERS)).values_list('tool_id', 'adapter'))
    except DatabaseError:  # before the first migrate: no table yet
        return []
    return [Warning(
        f'Tool {tool_id!r} uses adapter {adapter!r}, which no longer exists; calls to it fail.',
        hint='Disable or delete the tool in the admin, or restore the adapter.',
        id='gateway.W001',
    ) for tool_id, adapter in stale]
