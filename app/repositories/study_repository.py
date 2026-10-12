"""Study/SRS controllers shared by route handlers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

from sqlalchemy import false
from sqlalchemy.orm import aliased

from app.services.anki_scheduler import (
    CardState,
    FsrsMemoryState,
    _day_index,
    _day_index_to_datetime,
    _round_review_interval,
    DeckOptions,
    default_deck_options,
)
from app.services.scheduler_config_service import resolve_scheduler_runtime_settings
from models import db
from models.flashcard import Card
from models.study_progress_subject import StudyProgressSubject

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
    progress: Any | None,
    now: datetime,
    *,
    timezone_name: str = "UTC",
    user_id: int | None = None,
    options: DeckOptions | None = None,
) -> CardState:
    resolved_options = options
    if resolved_options is None:
        runtime = resolve_scheduler_runtime_settings(
            user_id=(
                user_id
                if user_id is not None
                else getattr(progress, "user_id", None)
            )
        )
        resolved_options = default_deck_options()
        resolved_options.dayBoundaryHourLocal = int(
            runtime.day_boundary_hour_local
        )
        resolved_options.learnAheadSeconds = int(runtime.learn_ahead_seconds)
    if not progress:
        return CardState(
            type=NEW_QUEUE,
            stepIndex=0,
            due=now,
            dueDay=None,
            intervalDays=0,
            ease=resolved_options.startingEase,
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
            resolved_options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )
    if due_day is not None and progress.due_at is None:
        due_at = _day_index_to_datetime(
            int(due_day),
            resolved_options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )

    return CardState(
        type=queue,  # type: ignore[arg-type]
        stepIndex=int(progress.step_index or 0),
        due=due_at,
        dueDay=due_day,
        intervalDays=float(
            getattr(progress, "interval_days_raw", None)
            if getattr(progress, "interval_days_raw", None) is not None
            else (progress.interval_days or 0)
        ),
        ease=float(progress.ease_factor or resolved_options.startingEase),
        reps=int(progress.reps or 0),
        lapses=int(progress.lapses or 0),
        lastReviewAt=progress.last_reviewed_at,
        reviewKind=str(getattr(progress, "review_kind", "review") or "review"),
        schedulerMode=str(getattr(progress, "scheduler_mode", "legacy") or "legacy"),
        suspended=bool(progress.is_suspended),
        suspensionReason=getattr(progress, "suspension_reason", None),
        leeched=bool(getattr(progress, "last_leech_lapses", 0) and int(progress.lapses or 0) >= int(getattr(progress, "last_leech_lapses", 0) or 0)),
        memoryState=(
            FsrsMemoryState(
                stability=float(progress.memory_stability),
                difficulty=float(progress.memory_difficulty),
            )
            if getattr(progress, "memory_stability", None) is not None
            and getattr(progress, "memory_difficulty", None) is not None
            else None
        ),
    )


def apply_card_state_to_progress(
    progress: Any,
    card_state: CardState,
    now: datetime,
    *,
    timezone_name: str = "UTC",
    options: DeckOptions | None = None,
) -> Any:
    resolved_options = options
    if resolved_options is None:
        runtime = resolve_scheduler_runtime_settings(
            user_id=getattr(progress, "user_id", None)
        )
        resolved_options = default_deck_options()
        resolved_options.dayBoundaryHourLocal = int(
            runtime.day_boundary_hour_local
        )
        resolved_options.learnAheadSeconds = int(runtime.learn_ahead_seconds)
    queue = normalize_progress_queue(card_state.type)
    due_at = card_state.due
    due_day = card_state.dueDay
    if due_day is not None and (queue == REVIEW_QUEUE or due_at is None):
        due_at = _day_index_to_datetime(
            int(due_day),
            resolved_options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )

    progress.queue = queue
    progress.step_index = int(card_state.stepIndex or 0)
    progress.due_at = due_at
    progress.due_day = due_day
    if queue == REVIEW_QUEUE:
        progress.interval_days = _round_review_interval(
            float(card_state.intervalDays or 0),
            resolved_options,
        )
    else:
        progress.interval_days = int(round(float(card_state.intervalDays or 0)))
    if hasattr(progress, "interval_days_raw"):
        progress.interval_days_raw = float(card_state.intervalDays or 0)
    progress.ease_factor = float(card_state.ease or resolved_options.startingEase)
    progress.is_suspended = bool(card_state.suspended)
    if hasattr(progress, "review_kind"):
        progress.review_kind = str(card_state.reviewKind or "review")
    if hasattr(progress, "scheduler_mode"):
        progress.scheduler_mode = str(card_state.schedulerMode or "legacy")
    if hasattr(progress, "memory_stability"):
        progress.memory_stability = (
            float(card_state.memoryState.stability)
            if card_state.memoryState is not None
            else None
        )
    if hasattr(progress, "memory_difficulty"):
        progress.memory_difficulty = (
            float(card_state.memoryState.difficulty)
            if card_state.memoryState is not None
            else None
        )
    if hasattr(progress, "suspension_reason"):
        progress.suspension_reason = card_state.suspensionReason if card_state.suspended else None
    if getattr(card_state, "leeched", False):
        if hasattr(progress, "last_leech_at"):
            progress.last_leech_at = now
        if hasattr(progress, "last_leech_lapses"):
            progress.last_leech_lapses = int(card_state.lapses or 0)
    progress.reps = int(card_state.reps or 0)
    progress.lapses = int(card_state.lapses or 0)
    progress.last_reviewed_at = card_state.lastReviewAt or now
    return progress


def _today_day_index(
    *,
    now: datetime,
    timezone_name: str,
    day_boundary_hour_local: int | None = None,
) -> int:
    boundary_hour = int(
        default_deck_options().dayBoundaryHourLocal
        if day_boundary_hour_local is None
        else day_boundary_hour_local
    )
    return _day_index(
        now,
        boundary_hour,
        timezone_name=timezone_name,
    )


def _next_day_boundary(
    *,
    now: datetime,
    timezone_name: str,
    day_boundary_hour_local: int | None = None,
) -> datetime:
    boundary_hour = int(
        default_deck_options().dayBoundaryHourLocal
        if day_boundary_hour_local is None
        else day_boundary_hour_local
    )
    return _day_index_to_datetime(
        _today_day_index(
            now=now,
            timezone_name=timezone_name,
            day_boundary_hour_local=boundary_hour,
        ) + 1,
        boundary_hour,
        timezone_name=timezone_name,
    )


def _learn_ahead_cutoff(*, now: datetime, learn_ahead_seconds: int | None = None) -> datetime:
    default_seconds = int(default_deck_options().learnAheadSeconds or 0)
    return now + timedelta(seconds=max(0, int(default_seconds if learn_ahead_seconds is None else learn_ahead_seconds)))


def _resolve_review_due_day(
    *,
    due_at: datetime | None,
    due_day: int | None,
    now: datetime,
    timezone_name: str,
    day_boundary_hour_local: int | None = None,
) -> int:
    if due_day is not None:
        return int(due_day)
    return _day_index(
        due_at or now,
        int(
            default_deck_options().dayBoundaryHourLocal
            if day_boundary_hour_local is None
            else day_boundary_hour_local
        ),
        timezone_name=timezone_name,
    )


def is_progress_suspended(progress: Any | None) -> bool:
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
    day_boundary_hour_local: int | None = None,
) -> datetime | None:
    queue_norm = normalize_progress_queue(queue)
    boundary_hour = int(
        default_deck_options().dayBoundaryHourLocal
        if day_boundary_hour_local is None
        else day_boundary_hour_local
    )
    if queue_norm == NEW_QUEUE:
        return None
    if queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE} and due_day is not None and due_at is None:
        return _day_index_to_datetime(
            int(due_day),
            boundary_hour,
            timezone_name=timezone_name,
        )
    if queue_norm == REVIEW_QUEUE and due_day is not None:
        return _day_index_to_datetime(
            int(due_day),
            boundary_hour,
            timezone_name=timezone_name,
        )
    return due_at


def _is_learning_due_now(
    *,
    due_at: datetime | None,
    due_day: int | None,
    now: datetime,
    timezone_name: str,
    day_boundary_hour_local: int | None = None,
) -> bool:
    if due_day is not None:
        return int(due_day) <= _today_day_index(
            now=now,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour_local,
        )
    return due_at is None or due_at <= now


def _is_learning_due_within_ahead_limit(
    *,
    due_at: datetime | None,
    due_day: int | None,
    now: datetime,
    learn_ahead_seconds: int | None = None,
) -> bool:
    if due_day is not None or due_at is None or due_at <= now:
        return False
    return due_at <= _learn_ahead_cutoff(now=now, learn_ahead_seconds=learn_ahead_seconds)


def study_bucket_for_progress_values(
    *,
    queue: str | None,
    due_at: datetime | None,
    due_day: int | None,
    is_suspended: bool | None,
    now: datetime,
    is_buried: bool | None = None,
    buried_until_day: int | None = None,
    timezone_name: str = "UTC",
    day_boundary_hour_local: int | None = None,
) -> str | None:
    today_day_index = _today_day_index(
        now=now,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local,
    )
    if _is_suspended_value(is_suspended) or (
        bool(is_buried)
        and (buried_until_day is None or int(buried_until_day) >= today_day_index)
    ):
        return None

    queue_norm = normalize_progress_queue(queue)
    if queue_norm == NEW_QUEUE:
        return NEW_QUEUE
    if queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE}:
        if _is_learning_due_now(
            due_at=due_at,
            due_day=due_day,
            now=now,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour_local,
        ):
            return LEARNING_QUEUE
        return LEARNING_LATER_BUCKET
    if queue_norm == REVIEW_QUEUE:
        review_due_day = _resolve_review_due_day(
            due_at=due_at,
            due_day=due_day,
            now=now,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour_local,
        )
        if review_due_day <= _today_day_index(
            now=now,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour_local,
        ):
            return REVIEW_QUEUE
        return None
    return NEW_QUEUE


def counter_bucket_for_progress_values(
    *,
    queue: str | None,
    due_at: datetime | None,
    due_day: int | None,
    now: datetime,
    is_suspended: bool | None = None,
    is_buried: bool | None = None,
    buried_until_day: int | None = None,
    timezone_name: str = "UTC",
    day_boundary_hour_local: int | None = None,
) -> str | None:
    bucket = study_bucket_for_progress_values(
        queue=queue,
        due_at=due_at,
        due_day=due_day,
        is_suspended=is_suspended,
        is_buried=is_buried,
        buried_until_day=buried_until_day,
        now=now,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local,
    )
    if bucket == LEARNING_LATER_BUCKET:
        return LEARNING_QUEUE
    return bucket


def is_due(
    progress: Any | None,
    now: datetime,
    *,
    timezone_name: str = "UTC",
    day_boundary_hour_local: int | None = None,
) -> bool:
    if progress is None:
        return True
    return (
        study_bucket_for_progress_values(
            queue=progress.queue,
            due_at=progress.due_at,
            due_day=progress.due_day,
            is_suspended=progress.is_suspended,
            is_buried=progress.is_buried,
            buried_until_day=progress.buried_until_day,
            now=now,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour_local,
        )
        in {NEW_QUEUE, LEARNING_QUEUE, REVIEW_QUEUE}
    )


def active_progress_expr(progress_alias, *, today_day_index: int | None = None):
    active = db.or_(
        progress_alias.id.is_(None),
        progress_alias.is_suspended.is_(False),
        progress_alias.is_suspended.is_(None),
    )
    if today_day_index is None:
        return active
    not_buried = db.or_(
        progress_alias.id.is_(None),
        progress_alias.is_buried.is_(False),
        progress_alias.is_buried.is_(None),
        progress_alias.buried_until_day < today_day_index,
    )
    return db.and_(active, not_buried)


def review_due_expr(
    progress_alias,
    *,
    now: datetime,
    timezone_name: str = "UTC",
    day_boundary_hour_local: int | None = None,
):
    today_day_index = _today_day_index(
        now=now,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local,
    )
    # A review timestamp without due_day still belongs to a local study day.
    # It is due anywhere before the next boundary, matching the NOTE reader.
    next_boundary = _next_day_boundary(
        now=now, timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local,
    )
    return db.or_(
        progress_alias.due_day <= today_day_index,
        db.and_(
            progress_alias.due_day.is_(None),
            db.or_(
                progress_alias.due_at.is_(None),
                progress_alias.due_at < next_boundary,
            ),
        ),
    )


def _ordered_study_card_queries(
    query,
    *,
    user_id: int,
    now: datetime,
    timezone_name: str = "UTC",
):
    runtime = resolve_scheduler_runtime_settings(user_id=user_id)
    day_boundary_hour = int(runtime.day_boundary_hour_local)
    learn_ahead_seconds = int(runtime.learn_ahead_seconds)
    subject = aliased(StudyProgressSubject)
    query = query.order_by(None).outerjoin(subject, db.and_(
        subject.live_note_id == Card.note_id,
        subject.learner_user_id == int(user_id),
    ))
    today_day_index = _today_day_index(
        now=now,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour,
    )
    # These are scheduling anchors, not old/new persistence fallbacks. A
    # multi-day learning step has due_day; an intraday step has due_at. Each
    # disjoint anchor branch gets a simple range predicate, and each queue
    # gets its own physical-column ORDER BY instead of a queue CASE sort.
    current = query.filter(
        subject.semantic_state_hash.isnot(None),
        subject.is_suspended == false(),
        db.or_(subject.is_buried.is_(False), subject.buried_until_day < today_day_index),
    )
    due_groups = []
    for queue_code in (RELEARNING_QUEUE, LEARNING_QUEUE, REVIEW_QUEUE):
        queue_query = current.filter(subject.normalized_queue == queue_code)
        time_due = (
            subject.due_at < _next_day_boundary(
                now=now, timezone_name=timezone_name,
                day_boundary_hour_local=day_boundary_hour,
            ) if queue_code == REVIEW_QUEUE else subject.due_at <= now
        )
        anchors = (
            subject.due_day <= today_day_index,
            db.and_(subject.due_day.is_(None), time_due),
            db.and_(subject.due_day.is_(None), subject.due_at.is_(None)),
        )
        sort_columns = (
            (subject.due_day.is_(None).asc(), subject.due_day.asc())
            if queue_code == REVIEW_QUEUE else ()
        )
        ordering = (*sort_columns, subject.due_at.is_(None).asc(),
                    subject.due_at.asc(), Card.created_at.asc(), Card.order_key.asc(), Card.id.asc())
        due_groups.append(tuple(
            queue_query.filter(anchor).order_by(*ordering).with_entities(
                Card.id, subject.due_day, subject.due_at, Card.created_at, Card.order_key,
            ).execution_options(note_queue_code=queue_code, note_anchor_index=anchor_index)
            for anchor_index, anchor in enumerate(anchors)
        ))
    # A never-studied Note has either no subject or an empty envelope.
    # NEW envelopes and missing/empty envelopes have the same presentation
    # creation order. One content scan replaces three independent sorts.
    # This presence OR is not a due-anchor fallback or another progress store.
    new_queries = (query.filter(db.or_(
        subject.semantic_state_hash.is_(None),
        db.and_(subject.normalized_queue == NEW_QUEUE,
                subject.is_suspended == false(),
                db.or_(subject.is_buried.is_(False), subject.buried_until_day < today_day_index)),
    )).order_by(Card.created_at.asc(), Card.order_key.asc(), Card.id.asc()).with_entities(
        Card.id, subject.due_day, subject.due_at, Card.created_at, Card.order_key,
    ),)
    due_groups.append(new_queries)
    learn_ahead_cutoff = _learn_ahead_cutoff(
        now=now,
        learn_ahead_seconds=learn_ahead_seconds,
    )
    ahead_groups = tuple((
        current.filter(
            subject.normalized_queue == queue_code,
            subject.due_day.is_(None),
            subject.due_at > now,
            subject.due_at <= learn_ahead_cutoff,
        ).order_by(subject.due_at.asc(), Card.created_at.asc(), Card.order_key.asc(), Card.id.asc())
        .with_entities(Card.id, subject.due_day, subject.due_at, Card.created_at, Card.order_key)
        .execution_options(note_queue_code=queue_code, note_anchor_index=1),
    ) for queue_code in (RELEARNING_QUEUE, LEARNING_QUEUE))
    return tuple(due_groups), ahead_groups


def _queue_row_order_key(row, *, queue_index: int):
    card_id, due_day, due_at, created_at, order_key = row
    if queue_index == 2:
        return review_selection_order_key(
            due_day=due_day, due_at=due_at, card_created_at=created_at,
            card_order_key=str(order_key),
        )
    if queue_index == 3:
        return (created_at or datetime.max, str(order_key), str(card_id))
    return (due_at is None, due_at or datetime.max, created_at or datetime.max, str(order_key), str(card_id))


def _first_queue_branch(branch):
    """Seek the earliest subject anchors before sorting presentation ties.

    Index-ordered LIMIT1 seeks retain the authorized scope, so a source Note
    hidden by a clone release never supplies an anchor. Only presentations
    sharing those exact anchors reach the final creation/alias-key tie sort.
    """

    options = branch.get_execution_options()
    queue_code = options.get('note_queue_code')
    anchor_index = options.get('note_anchor_index')
    if queue_code is None or anchor_index == 2:
        return branch.first()
    day = branch.column_descriptions[1]['expr']
    time = branch.column_descriptions[2]['expr']
    candidate = branch
    if queue_code == REVIEW_QUEUE and anchor_index == 0:
        first_day = candidate.order_by(None).with_entities(day).order_by(day.asc()).first()
        if first_day is None:
            return None
        candidate = candidate.filter(day == first_day[0])
    first_time = candidate.filter(time.isnot(None)).order_by(None).with_entities(time).order_by(time.asc()).first()
    if first_time is not None:
        return candidate.filter(time == first_time[0]).first()
    return candidate.filter(time.is_(None)).first() if anchor_index == 0 else None


def query_next_due_card_id(
    query,
    *,
    user_id: int,
    now: datetime,
    timezone_name: str = "UTC",
    queue_counts: tuple[int, int, int] | None = None,
) -> str | None:
    due_groups, ahead_groups = _ordered_study_card_queries(
        query, user_id=user_id, now=now, timezone_name=timezone_name
    )
    for stage, groups in enumerate((due_groups, ahead_groups)):
        for queue_index, branches in enumerate(groups):
            if queue_counts is not None:
                bucket = 1 if stage == 1 or queue_index in (0, 1) else (2 if queue_index == 2 else 0)
                if queue_counts[bucket] == 0:
                    continue
            # At most three LIMIT 1 results are merged in memory. We retain
            # the Query execution options (notably pinned retired applications).
            candidates = [row for branch in branches if (row := _first_queue_branch(branch)) is not None]
            if candidates:
                return str(min(candidates, key=lambda row: _queue_row_order_key(
                    row, queue_index=queue_index,
                ))[0])
    return None


def query_study_card_order(
    query,
    *,
    user_id: int,
    now: datetime,
    timezone_name: str = "UTC",
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Audit-only full SQL order using the same predicates as the serving picker."""

    due_groups, ahead_groups = _ordered_study_card_queries(
        query, user_id=user_id, now=now, timezone_name=timezone_name
    )
    def ordered(groups):
        result = []
        for queue_index, branches in enumerate(groups):
            rows = [row for branch in branches for row in branch.all()]
            rows.sort(key=lambda row: _queue_row_order_key(row, queue_index=queue_index))
            result.extend(str(row[0]) for row in rows)
        return tuple(result)
    return ordered(due_groups), ordered(ahead_groups)


