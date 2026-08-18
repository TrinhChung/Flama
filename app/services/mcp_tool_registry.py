"""Registry for MCP tools exposed by the Flama Connect MCP endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services import mcp_tool_service
from app.validators.mcp import (
    validate_batch_create_notes_arguments,
    validate_create_note_arguments,
    validate_find_notes_arguments,
    validate_get_deck_tree_arguments,
    validate_get_due_card_counts_arguments,
    validate_get_note_type_schema_arguments,
    validate_list_my_decks_arguments,
    validate_list_note_types_arguments,
)


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


# 1. list_my_decks
def _call_list_my_decks(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    del arguments
    return mcp_tool_service._wrap_tool_result({"decks": mcp_tool_service.list_my_decks(user_id=user_id)})


LIST_MY_DECKS_TOOL = McpToolDefinition(
    name=mcp_tool_service.LIST_MY_DECKS_TOOL_NAME,
    title="List My Decks",
    description="Return flashcard decks owned by the currently authenticated user.",
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    required_scope="deck:read",
    handler=_call_list_my_decks,
    arguments_validator=validate_list_my_decks_arguments,
)


# 2. get_deck_tree
def _call_get_deck_tree(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    del arguments
    return mcp_tool_service._wrap_tool_result({"tree": mcp_tool_service.get_deck_tree(user_id=user_id)})


GET_DECK_TREE_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_DECK_TREE_TOOL_NAME,
    title="Get Deck Tree",
    description="Return the hierarchical deck tree structure for the user.",
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    required_scope="deck:read",
    handler=_call_get_deck_tree,
    arguments_validator=validate_get_deck_tree_arguments,
)


# 3. list_note_types
def _call_list_note_types(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    del arguments
    return mcp_tool_service._wrap_tool_result({"note_types": mcp_tool_service.list_note_types(user_id=user_id)})


LIST_NOTE_TYPES_TOOL = McpToolDefinition(
    name=mcp_tool_service.LIST_NOTE_TYPES_TOOL_NAME,
    title="List Note Types",
    description="Return available flashcard note types (models) with field and template counts.",
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    required_scope="note-type:read",
    handler=_call_list_note_types,
    arguments_validator=validate_list_note_types_arguments,
)


# 4. get_note_type_schema
def _call_get_note_type_schema(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_note_type_schema(
            user_id=user_id,
            note_type_id=arguments.get("note_type_id"),
            name=arguments.get("name"),
        )
    )


GET_NOTE_TYPE_SCHEMA_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_NOTE_TYPE_SCHEMA_TOOL_NAME,
    title="Get Note Type Schema",
    description="Return detailed field definitions and templates for a specific note type by id or name.",
    input_schema={
        "type": "object",
        "properties": {
            "note_type_id": {"type": "string", "description": "UUID of the note type"},
            "name": {"type": "string", "description": "Exact name of the note type"},
        },
        "additionalProperties": False,
    },
    required_scope="note-type:read",
    handler=_call_get_note_type_schema,
    arguments_validator=validate_get_note_type_schema_arguments,
)


# 5. find_notes
def _call_find_notes(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        {
            "notes": mcp_tool_service.find_notes(
                user_id=user_id,
                query=arguments["query"],
                deck_id=arguments.get("deck_id"),
                limit=arguments.get("limit", 20),
            )
        }
    )


FIND_NOTES_TOOL = McpToolDefinition(
    name=mcp_tool_service.FIND_NOTES_TOOL_NAME,
    title="Find Notes",
    description="Search flashcard notes belonging to the user by query keyword, field content, or tag.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword or text query"},
            "deck_id": {"type": "integer", "description": "Optional deck ID to filter"},
            "limit": {"type": "integer", "description": "Max results to return (default 20, max 100)"},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    required_scope="note:check",
    handler=_call_find_notes,
    arguments_validator=validate_find_notes_arguments,
)


# 6. create_note
def _call_create_note(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(mcp_tool_service.create_note(user_id=user_id, note_data=arguments))


CREATE_NOTE_TOOL = McpToolDefinition(
    name=mcp_tool_service.CREATE_NOTE_TOOL_NAME,
    title="Create Flashcard Note",
    description="Create a new flashcard note in a deck with field values, tags, and generated cards.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": "integer", "description": "ID of target deck"},
            "deck_name": {"type": "string", "description": "Name or path of deck (created if not exists)"},
            "note_type_id": {"type": "string", "description": "Note type UUID"},
            "note_type_name": {"type": "string", "description": "Name of note type (e.g. 'Basic', 'Vocabulary')"},
            "fields": {"type": "object", "description": "Key-value mapping of field names to values"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "List of tags"},
            "allow_duplicate": {"type": "boolean", "description": "Whether to allow duplicate notes"},
        },
        "required": ["fields"],
        "additionalProperties": False,
    },
    required_scope="note:create",
    handler=_call_create_note,
    arguments_validator=validate_create_note_arguments,
)


# 7. batch_create_notes
def _call_batch_create_notes(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.batch_create_notes(user_id=user_id, notes=arguments["notes"])
    )


BATCH_CREATE_NOTES_TOOL = McpToolDefinition(
    name=mcp_tool_service.BATCH_CREATE_NOTES_TOOL_NAME,
    title="Batch Create Flashcard Notes",
    description="Create multiple flashcard notes in a single batch transaction (up to 50 notes).",
    input_schema={
        "type": "object",
        "properties": {
            "notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "deck_id": {"type": "integer"},
                        "deck_name": {"type": "string"},
                        "note_type_id": {"type": "string"},
                        "note_type_name": {"type": "string"},
                        "fields": {"type": "object"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "allow_duplicate": {"type": "boolean"},
                    },
                    "required": ["fields"],
                },
            }
        },
        "required": ["notes"],
        "additionalProperties": False,
    },
    required_scope="note:create",
    handler=_call_batch_create_notes,
    arguments_validator=validate_batch_create_notes_arguments,
)


# 8. get_due_card_counts
def _call_get_due_card_counts(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_due_card_counts(user_id=user_id, deck_id=arguments.get("deck_id"))
    )


GET_DUE_CARD_COUNTS_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_DUE_CARD_COUNTS_TOOL_NAME,
    title="Get Due Card Counts",
    description="Return due, new, and learning card counts for study scheduling.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": "integer", "description": "Optional deck ID to filter due counts"},
        },
        "additionalProperties": False,
    },
    required_scope="deck:read",
    handler=_call_get_due_card_counts,
    arguments_validator=validate_get_due_card_counts_arguments,
)


_MCP_TOOL_DEFINITIONS = (
    LIST_MY_DECKS_TOOL,
    GET_DECK_TREE_TOOL,
    LIST_NOTE_TYPES_TOOL,
    GET_NOTE_TYPE_SCHEMA_TOOL,
    FIND_NOTES_TOOL,
    CREATE_NOTE_TOOL,
    BATCH_CREATE_NOTES_TOOL,
    GET_DUE_CARD_COUNTS_TOOL,
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

