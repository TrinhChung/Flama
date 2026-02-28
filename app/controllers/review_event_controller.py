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

