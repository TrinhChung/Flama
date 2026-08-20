"""MCP tool execution service providing rich flashcard, deck, and study tools."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from sqlalchemy import or_

from app.repositories import study_repository, vocabulary_repository
from app.repositories.deck_tree_query import collect_subtree_ids as _collect_deck_subtree_ids
from app.services import flashcard_content_service, note_sync_service, stats_overview
from app.services.anki_content_normalizer import normalize_anki_field_values
from app.services.anki_scheduler import applyAnswer, computeAnswerPreview
from app.services.deck_management_service import delete_deck_subtree
from app.services.flashcard_renderer import TemplateCompileError, render_template_pair
from app.services.mcp_preview_service import (
    compute_resource_version,
    consume_preview_token,
    create_preview_token,
    validate_preview_token,
)
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_service import apply_study_answer_and_commit
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User

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


def _compact_description(raw_value: str | None, *, max_length: int = 200) -> str | None:
    normalized = " ".join(str(raw_value or "").split())
    if not normalized:
        return None
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."


def _wrap_tool_result(structured_content: dict[str, Any]) -> dict[str, Any]:
    """Wrap structured content in standard MCP content and structuredContent envelope."""
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(structured_content, ensure_ascii=False, indent=2),
            }
        ],
        "structuredContent": structured_content,
    }


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


# ---------------------------------------------------------------------------
# 1. Deck Operations
# ---------------------------------------------------------------------------


def list_my_decks(*, user_id: int) -> list[dict[str, Any]]:
    """Return a compact list of decks owned or accessible by the user."""
    decks = vocabulary_repository.collect_accessible_browse_decks(
        user_id=user_id,
        admin_mode=False,
    )

    payload_items: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for deck_obj in decks:
        if deck_obj.id is None or int(deck_obj.id) in seen_ids:
            continue
        if int(deck_obj.owner_user_id or 0) != int(user_id):
            continue

        seen_ids.add(int(deck_obj.id))
        item: dict[str, Any] = {
            "deck_id": int(deck_obj.id),
            "name": deck_obj.name,
            "parent_id": int(deck_obj.parent_id) if deck_obj.parent_id is not None else None,
            "position": int(deck_obj.position or 0),
        }

        description = _compact_description(deck_obj.description)
        if description:
            item["description"] = description
        if deck_obj.created_at is not None:
            item["created_at"] = deck_obj.created_at.isoformat()

        payload_items.append(item)

    return payload_items


def get_deck_tree(*, user_id: int) -> list[dict[str, Any]]:
    """Return the hierarchical deck tree structure for the user."""
    return vocabulary_repository.build_browse_deck_tree_payload(
        user_id=user_id,
        admin_mode=False,
    )


def get_deck(*, user_id: int, deck_id: int) -> dict[str, Any]:
    """Get metadata and counts for a single deck owned by user, including default note type and note types in use."""
    deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
    if deck is None:
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    full_path = _build_deck_full_path(deck, user_id)
    note_count = Note.query.filter_by(deck_id=deck_id, user_id=user_id).count()
    card_count = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id == deck_id, Note.user_id == user_id)
        .count()
    )
    subdeck_count = Deck.query.filter_by(parent_id=deck_id, owner_user_id=user_id, deleted_at=None).count()

    default_nt = None
    if deck.note_type:
        default_nt = {
            "id": str(deck.note_type.id),
            "name": deck.note_type.name,
        }

    note_types_rows = (
        db.session.query(Note.note_type_id, db.func.count(Note.id))
        .filter(Note.deck_id == deck_id, Note.user_id == user_id)
        .group_by(Note.note_type_id)
        .all()
    )
    note_type_ids = [r[0] for r in note_types_rows if r[0]]
    note_type_map: dict[str, str] = {}
    if note_type_ids:
        nts = NoteType.query.filter(NoteType.id.in_(note_type_ids)).all()
        note_type_map = {nt.id: nt.name for nt in nts}

    note_types_in_use = [
        {
            "id": str(nt_id),
            "name": note_type_map.get(nt_id, "Unknown"),
            "notes_count": int(count),
        }
        for nt_id, count in note_types_rows
    ]

    return {
        "deck_id": int(deck.id),
        "name": deck.name,
        "full_path": full_path,
        "description": deck.description,
        "parent_id": int(deck.parent_id) if deck.parent_id is not None else None,
        "position": int(deck.position or 0),
        "default_note_type": default_nt,
        "note_types_in_use": note_types_in_use,
        "note_count": note_count,
        "card_count": card_count,
        "subdeck_count": subdeck_count,
        "created_at": deck.created_at.isoformat() if deck.created_at else None,
    }


def resolve_deck(*, user_id: int, path: str) -> dict[str, Any]:
    """Find a deck by hierarchical path without creating it if missing."""
    cleaned = str(path or "").strip()
    if not cleaned:
        return {
            "found": False,
            "deck_id": None,
            "name": None,
            "full_path": None,
            "parent_id": None,
        }

    tokens = [t.strip() for t in cleaned.replace("/", "::").split("::") if t.strip()]
    if not tokens:
        return {
            "found": False,
            "deck_id": None,
            "name": None,
            "full_path": None,
            "parent_id": None,
        }

    current_parent_id: int | None = None
    leaf_deck: Deck | None = None

    for token in tokens:
        candidates = Deck.query.filter_by(
            parent_id=current_parent_id,
            owner_user_id=user_id,
            deleted_at=None,
        ).all()

        # 1. Exact match
        matched = next((d for d in candidates if d.name == token), None)
        # 2. Case-insensitive fallback
        if matched is None:
            token_lower = token.lower()
            matched = next((d for d in candidates if d.name.lower() == token_lower), None)

        if matched is None:
            return {
                "found": False,
                "deck_id": None,
                "name": None,
                "full_path": None,
                "parent_id": None,
            }

        leaf_deck = matched
        current_parent_id = matched.id

    if leaf_deck is None:
        return {
            "found": False,
            "deck_id": None,
            "name": None,
            "full_path": None,
            "parent_id": None,
        }

    return {
        "found": True,
        "deck_id": int(leaf_deck.id),
        "name": leaf_deck.name,
        "full_path": _build_deck_full_path(leaf_deck, user_id),
        "parent_id": int(leaf_deck.parent_id) if leaf_deck.parent_id is not None else None,
        "description": leaf_deck.description,
    }


def batch_ensure_decks(*, user_id: int, paths: list[str]) -> dict[str, Any]:
    """Ensure multiple hierarchical deck paths exist, creating missing nodes idempotently."""
    results: dict[str, Any] = {}
    created_count = 0
    existing_count = 0

    for raw_path in paths:
        cleaned = str(raw_path or "").strip()
        if not cleaned:
            continue
        tokens = [t.strip() for t in cleaned.replace("/", "::").split("::") if t.strip()]
        if not tokens:
            continue

        upsert_res = vocabulary_repository.upsert_deck_path(
            parent_id=None,
            path_tokens=tokens,
            owner_user_id=user_id,
            admin_mode=False,
        )
        if upsert_res.final_deck is not None:
            final_deck = upsert_res.final_deck
            is_created = upsert_res.created_count > 0
            if is_created:
                created_count += 1
            else:
                existing_count += 1

            results[cleaned] = {
                "deck_id": int(final_deck.id),
                "name": final_deck.name,
                "full_path": _build_deck_full_path(final_deck, user_id),
                "parent_id": int(final_deck.parent_id) if final_deck.parent_id is not None else None,
                "created": is_created,
            }

    db.session.commit()

    return {
        "results": results,
        "total_requested": len(paths),
        "created_count": created_count,
        "existing_count": existing_count,
    }


def create_deck(
    *,
    user_id: int,
    name: str,
    parent_id: int | None = None,
    description: str | None = None,
    default_note_type_id: str | None = None,
) -> dict[str, Any]:
    """Create a new flashcard deck or subdeck."""
    if parent_id is not None:
        parent_deck = Deck.query.filter_by(id=parent_id, owner_user_id=user_id, deleted_at=None).first()
        if parent_deck is None:
            raise RequestValidationError(
                f"Không tìm thấy parent deck ID {parent_id} của bạn.",
                field="parent_id",
                status=404,
                code="PARENT_DECK_NOT_FOUND",
            )

    resolved_note_type = None
    if default_note_type_id:
        resolved_note_type = _resolve_note_type_for_user(user_id=user_id, note_type_id=default_note_type_id)

    cleaned_name = str(name).strip()
    if "::" in cleaned_name or "/" in cleaned_name:
        tokens = [t.strip() for t in cleaned_name.replace("/", "::").split("::") if t.strip()]
        upsert_res = vocabulary_repository.upsert_deck_path(
            parent_id=parent_id,
            path_tokens=tokens,
            owner_user_id=user_id,
            admin_mode=False,
        )
        if upsert_res.final_deck is None:
            raise RequestValidationError(
                f"Không thể tạo deck '{name}'.",
                field="name",
                status=400,
                code="DECK_CREATION_FAILED",
            )
        if description:
            upsert_res.final_deck.description = description
        if resolved_note_type:
            upsert_res.final_deck.note_type_id = resolved_note_type.id
        db.session.commit()
        return {
            "deck_id": int(upsert_res.final_deck.id),
            "name": upsert_res.final_deck.name,
            "parent_id": int(upsert_res.final_deck.parent_id) if upsert_res.final_deck.parent_id else None,
            "default_note_type": {"id": str(resolved_note_type.id), "name": resolved_note_type.name} if resolved_note_type else None,
            "created_count": upsert_res.created_count,
            "created_at": upsert_res.final_deck.created_at.isoformat() if upsert_res.final_deck.created_at else None,
        }

    existing = Deck.query.filter_by(
        parent_id=parent_id,
        name=cleaned_name,
        owner_user_id=user_id,
        deleted_at=None,
    ).first()
    if existing is not None:
        if resolved_note_type and existing.note_type_id != resolved_note_type.id:
            existing.note_type_id = resolved_note_type.id
            db.session.commit()
        return {
            "deck_id": int(existing.id),
            "name": existing.name,
            "parent_id": int(existing.parent_id) if existing.parent_id is not None else None,
            "description": existing.description,
            "default_note_type": {"id": str(existing.note_type.id), "name": existing.note_type.name} if existing.note_type else None,
            "created_at": existing.created_at.isoformat() if existing.created_at else None,
            "existing": True,
        }

    position = vocabulary_repository.next_deck_position(parent_id)
    new_deck = Deck(
        owner_user_id=user_id,
        parent_id=parent_id,
        name=cleaned_name,
        description=description,
        position=position,
        note_type_id=resolved_note_type.id if resolved_note_type else None,
    )
    db.session.add(new_deck)
    db.session.commit()

    return {
        "deck_id": int(new_deck.id),
        "name": new_deck.name,
        "parent_id": int(new_deck.parent_id) if new_deck.parent_id is not None else None,
        "description": new_deck.description,
        "default_note_type": {"id": str(resolved_note_type.id), "name": resolved_note_type.name} if resolved_note_type else None,
        "created_at": new_deck.created_at.isoformat() if new_deck.created_at else None,
        "existing": False,
    }


def update_deck(
    *,
    user_id: int,
    deck_id: int,
    name: str | None = None,
    description: str | None = None,
    parent_id: int | None = None,
    update_parent: bool = False,
    default_note_type_id: str | None = None,
    update_default_note_type: bool = False,
) -> dict[str, Any]:
    """Update a deck's name, description, parent, or default note type."""
    deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
    if deck is None:
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    if name is not None:
        deck.name = name
    if description is not None:
        deck.description = description
    if update_parent:
        if parent_id == deck.id:
            raise RequestValidationError(
                "Một deck không thể làm parent của chính nó.",
                field="parent_id",
                status=400,
                code="CYCLIC_PARENT_ERROR",
            )
        if parent_id is not None:
            parent_deck = Deck.query.filter_by(id=parent_id, owner_user_id=user_id, deleted_at=None).first()
            if parent_deck is None:
                raise RequestValidationError(
                    f"Không tìm thấy parent deck ID {parent_id} của bạn.",
                    field="parent_id",
                    status=404,
                    code="PARENT_DECK_NOT_FOUND",
                )
            subtree_ids = _collect_deck_subtree_ids(deck.id)
            if parent_id in subtree_ids:
                raise RequestValidationError(
                    "Không thể chuyển deck vào một subdeck của chính nó.",
                    field="parent_id",
                    status=400,
                    code="CYCLIC_PARENT_ERROR",
                )
        deck.parent_id = parent_id
        deck.position = vocabulary_repository.next_deck_position(parent_id)

    if update_default_note_type:
        if default_note_type_id is not None:
            resolved_nt = _resolve_note_type_for_user(user_id=user_id, note_type_id=default_note_type_id)
            deck.note_type_id = resolved_nt.id
        else:
            deck.note_type_id = None

    db.session.commit()
    return {
        "deck_id": int(deck.id),
        "name": deck.name,
        "description": deck.description,
        "parent_id": int(deck.parent_id) if deck.parent_id is not None else None,
        "position": int(deck.position or 0),
        "default_note_type": {"id": str(deck.note_type.id), "name": deck.note_type.name} if deck.note_type else None,
        "updated": True,
    }


