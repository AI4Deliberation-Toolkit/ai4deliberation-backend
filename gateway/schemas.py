"""Ninja schemas shared by the API and the adapters."""
from ninja import Schema


class Health(Schema):
    status: str
    database: str