def review_selection_order_key(
    *,
    due_day: int | None,
    due_at: datetime | None,
    card_created_at: datetime | None,
    card_order_key: str | bytes,
):
    """Mirror the review ORDER BY of ``query_next_due_card_id`` for loaded reads."""

    return (
        due_day is None,
        int(due_day) if due_day is not None else 0,
        due_at is None,
        due_at or datetime.max,
        card_created_at or datetime.max,
        card_order_key,
    )


def select_next_due_card_from_loaded(
    cards: list[Card],
    progress_map: Mapping[str, Any],
    *,
    now: datetime,
    timezone_name: str = "UTC",
    user_id: int | None = None,
) -> Card | None:
    runtime = resolve_scheduler_runtime_settings(user_id=user_id)
    day_boundary_hour = int(runtime.day_boundary_hour_local)
    learn_ahead_seconds = int(runtime.learn_ahead_seconds)
    due_relearn: list[Card] = []
    due_learn: list[Card] = []
    due_review: list[Card] = []
    due_new: list[Card] = []
    learn_ahead_relearn: list[Card] = []
    learn_ahead_learn: list[Card] = []

    def _learning_sort_key(card_obj: Card):
        progress = progress_map.get(card_obj.id)
        due_at = progress.due_at if progress is not None else None
        return (due_at or datetime.max, card_obj.created_at or datetime.max,
                getattr(card_obj, 'order_key', card_obj.id))

    def _review_sort_key(card_obj: Card):
        progress = progress_map.get(card_obj.id)
        return review_selection_order_key(
            due_day=progress.due_day if progress is not None else None,
            due_at=progress.due_at if progress is not None else None,
            card_created_at=card_obj.created_at,
            card_order_key=getattr(card_obj, 'order_key', card_obj.id),
        )

    for card_obj in cards:
        progress = progress_map.get(card_obj.id)
        queue = normalize_progress_queue(progress.queue) if progress else NEW_QUEUE
        if not is_due(
            progress,
            now,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour,
        ):
            if progress and queue in {LEARNING_QUEUE, RELEARNING_QUEUE} and _is_learning_due_within_ahead_limit(
                due_at=progress.due_at,
                due_day=progress.due_day,
                now=now,
                learn_ahead_seconds=learn_ahead_seconds,
            ):
                if queue == RELEARNING_QUEUE:
                    learn_ahead_relearn.append(card_obj)
                else:
                    learn_ahead_learn.append(card_obj)
            continue
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
            if group is due_review:
                group.sort(key=_review_sort_key)
            else:
                group.sort(key=_learning_sort_key)
            return group[0]
    if due_new:
        due_new.sort(key=lambda card_obj: (card_obj.created_at or datetime.max,
                                          getattr(card_obj, 'order_key', card_obj.id)))
        return due_new[0]
    for group in (learn_ahead_relearn, learn_ahead_learn):
        if group:
            group.sort(key=_learning_sort_key)
            return group[0]
    return None


