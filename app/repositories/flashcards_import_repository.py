"""Import-focused controllers used by flashcards routes."""

from __future__ import annotations

from typing import Any

from app.services import flashcards_share
from app.services.flashcard_import import ImportValidationError, load_import_session
from models import db
from models.deck import Deck
from models.flashcard import DeckInstall, Note, NoteType


def collect_accessible_decks_for_import(*, user_id: int, admin_mode: bool) -> list[Deck]:
    if admin_mode:
        return (
            Deck.query.filter(
                db.or_(
                    Deck.owner_user_id == user_id,
                    Deck.owner_user_id.is_(None),
                )
            )
            .order_by(
                Deck.parent_id.isnot(None),
                Deck.position.asc(),
                Deck.created_at.asc(),
                Deck.id.asc(),
            )
            .all()
        )

    installs = DeckInstall.query.filter_by(user_id=user_id).all()
    installed_root_ids = {int(row.local_deck_id) for row in installs if row.local_deck_id}
    owned_deck_ids = {
        int(row[0])
        for row in db.session.query(Deck.id).filter(Deck.owner_user_id == user_id).all()
        if row and row[0] is not None
    }
    initial_visible_ids = installed_root_ids | owned_deck_ids
    if not initial_visible_ids:
        return []

    visible_ids: set[int] = set()
    frontier: set[int] = set(initial_visible_ids)
    while frontier:
        current_ids = {deck_id for deck_id in frontier if deck_id not in visible_ids}
        if not current_ids:
            break
        visible_ids.update(current_ids)
        child_rows = (
            db.session.query(Deck.id)
            .filter(Deck.parent_id.in_(current_ids))
            .all()
        )
        frontier = {int(row[0]) for row in child_rows if row and row[0] is not None}

    return (
        Deck.query.filter(Deck.id.in_(visible_ids))
        .order_by(
            Deck.parent_id.isnot(None),
            Deck.position.asc(),
            Deck.created_at.asc(),
            Deck.id.asc(),
        )
        .all()
    )


def deck_path_label(deck_obj: Deck, deck_map: dict[int, Deck]) -> str:
    parts: list[str] = []
    current = deck_obj
    seen: set[int] = set()
    while current and current.id not in seen:
        seen.add(current.id)
        parts.append(current.name)
        if current.parent_id is None:
            break
        current = deck_map.get(int(current.parent_id))
    return "::".join(reversed(parts)) if parts else deck_obj.name


def serialize_note_type_for_import(note_type: NoteType) -> dict[str, Any]:
    fields = [
        {
            "id": field_def.id,
            "name": field_def.name,
            "position": int(field_def.position or 0),
            "required": bool(field_def.required),
            "field_type": field_def.field_type,
        }
        for field_def in sorted(note_type.field_defs, key=lambda item: item.position)
    ]
    return {
        "id": note_type.id,
        "name": note_type.name,
        "fields": fields,
    }


def default_uniqueness_fields(note_type: NoteType) -> list[str]:
    fields = sorted(note_type.field_defs, key=lambda item: item.position)
    if not fields:
        return []

    priority = ["word", "front", "term", "expression", "vocabulary"]
    lowered_name_map = {field_def.name.lower(): field_def.name for field_def in fields}
    for key in priority:
        if key in lowered_name_map:
            return [lowered_name_map[key]]

    required = [field_def.name for field_def in fields if field_def.required]
    if required:
        return [required[0]]

    return [fields[0].name]


def infer_default_note_type_id_for_deck(*, deck_id: int | None, user_id: int) -> str | None:
    if deck_id is None:
        return None

    deck_obj = Deck.query.get(deck_id)
    if deck_obj and deck_obj.note_type_id:
        note_type = NoteType.query.filter_by(id=deck_obj.note_type_id, user_id=user_id).first()
        if note_type:
            return note_type.id

    query = db.session.query(Note.note_type_id).filter(
        Note.user_id == user_id,
        Note.deck_id == deck_id,
        Note.note_type_id.isnot(None),
    )
    note_type_ids = sorted({row[0] for row in query.all() if row[0]})
    if len(note_type_ids) == 1:
        return note_type_ids[0]
    return None


def resolve_import_execution_payload(
    *,
    payload: dict[str, Any],
    user_id: int,
    admin_mode: bool,
) -> tuple[dict[str, Any], NoteType, int]:
    token = (payload.get("token") or "").strip()
    if not token:
        raise ImportValidationError("Import token is required")

    session_meta = load_import_session(user_id=user_id, token=token)

    note_type_id = (payload.get("note_type_id") or "").strip()
    note_type = NoteType.query.filter_by(id=note_type_id, user_id=user_id).first()
    if note_type is None:
        raise ImportValidationError("Note type not found")

    target_deck_raw = payload.get("target_deck_id")
    if target_deck_raw in ("", None):
        raise ImportValidationError("target_deck_id is required")
    try:
        target_deck_id = int(target_deck_raw)
    except (TypeError, ValueError) as exc:
        raise ImportValidationError("target_deck_id must be an integer") from exc

    accessible_decks = collect_accessible_decks_for_import(
        user_id=user_id,
        admin_mode=admin_mode,
    )
    accessible_deck_ids = {deck.id for deck in accessible_decks}
    if target_deck_id not in accessible_deck_ids:
        raise ImportValidationError("Target deck is not accessible")

    deck_consistency_error = flashcards_share.validate_note_type_consistency_for_deck(
        deck_id=target_deck_id,
        note_type_id=note_type.id,
        user_id=user_id,
    )
    if deck_consistency_error:
        raise ImportValidationError(deck_consistency_error)

    return session_meta, note_type, target_deck_id
