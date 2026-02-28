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