def summarize_pending_learning_from_loaded(
    cards: list[Card],
    progress_map: Mapping[str, Any],
    *,
    now: datetime,
    timezone_name: str = "UTC",
    user_id: int | None = None,
) -> tuple[int, datetime | None]:
    runtime = resolve_scheduler_runtime_settings(user_id=user_id)
    day_boundary_hour = int(runtime.day_boundary_hour_local)
    learn_ahead_seconds = int(runtime.learn_ahead_seconds)
    pending_count = 0
    next_due_at: datetime | None = None
    today_day_index = _today_day_index(
        now=now,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour,
    )
    learn_ahead_cutoff = _learn_ahead_cutoff(
        now=now,
        learn_ahead_seconds=learn_ahead_seconds,
    )

    for card_obj in cards:
        progress = progress_map.get(card_obj.id)
        if progress is None:
            continue
        if is_progress_suspended(progress):
            continue
        queue = normalize_progress_queue(progress.queue)
        if queue not in {LEARNING_QUEUE, RELEARNING_QUEUE}:
            continue
        due_at = effective_due_at_for_progress_values(
            queue=progress.queue,
            due_at=progress.due_at,
            due_day=progress.due_day,
            now=now,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour,
        )
        if progress.due_day is not None:
            if int(progress.due_day) <= today_day_index:
                continue
        elif due_at is None or due_at <= learn_ahead_cutoff:
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
    """Exact NOTE count units and envelope integrity in one aggregate."""

    from flask import current_app
    from sqlalchemy import LargeBinary, cast
    from app.repositories.note_analytics_read_repository import (
        subject_integrity_violation, violation_error,
    )
    from app.repositories.study_authority_repository import StudyAuthorityFenceError

    runtime = resolve_scheduler_runtime_settings(user_id=user_id)
    today_day_index = _today_day_index(
        now=now, timezone_name=timezone_name,
        day_boundary_hour_local=int(runtime.day_boundary_hour_local),
    )
    subject = aliased(StudyProgressSubject)
    base = query.order_by(None).outerjoin(subject, db.and_(
        subject.logical_note_key == cast(Card.note_id, LargeBinary),
        subject.learner_user_id == int(user_id),
    ))
    current = db.and_(
        subject.semantic_state_hash.isnot(None), subject.is_suspended == false(),
        db.or_(subject.is_buried.is_(False), subject.buried_until_day < today_day_index),
    )
    new = db.or_(subject.id.is_(None), subject.semantic_state_hash.is_(None),
                 db.and_(current, subject.normalized_queue == NEW_QUEUE))
    learn = db.and_(current, subject.normalized_queue.in_([LEARNING_QUEUE, RELEARNING_QUEUE]))
    review_cutoff = _next_day_boundary(
        now=now, timezone_name=timezone_name,
        day_boundary_hour_local=int(runtime.day_boundary_hour_local),
    )
    review = db.and_(current, subject.normalized_queue == REVIEW_QUEUE, db.or_(
        subject.due_day <= today_day_index,
        db.and_(subject.due_day.is_(None), subject.due_at < review_cutoff),
        db.and_(subject.due_day.is_(None), subject.due_at.is_(None)),
    ))
    unit = Card.note_id if current_app.config.get('STUDY_NOTE_COUNT_ENABLED', False) else Card.id
    def count(condition):
        return db.func.count(db.distinct(db.case((condition, unit), else_=None)))
    row = base.with_entities(
        count(new), count(learn), count(review),
        db.func.max(subject_integrity_violation(subject, note_id=Card.note_id)),
    ).one()
    violation = violation_error(int(row[3] or 0))
    if violation is not None:
        raise StudyAuthorityFenceError(violation[0], violation[1])
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)