def delete_deck(*, user_id: int, deck_id: int, confirm: bool = False) -> dict[str, Any]:
    """Delete a deck subtree owned by the user with safety confirmation guardrail."""
    deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
    if deck is None:
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    subtree_ids = _collect_deck_subtree_ids(deck.id)
    subdeck_count = max(0, len(subtree_ids) - 1)
    notes_count = Note.query.filter(Note.deck_id.in_(subtree_ids), Note.user_id == user_id).count()
    cards_count = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id.in_(subtree_ids), Note.user_id == user_id)
        .count()
    )

    if not confirm:
        return {
            "requires_confirmation": True,
            "action": "delete_deck",
            "deck_id": int(deck.id),
            "deck_name": deck.name,
            "impact": {
                "subdecks_to_delete": subdeck_count,
                "notes_to_delete": notes_count,
                "cards_to_delete": cards_count,
            },
            "warning": (
                f"⚠️ CẢNH BÁO XÓA DECK: Thao tác này sẽ xóa vĩnh viễn deck '{deck.name}' "
                f"cùng {subdeck_count} subdeck(s), {notes_count} note(s), {cards_count} card(s) và toàn bộ tiến độ học tập. "
                "AI PHẢI giải thích rõ các mất mát này cho người dùng và yêu cầu người dùng phê duyệt trước. "
                "Chỉ gọi lại tool với 'confirm=true' khi người dùng đã xác nhận đồng ý."
            ),
        }

    action = delete_deck_subtree(deck_obj=deck, user_id=user_id, is_admin=False, purge=False)
    return {
        "success": True,
        "deck_id": deck_id,
        "action": action,
        "deleted_subdecks_count": subdeck_count,
        "deleted_notes_count": notes_count,
        "deleted_cards_count": cards_count,
        "message": f"Deck '{deck.name}' (ID: {deck_id}) đã được xóa thành công ({action}).",
    }


# ---------------------------------------------------------------------------
# 2. Note Listing, Reading & Search
# ---------------------------------------------------------------------------


def list_notes(
    *,
    user_id: int,
    deck_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    """List notes in a deck or across user's decks with pagination."""
    query = Note.query.filter(Note.user_id == user_id)
    if deck_id is not None:
        _resolve_deck_for_user(user_id=user_id, deck_id=deck_id)
        query = query.filter(Note.deck_id == deck_id)

    total = query.count()

    if sort_by == "updated_at":
        query = query.order_by(Note.updated_at.desc() if sort_dir == "desc" else Note.updated_at.asc())
    elif sort_by == "id":
        query = query.order_by(Note.id.desc() if sort_dir == "desc" else Note.id.asc())
    else:
        query = query.order_by(Note.created_at.desc() if sort_dir == "desc" else Note.created_at.asc())

    notes = query.offset(offset).limit(limit).all()

    decks_map = {d.id: d.name for d in Deck.query.filter_by(owner_user_id=user_id).all()}
    note_types_map = {nt.id: nt.name for nt in NoteType.query.all()}

    items: list[dict[str, Any]] = []
    for note in notes:
        items.append(
            {
                "note_id": str(note.id),
                "deck_id": int(note.deck_id) if note.deck_id else None,
                "deck_name": decks_map.get(note.deck_id) if note.deck_id else None,
                "note_type_id": str(note.note_type_id),
                "note_type_name": note_types_map.get(note.note_type_id),
                "fields": dict(note.field_values or {}),
                "tags": list(note.tags or []),
                "card_count": len(note.cards),
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None,
            }
        )

    return {
        "notes": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(items) < total),
    }


