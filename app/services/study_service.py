"""Study service representing the application-level boundary for flashcard studying."""

from __future__ import annotations

import json
from datetime import datetime

from models import db
from models.flashcard import Card
from models.card_progress import CardProgress
from app.services.anki_scheduler import _day_index, DeckOptions, default_deck_options
from app.repositories.study_repository import (
    apply_card_state_to_progress as _apply_card_state_to_progress,
)
from app.services.stats_overview import record_review_event
from app.routes.flashcards import (
    _touch_note_type_install_usage,
    _resolve_local_clone_deck_id_for_source_deck,
    _touch_deck_install_usage,
    _audit,
)
from app.services.flashcards_share_service import CloneDeckScope


class ConcurrentReviewError(Exception):
    """Raised when a card was already reviewed by another concurrent request."""
    pass


def _serialize_review_payload(payload: dict) -> str:
    try:
        return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return "{}"


def _compute_days_late(
    current_state,
    now: datetime,
    timezone_name: str,
    deck_options: DeckOptions | None = None,
) -> int | None:
    if str(getattr(current_state, "type", "") or "").strip().lower() != "review":
        return None
    options = deck_options or default_deck_options()
    due_day = getattr(current_state, "dueDay", None)
    if due_day is None:
        due_day = _day_index(
            getattr(current_state, "due", None) or now,
            options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )
    current_day = _day_index(
        now,
        options.dayBoundaryHourLocal,
        timezone_name=timezone_name,
    )
    return int(current_day - int(due_day))


def _resolve_local_deck_id(
    card: Card,
    clone_scope: CloneDeckScope | None,
    requested_scope_id: int | None,
) -> int | None:
    """Resolve the local deck id for usage tracking (single source of truth)."""
    local_deck_id = card.note.deck_id
    if clone_scope is not None:
        local_deck_id = (
            requested_scope_id
            if requested_scope_id is not None
            else _resolve_local_clone_deck_id_for_source_deck(
                install_id=clone_scope.install.id,
                source_deck_id=card.note.deck_id,
            )
        ) or clone_scope.install.local_deck_id
    return local_deck_id


def apply_study_answer_and_commit(
    *,
    user,
    card: Card,
    progress: CardProgress,
    expected_last_reviewed_at: datetime | None,
    current_state,
    updated_state,
    now: datetime,
    rating: str,
    review_mode: str,
    payload: dict,
    clone_scope: CloneDeckScope | None,
    requested_scope_id: int | None,
    timezone_name: str,
    deck_options: DeckOptions | None = None,
) -> int | None:
    """Applies the new study state to the progress record and commits the transaction.

    Returns the resolved local_deck_id_for_usage.
    Raises ConcurrentReviewError if the card was already reviewed concurrently.
    """
    # Optimistic lock: verify progress was not modified by a concurrent request.
    fresh = CardProgress.query.filter_by(
        user_id=user.id, card_id=card.id,
    ).first()
    if fresh is not None and fresh.last_reviewed_at != expected_last_reviewed_at:
        db.session.rollback()
        raise ConcurrentReviewError(
            "This card was already reviewed in another session. Loading next card."
        )

    _apply_card_state_to_progress(
        progress,
        updated_state,
        now,
        timezone_name=timezone_name,
        options=deck_options,
    )
    if getattr(updated_state, "leeched", False):
        current_tags = [str(tag).strip() for tag in (card.note.tags or []) if str(tag).strip()]
        normalized_tags = {tag.lower() for tag in current_tags}
        if "leech" not in normalized_tags:
            card.note.tags = current_tags + ["leech"]
    _touch_note_type_install_usage(user_id=user.id, installed_note_type_id=card.note.note_type_id, activity_at=now)

    local_deck_id_for_usage = _resolve_local_deck_id(card, clone_scope, requested_scope_id)

    if local_deck_id_for_usage is not None:
        _touch_deck_install_usage(user_id=user.id, local_deck_id=local_deck_id_for_usage, activity_at=now)

    review_event = record_review_event(
        user_id=user.id,
        card_id=card.id,
        deck_id=local_deck_id_for_usage,
        note_type_id=card.note.note_type_id,
        reviewed_at=now,
        duration_ms=payload.get("duration_ms"),
        rating=rating,
        mode=review_mode,
        scheduler_mode=str(getattr(updated_state, "schedulerMode", "legacy") or "legacy"),
        review_kind=str(getattr(updated_state, "reviewKind", "review") or "review"),
        queue_before=str(getattr(current_state, "type", "") or "").strip().lower() or None,
        queue_after=str(getattr(updated_state, "type", "") or "").strip().lower() or None,
        interval_days_before=float(getattr(current_state, "intervalDays", 0) or 0),
        interval_days_after=float(getattr(updated_state, "intervalDays", 0) or 0),
        due_day_before=getattr(current_state, "dueDay", None),
        due_day_after=getattr(updated_state, "dueDay", None),
        days_late=_compute_days_late(current_state, now, timezone_name, deck_options=deck_options),
        ease_factor_before=float(getattr(current_state, "ease", 0) or 0),
        ease_factor_after=float(getattr(updated_state, "ease", 0) or 0),
        memory_stability_before=(
            float(current_state.memoryState.stability)
            if getattr(current_state, "memoryState", None) is not None
            else None
        ),
        memory_stability_after=(
            float(updated_state.memoryState.stability)
            if getattr(updated_state, "memoryState", None) is not None
            else None
        ),
        memory_difficulty_before=(
            float(current_state.memoryState.difficulty)
            if getattr(current_state, "memoryState", None) is not None
            else None
        ),
        memory_difficulty_after=(
            float(updated_state.memoryState.difficulty)
            if getattr(updated_state, "memoryState", None) is not None
            else None
        ),
        leeched_after=bool(getattr(updated_state, "leeched", False)),
        suspended_after=bool(getattr(updated_state, "suspended", False)),
        payload_json=_serialize_review_payload(payload),
    )
    db.session.flush()
    if getattr(review_event, "id", None) is not None and hasattr(progress, "last_review_event_id"):
        progress.last_review_event_id = int(review_event.id)
    _audit("study.answer", {"card_id": card.id, "rating": rating})
    db.session.commit()
    return local_deck_id_for_usage
