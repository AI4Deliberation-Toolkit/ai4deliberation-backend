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


class ErrorDetail(Schema):
    source: str  # "gateway" | "tool"
    code: str
    message: str
    request_id: str | None
    tool_id: str | None = None
    tool_status: int | None = None  # source "tool" only
    tool_body: Any = None  # source "tool" only: the tool's JSON error body, or its text (≤ 4 KB)


class ErrorResponse(Schema):
    error: ErrorDetail


class CatalogueEntry(Schema):
    tool_id: str
    name: str
    description: str
    docs_url: str
    operations: list[str]
    depth: str  # native | adapted
    reachability: str  # open | direct | gateway_only
