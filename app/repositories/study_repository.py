"""Study/SRS controllers shared by route handlers."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from sqlalchemy.orm import aliased

from app.services.anki_scheduler import (
    CardState,
    _day_index,
    _day_index_to_datetime,
    default_deck_options,
)
from models import db
from models.card_progress import CardProgress
from models.flashcard import Card

LEARN_QUEUE = "learn"
REVIEW_QUEUE = "review"
NEW_QUEUE = "new"
LEARNING_QUEUE = "learning"
RELEARNING_QUEUE = "relearning"
LEARNING_LATER_BUCKET = "learning_later"


def normalize_progress_queue(value: str | None) -> str:
    normalized = (value or NEW_QUEUE).strip().lower()
    if normalized == LEARN_QUEUE:
        return LEARNING_QUEUE
    if normalized in {NEW_QUEUE, LEARNING_QUEUE, REVIEW_QUEUE, RELEARNING_QUEUE}:
        return normalized
    return NEW_QUEUE


def card_state_from_progress(
    progress: CardProgress | None,
    now: datetime,
    *,
    timezone_name: str = "UTC",
) -> CardState:
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
        due_day = _day_index(
            due_at,
            options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )

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
    progress: CardProgress,
    card_state: CardState,
    now: datetime,
    *,
    timezone_name: str = "UTC",
) -> CardProgress:
    options = default_deck_options()
    queue = normalize_progress_queue(card_state.type)
    due_at = card_state.due
    due_day = card_state.dueDay
    if due_day is not None:
        due_at = _day_index_to_datetime(
            int(due_day),
            options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
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


def _today_day_index(*, now: datetime, timezone_name: str) -> int:
    options = default_deck_options()
    return _day_index(
        now,
        options.dayBoundaryHourLocal,
        timezone_name=timezone_name,
    )


def _next_day_boundary(*, now: datetime, timezone_name: str) -> datetime:
    options = default_deck_options()
    return _day_index_to_datetime(
        _today_day_index(now=now, timezone_name=timezone_name) + 1,
        options.dayBoundaryHourLocal,
        timezone_name=timezone_name,
    )


def _resolve_review_due_day(
    *,
    due_at: datetime | None,
    due_day: int | None,
    now: datetime,
    timezone_name: str,
) -> int:
    if due_day is not None:
        return int(due_day)
    options = default_deck_options()
    return _day_index(
        due_at or now,
        options.dayBoundaryHourLocal,
        timezone_name=timezone_name,
    )


def is_progress_suspended(progress: CardProgress | None) -> bool:
    return bool(progress is not None and getattr(progress, "is_suspended", False))


def _is_suspended_value(is_suspended: bool | None) -> bool:
    return bool(is_suspended)


def effective_due_at_for_progress_values(
    *,
    queue: str | None,
    due_at: datetime | None,
    due_day: int | None,
    now: datetime,
    timezone_name: str = "UTC",
) -> datetime | None:
    queue_norm = normalize_progress_queue(queue)
    if queue_norm == NEW_QUEUE:
        return None
    if queue_norm == REVIEW_QUEUE and due_day is not None:
        options = default_deck_options()
        return _day_index_to_datetime(
            int(due_day),
            options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )
    return due_at


def study_bucket_for_progress_values(
    *,
    queue: str | None,
    due_at: datetime | None,
    due_day: int | None,
    is_suspended: bool | None,
    now: datetime,
    timezone_name: str = "UTC",
) -> str | None:
    if _is_suspended_value(is_suspended):
        return None

    queue_norm = normalize_progress_queue(queue)
    if queue_norm == NEW_QUEUE:
        return NEW_QUEUE
    if queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE}:
        if due_at is None or due_at <= now:
            return LEARNING_QUEUE
        if due_at < _next_day_boundary(now=now, timezone_name=timezone_name):
            return LEARNING_LATER_BUCKET
        return None
    if queue_norm == REVIEW_QUEUE:
        review_due_day = _resolve_review_due_day(
            due_at=due_at,
            due_day=due_day,
            now=now,
            timezone_name=timezone_name,
        )
        if review_due_day <= _today_day_index(now=now, timezone_name=timezone_name):
            return REVIEW_QUEUE
        return None
    return NEW_QUEUE


def counter_bucket_for_progress_values(
    *,
    queue: str | None,
    due_at: datetime | None,
    due_day: int | None,
    is_suspended: bool | None = None,
    now: datetime,
    timezone_name: str = "UTC",
) -> str | None:
    bucket = study_bucket_for_progress_values(
        queue=queue,
        due_at=due_at,
        due_day=due_day,
        is_suspended=is_suspended,
        now=now,
        timezone_name=timezone_name,
    )
    if bucket == LEARNING_LATER_BUCKET:
        return LEARNING_QUEUE
    return bucket


def is_due(progress: CardProgress | None, now: datetime, *, timezone_name: str = "UTC") -> bool:
    if progress is None:
        return True
    return (
        study_bucket_for_progress_values(
            queue=progress.queue,
            due_at=progress.due_at,
            due_day=progress.due_day,
            is_suspended=progress.is_suspended,
            now=now,
            timezone_name=timezone_name,
        )
        in {NEW_QUEUE, LEARNING_QUEUE, REVIEW_QUEUE}
    )


def normalized_queue_expr(progress_alias):
    normalized_queue = db.func.lower(db.func.coalesce(progress_alias.queue, NEW_QUEUE))
    return db.case(
        (normalized_queue == LEARN_QUEUE, LEARNING_QUEUE),
        else_=normalized_queue,
    )


def active_progress_expr(progress_alias):
    return db.or_(
        progress_alias.id.is_(None),
        progress_alias.is_suspended.is_(False),
        progress_alias.is_suspended.is_(None),
    )


def review_due_expr(progress_alias, *, now: datetime, timezone_name: str = "UTC"):
    today_day_index = _today_day_index(now=now, timezone_name=timezone_name)
    return db.or_(
        progress_alias.due_day <= today_day_index,
        db.and_(
            progress_alias.due_day.is_(None),
            db.or_(
                progress_alias.due_at.is_(None),
                progress_alias.due_at <= now,
            ),
        ),
    )


def query_next_due_card_id(
    query,
    *,
    user_id: int,
    now: datetime,
    timezone_name: str = "UTC",
) -> str | None:
    progress_alias = aliased(CardProgress)
    progress_join = db.and_(
        progress_alias.card_id == Card.id,
        progress_alias.user_id == user_id,
    )
    normalized_queue = normalized_queue_expr(progress_alias)
    learning_due_expr = db.or_(
        progress_alias.due_at.is_(None),
        progress_alias.due_at <= now,
    )
    is_due_expr = db.or_(
        progress_alias.id.is_(None),
        normalized_queue == NEW_QUEUE,
        db.and_(
            normalized_queue.in_([LEARNING_QUEUE, RELEARNING_QUEUE]),
            learning_due_expr,
        ),
        db.and_(
            normalized_queue == REVIEW_QUEUE,
            review_due_expr(progress_alias, now=now, timezone_name=timezone_name),
        ),
    )
    queue_priority = db.case(
        (normalized_queue == RELEARNING_QUEUE, 0),
        (normalized_queue == LEARNING_QUEUE, 1),
        (normalized_queue == REVIEW_QUEUE, 2),
        else_=3,
    )
    review_due_sort_key = db.case(
        (normalized_queue == REVIEW_QUEUE, progress_alias.due_day),
        else_=None,
    )
    due_sort_key = db.case(
        (
            normalized_queue.in_([LEARNING_QUEUE, RELEARNING_QUEUE, REVIEW_QUEUE]),
            progress_alias.due_at,
        ),
        else_=None,
    )
    row = (
        query.outerjoin(progress_alias, progress_join)
        .filter(active_progress_expr(progress_alias), is_due_expr)
        .order_by(
            queue_priority.asc(),
            review_due_sort_key.asc().nullslast(),
            due_sort_key.asc().nullslast(),
            Card.created_at.asc(),
            Card.id.asc(),
        )
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
    timezone_name: str = "UTC",
) -> Card | None:
    due_relearn: list[Card] = []
    due_learn: list[Card] = []
    due_review: list[Card] = []
    due_new: list[Card] = []

    def _sort_key(card_obj: Card):
        progress = progress_map.get(card_obj.id)
        due_at = progress.due_at if progress is not None else None
        return (due_at or datetime.max, card_obj.created_at or datetime.max, card_obj.id)

    for card_obj in cards:
        progress = progress_map.get(card_obj.id)
        if not is_due(progress, now, timezone_name=timezone_name):
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

    for group in (due_relearn, due_learn, due_review):
        if group:
            group.sort(key=_sort_key)
            return group[0]
    if due_new:
        due_new.sort(key=lambda card_obj: (card_obj.created_at or datetime.max, card_obj.id))
        return due_new[0]
    return None


def summarize_pending_learning_from_loaded(
    cards: list[Card],
    progress_map: Mapping[str, CardProgress],
    *,
    now: datetime,
    timezone_name: str = "UTC",
) -> tuple[int, datetime | None]:
    next_day_boundary = _next_day_boundary(now=now, timezone_name=timezone_name)
    pending_count = 0
    next_due_at: datetime | None = None

    for card_obj in cards:
        progress = progress_map.get(card_obj.id)
        if progress is None:
            continue
        if is_progress_suspended(progress):
            continue
        due_at = progress.due_at
        if (
            study_bucket_for_progress_values(
                queue=progress.queue,
                due_at=due_at,
                due_day=progress.due_day,
                is_suspended=progress.is_suspended,
                now=now,
                timezone_name=timezone_name,
            )
            != LEARNING_LATER_BUCKET
        ):
            continue
        pending_count += 1
        if next_due_at is None or due_at < next_due_at:
            next_due_at = due_at

    return pending_count, next_due_at


def query_study_queue_counts(
    query,
    *,
    user_id: int,
    now: datetime,
    timezone_name: str = "UTC",
) -> tuple[int, int, int]:
    progress_alias = aliased(CardProgress)
    progress_join = db.and_(
        progress_alias.card_id == Card.id,
        progress_alias.user_id == user_id,
    )
    rows = (
        query.outerjoin(progress_alias, progress_join)
        .order_by(None)
        .with_entities(
            Card.id,
            progress_alias.queue,
            progress_alias.due_at,
            progress_alias.due_day,
            progress_alias.is_suspended,
        )
        .all()
    )

    new_count = 0
    learn_count = 0
    due_count = 0
    seen_card_ids: set[str] = set()
    for card_id, queue, due_at, due_day, is_suspended in rows:
        card_id_str = str(card_id or "").strip()
        if not card_id_str or card_id_str in seen_card_ids:
            continue
        seen_card_ids.add(card_id_str)
        count_bucket = counter_bucket_for_progress_values(
            queue=queue,
            due_at=due_at,
            due_day=due_day,
            is_suspended=is_suspended,
            now=now,
            timezone_name=timezone_name,
        )
        if count_bucket == NEW_QUEUE:
            new_count += 1
        elif count_bucket == LEARNING_QUEUE:
            learn_count += 1
        elif count_bucket == REVIEW_QUEUE:
            due_count += 1

    return new_count, learn_count, due_count


def query_pending_learning_summary(
    query,
    *,
    user_id: int,
    now: datetime,
    timezone_name: str = "UTC",
) -> tuple[int, datetime | None]:
    progress_alias = aliased(CardProgress)
    progress_join = db.and_(
        progress_alias.card_id == Card.id,
        progress_alias.user_id == user_id,
    )
    normalized_queue = normalized_queue_expr(progress_alias)
    next_day_boundary = _next_day_boundary(now=now, timezone_name=timezone_name)
    row = (
        query.outerjoin(progress_alias, progress_join)
        .filter(
            active_progress_expr(progress_alias),
            normalized_queue.in_([LEARNING_QUEUE, RELEARNING_QUEUE]),
            progress_alias.due_at.isnot(None),
            progress_alias.due_at > now,
            progress_alias.due_at < next_day_boundary,
        )
        .order_by(None)
        .with_entities(
            db.func.count(db.distinct(Card.id)),
            db.func.min(progress_alias.due_at),
        )
        .first()
    )
    if not row:
        return 0, None
    return int(row[0] or 0), row[1]
