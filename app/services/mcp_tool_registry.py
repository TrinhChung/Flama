"""Registry for MCP tools exposed by the Flama MCP endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services import mcp_tool_service
from app.validators.mcp import validate_list_my_decks_arguments


McpToolHandler = Callable[..., dict[str, Any]]
McpToolArgumentsValidator = Callable[[Any], dict[str, Any]]


@dataclass(frozen=True)
class McpToolDefinition:
    """Metadata and execution hooks for a single MCP tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: McpToolHandler
    arguments_validator: McpToolArgumentsValidator
    required_scope: str | None = None
    title: str | None = None
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None

    def to_mcp_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
        if self.title:
            payload["title"] = self.title
        if self.output_schema:
            payload["outputSchema"] = self.output_schema
        if self.annotations:
            payload["annotations"] = self.annotations
        return payload

    def execute(self, *, user_id: int, arguments: Any) -> dict[str, Any]:
        normalized_arguments = self.arguments_validator(arguments)
        return self.handler(user_id=user_id, arguments=normalized_arguments)


def _call_list_my_decks(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    del arguments
    return mcp_tool_service.build_list_my_decks_tool_result(user_id=user_id)


LIST_MY_DECKS_TOOL = McpToolDefinition(
    name=mcp_tool_service.LIST_MY_DECKS_TOOL_NAME,
    title="List My Decks",
    description=(
        "Return decks owned by the currently authenticated user. "
        "The server resolves the user from the existing auth session or Bearer token and accepts no user_id input."
    ),
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    output_schema={
        "type": "object",
        "properties": {
            "decks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "deck_id": {"type": "integer"},
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "created_at": {"type": "string", "format": "date-time"},
                    },
                    "required": ["deck_id", "name"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["decks"],
        "additionalProperties": False,
    },
    annotations={
        "title": "List My Decks",
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    },
    required_scope="deck:read",
    handler=_call_list_my_decks,
    arguments_validator=validate_list_my_decks_arguments,
)

_MCP_TOOL_DEFINITIONS = (
    LIST_MY_DECKS_TOOL,
)
_MCP_TOOLS_BY_NAME = {tool.name: tool for tool in _MCP_TOOL_DEFINITIONS}


def list_mcp_tools() -> list[dict[str, Any]]:
    """Return MCP-compatible metadata for every exposed tool."""
    return [tool.to_mcp_payload() for tool in _MCP_TOOL_DEFINITIONS]


def get_mcp_tool(tool_name: str) -> McpToolDefinition | None:
    """Resolve a tool definition by name."""
    return _MCP_TOOLS_BY_NAME.get(str(tool_name or "").strip())


def call_mcp_tool(*, tool_name: str, user_id: int, arguments: Any) -> dict[str, Any]:
    """Execute a registered tool for the current user."""
    tool_definition = get_mcp_tool(tool_name)
    if tool_definition is None:
        raise KeyError(str(tool_name or "").strip())
    return tool_definition.execute(user_id=user_id, arguments=arguments)
