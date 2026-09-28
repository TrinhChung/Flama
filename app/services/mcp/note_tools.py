"""MCP note operations: listing, search, create, update, delete, move, tags, batch, sync."""

from __future__ import annotations

import logging
import hashlib
from datetime import datetime, timezone
from typing import Any

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.services import (
    flashcard_content_service,
    note_sync_service,
    study_progress_lifecycle_mirror_service,
)
from app.services.anki_content_normalizer import normalize_anki_field_values
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_authority_read_service import (
    StudyAuthorityReadError,
    load_study_authority_card_reads,
)
from app.services import stats_overview
from app.services.mcp.base import (
    _resolve_deck_for_user,
    _resolve_note_type_for_user,
)
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_progress_subject import StudyProgressSubject
from models.user import User

logger = logging.getLogger(__name__)

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
    try:
        route = lock_study_authority_route(
            db.session,
            learner_user_id=user_id,
            allow_note_authority=True,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise RequestValidationError(
            str(exc), field="note_id", status=409, code=exc.code
        ) from exc
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
    authority_reads = None
    if route.mode_code == "NOTE":
        if not note.cards:
            db.session.rollback()
            raise RequestValidationError(
                "NOTE detail has no canonical Card siblings.",
                field="note_id",
                status=409,
                code="INCOMPLETE_AUTHORITY_COMPATIBILITY",
            )
        user = db.session.get(User, user_id)
        timezone_name = stats_overview.get_effective_timezone_name(
            getattr(user, "timezone", "UTC")
        )
        options = resolve_deck_options(user_id=user_id, deck_id=note.deck_id)
        try:
            authority_reads = load_study_authority_card_reads(
                db.session,
                learner_user_id=user_id,
                cards=tuple(note.cards),
                now_utc=datetime.now(timezone.utc).replace(tzinfo=None),
                timezone_name=timezone_name,
                deck_options_by_card_id={str(card.id): options for card in note.cards},
            )
            subject = StudyProgressSubject.query.filter_by(
                learner_user_id=user_id,
                logical_note_key=str(note.id).encode("utf-8"),
            ).one_or_none()
            if (
                subject is None
                or str(subject.live_note_id or "") != str(note.id)
                or int(subject.contributor_count) != len(note.cards)
            ):
                raise StudyAuthorityReadError(
                    "INCOMPLETE_AUTHORITY_COMPATIBILITY",
                    "NOTE detail Card topology differs from its canonical subject.",
                )
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code is None:
                raise
            db.session.rollback()
            raise RequestValidationError(
                str(exc), field="note_id", status=409, code=str(code)
            ) from exc

    cards_data: list[dict[str, Any]] = []
    for card in note.cards:
        if authority_reads is not None:
            read = authority_reads[str(card.id)]
            queue = read.availability.normalized_queue
            reps = int(read.state.reps or 0)
            lapses = int(read.state.lapses or 0)
            interval_days = float(read.state.intervalDays or 0)
            ease_factor = float(read.state.ease or 2.5)
            due_at = read.availability.due_at
        else:
            progress = CardProgress.query.filter_by(
                card_id=card.id, user_id=user_id
            ).first()
            queue = progress.queue if progress else "new"
            reps = int(progress.reps or 0) if progress else 0
            lapses = int(progress.lapses or 0) if progress else 0
            interval_days = float(progress.interval_days or 0) if progress else 0.0
            ease_factor = float(progress.ease_factor or 2.5) if progress else 2.5
            due_at = progress.due_at if progress else None
        cards_data.append(
            {
                "card_id": str(card.id),
                "template_id": str(card.template_id),
                "template_name": card.template.name if card.template else None,
                "queue": queue,
                "reps": reps,
                "lapses": lapses,
                "interval_days": interval_days,
                "ease_factor": ease_factor,
                "due_at": due_at.isoformat() if due_at else None,
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


def _auto_crawl_note_fields(
    *,
    user_id: int,
    note: Note,
    field_defs: list[FieldDef] | tuple[FieldDef, ...],
) -> bool:
    """Detect external image URLs in image/diagram/markdown fields and crawl them into local MediaAssets."""
    from app.services import image_crawl_service
    from flask import current_app
    from pathlib import Path

    upload_root_cfg = current_app.config.get("FLASHCARD_MEDIA_UPLOAD_ROOT")
    if not upload_root_cfg:
        return False
    upload_root = Path(upload_root_cfg).resolve()
    max_bytes = int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024))
    scanner = current_app.config.get("FLASHCARD_MEDIA_SCANNER")
    scan_enabled = bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False))

    field_map = {f.name: f for f in field_defs}
    current_values = dict(note.field_values or {})
    changed = False

    for field_name, value in list(current_values.items()):
        f_def = field_map.get(field_name)
        if not f_def or not isinstance(value, str) or not value.strip():
            continue
        val_str = value.strip()
        f_type = str(f_def.field_type or "text").strip().lower()

        if f_type in {"image", "diagram"} and val_str.startswith(("http://", "https://")):
            try:
                payload, _ = image_crawl_service.crawl_and_save_note_media(
                    user_id=user_id,
                    note_id=note.id,
                    field_name=field_name,
                    url=val_str,
                    upload_root=upload_root,
                    max_bytes=max_bytes,
                    scanner=scanner,
                    scan_enabled=scan_enabled,
                    markdown_inline=False,
                )
                current_values[field_name] = payload["url"]
                changed = True
            except Exception as exc:
                logger.warning("MCP auto-crawl image failed for note %s field %s: %s", note.id, field_name, exc)

        elif f_type == "markdown" and ("http://" in val_str or "https://" in val_str):
            try:
                result = image_crawl_service.crawl_and_rewrite_markdown_media(
                    user_id=user_id,
                    note_id=note.id,
                    markdown_text=val_str,
                    field_name=field_name,
                    upload_root=upload_root,
                    max_bytes=max_bytes,
                    scanner=scanner,
                    scan_enabled=scan_enabled,
                )
                if result.get("crawled_count", 0) > 0:
                    current_values[field_name] = result["rewritten_markdown"]
                    changed = True
            except Exception as exc:
                logger.warning("MCP auto-crawl markdown failed for note %s field %s: %s", note.id, field_name, exc)

    if changed:
        note.field_values = current_values
    return changed


