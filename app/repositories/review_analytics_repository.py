"""Transactional persistence for the rebuildable historical analytics projection."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Mapping

from sqlalchemy import case, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from models.review_analytics import (
    DailyReviewCount,
    ReviewAnalyticsGeneration,
    ReviewAnalyticsHead,
)
from models.review_event import ReviewEvent

Bucket = tuple[int, int, date]
Measures = tuple[int, int, int]


def passed_rating_expression(session: Session):
    """Match the existing dialect's raw history reader, including collation."""
    rating = ReviewEvent.rating
    if session.get_bind().dialect.name != "mysql":
        # Python's str.strip() includes these characters; SQLite's default trim
        # only removes ASCII spaces.
        whitespace = " \t\n\r\v\f\x1c\x1d\x1e\x1f\x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
        rating = func.lower(func.trim(rating, whitespace))
    return case((rating.in_(("good", "easy", "3", "4")), 1), else_=0)


def lock_head(session: Session, user_id: int, *, create: bool = True):
    """Called after learner/domain locks; never acquire those locks afterwards."""
    table = ReviewAnalyticsHead.__table__
    if create:
        values = {"user_id": int(user_id), "next_generation": 1,
                  "source_revision": 0, "updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}
        dialect = session.get_bind().dialect.name
        if dialect == "mysql":
            statement = mysql_insert(table).values(**values)
            session.execute(statement.on_duplicate_key_update(user_id=table.c.user_id))
        elif dialect == "sqlite":
            session.execute(sqlite_insert(table).values(**values).on_conflict_do_nothing(
                index_elements=[table.c.user_id]))
        else:
            raise RuntimeError("Review analytics supports MySQL and SQLite only.")
    return session.execute(
        select(ReviewAnalyticsHead).where(ReviewAnalyticsHead.user_id == int(user_id))
        .with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()


def lock_generations(session: Session, user_id: int, generation_ids):
    ids = sorted({int(value) for value in generation_ids if value is not None})
    if not ids:
        return []
    return list(session.execute(
        select(ReviewAnalyticsGeneration)
        .where(ReviewAnalyticsGeneration.user_id == int(user_id),
               ReviewAnalyticsGeneration.generation.in_(ids))
        .order_by(ReviewAnalyticsGeneration.generation)
        .with_for_update().execution_options(populate_existing=True)
    ).scalars())


def add_grouped_deltas(session: Session, user_id: int, generation: int,
                       deltas: Mapping[Bucket, Measures]) -> None:
    """Add positive vectors, in deterministic key order and bounded SQL batches."""
    table = DailyReviewCount.__table__
    rows = []
    for (kind, scope_id, day), (count, duration, passed) in sorted(deltas.items()):
        if count < 0 or duration < 0 or passed < 0 or passed > count:
            raise ValueError("Historical corrections require generation invalidation.")
        if not count and not duration and not passed:
            continue
        rows.append({"user_id": int(user_id), "generation": int(generation),
                     "scope_kind": kind, "scope_id": scope_id, "study_day": day,
                     "review_event_count": count, "positive_duration_ms": duration,
                     "passed_review_count": passed})
    dialect = session.get_bind().dialect.name
    for offset in range(0, len(rows), 100):
        batch = rows[offset:offset + 100]
        if dialect == "mysql":
            statement = mysql_insert(table).values(batch)
            session.execute(statement.on_duplicate_key_update(**{
                name: table.c[name] + statement.inserted[name]
                for name in ("review_event_count", "positive_duration_ms", "passed_review_count")
            }))
        elif dialect == "sqlite":
            statement = sqlite_insert(table).values(batch)
            session.execute(statement.on_conflict_do_update(
                index_elements=list(table.primary_key.columns),
                set_={name: table.c[name] + statement.excluded[name]
                      for name in ("review_event_count", "positive_duration_ms", "passed_review_count")},
            ))
        else:
            raise RuntimeError("Review analytics supports MySQL and SQLite only.")


def load_inserted_events(session: Session, event_ids):
    """Read surviving inserted rows before head locks, using SQL passed semantics."""
    ids = sorted({int(value) for value in event_ids})
    rows = []
    for offset in range(0, len(ids), 500):
        rows.extend(session.execute(select(
            ReviewEvent.id, ReviewEvent.user_id, ReviewEvent.reviewed_at,
            ReviewEvent.deck_id, ReviewEvent.duration_ms, ReviewEvent.rating,
            passed_rating_expression(session).label("passed"),
        ).where(ReviewEvent.id.in_(ids[offset:offset + 500]))).all())
    return rows
