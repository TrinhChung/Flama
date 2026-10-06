"""Snapshot-only reads of the verified review-history projection.

Transaction ownership remains with the analytics service/HTTP boundary. This
module never heals metadata, starts a transaction, or locks projection rows.
"""

from __future__ import annotations

import random
import math
from datetime import datetime, timezone
from typing import Callable, TypeVar

from flask import current_app, has_request_context, request
from sqlalchemy import func, select

from models import db
from app.services.anki_scheduler import _day_index_to_datetime

T = TypeVar("T")


def _allowed_user(user_id: int) -> bool:
    configured = current_app.config.get("REVIEW_ANALYTICS_READ_USER_IDS")
    if configured is None or configured == "" or (
        isinstance(configured, (list, tuple, set)) and not configured
    ):
        return True
    values = configured.split(",") if isinstance(configured, str) else configured
    try:
        return int(user_id) in {int(value) for value in values if str(value).strip()}
    except (TypeError, ValueError):
        return False


def _shadow_sampled() -> bool:
    key = "flama.review_analytics_shadow_sampled"
    if has_request_context() and key in request.environ:
        return bool(request.environ[key])
    try:
        rate = float(current_app.config.get("REVIEW_ANALYTICS_SHADOW_SAMPLE_RATE", 0.01))
    except (TypeError, ValueError):
        rate = 0.0
    if not math.isfinite(rate):
        rate = 0.0
    sampled = random.random() < max(0.0, min(1.0, rate))
    if has_request_context():
        request.environ[key] = sampled
    return sampled


def _observe(metric: str, user_id: int, mode: str, outcome: str) -> None:
    current_app.logger.info(
        "review_analytics_read metric=%s user_id=%s mode=%s outcome=%s",
        metric, user_id, mode, outcome,
    )


def _utc_naive(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def _boundary_day(policy, moment: datetime):
    day = policy.study_day(_utc_naive(moment))
    boundary = _day_index_to_datetime(
        day.toordinal(), policy.day_boundary_hour, timezone_name=policy.timezone_name
    )
    return day if _utc_naive(moment) == _utc_naive(boundary) else None


def _ready_generation(user_id: int, policy):
    from models.review_analytics import ReviewAnalyticsHead, ReviewAnalyticsGeneration

    head, generation = ReviewAnalyticsHead, ReviewAnalyticsGeneration
    # Read columns, not ORM instances which may predate this request's snapshot.
    return db.session.execute(
        select(generation.generation)
        .join(head, (head.user_id == generation.user_id)
              & (head.active_generation == generation.generation))
        .where(
            head.user_id == int(user_id),
            generation.status == 1,
            generation.policy_hash == policy.policy_hash,
            generation.applied_source_revision == head.source_revision,
            generation.backfill_cursor_id == generation.baseline_high_water_id,
            generation.verified_at.isnot(None),
            generation.verification_contract_version == 1,
            generation.verified_source_revision.isnot(None),
            generation.verified_source_revision <= generation.applied_source_revision,
        )
    ).scalar_one_or_none()


def read_or_raw(
    *, metric: str, user_id: int, timezone_name: str | None,
    day_boundary_hour_local: int | None, raw: Callable[[], T],
    summary: Callable[[int, object], T | None],
) -> T:
    """Choose one verified generation, or preserve the existing raw result.

    Sampled shadow invokes both readers in the caller's same snapshot with the
    same captured arguments; it always returns raw, even when parity succeeds.
    """
    mode = str(current_app.config.get("REVIEW_ANALYTICS_READ_MODE", "raw")).strip().lower()
    if mode not in {"summary", "shadow"}:
        return raw()
    if not current_app.config.get("REVIEW_ANALYTICS_WRITE_ENABLED", False):
        _observe(metric, user_id, mode, "fallback_writes_disabled")
        return raw()
    if not _allowed_user(user_id):
        _observe(metric, user_id, mode, "fallback_allowlist")
        return raw()
    if mode == "shadow" and not _shadow_sampled():
        return raw()
    if timezone_name is None or day_boundary_hour_local is None:
        _observe(metric, user_id, mode, "fallback_missing_policy")
        return raw()
    from app.services.review_analytics_policy import ReviewAnalyticsPolicy

    policy = ReviewAnalyticsPolicy(timezone_name, day_boundary_hour_local)
    generation = _ready_generation(user_id, policy)
    if generation is None:
        _observe(metric, user_id, mode, "fallback_generation")
        return raw()
    projected = summary(int(generation), policy)
    if projected is None:
        _observe(metric, user_id, mode, "fallback_partial_day")
        return raw()
    if mode == "shadow":
        original = raw()
        _observe(metric, user_id, mode, "shadow_match" if projected == original else "shadow_drift")
        return original
    _observe(metric, user_id, mode, "summary_hit")
    return projected


def daily_measures(
    *, user_id: int, generation: int, policy, start_utc: datetime,
    end_utc: datetime, scope_deck_ids: list[int] | None = None,
):
    """Return grouped measures only for an exact business-day interval."""
    from models.review_analytics import DailyReviewCount

    start_day, end_day = _boundary_day(policy, start_utc), _boundary_day(policy, end_utc)
    if start_day is None or end_day is None:
        return None
    if scope_deck_ids is not None and not scope_deck_ids:
        return {}
    row = DailyReviewCount
    statement = select(
        row.study_day, func.sum(row.review_event_count),
        func.sum(row.positive_duration_ms), func.sum(row.passed_review_count),
    ).where(
        row.user_id == user_id, row.generation == generation,
        row.study_day >= start_day, row.study_day < end_day,
    )
    if scope_deck_ids is None:
        statement = statement.where(row.scope_kind == 0, row.scope_id == 0)
    else:
        # All direct attribution buckets in the subtree, including its root.
        statement = statement.where(row.scope_kind == 1, row.scope_id.in_(scope_deck_ids))
    return {
        day: {"count": int(count), "duration_ms": int(duration), "passed": int(passed)}
        for day, count, duration, passed in db.session.execute(
            statement.group_by(row.study_day)
        ).all()
    }


def active_days(*, user_id: int, generation: int, policy, end_utc: datetime):
    from models.review_analytics import DailyReviewCount

    end_day = _boundary_day(policy, end_utc)
    if end_day is None:
        return None
    row = DailyReviewCount
    return set(db.session.execute(select(row.study_day).where(
        row.user_id == user_id, row.generation == generation,
        row.scope_kind == 0, row.scope_id == 0,
        row.study_day < end_day, row.review_event_count > 0,
    )).scalars())