def get_note(*, user_id: int, note_id: str) -> dict[str, Any]:
    """Get full details of a single flashcard note with cards and learning state."""
    note = Note.query.filter_by(id=note_id, user_id=user_id).first()
    if note is None:
        raise RequestValidationError(
            f"Không tìm thấy note ID {note_id} của bạn.",
            field="note_id",
            status=404,
            code="NOTE_NOT_FOUND",
        )

    deck = Deck.query.filter_by(id=note.deck_id).first() if note.deck_id else None
    note_type = note.note_type

    cards_data: list[dict[str, Any]] = []
    for card in note.cards:
        progress = CardProgress.query.filter_by(card_id=card.id, user_id=user_id).first()
        cards_data.append(
            {
                "card_id": str(card.id),
                "template_id": str(card.template_id),
                "template_name": card.template.name if card.template else None,
                "queue": progress.queue if progress else "new",
                "reps": int(progress.reps or 0) if progress else 0,
                "lapses": int(progress.lapses or 0) if progress else 0,
                "interval_days": float(progress.interval_days or 0) if progress else 0.0,
                "ease_factor": float(progress.ease_factor or 2.5) if progress else 2.5,
                "due_at": progress.due_at.isoformat() if progress and progress.due_at else None,
            }
        )

    return {
        "note_id": str(note.id),
        "deck_id": int(note.deck_id) if note.deck_id else None,
        "deck_name": deck.name if deck else None,
        "note_type_id": str(note.note_type_id),
        "note_type_name": note_type.name if note_type else None,
        "fields": dict(note.field_values or {}),
        "tags": list(note.tags or []),
        "cards": cards_data,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def find_notes(
    *,
    user_id: int,
    query: str = "",
    deck_id: int | None = None,
    tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search flashcard notes by text keyword in fields or tags, with optional deck & tag filters."""
    base_query = Note.query.filter(Note.user_id == user_id)
    if deck_id is not None:
        base_query = base_query.filter(Note.deck_id == deck_id)

    notes = base_query.order_by(Note.updated_at.desc(), Note.created_at.desc()).all()
    search_term = str(query or "").strip().lower()
    tag_filter = str(tag or "").strip().lower() if tag else None

    decks_map = {d.id: d.name for d in Deck.query.filter_by(owner_user_id=user_id).all()}
    note_types_map = {nt.id: nt.name for nt in NoteType.query.all()}

    matching_notes: list[dict[str, Any]] = []
    for note in notes:
        field_values = dict(note.field_values or {})
        tags = list(note.tags or [])

        if tag_filter and not any(tag_filter == t.lower() for t in tags):
            continue

        matched = False
        if not search_term:
            matched = True
        elif any(search_term in str(val).lower() for val in field_values.values()):
            matched = True
        elif any(search_term in t.lower() for t in tags):
            matched = True

        if matched:
            matching_notes.append(
                {
                    "note_id": str(note.id),
                    "deck_id": int(note.deck_id) if note.deck_id else None,
                    "deck_name": decks_map.get(note.deck_id) if note.deck_id else None,
                    "note_type_id": str(note.note_type_id),
                    "note_type_name": note_types_map.get(note.note_type_id),
                    "fields": field_values,
                    "tags": tags,
                    "created_at": note.created_at.isoformat() if note.created_at else None,
                }
            )

    total_matches = len(matching_notes)
    paged = matching_notes[offset : offset + limit]

    return {
        "notes": paged,
        "total_matches": total_matches,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(paged) < total_matches),
    }


# ---------------------------------------------------------------------------
# 3. Note Mutations & Organization
# ---------------------------------------------------------------------------


def create_note(*, user_id: int, note_data: dict[str, Any]) -> dict[str, Any]:
    """Create a single flashcard note with cards for the user."""
    deck = _resolve_deck_for_user(
        user_id=user_id,
        deck_id=note_data.get("deck_id"),
        deck_name=note_data.get("deck_name"),
    )
    note_type = _resolve_note_type_for_user(
        user_id=user_id,
        note_type_id=note_data.get("note_type_id"),
        note_type_name=note_data.get("note_type_name"),
    )

    fields = note_data.get("fields", {})
    normalized_fields = normalize_anki_field_values(fields, tuple(note_type.field_defs))
    tags = list(note_data.get("tags") or [])
    allow_duplicate = bool(note_data.get("allow_duplicate", False))

    # Check for duplicate if primary identity field exists
    identity_field = next((f for f in note_type.field_defs if f.identity_role == "primary"), None)
    if not allow_duplicate and identity_field:
        identity_val = str(normalized_fields.get(identity_field.name) or "").strip().lower()
        if identity_val:
            existing = Note.query.filter_by(user_id=user_id, deck_id=deck.id).all()
            for ex in existing:
                if str((ex.field_values or {}).get(identity_field.name) or "").strip().lower() == identity_val:
                    # Update fields and return existing note
                    updated = False
                    fvals = dict(ex.field_values or {})
                    for k, v in normalized_fields.items():
                        if v and fvals.get(k) != v:
                            fvals[k] = v
                            updated = True
                    if updated:
                        ex.field_values = fvals
                        db.session.commit()
                    return {
                        "note_id": str(ex.id),
                        "deck_id": int(deck.id),
                        "deck_name": deck.name,
                        "updated_existing": True,
                        "cards": [{"id": str(c.id), "template_id": str(c.template_id)} for c in ex.cards],
                    }

    note = Note(
        note_type_id=note_type.id,
        user_id=user_id,
        deck_id=deck.id,
        field_values=normalized_fields,
        tags=tags,
    )
    db.session.add(note)
    db.session.flush()

    templates = list(note_type.templates)
    if not templates:
        raise RequestValidationError(
            f"NoteType '{note_type.name}' (ID: {note_type.id}) không có template nào. Một NoteType hợp lệ để tạo thẻ phải có ít nhất một Template.",
            field="note_type_id",
            status=400,
            code="NOTE_TYPE_HAS_NO_TEMPLATE",
        )

    created_cards: list[dict[str, Any]] = []
    for template in templates:
        card = Card(note_id=note.id, template_id=template.id)
        db.session.add(card)
        db.session.flush()
        created_cards.append(
            {
                "id": str(card.id),
                "template_id": str(template.id),
                "template_name": template.name,
            }
        )

    db.session.commit()
    return {
        "note_id": str(note.id),
        "deck_id": int(deck.id),
        "deck_name": deck.name,
        "updated_existing": False,
        "cards": created_cards,
    }


def update_note(
    *,
    user_id: int,
    note_id: str,
    fields: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    deck_id: int | None = None,
) -> dict[str, Any]:
    """Update an existing note's fields (partial), tags, or deck."""
    note = Note.query.filter_by(id=note_id, user_id=user_id).first()
    if note is None:
        raise RequestValidationError(
            f"Không tìm thấy note ID {note_id} của bạn.",
            field="note_id",
            status=404,
            code="NOTE_NOT_FOUND",
        )

    if deck_id is not None:
        target_deck = _resolve_deck_for_user(user_id=user_id, deck_id=deck_id)
        note.deck_id = target_deck.id

    if tags is not None:
        note.tags = [str(t).strip() for t in tags if str(t).strip()]

    if fields is not None:
        current_fields = dict(note.field_values or {})
        current_fields.update(fields)
        note_type = note.note_type
        if note_type:
            normalized = normalize_anki_field_values(current_fields, tuple(note_type.field_defs))
            note.field_values = normalized
        else:
            note.field_values = current_fields

    db.session.commit()
    return {
        "success": True,
        "note_id": str(note.id),
        "deck_id": int(note.deck_id) if note.deck_id else None,
        "fields": dict(note.field_values or {}),
        "tags": list(note.tags or []),
    }


def delete_note(*, user_id: int, note_id: str, confirm: bool = False) -> dict[str, Any]:
    """Permanently delete a note and its associated cards with safety confirmation guardrail."""
    note = Note.query.filter_by(id=note_id, user_id=user_id).first()
    if note is None:
        raise RequestValidationError(
            f"Không tìm thấy note ID {note_id} của bạn.",
            field="note_id",
            status=404,
            code="NOTE_NOT_FOUND",
        )

    card_ids = [c.id for c in note.cards]
    deck = Deck.query.filter_by(id=note.deck_id).first() if note.deck_id else None

    if not confirm:
        return {
            "requires_confirmation": True,
            "action": "delete_note",
            "note_id": str(note_id),
            "impact": {
                "deck_id": int(note.deck_id) if note.deck_id else None,
                "deck_name": deck.name if deck else None,
                "fields": dict(note.field_values or {}),
                "tags": list(note.tags or []),
                "cards_to_delete": len(card_ids),
            },
            "warning": (
                f"⚠️ CẢNH BÁO XÓA NOTE: Thao tác này sẽ xóa vĩnh viễn note '{note_id}' "
                f"cùng {len(card_ids)} card(s) và tiến độ học tập liên quan. "
                "AI PHẢI hiển thị nội dung note này cho người dùng và yêu cầu người dùng xác nhận. "
                "Chỉ gọi lại tool với 'confirm=true' khi người dùng đã phê duyệt rõ ràng."
            ),
        }

    if card_ids:
        CardProgress.query.filter(CardProgress.card_id.in_(card_ids)).delete(synchronize_session=False)

    db.session.delete(note)
    db.session.commit()

    return {
        "success": True,
        "note_id": str(note_id),
        "deleted_cards_count": len(card_ids),
        "message": f"Note '{note_id}' và {len(card_ids)} card(s) đã được xóa thành công.",
    }


def move_note(*, user_id: int, note_id: str, deck_id: int) -> dict[str, Any]:
    """Move a note to a target deck."""
    res = update_note(user_id=user_id, note_id=note_id, deck_id=deck_id)
    return {
        "success": True,
        "note_id": str(note_id),
        "deck_id": int(res["deck_id"]),
    }


def add_tags(*, user_id: int, note_ids: list[str], tags: list[str]) -> dict[str, Any]:
    """Append tags to specified notes without overwriting existing tags."""
    notes = Note.query.filter(Note.id.in_(note_ids), Note.user_id == user_id).all()
    if not notes:
        raise RequestValidationError(
            "Không tìm thấy notes nào phù hợp.",
            field="note_ids",
            status=404,
            code="NOTES_NOT_FOUND",
        )

    clean_new_tags = [str(t).strip() for t in tags if str(t).strip()]
    updated_ids: list[str] = []

    for note in notes:
        current_tags = list(note.tags or [])
        modified = False
        for tag in clean_new_tags:
            if tag not in current_tags:
                current_tags.append(tag)
                modified = True
        if modified:
            note.tags = current_tags
        updated_ids.append(str(note.id))

    db.session.commit()
    return {
        "success": True,
        "updated_count": len(updated_ids),
        "note_ids": updated_ids,
        "added_tags": clean_new_tags,
    }


def remove_tags(*, user_id: int, note_ids: list[str], tags: list[str]) -> dict[str, Any]:
    """Remove specific tags from notes."""
    notes = Note.query.filter(Note.id.in_(note_ids), Note.user_id == user_id).all()
    if not notes:
        raise RequestValidationError(
            "Không tìm thấy notes nào phù hợp.",
            field="note_ids",
            status=404,
            code="NOTES_NOT_FOUND",
        )

    tags_to_remove = set(str(t).strip() for t in tags if str(t).strip())
    updated_ids: list[str] = []

    for note in notes:
        current_tags = list(note.tags or [])
        remaining = [t for t in current_tags if t not in tags_to_remove]
        if len(remaining) != len(current_tags):
            note.tags = remaining
        updated_ids.append(str(note.id))

    db.session.commit()
    return {
        "success": True,
        "updated_count": len(updated_ids),
        "note_ids": updated_ids,
        "removed_tags": list(tags_to_remove),
    }


# ---------------------------------------------------------------------------
# 4. Batch Operations
# ---------------------------------------------------------------------------


def batch_create_notes(*, user_id: int, notes: list[dict[str, Any]]) -> dict[str, Any]:
    """Create multiple flashcard notes in a single batch."""
    created_note_ids: list[str] = []
    for item in notes:
        result = create_note(user_id=user_id, note_data=item)
        created_note_ids.append(str(result["note_id"]))

    return {
        "created_count": len(created_note_ids),
        "note_ids": created_note_ids,
    }


def batch_update_notes(*, user_id: int, notes: list[dict[str, Any]]) -> dict[str, Any]:
    """Update multiple notes in batch with partial fields support."""
    results: list[dict[str, Any]] = []
    updated_count = 0

    for item in notes:
        note_id = str(item.get("note_id") or "").strip()
        try:
            update_note(
                user_id=user_id,
                note_id=note_id,
                fields=item.get("fields"),
                tags=item.get("tags"),
                deck_id=item.get("deck_id"),
            )
            results.append({"note_id": note_id, "success": True, "error": None})
            updated_count += 1
        except Exception as exc:
            results.append({"note_id": note_id, "success": False, "error": str(exc)})

    return {
        "updated_count": updated_count,
        "total_requested": len(notes),
        "results": results,
    }


def batch_delete_notes(*, user_id: int, note_ids: list[str], confirm: bool = False) -> dict[str, Any]:
    """Delete multiple notes and their cards in batch with safety confirmation guardrail."""
    notes = Note.query.filter(Note.id.in_(note_ids), Note.user_id == user_id).all()
    found_note_ids = {str(n.id) for n in notes}

    all_card_ids: list[str] = []
    for note in notes:
        all_card_ids.extend([c.id for c in note.cards])

    failed_ids = [nid for nid in note_ids if nid not in found_note_ids]

    if not confirm:
        return {
            "requires_confirmation": True,
            "action": "batch_delete_notes",
            "impact": {
                "requested_count": len(note_ids),
                "found_notes_to_delete": len(notes),
                "total_cards_to_delete": len(all_card_ids),
                "not_found_note_ids": failed_ids,
            },
            "warning": (
                f"⚠️ CẢNH BÁO XÓA HÀNG LOẠT: Thao tác này sẽ xóa vĩnh viễn {len(notes)} note(s) "
                f"cùng {len(all_card_ids)} card(s) và tiến độ học tập liên quan. "
                "AI PHẢI thông báo số lượng cụ thể cho người dùng và yêu cầu người dùng xác nhận. "
                "Chỉ gọi lại tool với 'confirm=true' khi người dùng đã phê duyệt rõ ràng."
            ),
        }

    if all_card_ids:
        CardProgress.query.filter(CardProgress.card_id.in_(all_card_ids)).delete(synchronize_session=False)

    for note in notes:
        db.session.delete(note)

    db.session.commit()

    return {
        "success": True,
        "deleted_count": len(notes),
        "deleted_cards_count": len(all_card_ids),
        "deleted_note_ids": list(found_note_ids),
        "failed_note_ids": failed_ids,
        "message": f"Đã xóa thành công {len(notes)} notes và {len(all_card_ids)} cards.",
    }


def batch_move_notes(*, user_id: int, note_ids: list[str], deck_id: int) -> dict[str, Any]:
    """Move multiple notes to a target deck."""
    target_deck = _resolve_deck_for_user(user_id=user_id, deck_id=deck_id)
    notes = Note.query.filter(Note.id.in_(note_ids), Note.user_id == user_id).all()
    found_note_ids = {str(n.id) for n in notes}

    for note in notes:
        note.deck_id = target_deck.id

    db.session.commit()
    failed_ids = [nid for nid in note_ids if nid not in found_note_ids]

    return {
        "moved_count": len(notes),
        "target_deck_id": target_deck.id,
        "target_deck_name": target_deck.name,
        "moved_note_ids": list(found_note_ids),
        "failed_note_ids": failed_ids,
    }


def preview_note_sync(
    *,
    user_id: int,
    source_key: str | None = None,
    deck_id: int | None = None,
    deck_path: str | None = None,
    note_type_id: str | None = None,
    note_type_name: str | None = None,
    notes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Preview synchronization of external notes against existing records without mutating database."""
    return note_sync_service.preview_sync_notes(
        user_id=user_id,
        source_key=source_key,
        deck_id=deck_id,
        deck_path=deck_path,
        note_type_id=note_type_id,
        note_type_name=note_type_name,
        notes=notes,
    )


def sync_notes(
    *,
    user_id: int,
    source_key: str | None = None,
    deck_id: int | None = None,
    deck_path: str | None = None,
    note_type_id: str | None = None,
    note_type_name: str | None = None,
    notes: list[dict[str, Any]],
    stop_on_error: bool = False,
    ensure_decks: bool = True,
) -> dict[str, Any]:
    """Synchronize/upsert external notes into Flama decks with idempotency and external identity tracking."""
    return note_sync_service.execute_sync_notes(
        user_id=user_id,
        source_key=source_key,
        deck_id=deck_id,
        deck_path=deck_path,
        note_type_id=note_type_id,
        note_type_name=note_type_name,
        notes=notes,
        stop_on_error=stop_on_error,
        ensure_decks=ensure_decks,
    )


# ---------------------------------------------------------------------------
# 5. Study & Card Review Operations
# ---------------------------------------------------------------------------


def get_due_card_counts(*, user_id: int, deck_id: int | None = None) -> dict[str, Any]:
    """Return total due, new, review, and learning card counts."""
    now = datetime.utcnow()
    user = db.session.get(User, user_id)
    timezone_name = str(getattr(user, "timezone", "UTC") or "UTC")

    scoped_decks = vocabulary_repository.collect_accessible_browse_decks(
        user_id=user_id,
        admin_mode=False,
    )
    if deck_id is not None:
        target_decks = [d for d in scoped_decks if int(d.id or 0) == int(deck_id)]
    else:
        target_decks = scoped_decks

    deck_ids = [int(d.id) for d in target_decks if d.id is not None]
    if not deck_ids:
        return {
            "total_due": 0,
            "new_cards": 0,
            "review_cards": 0,
            "learn_cards": 0,
        }

    cards_query = db.session.query(Card).join(Note, Card.note_id == Note.id).filter(
        Note.user_id == user_id, Note.deck_id.in_(deck_ids)
    )
    new_count, learn_count, due_count = study_repository.query_study_queue_counts(
        cards_query,
        user_id=user_id,
        now=now,
        timezone_name=timezone_name,
    )

    return {
        "total_due": new_count + learn_count + due_count,
        "new_cards": new_count,
        "review_cards": due_count,
        "learn_cards": learn_count,
    }


def get_study_queue(*, user_id: int, deck_id: int | None = None, limit: int = 10) -> dict[str, Any]:
    """Retrieve cards due for study with rendered front/back & interval options."""
    now = datetime.utcnow()
    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(getattr(user, "timezone", "UTC"))

    counts = get_due_card_counts(user_id=user_id, deck_id=deck_id)

    scoped_decks = vocabulary_repository.collect_accessible_browse_decks(user_id=user_id, admin_mode=False)
    if deck_id is not None:
        _resolve_deck_for_user(user_id=user_id, deck_id=deck_id)
        target_decks = [d for d in scoped_decks if int(d.id or 0) == int(deck_id)]
    else:
        target_decks = scoped_decks

    deck_ids = [int(d.id) for d in target_decks if d.id is not None]
    if not deck_ids:
        return {"cards": [], "queue_counts": counts}

    cards_query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Note.user_id == user_id, Note.deck_id.in_(deck_ids))
    )

    # Fetch candidate cards
    candidate_cards = cards_query.all()
    actionable_cards: list[dict[str, Any]] = []

    for card in candidate_cards:
        if len(actionable_cards) >= limit:
            break
        note = card.note
        if not note or not note.note_type:
            continue

        progress = CardProgress.query.filter_by(card_id=card.id, user_id=user_id).first()
        deck_options = resolve_deck_options(user_id=user_id, deck_id=note.deck_id)
        card_state = study_repository.card_state_from_progress(
            progress,
            now,
            timezone_name=timezone_name,
            user_id=user_id,
            options=deck_options,
        )

        # Check if due/actionable
        is_actionable = False
        if card_state.type == "new":
            is_actionable = True
        elif card_state.type in ("learning", "relearning"):
            if card_state.due is None or card_state.due <= now:
                is_actionable = True
        elif card_state.type == "review":
            if card_state.dueDay is not None:
                today_idx = study_repository._today_day_index(
                    now=now,
                    timezone_name=timezone_name,
                    day_boundary_hour_local=deck_options.dayBoundaryHourLocal,
                )
                if card_state.dueDay <= today_idx:
                    is_actionable = True
            elif card_state.due is not None and card_state.due <= now:
                is_actionable = True

        if not is_actionable:
            continue

        intervals_preview = computeAnswerPreview(
            card_state,
            deck_options,
            now,
            timezone_name=timezone_name,
        )

        rendered = render_template_pair(
            template=card.template,
            field_defs=note.note_type.field_defs,
            field_values=note.field_values,
            media_assets=note.media_assets,
        )

        actionable_cards.append(
            {
                "card_id": str(card.id),
                "note_id": str(note.id),
                "deck_id": int(note.deck_id) if note.deck_id else None,
                "template_name": card.template.name if card.template else None,
                "queue": card_state.type,
                "front_html": rendered.get("front_html"),
                "back_html": rendered.get("back_html"),
                "fields": dict(note.field_values or {}),
                "intervals_preview": intervals_preview,
            }
        )

    return {
        "cards": actionable_cards,
        "queue_counts": counts,
    }


def get_card(*, user_id: int, card_id: str) -> dict[str, Any]:
    """Get single card detail with rendered HTML and scheduling intervals."""
    card = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Card.id == card_id, Note.user_id == user_id)
        .first()
    )
    if card is None or card.note is None:
        raise RequestValidationError(
            f"Không tìm thấy card ID {card_id} của bạn.",
            field="card_id",
            status=404,
            code="CARD_NOT_FOUND",
        )

    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(getattr(user, "timezone", "UTC"))
    now = datetime.utcnow()
    progress = CardProgress.query.filter_by(card_id=card.id, user_id=user_id).first()
    deck_options = resolve_deck_options(user_id=user_id, deck_id=card.note.deck_id)

    card_state = study_repository.card_state_from_progress(
        progress,
        now,
        timezone_name=timezone_name,
        user_id=user_id,
        options=deck_options,
    )
    intervals_preview = computeAnswerPreview(
        card_state,
        deck_options,
        now,
        timezone_name=timezone_name,
    )
    rendered = render_template_pair(
        template=card.template,
        field_defs=card.note.note_type.field_defs if card.note.note_type else [],
        field_values=card.note.field_values,
        media_assets=card.note.media_assets,
    )

    return {
        "card_id": str(card.id),
        "note_id": str(card.note.id),
        "deck_id": int(card.note.deck_id) if card.note.deck_id else None,
        "template_id": str(card.template_id),
        "template_name": card.template.name if card.template else None,
        "queue": card_state.type,
        "reps": int(card_state.reps or 0),
        "lapses": int(card_state.lapses or 0),
        "interval_days": float(card_state.intervalDays or 0),
        "ease_factor": float(card_state.ease or 2.5),
        "due_at": card_state.due.isoformat() if card_state.due else None,
        "front_html": rendered.get("front_html"),
        "back_html": rendered.get("back_html"),
        "fields": dict(card.note.field_values or {}),
        "tags": list(card.note.tags or []),
        "intervals_preview": intervals_preview,
    }


def submit_review(
    *,
    user_id: int,
    card_id: str,
    rating: str,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    """Submit a review answer rating ('again', 'hard', 'good', 'easy') to update card schedule."""
    card = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Card.id == card_id, Note.user_id == user_id)
        .first()
    )
    if card is None or card.note is None:
        raise RequestValidationError(
            f"Không tìm thấy card ID {card_id} của bạn.",
            field="card_id",
            status=404,
            code="CARD_NOT_FOUND",
        )

    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(getattr(user, "timezone", "UTC"))
    now = datetime.utcnow()
    progress = CardProgress.query.filter_by(user_id=user_id, card_id=card.id).first()
    deck_options = resolve_deck_options(user_id=user_id, deck_id=card.note.deck_id)

    if progress is None:
        progress = CardProgress(
            user_id=user_id,
            card_id=card.id,
            queue="new",
            step_index=0,
            due_at=None,
            due_day=None,
            interval_days=0,
            ease_factor=deck_options.startingEase,
            reps=0,
            lapses=0,
        )
        db.session.add(progress)
        db.session.flush()

    expected_last_reviewed_at = progress.last_reviewed_at
    current_state = study_repository.card_state_from_progress(
        progress,
        now,
        timezone_name=timezone_name,
        user_id=user_id,
        options=deck_options,
    )
    review_mode = stats_overview.normalize_review_mode(current_state.type)
    updated_state = applyAnswer(
        current_state,
        deck_options,
        now,
        rating,
        timezone_name=timezone_name,
    )

    service_payload = {
        "duration_ms": duration_ms,
        "timezone": timezone_name,
    }

    apply_study_answer_and_commit(
        user=user,
        card=card,
        progress=progress,
        expected_last_reviewed_at=expected_last_reviewed_at,
        current_state=current_state,
        updated_state=updated_state,
        now=now,
        rating=rating,
        review_mode=review_mode,
        payload=service_payload,
        clone_scope=None,
        requested_scope_id=card.note.deck_id,
        timezone_name=timezone_name,
        deck_options=deck_options,
    )

    return {
        "success": True,
        "card_id": str(card.id),
        "rating": rating,
        "previous_queue": current_state.type,
        "next_queue": updated_state.type,
        "interval_days": float(updated_state.intervalDays or 0),
        "due_at": updated_state.due.isoformat() if updated_state.due else None,
        "reps": int(updated_state.reps or 0),
        "lapses": int(updated_state.lapses or 0),
        "ease_factor": float(updated_state.ease or 2.5),
    }


# ---------------------------------------------------------------------------
# 6. Statistics Operations
# ---------------------------------------------------------------------------


def get_deck_stats(*, user_id: int, deck_id: int) -> dict[str, Any]:
    """Return learning and review stats for a specific deck."""
    deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
    if deck is None:
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    note_count = Note.query.filter_by(deck_id=deck_id, user_id=user_id).count()
    cards = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id == deck_id, Note.user_id == user_id)
        .all()
    )
    card_count = len(cards)

    due_counts = get_due_card_counts(user_id=user_id, deck_id=deck_id)

    # Progress breakdown
    card_ids = [c.id for c in cards]
    young_count = 0
    mature_count = 0
    if card_ids:
        progresses = CardProgress.query.filter(
            CardProgress.user_id == user_id, CardProgress.card_id.in_(card_ids)
        ).all()
        for p in progresses:
            if p.queue == "review":
                if float(p.interval_days or 0) >= 21:
                    mature_count += 1
                else:
                    young_count += 1

    return {
        "deck_id": int(deck.id),
        "deck_name": deck.name,
        "note_count": note_count,
        "card_count": card_count,
        "new_cards": due_counts["new_cards"],
        "learning_cards": due_counts["learn_cards"],
        "review_due_cards": due_counts["review_cards"],
        "total_due_today": due_counts["total_due"],
        "young_cards": young_count,
        "mature_cards": mature_count,
    }


def get_study_stats(*, user_id: int, year: int | None = None) -> dict[str, Any]:
    """Return user's overall study overview: streak, daily reviews, total decks/notes."""
    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(getattr(user, "timezone", "UTC"))

    overview = stats_overview.build_stats_overview(
        user_id=user_id,
        year=year,
        timezone_name=timezone_name,
    )

    total_decks = Deck.query.filter_by(owner_user_id=user_id, deleted_at=None).count()
    total_notes = Note.query.filter_by(user_id=user_id).count()
    total_cards = (
        Card.query.join(Note, Card.note_id == Note.id).filter(Note.user_id == user_id).count()
    )
    due_counts = get_due_card_counts(user_id=user_id)

    return {
        "current_streak_days": overview.get("current_streak", 0),
        "longest_streak_days": overview.get("longest_streak", 0),
        "reviewed_today_cards": overview.get("today_cards", 0),
        "study_time_today_minutes": overview.get("today_minutes", 0.0),
        "total_reviews_in_year": overview.get("total_cards", 0),
        "total_study_time_year_minutes": overview.get("total_minutes", 0.0),
        "total_decks": total_decks,
        "total_notes": total_notes,
        "total_cards": total_cards,
        "due_counts": due_counts,
    }


# ---------------------------------------------------------------------------
# 7. Note Type Schema
# ---------------------------------------------------------------------------


def list_note_types(*, user_id: int) -> list[dict[str, Any]]:
    """Return available note types (models) for the user."""
    note_types = (
        NoteType.query.filter(
            or_(
                NoteType.user_id == user_id,
                NoteType.is_official == True,
                NoteType.publish_status == "published",
            )
        )
        .order_by(NoteType.name.asc())
        .all()
    )

    items: list[dict[str, Any]] = []
    for nt in note_types:
        items.append(
            {
                "id": str(nt.id),
                "name": nt.name,
                "description": _compact_description(nt.description),
                "field_count": len(nt.field_defs),
                "template_count": len(nt.templates),
                "is_official": bool(nt.is_official),
                "is_owner": int(nt.user_id) == int(user_id),
            }
        )
    return items


def get_note_type_schema(*, user_id: int, note_type_id: str | None = None, name: str | None = None) -> dict[str, Any]:
    """Return comprehensive field definitions, validation metadata, and templates for a specific note type."""
    query = NoteType.query.filter(
        or_(
            NoteType.user_id == user_id,
            NoteType.is_official == True,
            NoteType.publish_status == "published",
        )
    )
    if note_type_id:
        nt = query.filter(NoteType.id == note_type_id).first()
    elif name:
        nt = query.filter(NoteType.name == name).first()
    else:
        nt = None

    if nt is None:
        raise RequestValidationError(
            f"Không tìm thấy NoteType phù hợp ({note_type_id or name}).",
            field="note_type_id",
            status=404,
            code="NOT_FOUND",
        )

    is_owner = int(nt.user_id) == int(user_id)
    sorted_field_defs = sorted(nt.field_defs, key=lambda item: item.position)
    sorted_templates = sorted(nt.templates, key=lambda item: item.position)

    fields = [
        {
            "id": str(f.id),
            "name": f.name,
            "field_type": f.field_type,
            "position": f.position,
            "required": bool(f.required),
            "identity_role": f.identity_role,
            "default": None,
            "editable": is_owner,
            "validation_constraints": {
                "allowed_types": ["text", "richtext", "markdown", "image", "audio", "diagram"],
                "required": bool(f.required),
                "is_primary_identity": f.identity_role == "primary",
                "max_length": 100000,
            },
        }
        for f in sorted_field_defs
    ]

    templates = [
        {
            "id": str(t.id),
            "name": t.name,
            "position": t.position,
            "is_default": bool(t.is_default),
            "front_html": t.front_html,
            "back_html": t.back_html,
            "shared_css": t.shared_css or "",
        }
        for t in sorted_templates
    ]

    return {
        "id": str(nt.id),
        "name": nt.name,
        "description": nt.description,
        "is_official": bool(nt.is_official),
        "is_owner": is_owner,
        "field_names": [f.name for f in sorted_field_defs],
        "fields": fields,
        "templates": templates,
        "sample_note_payload": {
            "deck_id": None,
            "note_type_id": str(nt.id),
            "fields": {f.name: f"<{f.name}>" for f in sorted_field_defs},
            "tags": [],
        },
    }


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


def create_note_type(
    *,
    user_id: int,
    name: str,
    description: str | None = None,
    fields: list[dict[str, Any]] | None = None,
    templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a new note type (model) with custom fields and templates."""
    cleaned_name = str(name or "").strip()
    if not cleaned_name:
        raise RequestValidationError("Tên NoteType là bắt buộc.", field="name", status=400, code="INVALID_PARAMS")

    existing = NoteType.query.filter_by(user_id=user_id, name=cleaned_name).first()
    if existing is not None:
        raise RequestValidationError(
            f"Note type '{cleaned_name}' đã tồn tại.",
            field="name",
            status=400,
            code="NOTE_TYPE_ALREADY_EXISTS",
        )

    note_type = NoteType(
        user_id=user_id,
        name=cleaned_name,
        description=str(description).strip() if description is not None else None,
    )
    db.session.add(note_type)
    db.session.flush()

    if not fields:
        fields = [
            {"name": "Word", "field_type": "text", "position": 0, "required": True, "identity_role": "primary"},
            {"name": "Meaning", "field_type": "text", "position": 1, "required": True, "identity_role": None},
        ]

    field_defs_objs: list[FieldDef] = []
    seen_names: set[str] = set()
    primary_count = 0
    for idx, f in enumerate(fields):
        f_name = str(f.get("name") or "").strip()
        if not f_name:
            db.session.rollback()
            raise RequestValidationError(f"Field name at index {idx} cannot be empty.", field="fields", status=400, code="INVALID_PARAMS")
        if f_name.lower() in seen_names:
            db.session.rollback()
            raise RequestValidationError(f"Duplicate field name: '{f_name}'.", field="fields", status=400, code="DUPLICATE_FIELD_NAME")
        seen_names.add(f_name.lower())

        f_type = str(f.get("field_type") or "text").strip().lower()
        if f_type not in {"text", "richtext", "markdown", "image", "audio", "diagram"}:
            db.session.rollback()
            raise RequestValidationError(f"Unsupported field_type: '{f_type}'.", field="fields", status=400, code="INVALID_FIELD_TYPE")

        identity_role = f.get("identity_role")
        if identity_role == "primary":
            primary_count += 1
            if primary_count > 1:
                db.session.rollback()
                raise RequestValidationError("Only one primary identity field allowed.", field="fields", status=400, code="MULTIPLE_PRIMARY_IDENTITY")
            if f_type != "text":
                db.session.rollback()
                raise RequestValidationError("Primary identity field must have type 'text'.", field="fields", status=400, code="INVALID_IDENTITY_TYPE")

        f_obj = FieldDef(
            note_type_id=note_type.id,
            name=f_name,
            field_type=f_type,
            position=int(f.get("position", idx)),
            required=True if identity_role == "primary" else bool(f.get("required", False)),
            identity_role=identity_role,
        )
        db.session.add(f_obj)
        field_defs_objs.append(f_obj)

    db.session.flush()

    if templates is not None and len(templates) == 0:
        db.session.rollback()
        raise RequestValidationError(
            "NoteType phải có ít nhất một Template.",
            field="templates",
            status=400,
            code="NOTE_TYPE_MUST_HAVE_TEMPLATES",
        )

    if not templates:
        first_name = field_defs_objs[0].name
        second_name = field_defs_objs[1].name if len(field_defs_objs) > 1 else first_name
        templates = [
            {
                "name": "Card 1",
                "front_html": f"{{{{{first_name}}}}}",
                "back_html": f"{{{{FrontSide}}}}\n<hr id=\"answer\">\n{{{{{second_name}}}}}",
                "shared_css": "",
                "position": 0,
            }
        ]

    for idx, t in enumerate(templates):
        t_name = str(t.get("name") or f"Card {idx + 1}").strip()
        front_html = str(t.get("front_html") or f"{{{{{field_defs_objs[0].name}}}}}").strip()
        back_html = str(t.get("back_html") or f"{{{{FrontSide}}}}\n<hr id=\"answer\">\n{{{{{field_defs_objs[0].name}}}}}").strip()
        shared_css = str(t.get("shared_css") or "").strip()

        t_obj = Template(
            note_type_id=note_type.id,
            name=t_name,
            front_html=front_html,
            back_html=back_html,
            shared_css=shared_css,
            position=int(t.get("position", idx)),
            is_default=(idx == 0),
        )

        try:
            render_template_pair(
                template=t_obj,
                field_defs=field_defs_objs,
                field_values={f.name: "sample" for f in field_defs_objs},
                preview_note_key="creation_check",
            )
        except Exception as exc:
            db.session.rollback()
            raise RequestValidationError(
                f"Lỗi cú pháp trong template '{t_name}': {str(exc)}",
                field="templates",
                status=400,
                code="TEMPLATE_SYNTAX_ERROR",
            ) from exc

        db.session.add(t_obj)

    db.session.commit()
    return get_note_type_schema(user_id=user_id, note_type_id=note_type.id)


def preview_note_type_update(
    *,
    user_id: int,
    note_type_id: str,
    name: str | None = None,
    description: str | None = None,
    fields: list[dict[str, Any]] | dict[str, Any] | None = None,
    templates: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze and preview the impact of modifying a note type, fields, or templates."""
    nt = _owned_note_type_for_mutation(user_id=user_id, note_type_id=note_type_id)

    notes_count = Note.query.filter_by(note_type_id=nt.id, user_id=user_id).count()
    cards_count = Card.query.join(Note, Card.note_id == Note.id).filter(Note.note_type_id == nt.id, Note.user_id == user_id).count()
    decks_rows = db.session.query(Deck.id, Deck.name).join(Note, Note.deck_id == Deck.id).filter(Note.note_type_id == nt.id, Note.user_id == user_id).distinct().all()
    affected_decks = [{"id": int(r[0]), "name": r[1]} for r in decks_rows]

    current_field_map = {f.name: f for f in nt.field_defs}
    current_field_ids = {f.id: f for f in nt.field_defs}
    current_template_map = {t.name: t for t in nt.templates}
    current_template_ids = {t.id: t for t in nt.templates}

    added_fields: list[dict[str, Any]] = []
    renamed_fields: list[dict[str, str]] = []
    removed_fields: list[str] = []
    modified_fields: list[dict[str, Any]] = []

    data_loss_possible = False
    template_regeneration_required = False
    validation_errors: list[str] = []
    warnings: list[str] = []

    # Parse Fields
    if fields is not None:
        if isinstance(fields, dict):
            for af in fields.get("added", []):
                added_fields.append({"name": af.get("name"), "field_type": af.get("field_type", "text")})
            for rf in fields.get("renamed", []):
                renamed_fields.append({"old_name": rf.get("old_name"), "new_name": rf.get("new_name")})
            for rm in fields.get("removed", []):
                removed_fields.append(str(rm))
            for mf in fields.get("modified", []):
                modified_fields.append(mf)
        elif isinstance(fields, list):
            new_names = set()
            for f in fields:
                f_name = f.get("name")
                f_id = f.get("id")
                old_name = f.get("old_name")
                new_names.add(f_name)

                if old_name and old_name in current_field_map and old_name != f_name:
                    renamed_fields.append({"old_name": old_name, "new_name": f_name})
                elif f_id and f_id in current_field_ids and current_field_ids[f_id].name != f_name:
                    renamed_fields.append({"old_name": current_field_ids[f_id].name, "new_name": f_name})
                elif f_name not in current_field_map and not old_name:
                    added_fields.append({"name": f_name, "field_type": f.get("field_type", "text")})

            renamed_old_names = {r["old_name"] for r in renamed_fields}
            for curr_name in current_field_map:
                if curr_name not in new_names and curr_name not in renamed_old_names:
                    removed_fields.append(curr_name)

    # Check data loss on removed fields
    for rem_f in removed_fields:
        if notes_count > 0:
            notes_with_data = 0
            for note in Note.query.filter_by(note_type_id=nt.id, user_id=user_id).all():
                if note.field_values and note.field_values.get(rem_f):
                    notes_with_data += 1
            if notes_with_data > 0:
                data_loss_possible = True
                warnings.append(
                    f"⚠️ Xóa trường '{rem_f}': Có {notes_with_data} note(s) đang chứa dữ liệu ở trường này. "
                    "Dữ liệu trong các trường này sẽ bị xóa vĩnh viễn khỏi các note."
                )
            else:
                warnings.append(f"Xóa trường '{rem_f}' (trường không chứa dữ liệu trong note nào).")

    # Parse Templates
    added_templates: list[str] = []
    updated_templates: list[str] = []
    removed_templates: list[str] = []

    if templates is not None:
        template_regeneration_required = True
        if isinstance(templates, dict):
            for at in templates.get("added", []):
                added_templates.append(at.get("name", "New Card"))
            for ut in templates.get("updated", []):
                updated_templates.append(ut.get("name", "Card"))
            for rt in templates.get("removed", []):
                removed_templates.append(str(rt))
        elif isinstance(templates, list):
            new_t_names = {t.get("name") for t in templates}
            for t in templates:
                t_name = t.get("name")
                t_id = t.get("id")
                if t_name not in current_template_map and not (t_id and t_id in current_template_ids):
                    added_templates.append(t_name)
                else:
                    updated_templates.append(t_name)
            for curr_t in current_template_map:
                if curr_t not in new_t_names:
                    removed_templates.append(curr_t)

    for rem_t in removed_templates:
        tmpl_obj = current_template_map.get(rem_t)
        if tmpl_obj:
            cards_affected = Card.query.filter_by(template_id=tmpl_obj.id).count()
            if cards_affected > 0:
                data_loss_possible = True
                warnings.append(
                    f"⚠️ Xóa template '{rem_t}': Sẽ xóa vĩnh viễn {cards_affected} card(s) và toàn bộ lịch sử học tập liên quan."
                )

    if renamed_fields:
        renamed_desc = ", ".join(f"{r['old_name']} -> {r['new_name']}" for r in renamed_fields)
        warnings.append(
            f"Đổi tên trường ({renamed_desc}): "
            f"Hệ thống sẽ tự động di chuyển dữ liệu trong {notes_count} note(s) sang tên trường mới mà không làm mất dữ liệu."
        )

    resource_version = compute_resource_version(
        resource_type="note_type",
        resource_id=nt.id,
        notes_count=notes_count,
        cards_count=cards_count,
        updated_at=nt.updated_at,
    )

    impact_summary = {
        "notes_count": notes_count,
        "cards_count": cards_count,
        "added_fields": len(added_fields),
        "renamed_fields": len(renamed_fields),
        "removed_fields": len(removed_fields),
        "added_templates": len(added_templates),
        "removed_templates": len(removed_templates),
        "data_loss_possible": data_loss_possible,
    }

    preview_id, expires_at = create_preview_token(
        user_id=user_id,
        action="update_note_type",
        resource_id=nt.id,
        resource_version=resource_version,
        impact_summary=impact_summary,
    )

    return {
        "preview_id": preview_id,
        "expires_at": expires_at,
        "resource_version": resource_version,
        "note_type_id": str(nt.id),
        "note_type_name": nt.name,
        "affected_notes": notes_count,
        "affected_cards": cards_count,
        "affected_decks": affected_decks,
        "changes": {
            "name_change": {"old": nt.name, "new": name} if (name and name != nt.name) else None,
            "description_change": bool(description is not None and description != nt.description),
            "added_fields": added_fields,
            "renamed_fields": renamed_fields,
            "removed_fields": removed_fields,
            "modified_fields": modified_fields,
            "added_templates": added_templates,
            "updated_templates": updated_templates,
            "removed_templates": removed_templates,
        },
        "data_loss_possible": data_loss_possible,
        "template_regeneration_required": template_regeneration_required,
        "validation_errors": validation_errors,
        "warnings": warnings,
        "requires_confirmation": data_loss_possible,
    }


def _detect_destructive_note_type_changes(
    *,
    nt: NoteType,
    fields: list[dict[str, Any]] | dict[str, Any] | None,
    templates: list[dict[str, Any]] | dict[str, Any] | None,
    notes_count: int,
    cards_count: int,
) -> tuple[bool, list[str]]:
    current_field_map = {f.name: f for f in nt.field_defs}
    current_field_ids = {f.id: f for f in nt.field_defs}
    current_template_map = {t.name: t for t in nt.templates}
    current_template_ids = {t.id: t for t in nt.templates}

    reasons: list[str] = []

    # Check removed fields
    removed_fields: list[str] = []
    if fields is not None:
        if isinstance(fields, dict):
            for rm in fields.get("removed", []):
                removed_fields.append(str(rm))
        elif isinstance(fields, list):
            new_names = set()
            renamed_old = set()
            for f in fields:
                f_name = f.get("name")
                f_id = f.get("id")
                old_name = f.get("old_name")
                new_names.add(f_name)
                if old_name and old_name in current_field_map and old_name != f_name:
                    renamed_old.add(old_name)
                elif f_id and f_id in current_field_ids and current_field_ids[f_id].name != f_name:
                    renamed_old.add(current_field_ids[f_id].name)
            for curr_name in current_field_map:
                if curr_name not in new_names and curr_name not in renamed_old:
                    removed_fields.append(curr_name)

    for rf in removed_fields:
        if notes_count > 0:
            reasons.append(f"Xóa trường '{rf}' khi có {notes_count} note(s) đang tồn tại")

    # Check removed templates
    removed_templates: list[str] = []
    if templates is not None:
        if isinstance(templates, dict):
            for rt in templates.get("removed", []):
                removed_templates.append(str(rt))
        elif isinstance(templates, list):
            new_t_names = {t.get("name") for t in templates}
            new_t_ids = {t.get("id") for t in templates if t.get("id")}
            for curr_name, curr_t in current_template_map.items():
                if curr_name not in new_t_names and curr_t.id not in new_t_ids:
                    removed_templates.append(curr_name)

    for rt in removed_templates:
        tmpl_obj = current_template_map.get(rt)
        if tmpl_obj:
            t_cards = Card.query.filter_by(template_id=tmpl_obj.id).count()
            if t_cards > 0 or cards_count > 0:
                reasons.append(f"Xóa template '{rt}' làm mất các thẻ card và lịch sử ôn tập")
        elif cards_count > 0:
            reasons.append(f"Xóa template '{rt}'")

    return bool(reasons), reasons


def update_note_type(
    *,
    user_id: int,
    note_type_id: str,
    name: str | None = None,
    description: str | None = None,
    fields: list[dict[str, Any]] | dict[str, Any] | None = None,
    templates: list[dict[str, Any]] | dict[str, Any] | None = None,
    preview_id: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Update a note type's schema, metadata, fields, or templates with data migration support."""
    nt = _owned_note_type_for_mutation(user_id=user_id, note_type_id=note_type_id)

    notes_count = Note.query.filter_by(note_type_id=nt.id, user_id=user_id).count()
    cards_count = Card.query.join(Note, Card.note_id == Note.id).filter(Note.note_type_id == nt.id, Note.user_id == user_id).count()

    is_destructive, destructive_reasons = _detect_destructive_note_type_changes(
        nt=nt,
        fields=fields,
        templates=templates,
        notes_count=notes_count,
        cards_count=cards_count,
    )

    if is_destructive:
        if not preview_id or not str(preview_id).strip():
            raise RequestValidationError(
                "Thao tác cập nhật NoteType này có khả năng gây mất dữ liệu ("
                + "; ".join(destructive_reasons)
                + "). Bắt buộc phải gọi preview_note_type_update trước để lấy preview_id và kiểm tra tác động.",
                field="preview_id",
                status=400,
                code="PREVIEW_REQUIRED",
            )
        if not confirm:
            raise RequestValidationError(
                "Thao tác cập nhật NoteType này có khả năng gây mất dữ liệu ("
                + "; ".join(destructive_reasons)
                + "). Bắt buộc phải có sự xác nhận của người dùng với confirm=true.",
                field="confirm",
                status=400,
                code="CONFIRMATION_REQUIRED",
            )

    current_resource_version = compute_resource_version(
        resource_type="note_type",
        resource_id=nt.id,
        notes_count=notes_count,
        cards_count=cards_count,
        updated_at=nt.updated_at,
    )

    if preview_id:
        is_valid, err_code, err_msg = validate_preview_token(
            preview_id=preview_id,
            user_id=user_id,
            action="update_note_type",
            resource_id=nt.id,
            current_resource_version=current_resource_version,
        )
        if not is_valid:
            raise RequestValidationError(
                err_msg or "Preview token không hợp lệ hoặc đã hết hạn.",
                field="preview_id",
                status=400 if err_code != "STALE_PREVIEW_ERROR" else 409,
                code=err_code or "INVALID_PREVIEW_TOKEN",
            )

    # 1. Update Name & Description
    if name is not None:
        clean_name = str(name).strip()
        if not clean_name:
            raise RequestValidationError("Tên NoteType không được để trống.", field="name", status=400, code="INVALID_PARAMS")
        if clean_name != nt.name:
            conflict = NoteType.query.filter_by(user_id=user_id, name=clean_name).first()
            if conflict:
                raise RequestValidationError(f"NoteType mang tên '{clean_name}' đã tồn tại.", field="name", status=400, code="DUPLICATE_NAME")
            nt.name = clean_name

    if description is not None:
        nt.description = str(description).strip() or None

    # 2. Update Fields
    if fields is not None:
        current_fields = {f.name: f for f in nt.field_defs}
        current_field_ids = {f.id: f for f in nt.field_defs}

        if isinstance(fields, dict):
            # Process delta format
            for ren in fields.get("renamed", []):
                old_name = ren.get("old_name")
                new_name = ren.get("new_name")
                if old_name and new_name and old_name in current_fields and old_name != new_name:
                    field_obj = current_fields[old_name]
                    field_obj.name = new_name
                    # Migrate data in notes
                    for note in Note.query.filter_by(note_type_id=nt.id, user_id=user_id).all():
                        if note.field_values and old_name in note.field_values:
                            fvals = dict(note.field_values)
                            fvals[new_name] = fvals.pop(old_name)
                            note.field_values = fvals

            for rem_name in fields.get("removed", []):
                if rem_name in current_fields:
                    field_obj = current_fields[rem_name]
                    for note in Note.query.filter_by(note_type_id=nt.id, user_id=user_id).all():
                        if note.field_values and rem_name in note.field_values:
                            fvals = dict(note.field_values)
                            fvals.pop(rem_name, None)
                            note.field_values = fvals
                    db.session.delete(field_obj)

            for add_f in fields.get("added", []):
                add_name = add_f.get("name")
                if add_name and add_name not in current_fields:
                    f_obj = FieldDef(
                        note_type_id=nt.id,
                        name=add_name,
                        field_type=add_f.get("field_type", "text"),
                        position=int(add_f.get("position", len(nt.field_defs))),
                        required=bool(add_f.get("required", False)),
                        identity_role=add_f.get("identity_role"),
                    )
                    db.session.add(f_obj)

            for mod_f in fields.get("modified", []):
                mod_name = mod_f.get("name")
                if mod_name in current_fields:
                    f_obj = current_fields[mod_name]
                    if "field_type" in mod_f:
                        f_obj.field_type = mod_f["field_type"]
                    if "required" in mod_f:
                        f_obj.required = bool(mod_f["required"])
                    if "position" in mod_f:
                        f_obj.position = int(mod_f["position"])
                    if "identity_role" in mod_f:
                        f_obj.identity_role = mod_f["identity_role"]

        elif isinstance(fields, list):
            # Process list format
            seen_names = set()
            new_field_names = {f.get("name") for f in fields if f.get("name")}
            for idx, f in enumerate(fields):
                f_name = f.get("name")
                f_id = f.get("id")
                old_name = f.get("old_name")

                if f_id and f_id in current_field_ids:
                    f_obj = current_field_ids[f_id]
                    if f_obj.name != f_name:
                        # Rename
                        prev_name = f_obj.name
                        f_obj.name = f_name
                        for note in Note.query.filter_by(note_type_id=nt.id, user_id=user_id).all():
                            if note.field_values and prev_name in note.field_values:
                                fvals = dict(note.field_values)
                                fvals[f_name] = fvals.pop(prev_name)
                                note.field_values = fvals
                    f_obj.field_type = f.get("field_type", f_obj.field_type)
                    f_obj.required = bool(f.get("required", f_obj.required))
                    f_obj.position = int(f.get("position", idx))
                    f_obj.identity_role = f.get("identity_role", f_obj.identity_role)
                    seen_names.add(f_name)
                elif old_name and old_name in current_fields:
                    f_obj = current_fields[old_name]
                    f_obj.name = f_name
                    for note in Note.query.filter_by(note_type_id=nt.id, user_id=user_id).all():
                        if note.field_values and old_name in note.field_values:
                            fvals = dict(note.field_values)
                            fvals[f_name] = fvals.pop(old_name)
                            note.field_values = fvals
                    f_obj.field_type = f.get("field_type", f_obj.field_type)
                    f_obj.required = bool(f.get("required", f_obj.required))
                    f_obj.position = int(f.get("position", idx))
                    f_obj.identity_role = f.get("identity_role", f_obj.identity_role)
                    seen_names.add(f_name)
                elif f_name in current_fields:
                    f_obj = current_fields[f_name]
                    f_obj.field_type = f.get("field_type", f_obj.field_type)
                    f_obj.required = bool(f.get("required", f_obj.required))
                    f_obj.position = int(f.get("position", idx))
                    f_obj.identity_role = f.get("identity_role", f_obj.identity_role)
                    seen_names.add(f_name)
                else:
                    # New field
                    f_obj = FieldDef(
                        note_type_id=nt.id,
                        name=f_name,
                        field_type=f.get("field_type", "text"),
                        position=int(f.get("position", idx)),
                        required=bool(f.get("required", False)),
                        identity_role=f.get("identity_role"),
                    )
                    db.session.add(f_obj)
                    seen_names.add(f_name)

            # Delete fields removed from list
            for curr_name, curr_f in current_fields.items():
                if curr_name not in new_field_names:
                    for note in Note.query.filter_by(note_type_id=nt.id, user_id=user_id).all():
                        if note.field_values and curr_name in note.field_values:
                            fvals = dict(note.field_values)
                            fvals.pop(curr_name, None)
                            note.field_values = fvals
                    db.session.delete(curr_f)

        db.session.flush()
        if not nt.field_defs:
            db.session.rollback()
            raise RequestValidationError(
                "NoteType phải có ít nhất một trường dữ liệu (field).",
                field="fields",
                status=400,
                code="NOTE_TYPE_MUST_HAVE_FIELDS",
            )

    # 3. Update Templates
    if templates is not None:
        current_templates = {t.name: t for t in nt.templates}
        current_template_ids = {t.id: t for t in nt.templates}

        if isinstance(templates, dict):
            for rem_name in templates.get("removed", []):
                t_obj = current_templates.get(str(rem_name))
                if t_obj:
                    Card.query.filter_by(template_id=t_obj.id).delete(synchronize_session=False)
                    db.session.delete(t_obj)

            for upd in templates.get("updated", []):
                t_id = upd.get("id")
                t_name = upd.get("name")
                t_obj = current_template_ids.get(t_id) if t_id else current_templates.get(t_name)
                if t_obj:
                    if "name" in upd:
                        t_obj.name = upd["name"]
                    if "front_html" in upd:
                        t_obj.front_html = upd["front_html"]
                    if "back_html" in upd:
                        t_obj.back_html = upd["back_html"]
                    if "shared_css" in upd:
                        t_obj.shared_css = upd["shared_css"]
                    if "position" in upd:
                        t_obj.position = int(upd["position"])

            for add_t in templates.get("added", []):
                t_name = add_t.get("name", "New Card")
                new_t = Template(
                    note_type_id=nt.id,
                    name=t_name,
                    front_html=str(add_t.get("front_html") or ""),
                    back_html=str(add_t.get("back_html") or ""),
                    shared_css=str(add_t.get("shared_css") or ""),
                    position=int(add_t.get("position", len(nt.templates))),
                    is_default=False,
                )
                db.session.add(new_t)
                db.session.flush()
                for note in Note.query.filter_by(note_type_id=nt.id, user_id=user_id).all():
                    db.session.add(Card(note_id=note.id, template_id=new_t.id))

        elif isinstance(templates, list):
            new_t_names = {t.get("name") for t in templates if t.get("name")}
            new_t_ids = {t.get("id") for t in templates if t.get("id")}
            for curr_name, curr_t in current_templates.items():
                if curr_name not in new_t_names and curr_t.id not in new_t_ids:
                    Card.query.filter_by(template_id=curr_t.id).delete(synchronize_session=False)
                    db.session.delete(curr_t)

            for idx, t in enumerate(templates):
                t_id = t.get("id")
                t_name = t.get("name") or f"Card {idx + 1}"
                t_obj = current_template_ids.get(t_id) if t_id else current_templates.get(t_name)

                if t_obj:
                    if "name" in t:
                        t_obj.name = t["name"]
                    if "front_html" in t:
                        t_obj.front_html = t["front_html"]
                    if "back_html" in t:
                        t_obj.back_html = t["back_html"]
                    if "shared_css" in t:
                        t_obj.shared_css = t["shared_css"]
                    if "position" in t:
                        t_obj.position = int(t["position"])
                else:
                    # Create new template and create cards for existing notes
                    new_t = Template(
                        note_type_id=nt.id,
                        name=t_name,
                        front_html=str(t.get("front_html") or ""),
                        back_html=str(t.get("back_html") or ""),
                        shared_css=str(t.get("shared_css") or ""),
                        position=int(t.get("position", idx)),
                        is_default=False,
                    )
                    db.session.add(new_t)
                    db.session.flush()
                    for note in Note.query.filter_by(note_type_id=nt.id, user_id=user_id).all():
                        db.session.add(Card(note_id=note.id, template_id=new_t.id))

        db.session.flush()
        if not nt.templates:
            db.session.rollback()
            raise RequestValidationError(
                "NoteType phải có ít nhất một Template.",
                field="templates",
                status=400,
                code="NOTE_TYPE_MUST_HAVE_TEMPLATES",
            )

    if preview_id:
        consume_preview_token(preview_id)

    db.session.commit()
    return get_note_type_schema(user_id=user_id, note_type_id=nt.id)


def delete_note_type(
    *,
    user_id: int,
    note_type_id: str,
    confirm: bool = False,
    preview_id: str | None = None,
) -> dict[str, Any]:
    """Delete a note type with 2-step confirmation and safety checks."""
    nt = _owned_note_type_for_mutation(user_id=user_id, note_type_id=note_type_id)

    notes_count = Note.query.filter_by(note_type_id=nt.id, user_id=user_id).count()
    cards_count = Card.query.join(Note, Card.note_id == Note.id).filter(Note.note_type_id == nt.id, Note.user_id == user_id).count()
    decks_rows = db.session.query(Deck.id, Deck.name).join(Note, Note.deck_id == Deck.id).filter(Note.note_type_id == nt.id, Note.user_id == user_id).distinct().all()
    affected_decks = [{"id": int(r[0]), "name": r[1]} for r in decks_rows]

    current_resource_version = compute_resource_version(
        resource_type="note_type",
        resource_id=nt.id,
        notes_count=notes_count,
        cards_count=cards_count,
        updated_at=nt.updated_at,
    )

    if not confirm:
        preview_token_id, expires_at = create_preview_token(
            user_id=user_id,
            action="delete_note_type",
            resource_id=nt.id,
            resource_version=current_resource_version,
            impact_summary={
                "notes_count": notes_count,
                "cards_count": cards_count,
                "affected_decks": affected_decks,
            },
        )

        can_delete = (notes_count == 0)
        warning_msg = (
            f"⚠️ CẢNH BÁO XÓA NOTE TYPE: Bạn đang chuẩn bị xóa NoteType '{nt.name}'. "
            if can_delete
            else (
                f"⚠️ KHÔNG THỂ XÓA: NoteType '{nt.name}' đang chứa {notes_count} note(s) và {cards_count} card(s) "
                f"thuộc {len(affected_decks)} deck(s). Theo business rule của hệ thống, không được xóa NoteType đang có notes. "
                "AI cần báo cho người dùng xóa hoặc di chuyển các notes trước."
            )
        )

        return {
            "requires_confirmation": True,
            "action": "delete_note_type",
            "preview_id": preview_token_id,
            "expires_at": expires_at,
            "resource_version": current_resource_version,
            "can_delete": can_delete,
            "impact": {
                "note_type_id": str(nt.id),
                "name": nt.name,
                "notes_count": notes_count,
                "cards_count": cards_count,
                "affected_decks": affected_decks,
            },
            "warning": warning_msg,
        }

    # If confirmed
    if preview_id:
        is_valid, err_code, err_msg = validate_preview_token(
            preview_id=preview_id,
            user_id=user_id,
            action="delete_note_type",
            resource_id=nt.id,
            current_resource_version=current_resource_version,
        )
        if not is_valid:
            raise RequestValidationError(
                err_msg or "Preview token không hợp lệ hoặc đã hết hạn.",
                field="preview_id",
                status=400 if err_code != "STALE_PREVIEW_ERROR" else 409,
                code=err_code or "INVALID_PREVIEW_TOKEN",
            )

    if notes_count > 0:
        raise RequestValidationError(
            f"Không thể xóa NoteType '{nt.name}' vì đang có {notes_count} notes sử dụng. Cần xóa hoặc di chuyển các notes trước khi xóa note type.",
            field="note_type_id",
            status=409,
            code="NOTE_TYPE_HAS_NOTES",
        )

    nt_name = nt.name
    nt_id = nt.id
    flashcard_content_service.delete_note_type(user_id=user_id, note_type_id=nt.id)

    if preview_id:
        consume_preview_token(preview_id)

    return {
        "success": True,
        "deleted": True,
        "note_type_id": str(nt_id),
        "note_type_name": nt_name,
        "message": f"NoteType '{nt_name}' đã được xóa thành công.",
    }


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

