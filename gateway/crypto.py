"""Tool keys at rest: MultiFernet over GATEWAY_ENCRYPTION_KEYS; the first key encrypts (spec §5).

Protects database dumps and backups, not a compromised host (the keys live in its environment).
"""
from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings


def _fernet() -> MultiFernet:
    return MultiFernet([Fernet(key) for key in settings.GATEWAY_ENCRYPTION_KEYS])


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode('ascii')


def decrypt(token: str) -> str:
    """Raises cryptography.fernet.InvalidToken if no configured key can read it."""
    return _fernet().decrypt(token.encode('ascii')).decode()
