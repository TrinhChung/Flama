"""Common constants, response wrappers, and resolution helpers for MCP tools."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from typing import Any

from sqlalchemy import or_

from app.repositories import vocabulary_repository
from app.services.common.mcp_response import (
    compact_description as _compact_description,
    wrap_tool_result as _wrap_tool_result,
    wrap_tool_error as _wrap_tool_error,
)
from app.validators.flashcard_input import RequestValidationError
from models.deck import Deck
from models.note_type import NoteType

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2025-11-25"

# Tool names
LIST_MY_DECKS_TOOL_NAME = "list_my_decks"
GET_DECK_TREE_TOOL_NAME = "get_deck_tree"
GET_DECK_TOOL_NAME = "get_deck"
RESOLVE_DECK_TOOL_NAME = "resolve_deck"
BATCH_ENSURE_DECKS_TOOL_NAME = "batch_ensure_decks"
CREATE_DECK_TOOL_NAME = "create_deck"
UPDATE_DECK_TOOL_NAME = "update_deck"
DELETE_DECK_TOOL_NAME = "delete_deck"

LIST_NOTES_TOOL_NAME = "list_notes"
GET_NOTE_TOOL_NAME = "get_note"
FIND_NOTES_TOOL_NAME = "find_notes"
CREATE_NOTE_TOOL_NAME = "create_note"
UPDATE_NOTE_TOOL_NAME = "update_note"
DELETE_NOTE_TOOL_NAME = "delete_note"
MOVE_NOTE_TOOL_NAME = "move_note"
ADD_TAGS_TOOL_NAME = "add_tags"
REMOVE_TAGS_TOOL_NAME = "remove_tags"

BATCH_CREATE_NOTES_TOOL_NAME = "batch_create_notes"
BATCH_UPDATE_NOTES_TOOL_NAME = "batch_update_notes"
BATCH_DELETE_NOTES_TOOL_NAME = "batch_delete_notes"
BATCH_MOVE_NOTES_TOOL_NAME = "batch_move_notes"
PREVIEW_NOTE_SYNC_TOOL_NAME = "preview_note_sync"
SYNC_NOTES_TOOL_NAME = "sync_notes"

GET_DUE_CARD_COUNTS_TOOL_NAME = "get_due_card_counts"
GET_STUDY_QUEUE_TOOL_NAME = "get_study_queue"
GET_CARD_TOOL_NAME = "get_card"
SUBMIT_REVIEW_TOOL_NAME = "submit_review"

GET_DECK_STATS_TOOL_NAME = "get_deck_stats"
GET_STUDY_STATS_TOOL_NAME = "get_study_stats"

LIST_NOTE_TYPES_TOOL_NAME = "list_note_types"
GET_NOTE_TYPE_SCHEMA_TOOL_NAME = "get_note_type_schema"
CREATE_NOTE_TYPE_TOOL_NAME = "create_note_type"
PREVIEW_NOTE_TYPE_UPDATE_TOOL_NAME = "preview_note_type_update"
UPDATE_NOTE_TYPE_TOOL_NAME = "update_note_type"
DELETE_NOTE_TYPE_TOOL_NAME = "delete_note_type"

IMPORT_IMAGE_TOOL_NAME = "import_image"
SEARCH_IMAGES_TOOL_NAME = "search_images"
GET_IMAGE_TOOL_NAME = "get_image"
CRAWL_NOTE_MEDIA_TOOL_NAME = "crawl_note_media"
EXTRACT_PAGE_IMAGES_TOOL_NAME = "extract_page_images"

# Shared Decks & Releases Tool Names
LIST_SHARED_DECKS_TOOL_NAME = "list_shared_decks"
GET_SHARED_DECK_TOOL_NAME = "get_shared_deck"
LIST_SHARED_DECK_NOTES_TOOL_NAME = "list_shared_deck_notes"
GET_DECK_PUBLISH_OPTIONS_TOOL_NAME = "get_deck_publish_options"
SHARE_DECK_TOOL_NAME = "share_deck"
UPDATE_SHARED_DECK_TOOL_NAME = "update_shared_deck"
PREVIEW_DECK_RELEASE_TOOL_NAME = "preview_deck_release"
PUBLISH_DECK_RELEASE_TOOL_NAME = "publish_deck_release"
LIST_DECK_RELEASES_TOOL_NAME = "list_deck_releases"
LIST_INSTALLED_DECKS_TOOL_NAME = "list_installed_decks"


def _resolve_deck_for_user(*, user_id: int, deck_id: int | None = None, deck_name: str | None = None) -> Deck:
    if deck_id is not None:
        deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
        if deck is not None:
            return deck
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )
    if deck_name and str(deck_name).strip():
        cleaned = str(deck_name).strip()
        tokens = [t.strip() for t in cleaned.replace("/", "::").split("::") if t.strip()]
        if not tokens:
            tokens = [cleaned]
        upsert_res = vocabulary_repository.upsert_deck_path(
            parent_id=None,
            path_tokens=tokens,
            owner_user_id=user_id,
            admin_mode=False,
        )
        if upsert_res.final_deck is not None:
            return upsert_res.final_deck
        raise RequestValidationError(
            f"Không thể tìm hoặc tạo deck '{deck_name}'.",
            field="deck_name",
            status=400,
            code="DECK_CREATION_FAILED",
        )
    raise RequestValidationError(
        "Cần chỉ định deck_id hoặc deck_name.",
        field="deck_id",
        status=400,
        code="INVALID_PARAMS",
    )


def _build_deck_full_path(deck_obj: Deck, user_id: int) -> str:
    parts = [deck_obj.name]
    current_parent_id = deck_obj.parent_id
    visited: set[int] = {deck_obj.id}
    while current_parent_id:
        if current_parent_id in visited:
            break
        visited.add(current_parent_id)
        parent = Deck.query.filter_by(id=current_parent_id, owner_user_id=user_id, deleted_at=None).first()
        if not parent:
            break
        parts.append(parent.name)
        current_parent_id = parent.parent_id
    return "::".join(reversed(parts))


def _resolve_note_type_for_user(*, user_id: int, note_type_id: str | None = None, note_type_name: str | None = None) -> NoteType:
    query = NoteType.query.filter(
        or_(
            NoteType.user_id == user_id,
            NoteType.is_official == True,
            NoteType.publish_status == "published",
        )
    )
    if note_type_id:
        nt = query.filter(NoteType.id == note_type_id).first()
    elif note_type_name:
        nt = query.filter(NoteType.name == note_type_name).first()
    else:
        # Fallback to first available note type for user
        nt = query.order_by(NoteType.is_official.desc(), NoteType.created_at.asc()).first()

    if nt is None:
        raise RequestValidationError(
            f"Không tìm thấy NoteType ({note_type_id or note_type_name}).",
            field="note_type_id",
            status=404,
            code="NOTE_TYPE_NOT_FOUND",
        )
    return nt


def _owned_note_type_for_mutation(*, user_id: int, note_type_id: str) -> NoteType:
    nt = NoteType.query.filter_by(id=note_type_id).first()
    if nt is None:
        raise RequestValidationError(
            f"Không tìm thấy NoteType ID {note_type_id}.",
            field="note_type_id",
            status=404,
            code="NOTE_TYPE_NOT_FOUND",
        )
    if int(nt.user_id) != int(user_id):
        raise RequestValidationError(
            "Bạn không có quyền chỉnh sửa hoặc xóa NoteType này vì không phải là người sở hữu.",
            field="note_type_id",
            status=403,
            code="FORBIDDEN",
        )
    return nt
