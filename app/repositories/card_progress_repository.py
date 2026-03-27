"""CardProgress model controllers for stats-related data access."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from models import db
from models.flashcard import Card, Note
from models.card_progress import CardProgress

UTC = timezone.utc


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_sql_day(raw_day: Any) -> date | None:
    if isinstance(raw_day, date):
        return raw_day
    if isinstance(raw_day, datetime):
        return raw_day.date()
    if raw_day is None:
        return None

    text = str(raw_day).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _utc_to_local_day(moment: datetime, timezone_obj) -> date:
    utc_moment = moment
    if utc_moment.tzinfo is None:
        utc_moment = utc_moment.replace(tzinfo=UTC)
    else:
        utc_moment = utc_moment.astimezone(UTC)
    return utc_moment.astimezone(timezone_obj).date()


def _query_future_due_day_counts_mysql(
    *,
    user_id: int,
    timezone_name: str,
    start_utc: datetime,
    end_utc: datetime,
) -> dict[date, int]:
    mysql_timezone = "+00:00" if str(timezone_name).upper() == "UTC" else timezone_name
    local_day_expr = db.func.date(
        db.func.convert_tz(CardProgress.due_at, "+00:00", mysql_timezone)
    )
    rows = (
        db.session.query(
            local_day_expr.label("local_day"),
            db.func.count(CardProgress.id).label("due_cards"),
        )
        .filter(
            CardProgress.user_id == user_id,
            CardProgress.due_at.isnot(None),
            CardProgress.due_at >= start_utc,
            CardProgress.due_at < end_utc,
            db.or_(CardProgress.is_suspended.is_(False), CardProgress.is_suspended.is_(None)),
        )
        .group_by(local_day_expr)
        .all()
    )

    by_day: dict[date, int] = {}
    for local_day, due_cards in rows:
        parsed_day = _parse_sql_day(local_day)
        if not parsed_day:
            continue
        by_day[parsed_day] = _safe_int(due_cards)
    return by_day


def _query_future_due_day_counts_python(
    *,
    user_id: int,
    timezone_obj,
    start_utc: datetime,
    end_utc: datetime,
) -> dict[date, int]:
    rows = (
        db.session.query(CardProgress.due_at)
        .filter(
            CardProgress.user_id == user_id,
            CardProgress.due_at.isnot(None),
            CardProgress.due_at >= start_utc,
            CardProgress.due_at < end_utc,
            db.or_(CardProgress.is_suspended.is_(False), CardProgress.is_suspended.is_(None)),
        )
        .all()
    )

    by_day: dict[date, int] = {}
    for (due_at,) in rows:
        if due_at is None:
            continue
        local_day = _utc_to_local_day(due_at, timezone_obj)
        by_day[local_day] = _safe_int(by_day.get(local_day)) + 1
    return by_day


def query_future_due_day_counts(
    *,
    user_id: int,
    timezone_name: str,
    timezone_obj,
    start_utc: datetime,
    end_utc: datetime,
) -> dict[date, int]:
    dialect = db.session.get_bind().dialect.name if db.session.get_bind() is not None else ""
    if dialect == "mysql":
        return _query_future_due_day_counts_mysql(
            user_id=user_id,
            timezone_name=timezone_name,
            start_utc=start_utc,
            end_utc=end_utc,
        )
    return _query_future_due_day_counts_python(
        user_id=user_id,
        timezone_obj=timezone_obj,
        start_utc=start_utc,
        end_utc=end_utc,
    )


def build_progress_rows_query(*, user_id: int):
    return (
        db.session.query(
            CardProgress.due_at,
            CardProgress.queue,
            CardProgress.interval_days,
            CardProgress.is_suspended,
            Note.deck_id.label("note_deck_id"),
        )
        .select_from(CardProgress)
        .outerjoin(Card, CardProgress.card_id == Card.id)
        .outerjoin(Note, Card.note_id == Note.id)
        .filter(CardProgress.user_id == user_id)
    )


def apply_scope_filter(query, scope_deck_ids: list[int] | None):
    if scope_deck_ids is None:
        return query
    if not scope_deck_ids:
        return query.filter(db.text("1=0"))
    return query.filter(Note.deck_id.in_(scope_deck_ids))


def aggregate_future_due_offsets_mysql(
    *,
    user_id: int,
    scope_deck_ids: list[int] | None,
    timezone_name: str,
    backlog: bool,
    end_offset: int | None,
    today_local: date,
) -> tuple[dict[int, dict[str, int]], int]:
    mysql_timezone = "+00:00" if str(timezone_name).upper() == "UTC" else timezone_name
    local_day_expr = db.func.date(
        db.func.convert_tz(CardProgress.due_at, "+00:00", mysql_timezone)
    )

    query = (
        db.session.query(
            local_day_expr.label("local_day"),
            CardProgress.queue.label("queue"),
            db.func.count(CardProgress.id).label("cnt"),
        )
        .select_from(CardProgress)
        .outerjoin(Card, CardProgress.card_id == Card.id)
        .outerjoin(Note, Card.note_id == Note.id)
        .filter(
            CardProgress.user_id == user_id,
            CardProgress.due_at.isnot(None),
            db.or_(CardProgress.is_suspended.is_(False), CardProgress.is_suspended.is_(None)),
        )
    )

    query = apply_scope_filter(query, scope_deck_ids)

    if end_offset is not None:
        end_local = today_local + timedelta(days=end_offset + 1)
        query = query.filter(local_day_expr < end_local.isoformat())
    if not backlog:
        query = query.filter(local_day_expr >= today_local.isoformat())

    rows = query.group_by(local_day_expr, CardProgress.queue).all()
    by_offset: dict[int, dict[str, int]] = {}
    min_offset = 0
    for local_day, queue_value, count_value in rows:
        if local_day is None:
            continue
        local_day_text = str(local_day)
        try:
            local_day_date = date.fromisoformat(local_day_text[:10])
        except ValueError:
            continue

        day_offset = int((local_day_date - today_local).days)
        if day_offset < min_offset:
            min_offset = day_offset

        queue_norm = str(queue_value or "").strip().lower()
        if queue_norm == "learn":
            queue_norm = "learning"

        bucket = by_offset.setdefault(
            day_offset,
            {
                "due_count": 0,
                "new": 0,
                "learning": 0,
                "review": 0,
                "relearning": 0,
            },
        )
        count_int = _safe_int(count_value)
        bucket["due_count"] += count_int
        if queue_norm in {"new", "learning", "review", "relearning"}:
            bucket[queue_norm] += count_int

    return by_offset, min_offset


def query_due_queue_rows_python(
    *,
    user_id: int,
    scope_deck_ids: list[int] | None,
    today_start_utc: datetime,
    end_utc_exclusive: datetime | None,
    include_backlog: bool,
) -> list[tuple[Any, Any]]:
    query = build_progress_rows_query(user_id=user_id)
    query = apply_scope_filter(query, scope_deck_ids)
    query = query.filter(
        CardProgress.due_at.isnot(None),
        db.or_(CardProgress.is_suspended.is_(False), CardProgress.is_suspended.is_(None)),
    )

    if end_utc_exclusive is not None:
        query = query.filter(CardProgress.due_at < end_utc_exclusive)
    if not include_backlog:
        query = query.filter(CardProgress.due_at >= today_start_utc)

    return query.with_entities(CardProgress.due_at, CardProgress.queue).all()


def query_interval_days_rows(
    *,
    user_id: int,
    scope_deck_ids: list[int] | None,
) -> list[tuple[Any]]:
    query = build_progress_rows_query(user_id=user_id)
    query = apply_scope_filter(query, scope_deck_ids)
    query = query.filter(
        db.or_(CardProgress.is_suspended.is_(False), CardProgress.is_suspended.is_(None))
    )
    return query.with_entities(
        db.func.coalesce(CardProgress.interval_days_raw, CardProgress.interval_days)
    ).all()
