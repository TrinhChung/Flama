"""Registry for MCP tools exposed by the Flama Connect MCP endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.services import mcp_tool_service
from app.services.mcp import public_search_tools
from app.validators import RequestValidationError
from models import db
from models.field_types import FIELD_TYPES
from app.validators.mcp import (
    validate_add_tags_arguments,
    validate_batch_create_notes_arguments,
    validate_batch_delete_notes_arguments,
    validate_batch_ensure_decks_arguments,
    validate_batch_move_notes_arguments,
    validate_batch_update_notes_arguments,
    validate_create_deck_arguments,
    validate_create_note_arguments,
    validate_create_note_type_arguments,
    validate_delete_deck_arguments,
    validate_delete_note_arguments,
    validate_delete_note_type_arguments,
    validate_find_notes_arguments,
    validate_get_image_arguments,
    validate_import_image_arguments,
    validate_crawl_note_media_arguments,
    validate_extract_page_images_arguments,
    validate_search_images_arguments,
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
    validate_preview_note_sync_arguments,
    validate_preview_note_type_update_arguments,
    validate_remove_tags_arguments,
    validate_resolve_deck_arguments,
    validate_submit_review_arguments,
    validate_sync_notes_arguments,
    validate_get_deck_publish_options_arguments,
    validate_get_shared_deck_arguments,
    validate_list_deck_releases_arguments,
    validate_list_installed_decks_arguments,
    validate_list_shared_deck_notes_arguments,
    validate_list_shared_decks_arguments,
    validate_preview_deck_release_arguments,
    validate_publish_deck_release_arguments,
    validate_share_deck_arguments,
    validate_update_shared_deck_arguments,
    validate_update_deck_arguments,
    validate_update_note_arguments,
    validate_update_note_type_arguments,
    validate_get_taxonomy_schema_arguments,
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
    is_public: bool = False
    meta: dict[str, Any] | None = None

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
        if self.meta:
            # Never advertise a missing bundled UI; data/text preview still works.
            from app.services.mcp_resource_registry import TEMPLATE_PREVIEW_URI, template_preview_ui_available
            if self.meta.get("ui", {}).get("resourceUri") != TEMPLATE_PREVIEW_URI or template_preview_ui_available():
                payload["_meta"] = self.meta
        return payload

    def execute(self, *, user_id: int | None = None, arguments: Any) -> dict[str, Any]:
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


def _call_resolve_deck(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.resolve_deck(user_id=user_id, path=arguments["path"])
    )


RESOLVE_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.RESOLVE_DECK_TOOL_NAME,
    title="Resolve Deck by Path",
    description="Find a flashcard deck by its hierarchical path (e.g. 'English::Luyện Đề::Bài 8') without creating it if missing.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Hierarchical path of the deck (separated by '::' or '/')"},
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    required_scope="deck:read",
    annotations={"readOnly": True},
    handler=_call_resolve_deck,
    arguments_validator=validate_resolve_deck_arguments,
)


def _call_batch_ensure_decks(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.batch_ensure_decks(user_id=user_id, paths=arguments["paths"])
    )


BATCH_ENSURE_DECKS_TOOL = McpToolDefinition(
    name=mcp_tool_service.BATCH_ENSURE_DECKS_TOOL_NAME,
    title="Batch Ensure Decks",
    description="Ensure multiple hierarchical deck paths exist in a single call, idempotently creating any missing parent or child decks.",
    input_schema={
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of hierarchical deck paths (e.g. ['English::Luyện Đề::Bài 8', 'English::Luyện Đề::Bài 9'])",
            },
        },
        "required": ["paths"],
        "additionalProperties": False,
    },
    required_scope="deck:write",
    handler=_call_batch_ensure_decks,
    arguments_validator=validate_batch_ensure_decks_arguments,
)


def _call_create_deck(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.create_deck(
            user_id=user_id,
            name=arguments["name"],
            parent_id=arguments.get("parent_id"),
            description=arguments.get("description"),
            default_note_type_id=arguments.get("default_note_type_id"),
        )
    )


CREATE_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.CREATE_DECK_TOOL_NAME,
    title="Create Deck",
    description="Create a new flashcard deck or subdeck. Supports path notation (e.g. 'Japanese::Vocabulary::N1'), explicit parent_id, and default_note_type_id.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name or hierarchical path of the deck"},
            "parent_id": {"type": ["integer", "null"], "description": "Optional parent deck ID"},
            "description": {"type": ["string", "null"], "description": "Optional deck description"},
            "default_note_type_id": {"type": ["string", "null"], "description": "Optional default note type UUID for notes created in this deck"},
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
            default_note_type_id=arguments.get("default_note_type_id"),
            update_default_note_type=bool(arguments.get("update_default_note_type")),
        )
    )


UPDATE_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.UPDATE_DECK_TOOL_NAME,
    title="Update Deck",
    description="Update a deck's name, description, move it under a new parent deck, or update its default note type.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": "integer", "description": "ID of the deck to update"},
            "name": {"type": "string", "description": "New deck name"},
            "description": {"type": ["string", "null"], "description": "New deck description"},
            "parent_id": {"type": ["integer", "null"], "description": "New parent deck ID (null to move to top level)"},
            "default_note_type_id": {"type": ["string", "null"], "description": "New default note type UUID (null to clear default note type)"},
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
            expected_content_revision=arguments.get("expected_content_revision"),
            expected_field_schema_revision=arguments.get("expected_field_schema_revision"),
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
            "expected_content_revision": {"type": "integer", "minimum": 0, "description": "Content revision returned by get_note"},
            "expected_field_schema_revision": {"type": "integer", "minimum": 0, "description": "Field schema revision returned by get_note"},
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


def _call_preview_note_sync(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.preview_note_sync(
            user_id=user_id,
            source_key=arguments.get("source_key"),
            deck_id=arguments.get("deck_id"),
            deck_path=arguments.get("deck_path"),
            note_type_id=arguments.get("note_type_id"),
            note_type_name=arguments.get("note_type_name"),
            notes=arguments["notes"],
        )
    )


PREVIEW_NOTE_SYNC_TOOL = McpToolDefinition(
    name=mcp_tool_service.PREVIEW_NOTE_SYNC_TOOL_NAME,
    title="Preview Note Synchronization",
    description="Simulate external note synchronization against existing database notes without modifying any data. Returns counts and per-item diffs (create, update, unchanged, invalid, conflict).",
    input_schema={
        "type": "object",
        "properties": {
            "source_key": {"type": ["string", "null"], "description": "Identifier for external source (e.g. 'google_sheets:doc123', 'excel:unit1')"},
            "deck_id": {"type": ["integer", "null"], "description": "Default target deck ID for items"},
            "deck_path": {"type": ["string", "null"], "description": "Default target deck path (e.g. 'English::Luyện Đề::Bài 8')"},
            "note_type_id": {"type": ["string", "null"], "description": "Note type UUID"},
            "note_type_name": {"type": ["string", "null"], "description": "Note type name (e.g. 'Vocabulary', 'Basic')"},
            "notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "external_id": {"type": ["string", "null"], "description": "Unique identifier from external source row"},
                        "fields": {"type": "object", "description": "Field values mapping"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags list"},
                        "deck_id": {"type": ["integer", "null"], "description": "Optional per-item deck override ID"},
                        "deck_path": {"type": ["string", "null"], "description": "Optional per-item deck override path"},
                    },
                    "required": ["fields"],
                },
                "description": "List of notes to preview sync",
            },
        },
        "required": ["notes"],
        "additionalProperties": False,
    },
    required_scope="note:read",
    annotations={"readOnly": True},
    handler=_call_preview_note_sync,
    arguments_validator=validate_preview_note_sync_arguments,
)


def _call_sync_notes(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.sync_notes(
            user_id=user_id,
            source_key=arguments.get("source_key"),
            deck_id=arguments.get("deck_id"),
            deck_path=arguments.get("deck_path"),
            note_type_id=arguments.get("note_type_id"),
            note_type_name=arguments.get("note_type_name"),
            notes=arguments["notes"],
            stop_on_error=bool(arguments.get("stop_on_error", False)),
            ensure_decks=bool(arguments.get("ensure_decks", True)),
        )
    )


SYNC_NOTES_TOOL = McpToolDefinition(
    name=mcp_tool_service.SYNC_NOTES_TOOL_NAME,
    title="Synchronize External Notes",
    description="Idempotently synchronize external notes into Flama decks with external identity tracking, field validation, and card generation. Automatically creates or updates changed notes while skipping identical ones.",
    input_schema={
        "type": "object",
        "properties": {
            "source_key": {"type": ["string", "null"], "description": "Identifier for external source (e.g. 'google_sheets:doc123', 'excel:unit1')"},
            "deck_id": {"type": ["integer", "null"], "description": "Default target deck ID for items"},
            "deck_path": {"type": ["string", "null"], "description": "Default target deck path (e.g. 'English::Luyện Đề::Bài 8')"},
            "note_type_id": {"type": ["string", "null"], "description": "Note type UUID"},
            "note_type_name": {"type": ["string", "null"], "description": "Note type name (e.g. 'Vocabulary', 'Basic')"},
            "stop_on_error": {"type": "boolean", "description": "Whether to halt and rollback on first validation error (default: false for partial sync)", "default": False},
            "ensure_decks": {"type": "boolean", "description": "Whether to automatically create target decks if they do not exist (default: true)", "default": True},
            "notes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "external_id": {"type": ["string", "null"], "description": "Unique identifier from external source row"},
                        "fields": {"type": "object", "description": "Field values mapping"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags list"},
                        "deck_id": {"type": ["integer", "null"], "description": "Optional per-item deck override ID"},
                        "deck_path": {"type": ["string", "null"], "description": "Optional per-item deck override path"},
                    },
                    "required": ["fields"],
                },
                "description": "List of notes to synchronize",
            },
        },
        "required": ["notes"],
        "additionalProperties": False,
    },
    required_scope="note:sync",
    handler=_call_sync_notes,
    arguments_validator=validate_sync_notes_arguments,
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
            operation_key=arguments.get("operation_key"),
        )
    )


SUBMIT_REVIEW_TOOL = McpToolDefinition(
    name=mcp_tool_service.SUBMIT_REVIEW_TOOL_NAME,
    title="Submit Card Review Answer",
    description="Submit a review answer rating ('again', 'hard', 'good', 'easy') using Flama's registered scheduler. For NOTE authority, reuse an operation_key only when retrying the same answer; identical retries return the original result.",
    input_schema={
        "type": "object",
        "properties": {
            "card_id": {"type": "string", "description": "UUID or ID of the card reviewed"},
            "rating": {"type": "string", "enum": ["again", "hard", "good", "easy"], "description": "Review rating button selected"},
            "duration_ms": {"type": ["integer", "null"], "description": "Optional response time in milliseconds"},
            "operation_key": {"type": ["string", "null"], "minLength": 1, "maxLength": 36, "description": "Optional stable retry identity for NOTE authority only (UUID recommended); use a new key for each new answer. LEGACY rejects this field."},
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
    description="Return detailed field definitions, validation constraints, and templates for a specific note type by id or name.",
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


def _call_create_note_type(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.create_note_type(
            user_id=user_id,
            name=arguments["name"],
            description=arguments.get("description"),
            primary_category=arguments.get("primary_category"),
            tags=arguments.get("tags"),
            taxonomy_metadata=arguments.get("taxonomy_metadata"),
            preview_text=arguments.get("preview_text"),
            preview_image_url=arguments.get("preview_image_url"),
            fields=arguments.get("fields"),
            templates=arguments.get("templates"),
        )
    )


CREATE_NOTE_TYPE_TOOL = McpToolDefinition(
    name=mcp_tool_service.CREATE_NOTE_TYPE_TOOL_NAME,
    title="Create Note Type",
    description="Create a new flashcard note type (model) with custom fields, card templates, metadata, and taxonomy.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Unique name of the new note type"},
            "description": {"type": ["string", "null"], "description": "Optional description"},
            "primary_category": {"type": ["string", "null"], "description": "Primary subject/category (e.g. 'japanese', 'english', 'it_coding')"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags describing the note type"},
            "taxonomy_metadata": {"type": ["object", "null"], "description": "Structured taxonomy metadata (domain, subject, difficulty_band, framework, framework_level, best_used_for, format_features)"},
            "preview_text": {"type": ["string", "null"], "description": "Brief preview summary text"},
            "preview_image_url": {"type": ["string", "null"], "description": "Preview banner or icon image URL"},
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Field name (e.g. 'Word', 'Meaning')"},
                        "field_type": {
                            "type": "string",
                            "enum": list(FIELD_TYPES),
                            "default": "text",
                            "description": "Field data type",
                        },
                        "required": {"type": "boolean", "default": False},
                        "identity_role": {"type": ["string", "null"], "enum": [None, "primary"], "description": "Set to 'primary' for duplicate detection key"},
                    },
                    "required": ["name"],
                },
                "description": "List of field definitions",
            },
            "templates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Template card name (e.g. 'Card 1')"},
                        "front_html": {"type": "string", "description": "Front card HTML markup with {{Field}} placeholders"},
                        "back_html": {"type": "string", "description": "Back card HTML markup with {{Field}} and {{FrontSide}} placeholders"},
                        "shared_css": {"type": "string", "description": "Optional shared CSS styling"},
                    },
                    "required": ["name"],
                },
                "description": "List of card templates",
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    },
    required_scope="note-type:write",
    handler=_call_create_note_type,
    arguments_validator=validate_create_note_type_arguments,
)


def _call_preview_note_type_update(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.preview_note_type_update(
            user_id=user_id,
            note_type_id=arguments["note_type_id"],
            name=arguments.get("name"),
            description=arguments.get("description"),
            fields=arguments.get("fields"),
            templates=arguments.get("templates"),
        )
    )


PREVIEW_NOTE_TYPE_UPDATE_TOOL = McpToolDefinition(
    name=mcp_tool_service.PREVIEW_NOTE_TYPE_UPDATE_TOOL_NAME,
    title="Preview Note Type Update",
    description="Analyze and preview the impact of modifying a note type, fields, or templates (affected notes/cards/decks, data loss risk, template recompilation) and generate a preview token.",
    input_schema={
        "type": "object",
        "properties": {
            "note_type_id": {"type": "string", "description": "UUID of the note type to update"},
            "name": {"type": "string", "description": "New note type name"},
            "description": {"type": ["string", "null"], "description": "New description"},
            "fields": {
                "description": "Full fields list or delta object with added/renamed/removed/modified",
            },
            "templates": {
                "description": "Full templates list or delta object",
            },
        },
        "required": ["note_type_id"],
        "additionalProperties": False,
    },
    required_scope="note-type:read",
    annotations={"readOnly": True},
    handler=_call_preview_note_type_update,
    arguments_validator=validate_preview_note_type_update_arguments,
)


def _call_update_note_type(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.update_note_type(
            user_id=user_id,
            note_type_id=arguments["note_type_id"],
            name=arguments.get("name"),
            description=arguments.get("description"),
            primary_category=arguments.get("primary_category"),
            tags=arguments.get("tags"),
            taxonomy_metadata=arguments.get("taxonomy_metadata"),
            preview_text=arguments.get("preview_text"),
            preview_image_url=arguments.get("preview_image_url"),
            pricing_mode=arguments.get("pricing_mode"),
            price_amount_minor=arguments.get("price_amount_minor"),
            publish_status=arguments.get("publish_status"),
            fields=arguments.get("fields"),
            templates=arguments.get("templates"),
            preview_id=arguments.get("preview_id"),
            confirm=bool(arguments.get("confirm", False)),
        )
    )


UPDATE_NOTE_TYPE_TOOL = McpToolDefinition(
    name=mcp_tool_service.UPDATE_NOTE_TYPE_TOOL_NAME,
    title="Update Note Type",
    description="Update a note type's name, description, fields, templates, metadata, taxonomy, or publish status with automatic data preservation when renaming fields.",
    input_schema={
        "type": "object",
        "properties": {
            "note_type_id": {"type": "string", "description": "UUID of the note type to update"},
            "name": {"type": "string", "description": "New note type name"},
            "description": {"type": ["string", "null"], "description": "New description"},
            "primary_category": {"type": ["string", "null"], "description": "Primary subject/category (e.g. 'japanese', 'english', 'it_coding')"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags list"},
            "taxonomy_metadata": {"type": ["object", "null"], "description": "Structured taxonomy metadata (domain, subject, difficulty_band, framework, framework_level, best_used_for, format_features)"},
            "preview_text": {"type": ["string", "null"], "description": "Brief preview summary text"},
            "preview_image_url": {"type": ["string", "null"], "description": "Preview banner or icon image URL"},
            "pricing_mode": {"type": ["string", "null"], "enum": [None, "free", "paid"], "description": "Pricing mode ('free' or 'paid')"},
            "price_amount_minor": {"type": ["integer", "null"], "description": "Price in minor units"},
            "publish_status": {"type": ["string", "null"], "enum": [None, "published", "unlisted", "archived", "private"], "description": "Publish status"},
            "fields": {"description": "Updated fields list or delta"},
            "templates": {"description": "Updated templates list or delta"},
            "preview_id": {"type": ["string", "null"], "description": "Preview token from preview_note_type_update for stale protection"},
            "confirm": {"type": "boolean", "description": "Explicit confirmation for destructive changes", "default": False},
        },
        "required": ["note_type_id"],
        "additionalProperties": False,
    },
    required_scope="note-type:write",
    handler=_call_update_note_type,
    arguments_validator=validate_update_note_type_arguments,
)



def _call_delete_note_type(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.delete_note_type(
            user_id=user_id,
            note_type_id=arguments["note_type_id"],
            confirm=bool(arguments.get("confirm", False)),
            preview_id=arguments.get("preview_id"),
        )
    )


DELETE_NOTE_TYPE_TOOL = McpToolDefinition(
    name=mcp_tool_service.DELETE_NOTE_TYPE_TOOL_NAME,
    title="Delete Note Type",
    description=(
        "Permanently delete a note type. This is a destructive operation. "
        "AI MUST first call without confirm (or confirm=false) to preview the impact (notes, cards, decks affected, and whether deletion is allowed), "
        "ask for user approval, and only call with confirm=true after the user explicitly confirms."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "note_type_id": {"type": "string", "description": "UUID of the note type to delete"},
            "confirm": {
                "type": "boolean",
                "description": "Set to true only after the user has explicitly confirmed deletion after reviewing the impact.",
                "default": False,
            },
            "preview_id": {"type": ["string", "null"], "description": "Preview token from the initial preview call"},
        },
        "required": ["note_type_id"],
        "additionalProperties": False,
    },
    required_scope="note-type:write",
    annotations={"destructive": True},
    handler=_call_delete_note_type,
    arguments_validator=validate_delete_note_type_arguments,
)


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 7. Image Library Tools
# ---------------------------------------------------------------------------

def _call_import_image(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.import_image(
            user_id=user_id,
            url=arguments.get("url"),
            file_data=arguments.get("file_data"),
            filename=arguments.get("filename"),
            image_key=arguments.get("image_key"),
            tags=arguments.get("tags"),
            description=arguments.get("description", ""),
            is_enabled=arguments.get("is_enabled", True),
        )
    )


IMPORT_IMAGE_TOOL = McpToolDefinition(
    name=mcp_tool_service.IMPORT_IMAGE_TOOL_NAME,
    title="Import Image to Library",
    description="Import an image into the Flama shared Image Library from a remote URL or base64 file data, with English tags and automatic SHA-256 deduplication.",
    required_scope="media:write",
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Public HTTP/HTTPS URL of the image to fetch and import.",
            },
            "file_data": {
                "type": "string",
                "description": "Base64-encoded image data or data URI (data:image/...;base64,...).",
            },
            "filename": {
                "type": "string",
                "description": "Optional original filename (e.g. apple.png).",
            },
            "image_key": {
                "type": "string",
                "description": "Optional unique slug identifier (e.g. 'red_apple'). If omitted, derived from tags or filename.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "English tags describing the image content (e.g. ['apple', 'fruit', 'red', 'food']).",
            },
            "description": {
                "type": "string",
                "description": "Optional description or context of the image.",
            },
            "is_enabled": {
                "type": "boolean",
                "description": "Whether the image is enabled for use. Defaults to true.",
            },
        },
    },
    handler=_call_import_image,
    arguments_validator=validate_import_image_arguments,
)


def _call_crawl_note_media(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.crawl_note_media(
            user_id=user_id,
            note_id=arguments["note_id"],
            field_name=arguments["field_name"],
            url=arguments["url"],
            markdown_inline=arguments.get("markdown_inline", False),
        )
    )


CRAWL_NOTE_MEDIA_TOOL = McpToolDefinition(
    name=mcp_tool_service.CRAWL_NOTE_MEDIA_TOOL_NAME,
    title="Crawl Image for Note",
    description="Crawl and download an image from a remote URL, sanitize and convert to WebP, and attach it to a specific note's field as a local media asset.",
    required_scope="media:write",
    input_schema={
        "type": "object",
        "properties": {
            "note_id": {
                "type": "string",
                "description": "ID of the target Note.",
            },
            "field_name": {
                "type": "string",
                "description": "Name of the target field (image, diagram, or markdown).",
            },
            "url": {
                "type": "string",
                "description": "Public HTTP/HTTPS URL of the image to crawl.",
            },
            "markdown_inline": {
                "type": "boolean",
                "description": "Set to true if this media is an inline image inside markdown content. Defaults to false.",
            },
        },
        "required": ["note_id", "field_name", "url"],
    },
    handler=_call_crawl_note_media,
    arguments_validator=validate_crawl_note_media_arguments,
)


def _call_extract_page_images(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.extract_page_images(
            user_id=user_id,
            page_url=arguments["page_url"],
            max_images=arguments.get("max_images", 20),
        )
    )


EXTRACT_PAGE_IMAGES_TOOL = McpToolDefinition(
    name=mcp_tool_service.EXTRACT_PAGE_IMAGES_TOOL_NAME,
    title="Extract Images from Webpage",
    description="Fetch a remote webpage safely with SSRF protection and extract candidate image URLs (OpenGraph, Twitter Cards, and img tags).",
    required_scope="media:read",
    input_schema={
        "type": "object",
        "properties": {
            "page_url": {
                "type": "string",
                "description": "Public HTTP/HTTPS URL of the webpage to crawl.",
            },
            "max_images": {
                "type": "integer",
                "description": "Maximum number of candidate images to return (default 20, max 50).",
            },
        },
        "required": ["page_url"],
    },
    handler=_call_extract_page_images,
    arguments_validator=validate_extract_page_images_arguments,
)



def _call_search_images(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.search_images(
            user_id=user_id,
            query=arguments.get("query", ""),
            tag=arguments.get("tag"),
            status=arguments.get("status", "enabled"),
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0),
        )
    )


SEARCH_IMAGES_TOOL = McpToolDefinition(
    name=mcp_tool_service.SEARCH_IMAGES_TOOL_NAME,
    title="Search Image Library",
    description="Search images in the Flama Image Library by keyword query, English tag, or status.",
    required_scope="media:read",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword search across image key, description, and tags.",
            },
            "tag": {
                "type": "string",
                "description": "Exact tag filter (e.g. 'apple', 'fruit').",
            },
            "status": {
                "type": "string",
                "enum": ["enabled", "disabled", "all"],
                "description": "Status filter. Defaults to 'enabled'.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of items to return (1-60). Default is 20.",
            },
            "offset": {
                "type": "integer",
                "description": "Number of items to skip for pagination. Default is 0.",
            },
        },
    },
    handler=_call_search_images,
    arguments_validator=validate_search_images_arguments,
)


def _call_get_image(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_image(
            user_id=user_id,
            image_key=arguments.get("image_key"),
            asset_id=arguments.get("asset_id"),
        )
    )


GET_IMAGE_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_IMAGE_TOOL_NAME,
    title="Get Image Details",
    description="Get metadata, URL, tags, and dimensions of a specific image by image_key or asset_id.",
    required_scope="media:read",
    input_schema={
        "type": "object",
        "properties": {
            "image_key": {
                "type": "string",
                "description": "The unique slug key of the image (e.g. 'red_apple').",
            },
            "asset_id": {
                "type": "string",
                "description": "The UUID/ID of the image asset.",
            },
        },
    },
    handler=_call_get_image,
    arguments_validator=validate_get_image_arguments,
)

# ---------------------------------------------------------------------------
# 8. Shared Decks & Releases Tools
# ---------------------------------------------------------------------------


def _call_list_shared_decks(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.list_shared_decks(
            user_id=user_id,
            query=arguments.get("query"),
            category=arguments.get("category"),
            tags=arguments.get("tags"),
            pricing_mode=arguments.get("pricing_mode"),
            sort_by=arguments.get("sort_by", "popular"),
            only_mine=bool(arguments.get("only_mine", False)),
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0),
        )
    )


LIST_SHARED_DECKS_TOOL = McpToolDefinition(
    name=mcp_tool_service.LIST_SHARED_DECKS_TOOL_NAME,
    title="List Shared Decks",
    description="Browse and search shared flashcard decks on the Flama Marketplace with keyword, tag, category, and pricing filters, or view decks shared by yourself.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": ["string", "null"], "description": "Search keyword for deck title or description"},
            "category": {"type": ["string", "null"], "description": "Category slug (e.g. 'japanese', 'kanji', 'vocabulary')"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags (e.g. ['n3', 'jlpt'])"},
            "pricing_mode": {"type": ["string", "null"], "enum": [None, "free", "paid"], "description": "Filter by pricing mode ('free' or 'paid')"},
            "sort_by": {"type": "string", "enum": ["popular", "recently_updated", "rating", "newest", "price_asc", "price_desc"], "default": "popular", "description": "Sort order"},
            "only_mine": {"type": "boolean", "default": False, "description": "Set to true to only list decks shared by the authenticated user"},
            "limit": {"type": "integer", "description": "Max results to return (default 20, max 100)"},
            "offset": {"type": "integer", "description": "Pagination offset (default 0)"},
        },
        "additionalProperties": False,
    },
    required_scope="deck-share:read",
    annotations={"readOnly": True},
    handler=_call_list_shared_decks,
    arguments_validator=validate_list_shared_decks_arguments,
)


def _call_get_shared_deck(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_shared_deck(user_id=user_id, deck_item_id=arguments["deck_item_id"])
    )


GET_SHARED_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_SHARED_DECK_TOOL_NAME,
    title="Get Shared Deck Detail",
    description="Get comprehensive details of a shared marketplace deck: title, description, categories, tags, source note type schema, sample cards, active stats, and current release version.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_item_id": {"type": "string", "description": "UUID of the shared deck marketplace item"},
        },
        "required": ["deck_item_id"],
        "additionalProperties": False,
    },
    required_scope="deck-share:read",
    annotations={"readOnly": True},
    handler=_call_get_shared_deck,
    arguments_validator=validate_get_shared_deck_arguments,
)


def _call_list_shared_deck_notes(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.list_shared_deck_notes(
            user_id=user_id,
            deck_item_id=arguments["deck_item_id"],
            query=arguments.get("query"),
            limit=arguments.get("limit", 20),
            offset=arguments.get("offset", 0),
        )
    )


LIST_SHARED_DECK_NOTES_TOOL = McpToolDefinition(
    name=mcp_tool_service.LIST_SHARED_DECK_NOTES_TOOL_NAME,
    title="List Notes in Shared Deck",
    description="Inspect and review notes, field values (words, readings, meanings, examples, descriptions), and cards inside a shared deck to verify accuracy and identify items needing improved explanations.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_item_id": {"type": "string", "description": "UUID of the shared deck marketplace item"},
            "query": {"type": ["string", "null"], "description": "Optional search keyword across note fields and tags"},
            "limit": {"type": "integer", "description": "Number of notes to return (default 20, max 100)"},
            "offset": {"type": "integer", "description": "Pagination offset (default 0)"},
        },
        "required": ["deck_item_id"],
        "additionalProperties": False,
    },
    required_scope="deck-share:read",
    annotations={"readOnly": True},
    handler=_call_list_shared_deck_notes,
    arguments_validator=validate_list_shared_deck_notes_arguments,
)


def _call_get_deck_publish_options(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_deck_publish_options(user_id=user_id, deck_id=arguments.get("deck_id"))
    )


GET_DECK_PUBLISH_OPTIONS_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_DECK_PUBLISH_OPTIONS_TOOL_NAME,
    title="Get Deck Publish Options & Eligibility",
    description="Check publish eligibility for personal decks, and retrieve available marketplace categories and note types for sharing.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": ["integer", "null"], "description": "Optional specific local deck ID to check publish eligibility for"},
        },
        "additionalProperties": False,
    },
    required_scope="deck-share:read",
    annotations={"readOnly": True},
    handler=_call_get_deck_publish_options,
    arguments_validator=validate_get_deck_publish_options_arguments,
)


def _call_get_taxonomy_schema(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.get_taxonomy_schema(
            user_id=user_id,
            content_type=arguments.get("content_type", "deck_marketplace_item"),
        )
    )


GET_TAXONOMY_SCHEMA_TOOL = McpToolDefinition(
    name=mcp_tool_service.GET_TAXONOMY_SCHEMA_TOOL_NAME,
    title="Get Taxonomy Schema",
    description="Retrieve the complete hierarchical taxonomy schema including domains, subjects, frameworks (JLPT, CEFR, TOEIC, HSK, AWS, etc.), levels, learning goals, topics, format features, and best_used_for options.",
    input_schema={
        "type": "object",
        "properties": {
            "content_type": {
                "type": "string",
                "enum": ["deck_marketplace_item", "note_type"],
                "default": "deck_marketplace_item",
                "description": "Content type to retrieve taxonomy schema for ('deck_marketplace_item' or 'note_type').",
            },
        },
        "additionalProperties": False,
    },
    required_scope="deck-share:read",
    annotations={"readOnly": True},
    handler=_call_get_taxonomy_schema,
    arguments_validator=validate_get_taxonomy_schema_arguments,
)


def _call_share_deck(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.share_deck(
            user_id=user_id,
            deck_id=arguments.get("deck_id"),
            deck_path=arguments.get("deck_path"),
            title=arguments.get("title"),
            description=arguments.get("description"),
            primary_category=arguments.get("primary_category"),
            tags=arguments.get("tags"),
            pricing_mode=arguments.get("pricing_mode", "free"),
            price_amount_minor=arguments.get("price_amount_minor"),
            is_unlisted=bool(arguments.get("is_unlisted", False)),
            preview_text=arguments.get("preview_text"),
            sample_cards_count=arguments.get("sample_cards_count"),
            taxonomy_metadata=arguments.get("taxonomy_metadata"),
        )
    )


SHARE_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.SHARE_DECK_TOOL_NAME,
    title="Share Deck to Marketplace",
    description="Publish and share a personal flashcard deck to the Flama Marketplace with title, rich description, category, tags, pricing mode, preview metadata, and taxonomy.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_id": {"type": ["integer", "null"], "description": "ID of the local deck to share"},
            "deck_path": {"type": ["string", "null"], "description": "Hierarchical path of the deck (e.g. 'Japanese::JLPT N3') if deck_id is not provided"},
            "title": {"type": ["string", "null"], "description": "Marketplace listing title (defaults to deck name)"},
            "description": {"type": ["string", "null"], "description": "Detailed description explaining what the deck covers, target level, and study tips"},
            "primary_category": {"type": ["string", "null"], "description": "Category slug (e.g. 'japanese', 'kanji', 'grammar', 'vocabulary', 'english')"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "List of tags (e.g. ['n3', 'jlpt', 'shadowing'])"},
            "pricing_mode": {"type": "string", "enum": ["free", "paid"], "default": "free", "description": "Pricing mode ('free' or 'paid')"},
            "price_amount_minor": {"type": ["integer", "null"], "description": "Price in minor units (e.g. VND) if pricing_mode is 'paid'"},
            "is_unlisted": {"type": "boolean", "default": False, "description": "Whether to make the shared deck unlisted (accessible via link only)"},
            "preview_text": {"type": ["string", "null"], "description": "Brief preview summary text"},
            "sample_cards_count": {"type": ["integer", "null"], "description": "Number of sample cards to show on marketplace"},
            "taxonomy_metadata": {"type": ["object", "null"], "description": "Structured taxonomy metadata (domain, subject, difficulty_band, framework, framework_level, framework_track, learning_goals, primary_topics, format_features, audience)"},
        },
        "additionalProperties": False,
    },
    required_scope="deck-share:write",
    handler=_call_share_deck,
    arguments_validator=validate_share_deck_arguments,
)


def _call_update_shared_deck(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.update_shared_deck(
            user_id=user_id,
            deck_item_id=arguments["deck_item_id"],
            title=arguments.get("title"),
            description=arguments.get("description"),
            primary_category=arguments.get("primary_category"),
            tags=arguments.get("tags"),
            pricing_mode=arguments.get("pricing_mode"),
            price_amount_minor=arguments.get("price_amount_minor"),
            publish_status=arguments.get("publish_status"),
            preview_text=arguments.get("preview_text"),
            sample_cards_count=arguments.get("sample_cards_count"),
            taxonomy_metadata=arguments.get("taxonomy_metadata"),
        )
    )


UPDATE_SHARED_DECK_TOOL = McpToolDefinition(
    name=mcp_tool_service.UPDATE_SHARED_DECK_TOOL_NAME,
    title="Update Shared Deck Listing",
    description="Update metadata, description, category, tags, pricing, taxonomy, preview, or publish status of an already shared deck.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_item_id": {"type": "string", "description": "UUID of the shared deck marketplace item to update"},
            "title": {"type": ["string", "null"], "description": "New title"},
            "description": {"type": ["string", "null"], "description": "New detailed description"},
            "primary_category": {"type": ["string", "null"], "description": "New primary category slug"},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "New tags list"},
            "pricing_mode": {"type": ["string", "null"], "enum": [None, "free", "paid"], "description": "New pricing mode"},
            "price_amount_minor": {"type": ["integer", "null"], "description": "New price in minor units"},
            "publish_status": {"type": ["string", "null"], "enum": [None, "published", "unlisted", "archived", "draft", "private"], "description": "New publish status"},
            "preview_text": {"type": ["string", "null"], "description": "New brief preview summary text"},
            "sample_cards_count": {"type": ["integer", "null"], "description": "New number of sample cards to show"},
            "taxonomy_metadata": {"type": ["object", "null"], "description": "New structured taxonomy metadata (domain, subject, difficulty_band, framework, framework_level, framework_track, learning_goals, primary_topics, format_features, audience)"},
        },
        "required": ["deck_item_id"],
        "additionalProperties": False,
    },
    required_scope="deck-share:write",
    handler=_call_update_shared_deck,
    arguments_validator=validate_update_shared_deck_arguments,
)



def _call_preview_deck_release(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.preview_deck_release(
            user_id=user_id,
            deck_item_id=arguments["deck_item_id"],
            limit=arguments.get("limit", 50),
            cursor=arguments.get("cursor"),
        )
    )


PREVIEW_DECK_RELEASE_TOOL = McpToolDefinition(
    name=mcp_tool_service.PREVIEW_DECK_RELEASE_TOOL_NAME,
    title="Preview Deck Release Diff",
    description="Preview the changes/diff between the working notes (after card descriptions/content have been updated) and the published release of a shared deck before releasing a new version.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_item_id": {"type": "string", "description": "UUID of the shared deck marketplace item"},
            "limit": {"type": "integer", "description": "Max changes to return (default 50, max 200)"},
            "cursor": {"type": ["string", "null"], "description": "Pagination cursor for large diffs"},
        },
        "required": ["deck_item_id"],
        "additionalProperties": False,
    },
    required_scope="deck-share:read",
    annotations={"readOnly": True},
    handler=_call_preview_deck_release,
    arguments_validator=validate_preview_deck_release_arguments,
)


def _call_publish_deck_release(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.publish_deck_release(
            user_id=user_id,
            deck_item_id=arguments["deck_item_id"],
            version_label=arguments["version_label"],
            changelog=arguments.get("changelog"),
            expected_current_release_id=arguments.get("expected_current_release_id"),
            expected_working_revision=arguments.get("expected_working_revision"),
        )
    )


PUBLISH_DECK_RELEASE_TOOL = McpToolDefinition(
    name=mcp_tool_service.PUBLISH_DECK_RELEASE_TOOL_NAME,
    title="Publish Deck Release",
    description="Publish a new immutable version/release for a shared deck with a version label and changelog after improving notes, card descriptions, or examples, pushing the updates to all subscribers.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_item_id": {"type": "string", "description": "UUID of the shared deck marketplace item"},
            "version_label": {"type": "string", "description": "Version string (e.g. '1.1.0', '2.0.0')"},
            "changelog": {"type": ["string", "null"], "description": "Changelog describing the improvements made (e.g. 'Bổ sung giải thích ngữ pháp và ví dụ thực tế cho các thẻ N2')"},
            "expected_current_release_id": {"type": ["string", "null"], "description": "Optional expected current release UUID for optimistic locking"},
            "expected_working_revision": {"type": ["integer", "null"], "description": "Optional expected working revision"},
        },
        "required": ["deck_item_id", "version_label"],
        "additionalProperties": False,
    },
    required_scope="deck-share:write",
    handler=_call_publish_deck_release,
    arguments_validator=validate_publish_deck_release_arguments,
)


def _call_list_deck_releases(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.list_deck_releases(
            user_id=user_id,
            deck_item_id=arguments["deck_item_id"],
            limit=arguments.get("limit", 20),
            cursor=arguments.get("cursor"),
        )
    )


LIST_DECK_RELEASES_TOOL = McpToolDefinition(
    name=mcp_tool_service.LIST_DECK_RELEASES_TOOL_NAME,
    title="List Deck Releases",
    description="List the immutable release versions, dates, and changelogs of a shared deck.",
    input_schema={
        "type": "object",
        "properties": {
            "deck_item_id": {"type": "string", "description": "UUID of the shared deck marketplace item"},
            "limit": {"type": "integer", "description": "Max results to return (default 20, max 100)"},
            "cursor": {"type": ["string", "null"], "description": "Pagination cursor"},
        },
        "required": ["deck_item_id"],
        "additionalProperties": False,
    },
    required_scope="deck-share:read",
    annotations={"readOnly": True},
    handler=_call_list_deck_releases,
    arguments_validator=validate_list_deck_releases_arguments,
)


def _call_list_installed_decks(*, user_id: int, arguments: dict[str, Any]) -> dict[str, Any]:
    del arguments
    return mcp_tool_service._wrap_tool_result(
        mcp_tool_service.list_installed_decks(user_id=user_id)
    )


LIST_INSTALLED_DECKS_TOOL = McpToolDefinition(
    name=mcp_tool_service.LIST_INSTALLED_DECKS_TOOL_NAME,
    title="List Installed Decks",
    description="List all shared marketplace decks installed into the user's library, showing their local deck ID and whether upstream release updates are available.",
    input_schema={
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    required_scope="deck:read",
    annotations={"readOnly": True},
    handler=_call_list_installed_decks,
    arguments_validator=validate_list_installed_decks_arguments,
)


# ---------------------------------------------------------------------------
# 10. Public AI Search & Documentation Tools
# ---------------------------------------------------------------------------

def _call_search_marketplace_decks(*, user_id: int | None = None, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        public_search_tools.search_marketplace_decks(
            query=arguments.get("query", ""),
            jlpt_level=arguments.get("jlpt_level", "All"),
            category=arguments.get("category", ""),
            pricing_mode=arguments.get("pricing_mode", "all"),
            sort_by=arguments.get("sort_by", "popular"),
            limit=arguments.get("limit", 10),
            offset=arguments.get("offset", 0),
            user_id=user_id,
        )
    )


SEARCH_MARKETPLACE_DECKS_TOOL = McpToolDefinition(
    name="search_marketplace_decks",
    title="Search Flama Marketplace Decks",
    description="Search public published flashcard decks on the Flama Marketplace by keyword, JLPT level (N5-N1), category, and pricing. Sample preview capped at 3-5 cards.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keyword in deck title, description, or tags",
                "default": "",
            },
            "jlpt_level": {
                "type": "string",
                "enum": ["N5", "N4", "N3", "N2", "N1", "All"],
                "description": "Filter by JLPT level",
                "default": "All",
            },
            "category": {
                "type": "string",
                "description": "Filter by primary category/subject",
                "default": "",
            },
            "pricing_mode": {
                "type": "string",
                "enum": ["free", "paid", "all"],
                "description": "Filter by pricing mode",
                "default": "all",
            },
            "sort_by": {
                "type": "string",
                "enum": ["popular", "rating", "newest", "card_count"],
                "description": "Ordering criteria",
                "default": "popular",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of deck items to return (default 10, max 20)",
                "default": 10,
                "maximum": 20,
            },
            "offset": {
                "type": "integer",
                "description": "Pagination offset",
                "default": 0,
            },
        },
        "additionalProperties": False,
    },
    required_scope=None,
    is_public=True,
    annotations={"readOnly": True},
    handler=_call_search_marketplace_decks,
    arguments_validator=public_search_tools.validate_search_marketplace_decks_arguments,
)


def _call_lookup_public_vocabulary(*, user_id: int | None = None, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        public_search_tools.lookup_public_vocabulary(
            query=arguments.get("query", ""),
            jlpt_level=arguments.get("jlpt_level", "All"),
            limit=arguments.get("limit", 10),
            offset=arguments.get("offset", 0),
            user_id=user_id,
        )
    )


LOOKUP_PUBLIC_VOCABULARY_TOOL = McpToolDefinition(
    name="lookup_public_vocabulary",
    title="Lookup Public Japanese Vocabulary",
    description="Search vocabulary words, kana readings, and definitions across published Flama marketplace decks. Excludes all private user data.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Japanese word (kanji/kana), romaji, or meaning keyword",
            },
            "jlpt_level": {
                "type": "string",
                "enum": ["N5", "N4", "N3", "N2", "N1", "All"],
                "description": "Filter by JLPT level",
                "default": "All",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of vocabulary matches to return (default 10, max 20)",
                "default": 10,
                "maximum": 20,
            },
            "offset": {
                "type": "integer",
                "description": "Pagination offset",
                "default": 0,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    required_scope=None,
    is_public=True,
    annotations={"readOnly": True},
    handler=_call_lookup_public_vocabulary,
    arguments_validator=public_search_tools.validate_lookup_public_vocabulary_arguments,
)


def _call_get_public_deck_preview(*, user_id: int | None = None, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        public_search_tools.get_public_deck_preview(
            deck_item_id=arguments.get("deck_item_id", ""),
            user_id=user_id,
        )
    )


GET_PUBLIC_DECK_PREVIEW_TOOL = McpToolDefinition(
    name="get_public_deck_preview",
    title="Get Public Deck Preview",
    description="Inspect metadata and sample cards of a published marketplace deck (strictly 3 to 5 sample preview cards max, anti-scraping enforced).",
    input_schema={
        "type": "object",
        "properties": {
            "deck_item_id": {
                "type": "string",
                "description": "UUID of the published marketplace deck",
            },
        },
        "required": ["deck_item_id"],
        "additionalProperties": False,
    },
    required_scope=None,
    is_public=True,
    annotations={"readOnly": True},
    handler=_call_get_public_deck_preview,
    arguments_validator=public_search_tools.validate_get_public_deck_preview_arguments,
)


def _call_get_flama_documentation(*, user_id: int | None = None, arguments: dict[str, Any]) -> dict[str, Any]:
    return mcp_tool_service._wrap_tool_result(
        public_search_tools.get_flama_documentation(
            topic=arguments.get("topic", "overview"),
            user_id=user_id,
        )
    )


GET_FLAMA_DOCUMENTATION_TOOL = McpToolDefinition(
    name="get_flama_documentation",
    title="Get Flama Feature Documentation",
    description="Reference official Flama documentation on template-authoring syntax/sandbox/preview, quiz-template recipe, SRS, Yomitan mining, Local TTS, and Marketplace.",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "enum": list(public_search_tools.FLAMA_DOCUMENTATION_TOPICS),
                "description": "Specific feature domain documentation topic",
                "default": "overview",
            },
        },
        "additionalProperties": False,
    },
    required_scope=None,
    is_public=True,
    annotations={"readOnly": True},
    handler=_call_get_flama_documentation,
    arguments_validator=public_search_tools.validate_get_flama_documentation_arguments,
)

from app.services.mcp.template_preview_tools import preview_note_type_template
from app.validators.mcp_template_preview import (
    TEMPLATE_PREVIEW_INPUT_SCHEMA, TEMPLATE_PREVIEW_OUTPUT_SCHEMA, validate_template_preview_arguments,
)

PREVIEW_NOTE_TYPE_TEMPLATE_TOOL = McpToolDefinition(
    name="preview_note_type_template",
    title="Preview NoteType Template",
    description=("Analyze a candidate without saving, and return Study client artifacts for sandbox preview. "
        "Supply input_schema, front_html, back_html and explicit sample_values for a raw candidate, or "
        "an owned note_type_id plus application_id. Browser/interaction checks remain not_run. "
        "Use get_flama_documentation(topic='template-authoring') for syntax and quiz-template for a recipe."),
    input_schema=TEMPLATE_PREVIEW_INPUT_SCHEMA,
    output_schema=TEMPLATE_PREVIEW_OUTPUT_SCHEMA,
    required_scope="note-type:read",
    annotations={"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    meta={"ui": {"resourceUri": "ui://flama/template-preview/v1.html"}},
    handler=preview_note_type_template,
    arguments_validator=validate_template_preview_arguments,
)


# All Registered MCP Tools
# ---------------------------------------------------------------------------

_MCP_TOOL_DEFINITIONS = (
    # Decks
    LIST_MY_DECKS_TOOL,
    GET_DECK_TREE_TOOL,
    GET_DECK_TOOL,
    RESOLVE_DECK_TOOL,
    BATCH_ENSURE_DECKS_TOOL,
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
    # Batch & Sync
    BATCH_CREATE_NOTES_TOOL,
    BATCH_UPDATE_NOTES_TOOL,
    BATCH_DELETE_NOTES_TOOL,
    BATCH_MOVE_NOTES_TOOL,
    PREVIEW_NOTE_SYNC_TOOL,
    SYNC_NOTES_TOOL,
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
    CREATE_NOTE_TYPE_TOOL,
    PREVIEW_NOTE_TYPE_UPDATE_TOOL,
    PREVIEW_NOTE_TYPE_TEMPLATE_TOOL,
    UPDATE_NOTE_TYPE_TOOL,
    DELETE_NOTE_TYPE_TOOL,
    # Image Library & Crawling
    IMPORT_IMAGE_TOOL,
    SEARCH_IMAGES_TOOL,
    GET_IMAGE_TOOL,
    CRAWL_NOTE_MEDIA_TOOL,
    EXTRACT_PAGE_IMAGES_TOOL,
    # Shared Decks & Releases & Taxonomy
    GET_TAXONOMY_SCHEMA_TOOL,
    LIST_SHARED_DECKS_TOOL,
    GET_SHARED_DECK_TOOL,
    LIST_SHARED_DECK_NOTES_TOOL,
    GET_DECK_PUBLISH_OPTIONS_TOOL,
    SHARE_DECK_TOOL,
    UPDATE_SHARED_DECK_TOOL,
    PREVIEW_DECK_RELEASE_TOOL,
    PUBLISH_DECK_RELEASE_TOOL,
    LIST_DECK_RELEASES_TOOL,
    LIST_INSTALLED_DECKS_TOOL,
    # Public AI Search & Documentation Tools
    SEARCH_MARKETPLACE_DECKS_TOOL,
    LOOKUP_PUBLIC_VOCABULARY_TOOL,
    GET_PUBLIC_DECK_PREVIEW_TOOL,
    GET_FLAMA_DOCUMENTATION_TOOL,
)

_MCP_TOOLS_BY_NAME = {tool.name: tool for tool in _MCP_TOOL_DEFINITIONS}
_MCP_TOOLS_BY_LOWER_NAME = {tool.name.lower(): tool for tool in _MCP_TOOL_DEFINITIONS}


def list_mcp_tools(*, include_public: bool = True) -> list[dict[str, Any]]:
    """Return MCP-compatible metadata for exposed tools."""
    if include_public:
        return [tool.to_mcp_payload() for tool in _MCP_TOOL_DEFINITIONS]
    return [
        tool.to_mcp_payload()
        for tool in _MCP_TOOL_DEFINITIONS
        if not getattr(tool, "is_public", False)
    ]


def get_mcp_tool(tool_name: str) -> McpToolDefinition | None:
    """Resolve a tool definition by name, supporting exact match, case-insensitivity, and namespace prefixes.

    Examples supported:
    - 'search_images' (exact)
    - 'Flama.search_images', 'flama.search_images' (dot namespace)
    - 'Flama:search_images' (colon namespace)
    - 'Flama/search_images' (slash namespace)
    - 'Flama__search_images' (double underscore namespace)
    - 'flama_search_images' (single underscore namespace fallback)
    """
    raw_name = str(tool_name or "").strip()
    if not raw_name:
        return None

    # 1. Exact match
    if raw_name in _MCP_TOOLS_BY_NAME:
        return _MCP_TOOLS_BY_NAME[raw_name]

    # 2. Case-insensitive exact match
    raw_lower = raw_name.lower()
    if raw_lower in _MCP_TOOLS_BY_LOWER_NAME:
        return _MCP_TOOLS_BY_LOWER_NAME[raw_lower]

    # 3. Explicit namespace separators (., :, /, __)
    for sep in (".", ":", "/", "__"):
        if sep in raw_name:
            suffix = raw_name.split(sep, 1)[-1].strip()
            if suffix in _MCP_TOOLS_BY_NAME:
                return _MCP_TOOLS_BY_NAME[suffix]
            suffix_lower = suffix.lower()
            if suffix_lower in _MCP_TOOLS_BY_LOWER_NAME:
                return _MCP_TOOLS_BY_LOWER_NAME[suffix_lower]

    # 4. Fallback for flama_<tool_name> prefix
    if raw_lower.startswith("flama_"):
        suffix = raw_name[6:].strip()
        if suffix in _MCP_TOOLS_BY_NAME:
            return _MCP_TOOLS_BY_NAME[suffix]
        suffix_lower = suffix.lower()
        if suffix_lower in _MCP_TOOLS_BY_LOWER_NAME:
            return _MCP_TOOLS_BY_LOWER_NAME[suffix_lower]

    return None


def call_mcp_tool(*, tool_name: str, user_id: int | None = None, arguments: Any) -> dict[str, Any]:
    """Execute a registered tool for the current user or guest."""
    tool_definition = get_mcp_tool(tool_name)
    if tool_definition is None:
        raise KeyError(str(tool_name or "").strip())
    return tool_definition.execute(user_id=user_id, arguments=arguments)

