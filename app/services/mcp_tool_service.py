"""MCP tool execution service providing rich flashcard, deck, and study tools."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from sqlalchemy import or_

from app.repositories import study_repository, vocabulary_repository
from app.services.anki_content_normalizer import normalize_anki_field_values
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User

MCP_PROTOCOL_VERSION = "2025-11-25"

LIST_MY_DECKS_TOOL_NAME = "list_my_decks"
GET_DECK_TREE_TOOL_NAME = "get_deck_tree"
LIST_NOTE_TYPES_TOOL_NAME = "list_note_types"
GET_NOTE_TYPE_SCHEMA_TOOL_NAME = "get_note_type_schema"
FIND_NOTES_TOOL_NAME = "find_notes"
CREATE_NOTE_TOOL_NAME = "create_note"
BATCH_CREATE_NOTES_TOOL_NAME = "batch_create_notes"
GET_DUE_CARD_COUNTS_TOOL_NAME = "get_due_card_counts"


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
    """Return field definitions and templates for a specific note type."""
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

    fields = [
        {
            "name": f.name,
            "field_type": f.field_type,
            "position": f.position,
            "required": bool(f.required),
            "identity_role": f.identity_role,
        }
        for f in sorted(nt.field_defs, key=lambda item: item.position)
    ]

    templates = [
        {
            "name": t.name,
            "position": t.position,
            "front_html": t.front_html,
            "back_html": t.back_html,
        }
        for t in sorted(nt.templates, key=lambda item: item.position)
    ]

    return {
        "id": str(nt.id),
        "name": nt.name,
        "description": nt.description,
        "fields": fields,
        "templates": templates,
    }


def find_notes(*, user_id: int, query: str, deck_id: int | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Search notes belonging to the user by text query."""
    base_query = Note.query.filter(Note.user_id == user_id)
    if deck_id is not None:
        base_query = base_query.filter(Note.deck_id == deck_id)

    notes = base_query.order_by(Note.updated_at.desc()).all()
    search_term = str(query or "").strip().lower()

    decks_map = {d.id: d.name for d in Deck.query.filter_by(owner_user_id=user_id).all()}
    note_types_map = {nt.id: nt.name for nt in NoteType.query.all()}

    results: list[dict[str, Any]] = []
    for note in notes:
        field_values = dict(note.field_values or {})
        tags = list(note.tags or [])
        matched = False

        if not search_term or any(search_term in str(val).lower() for val in field_values.values()):
            matched = True
        elif any(search_term in tag.lower() for tag in tags):
            matched = True

        if matched:
            results.append(
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
            if len(results) >= limit:
                break

    return results


def _resolve_deck_for_user(*, user_id: int, deck_id: int | None = None, deck_name: str | None = None) -> Deck:
    if deck_id is not None:
        deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id).first()
        if deck is not None:
            return deck
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )
    if deck_name and str(deck_name).strip():
        return vocabulary_repository.upsert_deck_path(
            user_id=user_id,
            deck_path=str(deck_name).strip(),
            lock=True,
        )
    raise RequestValidationError(
        "Cần chỉ định deck_id hoặc deck_name.",
        field="deck_id",
        status=400,
        code="INVALID_PARAMS",
    )


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
        tmpl = Template(
            note_type_id=note_type.id,
            name="Card 1",
            position=0,
            front_html="{{Front}}",
            back_html="{{Back}}",
        )
        db.session.add(tmpl)
        db.session.flush()
        templates = [tmpl]

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

    cards_query = db.session.query(Card).join(Note, Card.note_id == Note.id).filter(Note.deck_id.in_(deck_ids))
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

