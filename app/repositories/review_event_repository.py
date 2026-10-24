"""ReviewEvent persistence; analytics reads live in ``stats_query_repository``."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from models import db
from models.flashcard import ReviewEvent
# Registers capture/rollback/commit guards for canonical ReviewEvent writers.
from app.services import review_analytics_projection_service as _analytics_projection  # noqa: F401


def create_review_event_record(
    *,
    user_id: int,
    card_id: str,
    rating: str,
    mode: str,
    reviewed_at: datetime,
    duration_ms: int | None,
    deck_id: int | None,
    note_type_id: str | None,
    note_id: str | None = None,
    scheduler_preset_id: int | None = None,
    study_session_id: str | None = None,
    client_event_id: str | None = None,
    sequence_no: int | None = None,
    scheduler_algorithm: str | None = None,
    algorithm_version: str | None = None,
    scheduler_config_hash: str | None = None,
    scheduler_mode: str = "legacy",
    review_kind: str = "review",
    queue_before: str | None = None,
    queue_after: str | None = None,
    interval_days_before: float | None = None,
    interval_days_after: float | None = None,
    due_day_before: int | None = None,
    due_day_after: int | None = None,
    days_late: int | None = None,
    ease_factor_before: float | None = None,
    ease_factor_after: float | None = None,
    memory_stability_before: float | None = None,
    memory_stability_after: float | None = None,
    memory_difficulty_before: float | None = None,
    memory_difficulty_after: float | None = None,
    leeched_after: bool = False,
    suspended_after: bool = False,
    payload_json: str = "{}",
    session: Session | None = None,
) -> ReviewEvent:
    event = ReviewEvent(
        user_id=user_id,
        card_id=str(card_id),
        # Callers holding the Card stamp its Note; otherwise the before_flush
        # hook resolves it (Phase 6, D6-07).
        note_id=str(note_id) if note_id else None,
        deck_id=deck_id,
        note_type_id=note_type_id,
        scheduler_preset_id=scheduler_preset_id,
        study_session_id=study_session_id,
        client_event_id=client_event_id,
        sequence_no=sequence_no,
        scheduler_algorithm=scheduler_algorithm,
        algorithm_version=algorithm_version,
        scheduler_config_hash=scheduler_config_hash,
        reviewed_at=reviewed_at,
        duration_ms=duration_ms,
        rating=rating,
        mode=mode,
        scheduler_mode=str(scheduler_mode or "legacy"),
        review_kind=str(review_kind or "review"),
        queue_before=queue_before,
        queue_after=queue_after,
        interval_days_before=interval_days_before,
        interval_days_after=interval_days_after,
        due_day_before=due_day_before,
        due_day_after=due_day_after,
        days_late=days_late,
        ease_factor_before=ease_factor_before,
        ease_factor_after=ease_factor_after,
        memory_stability_before=memory_stability_before,
        memory_stability_after=memory_stability_after,
        memory_difficulty_before=memory_difficulty_before,
        memory_difficulty_after=memory_difficulty_after,
        leeched_after=bool(leeched_after),
        suspended_after=bool(suspended_after),
        payload_json=payload_json or "{}",
    )
    (session or db.session).add(event)
    return event
