"""ReviewEvent model controllers for analytics and persistence."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from models import db
from models.flashcard import ReviewEvent

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
) -> ReviewEvent:
    event = ReviewEvent(
        user_id=user_id,
        card_id=str(card_id),
        deck_id=deck_id,
        note_type_id=note_type_id,
        reviewed_at=reviewed_at,
        duration_ms=duration_ms,
        rating=rating,
        mode=mode,
    )
    db.session.add(event)
    return event


def _query_daily_review_aggregates_mysql(
    *,
    user_id: int,
    timezone_name: str,
    start_utc: datetime,
    end_utc: datetime,
) -> dict[date, dict[str, int]]:
    mysql_timezone = "+00:00" if str(timezone_name).upper() == "UTC" else timezone_name
    local_day_expr = db.func.date(
        db.func.convert_tz(ReviewEvent.reviewed_at, "+00:00", mysql_timezone)
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
    timezone_obj,
    start_utc: datetime,
    end_utc: datetime,
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
        local_day = _utc_to_local_day(reviewed_at, timezone_obj)
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
) -> dict[date, dict[str, int]]:
    dialect = db.session.get_bind().dialect.name if db.session.get_bind() is not None else ""
    if dialect == "mysql":
        return _query_daily_review_aggregates_mysql(
            user_id=user_id,
            timezone_name=timezone_name,
            start_utc=start_utc,
            end_utc=end_utc,
        )
    return _query_daily_review_aggregates_python(
        user_id=user_id,
        timezone_obj=timezone_obj,
        start_utc=start_utc,
        end_utc=end_utc,
    )


def _query_active_review_days_mysql(
    *,
    user_id: int,
    timezone_name: str,
    end_utc: datetime,
) -> set[date]:
    mysql_timezone = "+00:00" if str(timezone_name).upper() == "UTC" else timezone_name
    local_day_expr = db.func.date(
        db.func.convert_tz(ReviewEvent.reviewed_at, "+00:00", mysql_timezone)
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
    timezone_obj,
    end_utc: datetime,
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
        result.add(_utc_to_local_day(reviewed_at, timezone_obj))
    return result


def query_active_review_days(
    *,
    user_id: int,
    timezone_name: str,
    timezone_obj,
    end_utc: datetime,
) -> set[date]:
    dialect = db.session.get_bind().dialect.name if db.session.get_bind() is not None else ""
    if dialect == "mysql":
        return _query_active_review_days_mysql(
            user_id=user_id,
            timezone_name=timezone_name,
            end_utc=end_utc,
        )
    return _query_active_review_days_python(
        user_id=user_id,
        timezone_obj=timezone_obj,
        end_utc=end_utc,
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