def _auto_assign_sequence_field_if_needed(
    *,
    user_id: int,
    deck_id: int,
    note_type: NoteType,
    normalized_fields: dict[str, Any],
) -> None:
    """Auto-assign next sequential integer for ordinal fields (STT, No, Index, etc.) if missing."""
    sequence_field_names = {"stt", "no", "order", "index", "position", "stt_number"}
    for f in note_type.field_defs:
        if f.name.strip().lower() in sequence_field_names:
            current_val = str(normalized_fields.get(f.name) or "").strip()
            if not current_val:
                existing_notes = Note.query.filter_by(user_id=user_id, deck_id=deck_id).all()
                max_seq = 0
                for ex in existing_notes:
                    val_str = str((ex.field_values or {}).get(f.name) or "").strip()
                    if val_str.isdigit():
                        try:
                            max_seq = max(max_seq, int(val_str))
                        except ValueError:
                            pass
                normalized_fields[f.name] = str(max_seq + 1)


def create_note(
    *,
    user_id: int,
    note_data: dict[str, Any],
    auto_commit: bool = True,
) -> dict[str, Any]:
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
    try:
        authority_route = lock_study_authority_route(
            db.session,
            learner_user_id=int(user_id),
            allow_note_authority=True,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise RequestValidationError(
            str(exc),
            status=409,
            code=exc.code,
        ) from exc

    fields = note_data.get("fields", {})
    normalized_fields = normalize_anki_field_values(fields, tuple(note_type.field_defs))
    tags = list(note_data.get("tags") or [])
    allow_duplicate = bool(note_data.get("allow_duplicate", False))

    # Auto-assign sequence field (STT, No, etc.) if not provided by client
    _auto_assign_sequence_field_if_needed(
        user_id=user_id,
        deck_id=deck.id,
        note_type=note_type,
        normalized_fields=normalized_fields,
    )

    # Check for duplicate if primary identity field exists
    identity_field = next((f for f in note_type.field_defs if f.identity_role == "primary"), None)
    if not allow_duplicate and identity_field:
        identity_val = str(normalized_fields.get(identity_field.name) or "").strip().lower()
        if identity_val:
            existing = Note.query.filter_by(user_id=user_id, deck_id=deck.id).all()
            for ex in existing:
                if str((ex.field_values or {}).get(identity_field.name) or "").strip().lower() == identity_val:
                    raise RequestValidationError(
                        f"Thẻ với trường định danh '{identity_field.name}' có giá trị '{normalized_fields.get(identity_field.name)}' đã tồn tại trong deck '{deck.name}'. Vui lòng sử dụng update_note nếu muốn cập nhật thẻ.",
                        field=identity_field.name,
                        status=409,
                        code="NOTE_IDENTITY_CONFLICT",
                    )

    note = Note(
        note_type_id=note_type.id,
        user_id=user_id,
        deck_id=deck.id,
        field_values=normalized_fields,
        tags=tags,
    )
    db.session.add(note)
    db.session.flush()

    _auto_crawl_note_fields(user_id=user_id, note=note, field_defs=note_type.field_defs)

    templates = list(note_type.templates)
    if not templates:
        raise RequestValidationError(
            f"NoteType '{note_type.name}' (ID: {note_type.id}) không có template nào. Một NoteType hợp lệ để tạo thẻ phải có ít nhất một Template.",
            field="note_type_id",
            status=400,
            code="NOTE_TYPE_HAS_NO_TEMPLATE",
        )

    created_cards: list[dict[str, Any]] = []
    card_rows: list[Card] = []
    for template in templates:
        card = Card(note_id=note.id, template_id=template.id)
        db.session.add(card)
        db.session.flush()
        card_rows.append(card)
        created_cards.append(
            {
                "id": str(card.id),
                "template_id": str(template.id),
                "template_name": template.name,
            }
        )

    try:
        study_progress_lifecycle_mirror_service.materialize_new_note_authority(
            db.session,
            route=authority_route,
            note=note,
            cards=card_rows,
            provenance_code="NATIVE_MCP",
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise RequestValidationError(
            str(exc),
            status=409,
            code=exc.code,
        ) from exc

    from app.services import deck_working_tree_service

    deck_working_tree_service.mark_note_fields_changed(
        note=note,
        field_names=(note.field_values or {}).keys(),
        operation="add",
    )
    if auto_commit:
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

    original_deck_id = note.deck_id
    original_fields = dict(note.field_values or {})

    target_deck = (
        _resolve_deck_for_user(user_id=user_id, deck_id=deck_id)
        if deck_id is not None
        else None
    )
    from app.services import deck_working_tree_service

    if (
        target_deck is not None
        and original_deck_id != target_deck.id
        and deck_working_tree_service.note_has_shared_release_dependents(note)
    ):
        raise RequestValidationError(
            "A released shared note cannot move decks until release-aware membership moves are supported.",
            field="deck_id",
            status=409,
            code="SHARED_ENTITY_RETIRE_REQUIRED",
        )

    if tags is not None:
        next_tags = [str(t).strip() for t in tags if str(t).strip()]
        _ensure_note_tags_version_safe(note=note, next_tags=next_tags)
        note.tags = next_tags

    if target_deck is not None:
        note.deck_id = target_deck.id

    if fields is not None:
        current_fields = dict(note.field_values or {})
        current_fields.update(fields)
        note_type = note.note_type
        if note_type:
            normalized = normalize_anki_field_values(current_fields, tuple(note_type.field_defs))
            note.field_values = normalized
            _auto_crawl_note_fields(user_id=user_id, note=note, field_defs=note_type.field_defs)
        else:
            note.field_values = current_fields

    changed_field_names = {
        field_name
        for field_name in set(original_fields) | set(note.field_values or {})
        if original_fields.get(field_name) != (note.field_values or {}).get(field_name)
    }
    if original_deck_id != note.deck_id:
        all_field_names = set(original_fields) | set(note.field_values or {})
        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=[
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "remove",
                    "deck_id": original_deck_id,
                },
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "add",
                    "deck_id": note.deck_id,
                },
            ],
        )
    elif changed_field_names:
        deck_working_tree_service.mark_note_fields_changed(
            note=note,
            field_names=changed_field_names,
        )

    db.session.commit()
    return {
        "success": True,
        "note_id": str(note.id),
        "deck_id": int(note.deck_id) if note.deck_id else None,
        "fields": dict(note.field_values or {}),
        "tags": list(note.tags or []),
    }