def query_pending_learning_summary(
    query,
    *,
    user_id: int,
    now: datetime,
    timezone_name: str = "UTC",
) -> tuple[int, datetime | None]:
    runtime = resolve_scheduler_runtime_settings(user_id=user_id)
    day_boundary_hour = int(runtime.day_boundary_hour_local)
    learn_ahead_seconds = int(runtime.learn_ahead_seconds)
    subject = aliased(StudyProgressSubject)
    today_day_index = _today_day_index(
        now=now,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour,
    )
    learn_ahead_cutoff = _learn_ahead_cutoff(
        now=now,
        learn_ahead_seconds=learn_ahead_seconds,
    )
    base = query.order_by(None).join(subject, db.and_(
        subject.live_note_id == Card.note_id, subject.learner_user_id == int(user_id),
    )).filter(
        subject.semantic_state_hash.isnot(None), subject.is_suspended == false(),
        db.or_(subject.is_buried.is_(False), subject.buried_until_day < today_day_index),
    )
    count = 0
    due_dates = []
    for queue_code in (LEARNING_QUEUE, RELEARNING_QUEUE):
        queue = base.filter(subject.normalized_queue == queue_code)
        day_row = queue.filter(subject.due_day > today_day_index, subject.due_at.is_(None)).with_entities(
            db.func.count(db.distinct(Card.id)), db.func.min(subject.due_day),
        ).one()
        anchored_time_row = queue.filter(
            subject.due_day > today_day_index, subject.due_at.isnot(None),
        ).with_entities(db.func.count(db.distinct(Card.id)), db.func.min(subject.due_at)).one()
        time_row = queue.filter(
            subject.due_day.is_(None), subject.due_at > learn_ahead_cutoff,
        ).with_entities(db.func.count(db.distinct(Card.id)), db.func.min(subject.due_at)).one()
        count += int(day_row[0] or 0) + int(anchored_time_row[0] or 0) + int(time_row[0] or 0)
        if day_row[1] is not None:
            due_dates.append(_day_index_to_datetime(
                int(day_row[1]), day_boundary_hour, timezone_name=timezone_name,
            ))
        if time_row[1] is not None:
            due_dates.append(time_row[1])
        if anchored_time_row[1] is not None:
            due_dates.append(anchored_time_row[1])
    return count, min(due_dates) if due_dates else None
