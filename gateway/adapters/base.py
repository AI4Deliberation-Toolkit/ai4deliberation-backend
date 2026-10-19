"""The adapter contract (spec §6.1). Adapters never do I/O."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Outbound:
    method: str  # "POST" or "GET"
    path: str  # appended to tool.base_url; starts with "/"
    params: dict[str, str] = field(default_factory=dict)  # query string
    json: dict | None = None  # None: no body (always for GET)


@dataclass
class Result:
    output: dict
    metadata: dict = field(default_factory=dict)  # returned to the caller; only allow-listed keys reach the log


class ToolError(Exception):
    """The tool answered, but with an error status (`source: tool`).

    `body` may carry content: it goes back to the caller and is never logged, so str() leaves it out.
    """

    def __init__(self, status: int, body: Any = None, message: str = 'The tool returned an error.'):
        super().__init__(message)
        self.status = status
        self.body = body
        self.message = message
        self.tool_id = None

    def __str__(self):
        return f'{self.message} (tool status {self.status})'


class Adapter:
    operations: set[str] | None = None  # None means any operation
    # The operations called with GET. None: each registry entry declares its own (Tool.read_operations).
    read_operations: frozenset[str] | None = frozenset()

    def build_request(self, tool, operation: str, envelope) -> Outbound:
        """May raise GatewayError(INVALID_REQUEST)."""
        raise NotImplementedError

    def build_read_request(self, tool, operation: str, params: dict[str, str]) -> Outbound:
        """A read call. `params` is the caller's query string, one value per name.

        May raise GatewayError(INVALID_REQUEST).
        """
        raise NotImplementedError

    def parse_response(self, tool, operation: str, status: int, body: Any) -> Result:
        """`body` is the decoded JSON, or None if the response wasn't JSON.

        May raise ToolError or GatewayError(TOOL_BAD_RESPONSE).
        """
        raise NotImplementedError
