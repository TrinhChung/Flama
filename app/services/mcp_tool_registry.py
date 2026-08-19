"""Registry for MCP tools exposed by the Flama Connect MCP endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services import mcp_tool_service
from app.validators.mcp import (
    validate_add_tags_arguments,
    validate_batch_create_notes_arguments,
    validate_batch_delete_notes_arguments,
    validate_batch_move_notes_arguments,
    validate_batch_update_notes_arguments,
    validate_create_deck_arguments,
    validate_create_note_arguments,
    validate_delete_deck_arguments,
    validate_delete_note_arguments,
    validate_find_notes_arguments,
    validate_get_card_arguments,
    validate_get_deck_arguments,
    validate_get_deck_tree_arguments,
    validate_get_deck_stats_arguments,
    validate_get_due_card_counts_arguments,
    validate_get_note_arguments,
    validate_get_note_type_schema_arguments,
    validate_get_study_queue_arguments,
    validate_get_study_stats_arguments,
    validate_list_my_decks_arguments,
    validate_list_note_types_arguments,
    validate_list_notes_arguments,
    validate_move_note_arguments,
    validate_remove_tags_arguments,
    validate_submit_review_arguments,
    validate_update_deck_arguments,
    validate_update_note_arguments,
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


# ---------------------------------------------------------------------------
# 1. Deck Tools
# ---------------------------------------------------------------------------

def _call_list_my_decks(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    del arguments
    return mcp_tool_service._wrap_tool_result({"decks": mcp_tool_service.list_my_decks(user_id=user_id)})


LIST_MY_DECKS_TOOL = McpToolDefinition(
    name=mcp_tool_service.LIST_MY_DECKS_TOOL_NAME,
    title="List My Decks",
    description="Return flashcard decks owned by the currently authenticated user with basic metadata.",
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    required_scope="deck:read",
    annotations={"readOnly": True},
    handler=_call_list_my_decks,
    arguments_validator=validate_list_my_decks_arguments,
)


def _call_get_deck_tree(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    del arguments
    return mcp_tool_service._wrap_tool_result({"tree": mcp_tool_service.get_deck_tree(user_id=user_id)})


GET_DECK_TREE_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_DECK_TREE_TOOL_NAME,
    title="Get Deck Tree",
    description="Return the hierarchical deck tree structure for the user with nested subdecks and card counts.",
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    required_scope="deck:read",
    annotations={"readOnly": True},
    handler=_call_get_deck_tree,
    arguments_validator=validate_get_deck_tree_arguments,
)


def _call_get_deck(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_deck(user_id=user_id, deck_id=arguments["deck_id"])
    )


GET_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_DECK_TOOL_NAME,
    title="Get Deck",
    description="Return detailed metadata for a specific deck by deck_id, including full path, note count, card count, and subdeck count.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": "integer", "description": "ID of the deck to retrieve"},
        },
        "required": ["deck_id"],
        "additionalProperties": False,
    },
    required_scope="deck:read",
    annotations={"readOnly": True},
    handler=_call_get_deck,
    arguments_validator=validate_get_deck_arguments,
)


def _call_create_deck(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.create_deck(
            user_id=user_id,
            name=arguments["name"],
            parent_id=arguments.get("parent_id"),
            description=arguments.get("description"),
        )
    )


CREATE_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.CREATE_DECK_TOOL_NAME,
    title="Create Deck",
    description="Create a new flashcard deck or subdeck. Supports path notation (e.g. 'Japanese::Vocabulary::N1') or explicit parent_id.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name or hierarchical path of the deck"},
            "parent_id": {"type": ["integer", "null"], "description": "Optional parent deck ID"},
            "description": {"type": ["string", "null"], "description": "Optional deck description"},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
    required_scope="deck:write",
    handler=_call_create_deck,
    arguments_validator=validate_create_deck_arguments,
)


def _call_update_deck(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.update_deck(
            user_id=user_id,
            deck_id=arguments["deck_id"],
            name=arguments.get("name"),
            description=arguments.get("description"),
            parent_id=arguments.get("parent_id"),
            update_parent=bool(arguments.get("update_parent")),
        )
    )


UPDATE_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.UPDATE_DECK_TOOL_NAME,
    title="Update Deck",
    description="Update a deck's name, description, or move it under a new parent deck.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": "integer", "description": "ID of the deck to update"},
            "name": {"type": "string", "description": "New deck name"},
            "description": {"type": ["string", "null"], "description": "New deck description"},
            "parent_id": {"type": ["integer", "null"], "description": "New parent deck ID (null to move to top level)"},
        },
        "required": ["deck_id"],
        "additionalProperties": False,
    },
    required_scope="deck:write",
    handler=_call_update_deck,
    arguments_validator=validate_update_deck_arguments,
)


def _call_delete_deck(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.delete_deck(
            user_id=user_id,
            deck_id=arguments["deck_id"],
            confirm=bool(arguments.get("confirm", False)),
        )
    )


DELETE_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.DELETE_DECK_TOOL_NAME,
    title="Delete Deck",
    description=(
        "Delete a deck and all its subdecks, notes, and cards. This is a destructive operation. "
        "AI MUST first call without confirm (or confirm=false) to preview the impact (subdecks, notes, cards, and study progress lost), "
        "ask for user approval, and only call with confirm=true after the user explicitly confirms."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": "integer", "description": "ID of the deck to delete"},
            "confirm": {
                "type": "boolean",
                "description": "Set to true only after the user has explicitly confirmed deletion after reviewing the impact.",
                "default": False,
            },
        },
        "required": ["deck_id"],
        "additionalProperties": False,
    },
    required_scope="deck:write",
    annotations={"destructive": True},
    handler=_call_delete_deck,
    arguments_validator=validate_delete_deck_arguments,
)


# ---------------------------------------------------------------------------
# 2. Note Listing, Reading & Search
# ---------------------------------------------------------------------------


def _call_list_notes(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.list_notes(
            user_id=user_id,
            deck_id=arguments.get("deck_id"),
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0),
            sort_by=arguments.get("sort_by", "created_at"),
            sort_dir=arguments.get("sort_dir", "desc"),
        )
    )


LIST_NOTES_TOOL = McpToolDefinition(
    name=mcp_tool_service.LIST_NOTES_TOOL_NAME,
    title="List Notes",
    description="List flashcard notes in a deck or across all user's decks with pagination without requiring any search query. Returns dynamic fields for each note type.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": ["integer", "null"], "description": "Optional deck ID to list notes from"},
            "limit": {"type": "integer", "description": "Number of notes to return (default 20, max 100)"},
            "offset": {"type": "integer", "description": "Number of notes to skip for pagination (default 0)"},
            "sort_by": {"type": "string", "enum": ["created_at", "updated_at", "id"], "description": "Field to sort by (default 'created_at')"},
            "sort_dir": {"type": "string", "enum": ["asc", "desc"], "description": "Sort direction (default 'desc')"},
        },
        "additionalProperties": False,
    },
    required_scope="note:read",
    annotations={"readOnly": True},
    handler=_call_list_notes,
    arguments_validator=validate_list_notes_arguments,
)


def _call_get_note(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_note(user_id=user_id, note_id=arguments["note_id"])
    )


GET_NOTE_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_NOTE_TOOL_NAME,
    title="Get Note",
    description="Get complete details of a single flashcard note by note_id, including dynamic field values, tags, deck information, and associated cards with their learning states.",
    input_schema={
        "type": "object",
        "properties": {
            "note_id": {"type": "string", "description": "UUID or ID of the note"},
        },
        "required": ["note_id"],
        "additionalProperties": False,
    },
    required_scope="note:read",
    annotations={"readOnly": True},
    handler=_call_get_note,
    arguments_validator=validate_get_note_arguments,
)


def _call_find_notes(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.find_notes(
            user_id=user_id,
            query=arguments.get("query", ""),
            deck_id=arguments.get("deck_id"),
            tag=arguments.get("tag"),
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0),
        )
    )


FIND_NOTES_TOOL = McpToolDefinition(
    name=mcp_tool_service.FIND_NOTES_TOOL_NAME,
    title="Find Notes",
    description="Search flashcard notes belonging to the user by text keyword across field values or tags, with optional deck and tag filtering and pagination.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search keyword or text query"},
            "deck_id": {"type": ["integer", "null"], "description": "Optional deck ID to filter"},
            "tag": {"type": ["string", "null"], "description": "Optional tag to filter"},
            "limit": {"type": "integer", "description": "Max results to return (default 20, max 100)"},
            "offset": {"type": "integer", "description": "Pagination offset (default 0)"},
        },
        "additionalProperties": False,
    },
    required_scope="note:read",
    annotations={"readOnly": True},
    handler=_call_find_notes,
    arguments_validator=validate_find_notes_arguments,
)


# ---------------------------------------------------------------------------
# 3. Note Mutation & Organization
# ---------------------------------------------------------------------------


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


def _call_update_note(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.update_note(
            user_id=user_id,
            note_id=arguments["note_id"],
            fields=arguments.get("fields"),
            tags=arguments.get("tags"),
            deck_id=arguments.get("deck_id"),
        )
    )


UPDATE_NOTE_TOOL = McpToolDefinition(
    name=mcp_tool_service.UPDATE_NOTE_TOOL_NAME,
    title="Update Flashcard Note",
    description="Update field values, tags, or deck for an existing note. Partial field updates are supported: unmentioned fields are preserved.",
    input_schema={
        "type": "object",
        "properties": {
            "note_id": {"type": "string", "description": "UUID or ID of the note to update"},
            "fields": {"type": "object", "description": "Key-value mapping of field names to new values (partial update)"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "New list of tags (replaces tags)"},
            "deck_id": {"type": "integer", "description": "New deck ID to move note into"},
        },
        "required": ["note_id"],
        "additionalProperties": False,
    },
    required_scope="note:update",
    handler=_call_update_note,
    arguments_validator=validate_update_note_arguments,
)


def _call_delete_note(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.delete_note(
            user_id=user_id,
            note_id=arguments["note_id"],
            confirm=bool(arguments.get("confirm", False)),
        )
    )


DELETE_NOTE_TOOL = McpToolDefinition(
    name=mcp_tool_service.DELETE_NOTE_TOOL_NAME,
    title="Delete Flashcard Note",
    description=(
        "Permanently delete a single flashcard note and all its generated cards. This is a destructive operation. "
        "AI MUST first call without confirm (or confirm=false) to preview the note content and cards to be deleted, "
        "ask for user approval, and only call with confirm=true after the user explicitly approves."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "note_id": {"type": "string", "description": "UUID or ID of the note to delete"},
            "confirm": {
                "type": "boolean",
                "description": "Set to true only after the user has explicitly approved deleting this note.",
                "default": False,
            },
        },
        "required": ["note_id"],
        "additionalProperties": False,
    },
    required_scope="note:delete",
    annotations={"destructive": True},
    handler=_call_delete_note,
    arguments_validator=validate_delete_note_arguments,
)


def _call_move_note(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.move_note(user_id=user_id, note_id=arguments["note_id"], deck_id=arguments["deck_id"])
    )


MOVE_NOTE_TOOL = McpToolDefinition(
    name=mcp_tool_service.MOVE_NOTE_TOOL_NAME,
    title="Move Flashcard Note",
    description="Move a single flashcard note to a target deck.",
    input_schema={
        "type": "object",
        "properties": {
            "note_id": {"type": "string", "description": "UUID or ID of the note to move"},
            "deck_id": {"type": "integer", "description": "Target deck ID"},
        },
        "required": ["note_id", "deck_id"],
        "additionalProperties": False,
    },
    required_scope="note:update",
    handler=_call_move_note,
    arguments_validator=validate_move_note_arguments,
)


def _call_add_tags(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.add_tags(user_id=user_id, note_ids=arguments["note_ids"], tags=arguments["tags"])
    )


ADD_TAGS_TOOL = McpToolDefinition(
    name=mcp_tool_service.ADD_TAGS_TOOL_NAME,
    title="Add Tags to Notes",
    description="Append one or more tags to specified notes without overwriting existing tags.",
    input_schema={
        "type": "object",
        "properties": {
            "note_ids": {"type": "array", "items": {"type": "string"}, "description": "List of note IDs to tag"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "List of tags to append"},
        },
        "required": ["note_ids", "tags"],
        "additionalProperties": False,
    },
    required_scope="note:update",
    handler=_call_add_tags,
    arguments_validator=validate_add_tags_arguments,
)


def _call_remove_tags(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.remove_tags(user_id=user_id, note_ids=arguments["note_ids"], tags=arguments["tags"])
    )


REMOVE_TAGS_TOOL = McpToolDefinition(
    name=mcp_tool_service.REMOVE_TAGS_TOOL_NAME,
    title="Remove Tags from Notes",
    description="Remove one or more tags from specified notes.",
    input_schema={
        "type": "object",
        "properties": {
            "note_ids": {"type": "array", "items": {"type": "string"}, "description": "List of note IDs"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "List of tags to remove"},
        },
        "required": ["note_ids", "tags"],
        "additionalProperties": False,
    },
    required_scope="note:update",
    handler=_call_remove_tags,
    arguments_validator=validate_remove_tags_arguments,
)


# ---------------------------------------------------------------------------
# 4. Batch Operations
# ---------------------------------------------------------------------------


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


def _call_batch_update_notes(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.batch_update_notes(user_id=user_id, notes=arguments["notes"])
    )


BATCH_UPDATE_NOTES_TOOL = McpToolDefinition(
    name=mcp_tool_service.BATCH_UPDATE_NOTES_TOOL_NAME,
    title="Batch Update Flashcard Notes",
    description="Update multiple flashcard notes in a single batch (up to 50 notes). Supports partial field updates.",
    input_schema={
        "type": "object",
        "properties": {
            "notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "note_id": {"type": "string"},
                        "fields": {"type": "object"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "deck_id": {"type": "integer"},
                    },
                    "required": ["note_id"],
                },
            }
        },
        "required": ["notes"],
        "additionalProperties": False,
    },
    required_scope="note:update",
    handler=_call_batch_update_notes,
    arguments_validator=validate_batch_update_notes_arguments,
)


def _call_batch_delete_notes(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.batch_delete_notes(
            user_id=user_id,
            note_ids=arguments["note_ids"],
            confirm=bool(arguments.get("confirm", False)),
        )
    )


BATCH_DELETE_NOTES_TOOL = McpToolDefinition(
    name=mcp_tool_service.BATCH_DELETE_NOTES_TOOL_NAME,
    title="Batch Delete Flashcard Notes",
    description=(
        "Permanently delete multiple flashcard notes and their cards in a single batch (up to 50 notes). This is a destructive operation. "
        "AI MUST first call without confirm (or confirm=false) to preview the total notes/cards to be deleted, "
        "ask for user approval, and only call with confirm=true after the user explicitly approves."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "note_ids": {"type": "array", "items": {"type": "string"}, "description": "List of note IDs to delete"},
            "confirm": {
                "type": "boolean",
                "description": "Set to true only after the user has explicitly approved deleting these notes.",
                "default": False,
            },
        },
        "required": ["note_ids"],
        "additionalProperties": False,
    },
    required_scope="note:delete",
    annotations={"destructive": True},
    handler=_call_batch_delete_notes,
    arguments_validator=validate_batch_delete_notes_arguments,
)


def _call_batch_move_notes(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.batch_move_notes(user_id=user_id, note_ids=arguments["note_ids"], deck_id=arguments["deck_id"])
    )


BATCH_MOVE_NOTES_TOOL = McpToolDefinition(
    name=mcp_tool_service.BATCH_MOVE_NOTES_TOOL_NAME,
    title="Batch Move Flashcard Notes",
    description="Move multiple flashcard notes to a target deck in a single batch (up to 50 notes).",
    input_schema={
        "type": "object",
        "properties": {
            "note_ids": {"type": "array", "items": {"type": "string"}, "description": "List of note IDs to move"},
            "deck_id": {"type": "integer", "description": "Target deck ID"},
        },
        "required": ["note_ids", "deck_id"],
        "additionalProperties": False,
    },
    required_scope="note:update",
    handler=_call_batch_move_notes,
    arguments_validator=validate_batch_move_notes_arguments,
)


# ---------------------------------------------------------------------------
# 5. Study & Card Review Operations
# ---------------------------------------------------------------------------


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
    required_scope="study:read",
    annotations={"readOnly": True},
    handler=_call_get_due_card_counts,
    arguments_validator=validate_get_due_card_counts_arguments,
)


def _call_get_study_queue(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_study_queue(
            user_id=user_id,
            deck_id=arguments.get("deck_id"),
            limit=arguments.get("limit", 10),
        )
    )


GET_STUDY_QUEUE_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_STUDY_QUEUE_TOOL_NAME,
    title="Get Study Queue",
    description="Retrieve actionable cards due for study according to spaced repetition schedule, with rendered front/back HTML, field values, queue status, and answer interval previews.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": ["integer", "null"], "description": "Optional deck ID to study from"},
            "limit": {"type": "integer", "description": "Number of cards to fetch (default 10, max 50)"},
        },
        "additionalProperties": False,
    },
    required_scope="study:read",
    annotations={"readOnly": True},
    handler=_call_get_study_queue,
    arguments_validator=validate_get_study_queue_arguments,
)


def _call_get_card(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_card(user_id=user_id, card_id=arguments["card_id"])
    )


GET_CARD_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_CARD_TOOL_NAME,
    title="Get Card Detail",
    description="Get detailed information about a single flashcard, including rendered front/back HTML, template info, note fields, and spaced repetition history (interval, ease, reps, lapses, due date).",
    input_schema={
        "type": "object",
        "properties": {
            "card_id": {"type": "string", "description": "UUID or ID of the card"},
        },
        "required": ["card_id"],
        "additionalProperties": False,
    },
    required_scope="study:read",
    annotations={"readOnly": True},
    handler=_call_get_card,
    arguments_validator=validate_get_card_arguments,
)


def _call_submit_review(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.submit_review(
            user_id=user_id,
            card_id=arguments["card_id"],
            rating=arguments["rating"],
            duration_ms=arguments.get("duration_ms"),
        )
    )


SUBMIT_REVIEW_TOOL = McpToolDefinition(
    name=mcp_tool_service.SUBMIT_REVIEW_TOOL_NAME,
    title="Submit Card Review Answer",
    description="Submit a review answer rating ('again', 'hard', 'good', 'easy') for a flashcard, recalculating its spaced-repetition schedule using Flama's canonical Anki/FSRS scheduler.",
    input_schema={
        "type": "object",
        "properties": {
            "card_id": {"type": "string", "description": "UUID or ID of the card reviewed"},
            "rating": {"type": "string", "enum": ["again", "hard", "good", "easy"], "description": "Review rating button selected"},
            "duration_ms": {"type": ["integer", "null"], "description": "Optional response time in milliseconds"},
        },
        "required": ["card_id", "rating"],
        "additionalProperties": False,
    },
    required_scope="study:write",
    handler=_call_submit_review,
    arguments_validator=validate_submit_review_arguments,
)


# ---------------------------------------------------------------------------
# 6. Statistics Operations
# ---------------------------------------------------------------------------


def _call_get_deck_stats(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_deck_stats(user_id=user_id, deck_id=arguments["deck_id"])
    )


GET_DECK_STATS_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_DECK_STATS_TOOL_NAME,
    title="Get Deck Statistics",
    description="Return comprehensive learning statistics for a deck: total notes, total cards, new/learning/review/mature card breakdown, and due counts.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": "integer", "description": "ID of the deck"},
        },
        "required": ["deck_id"],
        "additionalProperties": False,
    },
    required_scope="stats:read",
    annotations={"readOnly": True},
    handler=_call_get_deck_stats,
    arguments_validator=validate_get_deck_stats_arguments,
)


def _call_get_study_stats(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_study_stats(user_id=user_id, year=arguments.get("year"))
    )


GET_STUDY_STATS_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_STUDY_STATS_TOOL_NAME,
    title="Get Study Statistics",
    description="Return user's overall study overview: current streak days, longest streak days, cards reviewed today, study time today, and totals.",
    input_schema={
        "type": "object",
        "properties": {
            "year": {"type": ["integer", "null"], "description": "Optional calendar year for stats overview (defaults to current year)"},
        },
        "additionalProperties": False,
    },
    required_scope="stats:read",
    annotations={"readOnly": True},
    handler=_call_get_study_stats,
    arguments_validator=validate_get_study_stats_arguments,
)


# ---------------------------------------------------------------------------
# 7. Note Types
# ---------------------------------------------------------------------------


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
    annotations={"readOnly": True},
    handler=_call_list_note_types,
    arguments_validator=validate_list_note_types_arguments,
)


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
    annotations={"readOnly": True},
    handler=_call_get_note_type_schema,
    arguments_validator=validate_get_note_type_schema_arguments,
)


# ---------------------------------------------------------------------------
# All Registered MCP Tools
# ---------------------------------------------------------------------------

_MCP_TOOL_DEFINITIONS = (
    # Decks
    LIST_MY_DECKS_TOOL,
    GET_DECK_TREE_TOOL,
    GET_DECK_TOOL,
    CREATE_DECK_TOOL,
    UPDATE_DECK_TOOL,
    DELETE_DECK_TOOL,
    # Notes Listing & Search
    LIST_NOTES_TOOL,
    GET_NOTE_TOOL,
    FIND_NOTES_TOOL,
    # Note Mutations
    CREATE_NOTE_TOOL,
    UPDATE_NOTE_TOOL,
    DELETE_NOTE_TOOL,
    MOVE_NOTE_TOOL,
    ADD_TAGS_TOOL,
    REMOVE_TAGS_TOOL,
    # Batch
    BATCH_CREATE_NOTES_TOOL,
    BATCH_UPDATE_NOTES_TOOL,
    BATCH_DELETE_NOTES_TOOL,
    BATCH_MOVE_NOTES_TOOL,
    # Study & Cards
    GET_DUE_CARD_COUNTS_TOOL,
    GET_STUDY_QUEUE_TOOL,
    GET_CARD_TOOL,
    SUBMIT_REVIEW_TOOL,
    # Stats
    GET_DECK_STATS_TOOL,
    GET_STUDY_STATS_TOOL,
    # Note Types
    LIST_NOTE_TYPES_TOOL,
    GET_NOTE_TYPE_SCHEMA_TOOL,
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
