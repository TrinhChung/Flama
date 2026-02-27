"""Study/SRS controllers shared by route handlers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping

from sqlalchemy.orm import aliased

from app.services.anki_scheduler import CardState, default_deck_options
from models import db
from models.card_progress import CardProgress
from models.flashcard import Card

LEARN_QUEUE = "learn"
REVIEW_QUEUE = "review"
NEW_QUEUE = "new"
LEARNING_QUEUE = "learning"
RELEARNING_QUEUE = "relearning"


def normalize_progress_queue(value: str | None) -> str:
    normalized = (value or NEW_QUEUE).strip().lower()
    if normalized == LEARN_QUEUE:
        return LEARNING_QUEUE
    if normalized in {NEW_QUEUE, LEARNING_QUEUE, REVIEW_QUEUE, RELEARNING_QUEUE}:
        return normalized
    return NEW_QUEUE


def card_state_from_progress(progress: CardProgress | None, now: datetime) -> CardState:
    options = default_deck_options()
    if not progress:
        return CardState(
            type=NEW_QUEUE,
            stepIndex=0,
            due=now,
            dueDay=None,
            intervalDays=0,
            ease=options.startingEase,
            reps=0,
            lapses=0,
            lastReviewAt=None,
        )

    queue = normalize_progress_queue(progress.queue)
    due_at = progress.due_at or now
    due_day = progress.due_day

    # Backward compatibility for rows that only have due_at.
    if due_day is None and queue == REVIEW_QUEUE:
        shifted = due_at - timedelta(hours=options.dayBoundaryHourLocal)
        due_day = shifted.date().toordinal()

    return CardState(
        type=queue,  # type: ignore[arg-type]
        stepIndex=int(progress.step_index or 0),
        due=due_at,
        dueDay=due_day,
        intervalDays=float(progress.interval_days or 0),
        ease=float(progress.ease_factor or options.startingEase),
        reps=int(progress.reps or 0),
        lapses=int(progress.lapses or 0),
        lastReviewAt=progress.last_reviewed_at,
    )


def apply_card_state_to_progress(
    progress: CardProgress, card_state: CardState, now: datetime
) -> CardProgress:
    options = default_deck_options()
    queue = normalize_progress_queue(card_state.type)
    due_at = card_state.due
    due_day = card_state.dueDay
    if due_day is not None:
        day_date = datetime.fromordinal(int(due_day)).date()
        due_at = datetime.combine(day_date, datetime.min.time()) + timedelta(
            hours=options.dayBoundaryHourLocal
        )

    progress.queue = queue
    progress.step_index = int(card_state.stepIndex or 0)
    progress.due_at = due_at
    progress.due_day = due_day
    progress.interval_days = int(round(float(card_state.intervalDays or 0)))
    progress.ease_factor = float(card_state.ease or options.startingEase)
    progress.reps = int(card_state.reps or 0)
    progress.lapses = int(card_state.lapses or 0)
    progress.last_reviewed_at = card_state.lastReviewAt or now
    return progress


def is_due(progress: CardProgress | None, now: datetime) -> bool:
    if progress is None:
        return True
    queue = normalize_progress_queue(progress.queue)
    if queue == NEW_QUEUE:
        return True
    if progress.due_at is None:
        return True
    return progress.due_at <= now


def query_next_due_card_id(query, *, user_id: int, now: datetime) -> str | None:
    progress_alias = aliased(CardProgress)
    progress_join = db.and_(
        progress_alias.card_id == Card.id,
        progress_alias.user_id == user_id,
    )
    normalized_queue = db.func.lower(db.func.coalesce(progress_alias.queue, NEW_QUEUE))
    normalized_queue = db.case(
        (normalized_queue == LEARN_QUEUE, LEARNING_QUEUE),
        else_=normalized_queue,
    )
    is_due_expr = db.or_(
        progress_alias.id.is_(None),
        normalized_queue == NEW_QUEUE,
        progress_alias.due_at.is_(None),
        progress_alias.due_at <= now,
    )
    queue_priority = db.case(
        (normalized_queue == RELEARNING_QUEUE, 0),
        (normalized_queue == LEARNING_QUEUE, 1),
        (normalized_queue == REVIEW_QUEUE, 2),
        else_=3,
    )
    row = (
        query.outerjoin(progress_alias, progress_join)
        .filter(is_due_expr)
        .order_by(queue_priority.asc(), Card.created_at.asc(), Card.id.asc())
        .with_entities(Card.id)
        .first()
    )
    if not row:
        return None
    return str(row[0])


def load_card_progress_map(*, user_id: int, card_ids: list[str]) -> dict[str, CardProgress]:
    if not card_ids:
        return {}
    rows = CardProgress.query.filter(
        CardProgress.user_id == user_id,
        CardProgress.card_id.in_(card_ids),
    ).all()
    return {row.card_id: row for row in rows if row.card_id}


def select_next_due_card_from_loaded(
    cards: list[Card],
    progress_map: Mapping[str, CardProgress],
    *,
    now: datetime,
) -> Card | None:
    due_relearn: list[Card] = []
    due_learn: list[Card] = []
    due_review: list[Card] = []
    due_new: list[Card] = []

    for card_obj in cards:
        progress = progress_map.get(card_obj.id)
        if not is_due(progress, now):
            continue
        queue = normalize_progress_queue(progress.queue) if progress else NEW_QUEUE
        if queue == RELEARNING_QUEUE:
            due_relearn.append(card_obj)
        elif queue == LEARNING_QUEUE:
            due_learn.append(card_obj)
        elif queue == REVIEW_QUEUE:
            due_review.append(card_obj)
        else:
            due_new.append(card_obj)

    for group in (due_relearn, due_learn, due_review, due_new):
        if group:
            return group[0]
    return None
