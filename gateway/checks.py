from django.core.checks import Error, register

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