def _ensure_note_tags_version_safe(
    *,
    note: Note,
    next_tags: list[str],
) -> None:
    if list(note.tags or []) == list(next_tags or []):
        return
    from app.services import deck_working_tree_service

    if not deck_working_tree_service.note_has_shared_release_dependents(note):
        return
    raise RequestValidationError(
        "Tags on a released shared note cannot change until note metadata is included in deck releases.",
        field="tags",
        status=409,
        code="SHARED_NOTE_METADATA_VERSIONING_REQUIRED",
    )


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

    from app.services import deck_working_tree_service

    if deck_working_tree_service.note_has_shared_release_dependents(note):
        raise RequestValidationError(
            "Published shared notes cannot be hard-deleted because learner history must be preserved.",
            field="note_id",
            status=409,
            code="SHARED_ENTITY_RETIRE_REQUIRED",
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

    try:
        flashcard_content_service.delete_note(
            user_id=user_id,
            note_id=str(note.id),
        )
    except flashcard_content_service.ContentApiError as exc:
        raise RequestValidationError(
            str(exc),
            field="note_id",
            status=exc.status,
            code=exc.error,
        ) from exc

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
    changed_tags_by_note_id: dict[str, list[str]] = {}

    for note in notes:
        current_tags = list(note.tags or [])
        modified = False
        for tag in clean_new_tags:
            if tag not in current_tags:
                current_tags.append(tag)
                modified = True
        if modified:
            _ensure_note_tags_version_safe(note=note, next_tags=current_tags)
            changed_tags_by_note_id[str(note.id)] = current_tags
        updated_ids.append(str(note.id))

    for note in notes:
        next_tags = changed_tags_by_note_id.get(str(note.id))
        if next_tags is not None:
            note.tags = next_tags

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
    changed_tags_by_note_id: dict[str, list[str]] = {}

    for note in notes:
        current_tags = list(note.tags or [])
        remaining = [t for t in current_tags if t not in tags_to_remove]
        if len(remaining) != len(current_tags):
            _ensure_note_tags_version_safe(note=note, next_tags=remaining)
            changed_tags_by_note_id[str(note.id)] = remaining
        updated_ids.append(str(note.id))

    for note in notes:
        next_tags = changed_tags_by_note_id.get(str(note.id))
        if next_tags is not None:
            note.tags = next_tags

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
    """Create multiple flashcard notes in a single atomic batch transaction."""
    if not notes:
        return {
            "created_count": 0,
            "note_ids": [],
        }

    created_note_ids: list[str] = []
    try:
        for item in notes:
            result = create_note(user_id=user_id, note_data=item, auto_commit=False)
            created_note_ids.append(str(result["note_id"]))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

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

    from app.services import deck_working_tree_service

    protected_note_ids = [
        str(note.id)
        for note in notes
        if deck_working_tree_service.note_has_shared_release_dependents(note)
    ]
    if protected_note_ids:
        raise RequestValidationError(
            "Published shared notes cannot be hard-deleted because learner history must be preserved.",
            field="note_ids",
            status=409,
            code="SHARED_ENTITY_RETIRE_REQUIRED",
        )

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

    if not notes:
        return {
            "success": True,
            "deleted_count": 0,
            "deleted_cards_count": 0,
            "deleted_note_ids": [],
            "failed_note_ids": failed_ids,
            "message": "KhÃ´ng cÃ³ note nÃ o Ä‘á»ƒ xÃ³a.",
        }

    from app.services import study_content_delete_service as content_delete

    deleted_note_ids = tuple(sorted(found_note_ids))
    operation_key = "mcp-note-batch-delete:" + hashlib.sha256(
        "\n".join(deleted_note_ids).encode("utf-8")
    ).hexdigest()
    # Every learner holding state on these Cards is fenced and planned together.
    try:
        authority_routes = content_delete.lock_content_delete_routes(
            db.session,
            actor_user_ids=(int(user_id),),
            card_ids=all_card_ids,
            deleted_note_ids=deleted_note_ids,
        )
        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=[
                {
                    "note": note,
                    "field_names": (note.field_values or {}).keys(),
                    "operation": "remove",
                }
                for note in notes
            ],
        )
        lifecycle_plan = content_delete.prepare_content_delete(
            db.session,
            routes=authority_routes,
            card_ids=all_card_ids,
            note_ids=deleted_note_ids,
            cancel_legacy_sessions=False,
        )
        content_delete.verify_content_delete_scope(
            db.session,
            routes=authority_routes,
            card_ids=all_card_ids,
            deleted_note_ids=deleted_note_ids,
        )
        if all_card_ids:
            CardProgress.query.filter(CardProgress.card_id.in_(all_card_ids)).delete(synchronize_session=False)
        content_delete.finalize_content_delete(
            lifecycle_plan,
            source_path="mcp.note_batch_delete",
            operation_key=operation_key,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise RequestValidationError(
            str(exc),
            field="note_ids",
            status=409,
            code=exc.code,
        ) from exc

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

    from app.services import deck_working_tree_service

    protected_move_ids = [
        str(note.id)
        for note in notes
        if note.deck_id != target_deck.id
        and deck_working_tree_service.note_has_shared_release_dependents(note)
    ]
    if protected_move_ids:
        raise RequestValidationError(
            "Released shared notes cannot move decks until release-aware membership moves are supported.",
            field="note_ids",
            status=409,
            code="SHARED_ENTITY_RETIRE_REQUIRED",
        )

    dirty_mutations: list[dict[str, Any]] = []
    for note in notes:
        original_deck_id = note.deck_id
        note.deck_id = target_deck.id
        if original_deck_id == note.deck_id:
            continue
        all_field_names = list((note.field_values or {}).keys())
        dirty_mutations.extend(
            [
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "remove",
                    "deck_id": original_deck_id,
                },
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "add",
                    "deck_id": note.deck_id,
                },
            ]
        )

    deck_working_tree_service.mark_note_field_batches_changed(
        mutations=dirty_mutations,
    )

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
