"""Repository for statistics queries."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from models import db
from models.flashcard import Card, Note, ReviewEvent
from models.card_progress import CardProgress
from app.services.anki_scheduler import _day_index
from app.repositories.study_repository import REVIEW_QUEUE, normalize_progress_queue

UTC = timezone.utc
MYSQL_FIXED_OFFSET_MINUTES = {
    "UTC": 0,
    "ETC/UTC": 0,
    "GMT": 0,
    "ASIA/HO_CHI_MINH": 7 * 60,
    "ASIA/BANGKOK": 7 * 60,
    "ASIA/JAKARTA": 7 * 60,
    "ASIA/TOKYO": 9 * 60,
    "ASIA/SEOUL": 9 * 60,
    "ASIA/SHANGHAI": 8 * 60,
    "ASIA/HONG_KONG": 8 * 60,
    "ASIA/SINGAPORE": 8 * 60,
    "ASIA/TAIPEI": 8 * 60,
}


def _session_dialect_name() -> str:
    bind = db.session.get_bind()
    return bind.dialect.name if bind is not None else ""


def can_use_mysql_local_day_sql(*, timezone_name: str) -> bool:
    """Use SQL for fixed-offset zones without requiring MySQL timezone tables."""
    bind = db.session.get_bind()
    if bind is None or bind.dialect.name != "mysql":
        return False
    return str(timezone_name or "").strip().upper() in MYSQL_FIXED_OFFSET_MINUTES


def _mysql_local_timestamp(timezone_name: str):
    offset = MYSQL_FIXED_OFFSET_MINUTES[str(timezone_name or "").strip().upper()]
    if offset == 0:
        return ReviewEvent.reviewed_at
    return db.func.date_add(
        ReviewEvent.reviewed_at,
        db.text(f"INTERVAL {int(offset)} MINUTE"),
    )


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


def _utc_to_business_day(
    moment: datetime,
    *,
    timezone_name: str,
    day_boundary_hour_local: int,
) -> date:
    tz_key = str(timezone_name or "").strip().upper()
    offset_min = MYSQL_FIXED_OFFSET_MINUTES.get(tz_key)
    if offset_min is not None:
        naive_moment = moment.replace(tzinfo=None) if moment.tzinfo else moment
        return (naive_moment + timedelta(minutes=offset_min - day_boundary_hour_local * 60)).date()
    return date.fromordinal(
        _day_index(
            moment,
            day_boundary_hour_local,
            timezone_name=timezone_name,
        )
    )


def _progress_due_local_day(
    *,
    due_at: datetime | None,
    due_day: int | None,
    queue_value: Any,
    timezone_name: str,
    day_boundary_hour_local: int,
) -> date | None:
    queue_norm = normalize_progress_queue(queue_value)
    if queue_norm == REVIEW_QUEUE and due_day is not None:
        try:
            return date.fromordinal(int(due_day))
        except (TypeError, ValueError):
            return None
    if due_at is None:
        return None
    return _utc_to_business_day(
        due_at,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local,
    )


def _query_daily_review_aggregates_mysql(
    *,
    user_id: int,
    timezone_name: str,
    start_utc: datetime,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> dict[date, dict[str, int]]:
    local_day_expr = db.func.date(
        db.func.date_sub(
            _mysql_local_timestamp(timezone_name),
            db.text(f"INTERVAL {int(day_boundary_hour_local)} HOUR"),
        )
    )
    duration_expr = db.func.coalesce(
        db.func.sum(
            db.case(
                (
                    db.and_(
                        ReviewEvent.duration_ms.isnot(None),
                        ReviewEvent.duration_ms > 0,
                    ),
                    ReviewEvent.duration_ms,
                ),
                else_=0,
            )
        ),
        0,
    )

    rows = (
        db.session.query(
            local_day_expr.label("local_day"),
            db.func.count(ReviewEvent.id).label("cards"),
            duration_expr.label("duration_ms"),
        )
        .filter(
            ReviewEvent.user_id == user_id,
            ReviewEvent.reviewed_at >= start_utc,
            ReviewEvent.reviewed_at < end_utc,
        )
        .group_by(local_day_expr)
        .all()
    )

    by_day: dict[date, dict[str, int]] = {}
    for local_day, cards, duration_ms in rows:
        parsed_day = _parse_sql_day(local_day)
        if not parsed_day:
            continue
        by_day[parsed_day] = {
            "cards": _safe_int(cards),
            "duration_ms": max(0, _safe_int(duration_ms)),
        }
    return by_day


def _query_daily_review_aggregates_python(
    *,
    user_id: int,
    timezone_name: str,
    start_utc: datetime,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> dict[date, dict[str, int]]:
    rows = (
        db.session.query(ReviewEvent.reviewed_at, ReviewEvent.duration_ms)
        .filter(
            ReviewEvent.user_id == user_id,
            ReviewEvent.reviewed_at >= start_utc,
            ReviewEvent.reviewed_at < end_utc,
        )
        .all()
    )

    by_day: dict[date, dict[str, int]] = {}
    for reviewed_at, duration_ms in rows:
        if reviewed_at is None:
            continue
        local_day = _utc_to_business_day(
            reviewed_at,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour_local,
        )
        bucket = by_day.setdefault(local_day, {"cards": 0, "duration_ms": 0})
        bucket["cards"] += 1
        duration = _safe_int(duration_ms)
        if duration > 0:
            bucket["duration_ms"] += duration
    return by_day


def query_daily_review_aggregates(
    *,
    user_id: int,
    timezone_name: str,
    timezone_obj,
    start_utc: datetime,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> dict[date, dict[str, int]]:
    if can_use_mysql_local_day_sql(timezone_name=timezone_name):
        return _query_daily_review_aggregates_mysql(
            user_id=user_id,
            timezone_name=timezone_name,
            start_utc=start_utc,
            end_utc=end_utc,
            day_boundary_hour_local=day_boundary_hour_local,
        )
    return _query_daily_review_aggregates_python(
        user_id=user_id,
        timezone_name=timezone_name,
        start_utc=start_utc,
        end_utc=end_utc,
        day_boundary_hour_local=day_boundary_hour_local,
    )


def _query_active_review_days_mysql(
    *,
    user_id: int,
    timezone_name: str,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> set[date]:
    local_day_expr = db.func.date(
        db.func.date_sub(
            _mysql_local_timestamp(timezone_name),
            db.text(f"INTERVAL {int(day_boundary_hour_local)} HOUR"),
        )
    )
    rows = (
        db.session.query(local_day_expr.label("local_day"))
        .filter(
            ReviewEvent.user_id == user_id,
            ReviewEvent.reviewed_at < end_utc,
        )
        .group_by(local_day_expr)
        .all()
    )

    result: set[date] = set()
    for (local_day,) in rows:
        parsed_day = _parse_sql_day(local_day)
        if parsed_day:
            result.add(parsed_day)
    return result


def _query_active_review_days_python(
    *,
    user_id: int,
    timezone_name: str,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> set[date]:
    rows = (
        db.session.query(ReviewEvent.reviewed_at)
        .filter(
            ReviewEvent.user_id == user_id,
            ReviewEvent.reviewed_at < end_utc,
        )
        .all()
    )

    result: set[date] = set()
    for (reviewed_at,) in rows:
        if reviewed_at is None:
            continue
        result.add(
            _utc_to_business_day(
                reviewed_at,
                timezone_name=timezone_name,
                day_boundary_hour_local=day_boundary_hour_local,
            )
        )
    return result


def query_active_review_days(
    *,
    user_id: int,
    timezone_name: str,
    timezone_obj,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> set[date]:
    if can_use_mysql_local_day_sql(timezone_name=timezone_name):
        return _query_active_review_days_mysql(
            user_id=user_id,
            timezone_name=timezone_name,
            end_utc=end_utc,
            day_boundary_hour_local=day_boundary_hour_local,
        )
    return _query_active_review_days_python(
        user_id=user_id,
        timezone_name=timezone_name,
        end_utc=end_utc,
        day_boundary_hour_local=day_boundary_hour_local,
    )


def query_today_review_summary(
    *,
    user_id: int,
    scope_deck_ids: list[int] | None,
    today_start_utc: datetime,
    tomorrow_start_utc: datetime,
) -> tuple[int, int]:
    duration_expr = db.func.coalesce(
        db.func.sum(
            db.case(
                (
                    db.and_(
                        ReviewEvent.duration_ms.isnot(None),
                        ReviewEvent.duration_ms > 0,
                    ),
                    ReviewEvent.duration_ms,
                ),
                else_=0,
            )
        ),
        0,
    )
    query = (
        db.session.query(
            db.func.count(ReviewEvent.id),
            duration_expr,
        )
        .filter(
            ReviewEvent.user_id == user_id,
            ReviewEvent.reviewed_at >= today_start_utc,
            ReviewEvent.reviewed_at < tomorrow_start_utc,
        )
    )

    if scope_deck_ids is not None:
        if not scope_deck_ids:
            return 0, 0
        query = query.filter(ReviewEvent.deck_id.in_(scope_deck_ids))

    cards, duration_ms = query.one()
    return _safe_int(cards), max(0, _safe_int(duration_ms))


def _query_future_due_day_counts_mysql(
    *,
    user_id: int,
    mysql_timezone: str,
    start_utc: datetime,
    end_utc: datetime,
) -> dict[date, int]:
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


def build_progress_rows_query(*, user_id: int):
    return (
        db.session.query(
            CardProgress.due_at,
            CardProgress.due_day,
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


def query_future_due_day_counts(
    *,
    user_id: int,
    timezone_name: str,
    timezone_obj,
    start_utc: datetime,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> dict[date, int]:
    start_local_day = _utc_to_business_day(
        start_utc,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local,
    )
    end_local_day = _utc_to_business_day(
        end_utc,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local,
    )
    rows = query_due_progress_rows(user_id=user_id)

    by_day: dict[date, int] = {}
    for due_at, due_day, queue_value in rows:
        local_day = _progress_due_local_day(
            due_at=due_at,
            due_day=due_day,
            queue_value=queue_value,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour_local,
        )
        if local_day is None:
            continue
        if local_day < start_local_day:
            by_day[start_local_day] = _safe_int(by_day.get(start_local_day)) + 1
        elif local_day < end_local_day:
            by_day[local_day] = _safe_int(by_day.get(local_day)) + 1
    return by_day


def aggregate_future_due_offsets_mysql(
    *,
    user_id: int,
    scope_deck_ids: list[int] | None,
    mysql_timezone: str,
    backlog: bool,
    end_offset: int | None,
    today_local: date,
) -> tuple[dict[int, dict[str, int]], int]:
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
) -> list[tuple[Any, Any]]:
    if scope_deck_ids is None:
        return (
            db.session.query(
                db.func.coalesce(CardProgress.interval_days_raw, CardProgress.interval_days),
                CardProgress.queue,
            )
            .filter(
                CardProgress.user_id == user_id,
                db.or_(CardProgress.is_suspended.is_(False), CardProgress.is_suspended.is_(None)),
            )
            .all()
        )
    query = build_progress_rows_query(user_id=user_id)
    query = apply_scope_filter(query, scope_deck_ids)
    query = query.filter(
        db.or_(CardProgress.is_suspended.is_(False), CardProgress.is_suspended.is_(None))
    )
    return query.with_entities(
        db.func.coalesce(CardProgress.interval_days_raw, CardProgress.interval_days),
        CardProgress.queue,
    ).all()


def query_due_progress_rows(
    *,
    user_id: int,
    scope_deck_ids: list[int] | None = None,
) -> list[tuple[Any, Any, Any]]:
    if scope_deck_ids is None:
        return (
            db.session.query(CardProgress.due_at, CardProgress.due_day, CardProgress.queue)
            .filter(
                CardProgress.user_id == user_id,
                db.or_(CardProgress.due_at.isnot(None), CardProgress.due_day.isnot(None)),
                db.or_(CardProgress.is_suspended.is_(False), CardProgress.is_suspended.is_(None)),
            )
            .all()
        )
    query = build_progress_rows_query(user_id=user_id)
    query = apply_scope_filter(query, scope_deck_ids)
    query = query.filter(
        db.or_(CardProgress.due_at.isnot(None), CardProgress.due_day.isnot(None)),
        db.or_(CardProgress.is_suspended.is_(False), CardProgress.is_suspended.is_(None)),
    )
    return query.with_entities(CardProgress.due_at, CardProgress.due_day, CardProgress.queue).all()
