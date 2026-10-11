"""Ninja schemas shared by the API and the adapters."""
from typing import Any

from ninja import Field, Schema


class Health(Schema):
    status: str
    database: str


class Envelope(Schema):
    """The unified request body (spec §4.1). `input` stays in the tool's own shape."""

    model_config = {'extra': 'forbid'}

    input: dict[str, Any]
    options: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = Field(default=None, max_length=200)


class UnifiedResponse(Schema):
    output: dict[str, Any]
    metadata: dict[str, Any]
