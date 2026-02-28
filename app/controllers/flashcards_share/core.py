"""Share/marketplace business logic extracted from flashcards routes."""

from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime, timedelta

from types import SimpleNamespace

from typing import Any

from app.controllers import flashcards_marketplace_controller as marketplace_ctrl

from app.controllers.deck_controller import (
    collect_ancestor_ids,
    collect_subtree_ids,
)

from models import db

from models.card_progress import CardProgress

from models.deck import Deck

from models.flashcard import (
    Card,
    DeckCloneAddedFieldDef,
    DeckCloneDeckMap,
    DeckCloneFieldDefOverride,
    DeckCloneFieldOrderOverride,
    DeckCloneNoteFieldOverride,
    DeckInstall,
    DeckMarketplaceItem,
    DeckReview,
    FieldDef,
    Note,
    NoteType,
    NoteTypeInstall,
    NoteTypeReview,
    Template,
)

DEFAULT_VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}

class ShareControllerError(Exception):
    """Domain error for flashcard share/deck flows."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        error: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field
        self.error = error

def make_unique_note_type_name(user_id: int, base_name: str) -> str:
    candidate = base_name.strip() or "Installed NoteType"
    if not NoteType.query.filter_by(user_id=user_id, name=candidate).first():
        return candidate
    counter = 2
    while True:
        candidate_with_counter = f"{candidate} ({counter})"
        if not NoteType.query.filter_by(user_id=user_id, name=candidate_with_counter).first():
            return candidate_with_counter
        counter += 1

def resolve_single_note_type_for_deck(
    *,
    deck_id: int,
    owner_user_id: int | None = None,
) -> tuple[str | None, str | None]:
    query = db.session.query(Note.note_type_id).filter(Note.deck_id == deck_id)
    if owner_user_id is not None:
        query = query.filter(Note.user_id == owner_user_id)

    note_type_ids = sorted({row[0] for row in query.all() if row[0]})
    if not note_type_ids:
        return None, "Deck has no notes, cannot infer source_note_type_id."
    if len(note_type_ids) > 1:
        return None, "All notes in one deck must use the same template (note type)."

    resolved_note_type_id = note_type_ids[0]
    resolved_note_type = NoteType.query.get(resolved_note_type_id)
    if not resolved_note_type:
        return None, "Deck source note type not found."
    if not resolved_note_type.templates:
        return None, "Deck source note type has no templates."
    return resolved_note_type.id, None

def bind_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> str | None:
    if deck_item.source_deck_id is None:
        return "source_deck_id is required."

    if deck_item.source_deck_id is not None:
        inferred_note_type_id, infer_error = resolve_single_note_type_for_deck(
            deck_id=deck_item.source_deck_id,
            owner_user_id=deck_item.owner_user_id,
        )
        if infer_error and require_source_note_type and not (deck_item.source_note_type_id or "").strip():
            return infer_error
        if inferred_note_type_id:
            if deck_item.source_note_type_id and deck_item.source_note_type_id != inferred_note_type_id:
                return "source_note_type_id does not match notes inside source_deck_id."
            deck_item.source_note_type_id = inferred_note_type_id

    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        if require_source_note_type:
            return "source_note_type_id is required."
        return None

    source_note_type = NoteType.query.get(source_note_type_id)
    if not source_note_type:
        return "source_note_type_id not found."
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type with at least one template."
    return None

def validate_note_type_consistency_for_deck(
    *,
    deck_id: int | None,
    note_type_id: str,
    user_id: int,
    exclude_note_id: str | None = None,
) -> str | None:
    if deck_id is None:
        return None

    query = db.session.query(Note.note_type_id).filter(
        Note.deck_id == deck_id,
        Note.user_id == user_id,
    )
    if exclude_note_id:
        query = query.filter(Note.id != exclude_note_id)

    existing_note_type_ids = {row[0] for row in query.distinct().all() if row[0]}
    if not existing_note_type_ids:
        return None
    if existing_note_type_ids == {note_type_id}:
        return None
    return "All notes in one deck must use the same template (note type)."

def _next_deck_position(parent_deck_id: int | None) -> int:
    query = db.session.query(db.func.max(Deck.position))
    if parent_deck_id is None:
        max_pos = query.filter(Deck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(Deck.parent_id == parent_deck_id).scalar()
    return int(max_pos or 0) + 1

def sync_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> tuple[str | None, bool]:
    original_note_type_id = deck_item.source_note_type_id
    bind_error = bind_deck_item_source_note_type(
        deck_item,
        require_source_note_type=require_source_note_type,
    )
    changed = deck_item.source_note_type_id != original_note_type_id
    return bind_error, changed

def build_shared_deck_item_payload(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    sample_limit: int,
    deck_active_review_threshold: int = 3,
) -> dict[str, Any]:
    install = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    review = DeckReview.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    payload = marketplace_ctrl.serialize_deck_marketplace_item(deck_item)
    payload["is_installed"] = install is not None
    payload["installed_deck_id"] = install.local_deck_id if install else None
    payload["is_owner"] = deck_item.owner_user_id == user_id
    payload["can_rate"] = can_user_rate_deck(
        deck_item,
        user_id=user_id,
        deck_active_review_threshold=deck_active_review_threshold,
    )
    payload["my_review"] = (
        {
            "rating": review.rating,
            "comment": review.comment,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        }
        if review
        else None
    )

    source_note_type_payload = None
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if source_note_type_id:
        source_note_type = NoteType.query.get(source_note_type_id)
        if source_note_type:
            ordered_templates = sorted(
                source_note_type.templates,
                key=lambda item: (int(item.position or 0), str(item.name or "").lower()),
            )
            source_note_type_payload = {
                "id": source_note_type.id,
                "name": source_note_type.name,
                "title": source_note_type.name,
                "publish_status": source_note_type.publish_status,
                "templates": [
                    {
                        "id": template.id,
                        "name": template.name,
                        "position": int(template.position or 0),
                        "is_default": bool(template.is_default),
                    }
                    for template in ordered_templates
                ],
            }
    payload["source_note_type"] = source_note_type_payload
    payload["test_samples"] = marketplace_ctrl.build_shared_deck_test_samples(
        deck_item,
        limit=sample_limit,
    )
    payload["test_sample_limit"] = sample_limit
    return payload

def select_preview_note_for_shared_deck(
    deck_item: DeckMarketplaceItem,
    *,
    note_type_id: str,
    requested_note_id: str | None,
) -> Note | None:
    if deck_item.source_deck_id is None:
        return None

    deck_ids = collect_subtree_ids(deck_item.source_deck_id)
    if not deck_ids:
        return None

    if requested_note_id:
        query = Note.query.filter(
            Note.id == requested_note_id,
            Note.note_type_id == note_type_id,
            Note.deck_id.in_(deck_ids),
        )
        if deck_item.owner_user_id is not None:
            query = query.filter(Note.user_id == deck_item.owner_user_id)
        preview_note = query.first()
        if preview_note is not None:
            return preview_note

    query = Note.query.filter(
        Note.deck_id.in_(deck_ids),
        Note.note_type_id == note_type_id,
    )
    if deck_item.owner_user_id is not None:
        query = query.filter(Note.user_id == deck_item.owner_user_id)
    return query.order_by(Note.created_at.asc(), Note.id.asc()).first()

def _normalize_note_field_values_for_cutover(raw_values: dict | None) -> dict[str, str]:
    if not isinstance(raw_values, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw_values.items():
        key_name = str(key).strip()
        if not key_name:
            continue
        normalized[key_name] = "" if value is None else str(value)
    return normalized

def _deck_paths_for_cutover(root_deck_id: int) -> dict[tuple[int, ...], int]:
    deck_ids = collect_subtree_ids(root_deck_id)
    if not deck_ids:
        return {}
    deck_rows = Deck.query.filter(Deck.id.in_(deck_ids)).all()
    if not deck_rows:
        return {}
    children_by_parent: dict[int | None, list[Deck]] = {}
    for deck_obj in deck_rows:
        children_by_parent.setdefault(deck_obj.parent_id, []).append(deck_obj)
    for rows in children_by_parent.values():
        rows.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    path_to_deck: dict[tuple[int, ...], int] = {}

    def _walk(deck_id: int, path: tuple[int, ...]) -> None:
        path_to_deck[path] = deck_id
        for index, child in enumerate(children_by_parent.get(deck_id, [])):
            _walk(child.id, path + (index,))

    _walk(root_deck_id, ())
    return path_to_deck

def _pair_legacy_local_source_notes_for_cutover(
    *,
    install: DeckInstall,
    source_to_local_deck_id: dict[int, int],
    source_owner_user_id: int | None,
    source_note_type_id: str | None,
    snapshot_at: datetime | None,
) -> list[tuple[Note, Note]]:
    local_to_source = {
        int(local_deck_id): int(source_deck_id)
        for source_deck_id, local_deck_id in source_to_local_deck_id.items()
    }
    pairs: list[tuple[Note, Note]] = []

    for local_deck_id in sorted(local_to_source.keys()):
        source_deck_id = local_to_source[local_deck_id]
        local_notes = (
            Note.query.filter(
                Note.user_id == install.user_id,
                Note.deck_id == local_deck_id,
            )
            .order_by(Note.created_at.asc(), Note.id.asc())
            .all()
        )
        source_query = Note.query.filter(Note.deck_id == source_deck_id)
        if source_owner_user_id is not None:
            source_query = source_query.filter(Note.user_id == source_owner_user_id)
        if source_note_type_id:
            source_query = source_query.filter(Note.note_type_id == source_note_type_id)
        if snapshot_at is not None:
            source_query = source_query.filter(Note.created_at <= snapshot_at)
        source_notes = source_query.order_by(Note.created_at.asc(), Note.id.asc()).all()

        if len(local_notes) != len(source_notes):
            raise ShareControllerError(
                (
                    f"Install {install.id}: note count mismatch in deck pair "
                    f"(local_deck_id={local_deck_id}, source_deck_id={source_deck_id}, "
                    f"local={len(local_notes)}, source={len(source_notes)})."
                ),
                status=409,
            )
        pairs.extend(zip(local_notes, source_notes))

    return pairs

def _merge_card_progress_rows_for_cutover(
    *,
    user_id: int,
    local_card_id: str,
    source_card_id: str,
) -> int:
    moved_count = 0
    progress_rows = (
        CardProgress.query.filter_by(
            user_id=user_id,
            card_id=local_card_id,
        )
        .order_by(CardProgress.updated_at.desc(), CardProgress.id.desc())
        .all()
    )
    for row in progress_rows:
        target = CardProgress.query.filter_by(
            user_id=user_id,
            card_id=source_card_id,
        ).first()
        if target is None:
            row.card_id = source_card_id
            moved_count += 1
            continue

        row_newer = (row.updated_at or datetime.min) >= (target.updated_at or datetime.min)
        if row_newer:
            target.queue = row.queue
            target.step_index = row.step_index
            target.due_at = row.due_at
            target.due_day = row.due_day
            target.interval_days = row.interval_days
            target.is_suspended = bool(row.is_suspended)
            target.ease_factor = row.ease_factor
            target.last_reviewed_at = row.last_reviewed_at or target.last_reviewed_at
        target.reps = max(int(target.reps or 0), int(row.reps or 0))
        target.lapses = max(int(target.lapses or 0), int(row.lapses or 0))
        db.session.delete(row)
        moved_count += 1
    return moved_count

def _assert_cutover_note_equivalence(
    *,
    install: DeckInstall,
    pairs: list[tuple[Note, Note]],
    schema_view: CloneSchemaView,
) -> None:
    for local_note, source_note in pairs:
        migrated_values = _normalize_note_field_values_for_cutover(
            apply_clone_note_field_overrides(
                install=install,
                source_note=source_note,
                schema_view=schema_view,
            )
        )
        local_values = _normalize_note_field_values_for_cutover(local_note.field_values)
        if migrated_values != local_values:
            raise ShareControllerError(
                (
                    f"Install {install.id}: cutover mismatch for source_note_id={source_note.id}, "
                    f"local_note_id={local_note.id}."
                ),
                status=409,
            )

