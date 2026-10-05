"""Source reads and exact grouped parity queries for review analytics backfill."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import case, func, literal, select, text, union_all

from app.repositories.review_analytics_repository import passed_rating_expression
from app.services.review_analytics_policy import passed_count_for_policy, uses_mysql_day_sql
from models.review_analytics import DailyReviewCount, ReviewAnalyticsGeneration, ReviewAnalyticsHead
from models.review_event import ReviewEvent
from models.user import User


def lock_backfill_user(session, user_id: int) -> None:
    """Drain compliant writers before opening the baseline read snapshot."""
    found = session.execute(
        select(User.id).where(User.id == int(user_id)).with_for_update()
    ).scalar_one_or_none()
    if found is None:
        raise ValueError("Review analytics user does not exist")


def read_head(session, user_id: int):
    return session.execute(
        select(ReviewAnalyticsHead).where(ReviewAnalyticsHead.user_id == int(user_id))
    ).scalar_one_or_none()


def read_generation(session, user_id: int, generation: int):
    return session.execute(
        select(ReviewAnalyticsGeneration).where(
            ReviewAnalyticsGeneration.user_id == int(user_id),
            ReviewAnalyticsGeneration.generation == int(generation),
        )
    ).scalar_one_or_none()


def committed_high_water(session, user_id: int) -> int:
    return int(session.execute(
        select(func.max(ReviewEvent.id)).where(ReviewEvent.user_id == int(user_id))
    ).scalar_one() or 0)


def invalid_deck_attribution_count(session, user_id: int) -> int:
    return int(session.execute(
        select(func.count(ReviewEvent.id)).where(
            ReviewEvent.user_id == int(user_id), ReviewEvent.deck_id <= 0,
        )
    ).scalar_one())


def load_baseline_chunk(session, *, user_id: int, cursor: int, high_water: int, limit: int):
    return session.execute(
        select(
            ReviewEvent.id, ReviewEvent.reviewed_at, ReviewEvent.deck_id,
            ReviewEvent.duration_ms, ReviewEvent.rating,
            passed_rating_expression(session).label("sql_passed"),
        )
        .where(
            ReviewEvent.user_id == int(user_id),
            ReviewEvent.id > int(cursor), ReviewEvent.id <= int(high_water),
        )
        .order_by(ReviewEvent.id).limit(int(limit))
    ).all()


def group_baseline_chunk(rows, *, policy, dialect_name: str):
    buckets = defaultdict(lambda: [0, 0, 0])
    for _event_id, reviewed_at, deck_id, duration_ms, rating, sql_passed in rows:
        if deck_id is not None and int(deck_id) <= 0:
            raise ValueError("Historical deck attribution must be NULL or a positive deck ID")
        day = policy.study_day(reviewed_at)
        vector = (
            1, max(int(duration_ms or 0), 0),
            passed_count_for_policy(policy, rating, sql_passed, dialect_name),
        )
        keys = [(0, 0, day)]
        if deck_id is not None and int(deck_id) > 0:
            keys.append((1, int(deck_id), day))
        for key in keys:
            for index, value in enumerate(vector):
                buckets[key][index] += value
    return {key: tuple(values) for key, values in buckets.items()}


def raw_grouped_counts(session, *, user_id: int, policy):
    """Return exact all-history collection/deck buckets, not hydrated events.

    Fixed-offset MySQL policies group in SQL like the existing reader. Other
    policies stream source rows and retain only grouped deck-day measures.
    """
    dialect = session.get_bind().dialect.name
    if not uses_mysql_day_sql(policy, dialect):
        rows = session.execute(
            select(
                ReviewEvent.id, ReviewEvent.reviewed_at, ReviewEvent.deck_id,
                ReviewEvent.duration_ms, ReviewEvent.rating,
                passed_rating_expression(session).label("sql_passed"),
            ).where(ReviewEvent.user_id == int(user_id))
            .execution_options(yield_per=500)
        )
        try:
            return group_baseline_chunk(rows, policy=policy, dialect_name=dialect)
        finally:
            rows.close()

    from app.repositories.stats_query_repository import _mysql_local_timestamp

    study_day = func.date(func.date_sub(
        _mysql_local_timestamp(policy.timezone_name),
        text(f"INTERVAL {int(policy.day_boundary_hour)} HOUR"),
    ))
    duration = func.coalesce(func.sum(case(
        (ReviewEvent.duration_ms > 0, ReviewEvent.duration_ms), else_=0,
    )), 0)
    measures = (
        func.count(ReviewEvent.id).label("event_count"),
        duration.label("positive_ms"),
        func.sum(passed_rating_expression(session)).label("passed_count"),
    )
    collection = select(
        literal(0).label("scope_kind"), literal(0).label("scope_id"),
        study_day.label("study_day"), *measures,
    ).where(ReviewEvent.user_id == int(user_id)).group_by(study_day)
    decks = select(
        literal(1).label("scope_kind"), ReviewEvent.deck_id.label("scope_id"),
        study_day.label("study_day"), *measures,
    ).where(
        ReviewEvent.user_id == int(user_id), ReviewEvent.deck_id > 0,
    ).group_by(ReviewEvent.deck_id, study_day)
    rows = session.execute(union_all(collection, decks).execution_options(yield_per=500))
    try:
        return {
            (int(kind), int(scope_id), day if isinstance(day, date) else date.fromisoformat(str(day))):
                (int(count), int(positive_ms or 0), int(passed or 0))
            for kind, scope_id, day, count, positive_ms, passed in rows
        }
    finally:
        rows.close()


def projected_grouped_counts(session, *, user_id: int, generation: int):
    rows = session.execute(
        select(
            DailyReviewCount.scope_kind, DailyReviewCount.scope_id, DailyReviewCount.study_day,
            DailyReviewCount.review_event_count, DailyReviewCount.positive_duration_ms,
            DailyReviewCount.passed_review_count,
        ).where(
            DailyReviewCount.user_id == int(user_id),
            DailyReviewCount.generation == int(generation),
        ).execution_options(yield_per=500)
    )
    try:
        # Empty measure rows are excess buckets, not equivalent to absent rows.
        return {
            (int(kind), int(scope_id), day): (int(count), int(positive_ms), int(passed))
            for kind, scope_id, day, count, positive_ms, passed in rows
        }
    finally:
        rows.close()
