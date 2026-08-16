"""Statistics aggregation and review-event capture helpers."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.anki_scheduler import _day_index, _day_index_to_datetime
from app.services.scheduler_config_service import resolve_day_boundary_hour_local
from app.repositories.stats_query_repository import (
    query_active_review_days,
    query_daily_review_aggregates,
)
from app.repositories.review_event_repository import create_review_event_record
from app.repositories.stats_query_repository import query_future_due_day_counts
from models.flashcard import ReviewEvent

UTC = timezone.utc
DEFAULT_TIMEZONE = "UTC"
VALID_REVIEW_MODES = {"new", "learn", "review"}
FALLBACK_FIXED_OFFSETS_MINUTES = {
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
OFFSET_TZ_PATTERN = re.compile(r"^(?:UTC|GMT)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?$", re.IGNORECASE)


def _resolve_fixed_offset_minutes(candidate: str) -> int | None:
    key = str(candidate or "").strip()
    key_upper = key.upper()
    if key_upper in {"UTC", "ETC/UTC", "GMT"}:
        return 0
    if key_upper in FALLBACK_FIXED_OFFSETS_MINUTES:
        return int(FALLBACK_FIXED_OFFSETS_MINUTES[key_upper])
    match = OFFSET_TZ_PATTERN.match(key)
    if not match:
        return None
    sign, hours_text, minutes_text = match.groups()
    hours = int(hours_text)
    minutes = int(minutes_text or 0)
    if hours > 14 or minutes >= 60:
        return None
    total = hours * 60 + minutes
    return total if sign == "+" else -total


def _is_supported_timezone_name(candidate: str) -> bool:
    try:
        ZoneInfo(candidate)
        return True
    except ZoneInfoNotFoundError:
        return _resolve_fixed_offset_minutes(candidate) is not None


def normalize_timezone_name(raw_timezone: Any) -> str | None:
    if raw_timezone is None:
        return None
    candidate = str(raw_timezone).strip()
    if not candidate or len(candidate) > 64:
        return None
    if candidate.upper() in {"UTC", "ETC/UTC", "GMT"}:
        return DEFAULT_TIMEZONE
    if not _is_supported_timezone_name(candidate):
        return None
    return candidate


def get_effective_timezone_name(raw_timezone: Any) -> str:
    normalized = normalize_timezone_name(raw_timezone)
    return normalized or DEFAULT_TIMEZONE


def update_user_timezone(user_obj: Any, raw_timezone: Any) -> bool:
    if user_obj is None:
        return False
    normalized = normalize_timezone_name(raw_timezone)
    if not normalized:
        return False
    if getattr(user_obj, "timezone", None) == normalized:
        return False
    user_obj.timezone = normalized
    return True


def normalize_review_mode(raw_mode: Any) -> str:
    mode = str(raw_mode or "").strip().lower()
    if mode in {"learning", "relearning", "learn"}:
        return "learn"
    if mode == "review":
        return "review"
    if mode == "new":
        return "new"
    return "review"


def _normalize_duration_ms(raw_duration_ms: Any) -> int | None:
    if raw_duration_ms is None:
        return None
    try:
        value = int(raw_duration_ms)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def _ensure_naive_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


def _local_start_to_utc_naive(day_value: date, timezone_obj) -> datetime:
    local_start = datetime.combine(day_value, time.min, tzinfo=timezone_obj)
    return local_start.astimezone(UTC).replace(tzinfo=None)


def _next_day(day_value: date) -> date:
    return day_value + timedelta(days=1)


def _iter_days(start_day: date, end_day: date):
    cursor = start_day
    while cursor <= end_day:
        yield cursor
        cursor = _next_day(cursor)


def _round2(value: float) -> float:
    return round(float(value) + 1e-12, 2)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _build_timezone_obj(timezone_name: str):
    if str(timezone_name).upper() == "UTC":
        return UTC
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        fallback_minutes = _resolve_fixed_offset_minutes(timezone_name)
        if fallback_minutes is not None:
            return timezone(timedelta(minutes=fallback_minutes))
        return UTC


def _longest_streak_in_range(
    *,
    day_map: dict[date, dict[str, int]],
    start_day: date,
    end_day: date,
) -> int:
    best = 0
    current = 0
    for day_value in _iter_days(start_day, end_day):
        cards = _safe_int((day_map.get(day_value) or {}).get("cards"))
        if cards > 0:
            current += 1
            if current > best:
                best = current
        else:
            current = 0
    return best


def _current_streak_from_active_days(*, active_days: set[date], today_local: date) -> int:
    if today_local in active_days:
        cursor = today_local
    else:
        cursor = today_local - timedelta(days=1)
        if cursor not in active_days:
            return 0

    streak = 0
    while cursor in active_days:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


def record_review_event(
    *,
    user_id: int,
    card_id: str,
    rating: str,
    mode: str,
    reviewed_at: datetime | None = None,
    duration_ms: Any = None,
    deck_id: int | None = None,
    note_type_id: str | None = None,
    scheduler_preset_id: int | None = None,
    scheduler_mode: str | None = None,
    review_kind: str | None = None,
    queue_before: str | None = None,
    queue_after: str | None = None,
    interval_days_before: float | None = None,
    interval_days_after: float | None = None,
    due_day_before: int | None = None,
    due_day_after: int | None = None,
    days_late: int | None = None,
    ease_factor_before: float | None = None,
    ease_factor_after: float | None = None,
    memory_stability_before: float | None = None,
    memory_stability_after: float | None = None,
    memory_difficulty_before: float | None = None,
    memory_difficulty_after: float | None = None,
    leeched_after: bool = False,
    suspended_after: bool = False,
    payload_json: str | None = None,
) -> ReviewEvent:
    review_time = _ensure_naive_utc(reviewed_at or datetime.utcnow())
    normalized_mode = normalize_review_mode(mode)
    normalized_rating = str(rating or "").strip().lower() or "again"

    return create_review_event_record(
        user_id=user_id,
        card_id=str(card_id),
        deck_id=deck_id,
        note_type_id=note_type_id,
        reviewed_at=review_time,
        duration_ms=_normalize_duration_ms(duration_ms),
        rating=normalized_rating,
        mode=normalized_mode if normalized_mode in VALID_REVIEW_MODES else "review",
        scheduler_preset_id=scheduler_preset_id,
        scheduler_mode=str(scheduler_mode or "legacy"),
        review_kind=str(review_kind or "review"),
        queue_before=queue_before,
        queue_after=queue_after,
        interval_days_before=interval_days_before,
        interval_days_after=interval_days_after,
        due_day_before=due_day_before,
        due_day_after=due_day_after,
        days_late=days_late,
        ease_factor_before=ease_factor_before,
        ease_factor_after=ease_factor_after,
        memory_stability_before=memory_stability_before,
        memory_stability_after=memory_stability_after,
        memory_difficulty_before=memory_difficulty_before,
        memory_difficulty_after=memory_difficulty_after,
        leeched_after=bool(leeched_after),
        suspended_after=bool(suspended_after),
        payload_json=payload_json or "{}",
    )


def build_stats_overview(
    *,
    user_id: int,
    year: int | None,
    timezone_name: str | None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    effective_timezone_name = get_effective_timezone_name(timezone_name)
    timezone_obj = _build_timezone_obj(effective_timezone_name)
    now_utc_naive = _ensure_naive_utc(now_utc or datetime.utcnow())
    day_boundary_hour = resolve_day_boundary_hour_local(user_id=user_id)
    today_day_index = _day_index(
        now_utc_naive,
        day_boundary_hour,
        timezone_name=effective_timezone_name,
    )
    today_local = date.fromordinal(today_day_index)

    selected_year = year if year is not None else today_local.year
    year_start = date(selected_year, 1, 1)
    year_end = date(selected_year, 12, 31)

    year_start_utc = _day_index_to_datetime(
        year_start.toordinal(),
        day_boundary_hour,
        timezone_name=effective_timezone_name,
    )
    year_end_utc = _day_index_to_datetime(
        date(selected_year + 1, 1, 1).toordinal(),
        day_boundary_hour,
        timezone_name=effective_timezone_name,
    )

    day_map = query_daily_review_aggregates(
        user_id=user_id,
        timezone_name=effective_timezone_name,
        timezone_obj=timezone_obj,
        start_utc=year_start_utc,
        end_utc=year_end_utc,
        day_boundary_hour_local=day_boundary_hour,
    )

    due_day_map: dict[date, int] = {}
    if selected_year == today_local.year:
        future_start_local = today_local
        if future_start_local <= year_end:
            future_start_utc = _day_index_to_datetime(
                future_start_local.toordinal(),
                day_boundary_hour,
                timezone_name=effective_timezone_name,
            )
            due_day_map = query_future_due_day_counts(
                user_id=user_id,
                timezone_name=effective_timezone_name,
                timezone_obj=timezone_obj,
                start_utc=future_start_utc,
                end_utc=year_end_utc,
                day_boundary_hour_local=day_boundary_hour,
            )

    today_start_utc = _day_index_to_datetime(
        today_day_index,
        day_boundary_hour,
        timezone_name=effective_timezone_name,
    )
    tomorrow_start_utc = _day_index_to_datetime(
        today_day_index + 1,
        day_boundary_hour,
        timezone_name=effective_timezone_name,
    )
    today_map = query_daily_review_aggregates(
        user_id=user_id,
        timezone_name=effective_timezone_name,
        timezone_obj=timezone_obj,
        start_utc=today_start_utc,
        end_utc=tomorrow_start_utc,
        day_boundary_hour_local=day_boundary_hour,
    )
    today_data = today_map.get(today_local, {"cards": 0, "duration_ms": 0})
    today_cards = _safe_int(today_data.get("cards"))
    today_duration_ms = max(0, _safe_int(today_data.get("duration_ms")))
    today_minutes = _round2(today_duration_ms / 60000.0)
    today_sec_per_card = _round2((today_duration_ms / 1000.0) / today_cards) if today_cards > 0 else 0.0

    if selected_year < today_local.year:
        counted_start = year_start
        counted_end = year_end
    elif selected_year == today_local.year:
        counted_start = year_start
        counted_end = today_local
    else:
        counted_start = None
        counted_end = None

    if counted_start and counted_end and counted_end >= counted_start:
        counted_days = (counted_end - counted_start).days + 1
        counted_total_cards = 0
        counted_active_days = 0
        for day_value in _iter_days(counted_start, counted_end):
            cards = _safe_int((day_map.get(day_value) or {}).get("cards"))
            counted_total_cards += cards
            if cards > 0:
                counted_active_days += 1
        daily_average_cards = counted_total_cards / counted_days if counted_days > 0 else 0.0
        days_learned_percent = (counted_active_days / counted_days * 100.0) if counted_days > 0 else 0.0
        longest_streak_days = _longest_streak_in_range(
            day_map=day_map,
            start_day=counted_start,
            end_day=counted_end,
        )
    else:
        counted_days = 0
        daily_average_cards = 0.0
        days_learned_percent = 0.0
        longest_streak_days = 0

    all_active_days = query_active_review_days(
        user_id=user_id,
        timezone_name=effective_timezone_name,
        timezone_obj=timezone_obj,
        end_utc=tomorrow_start_utc,
        day_boundary_hour_local=day_boundary_hour,
    )
    current_streak_days = _current_streak_from_active_days(
        active_days=all_active_days,
        today_local=today_local,
    )

    heatmap: list[dict[str, Any]] = []
    for day_value in _iter_days(year_start, year_end):
        is_future = day_value > today_local
        if selected_year == today_local.year and is_future:
            cards = _safe_int(due_day_map.get(day_value))
            duration_ms = 0
            minutes = 0.0
            sec_per_card = 0.0
            source = "due"
        elif selected_year == today_local.year and day_value == today_local:
            day_bucket = day_map.get(day_value) or {"cards": 0, "duration_ms": 0}
            reviewed_cards = _safe_int(day_bucket.get("cards"))
            if reviewed_cards > 0:
                cards = reviewed_cards
                duration_ms = max(0, _safe_int(day_bucket.get("duration_ms")))
                minutes = _round2(duration_ms / 60000.0)
                sec_per_card = _round2((duration_ms / 1000.0) / cards)
                is_future = False
                source = "reviewed"
            else:
                today_due = _safe_int(due_day_map.get(day_value))
                if today_due > 0:
                    cards = today_due
                    duration_ms = 0
                    minutes = 0.0
                    sec_per_card = 0.0
                    is_future = True
                    source = "due"
                else:
                    cards = 0
                    duration_ms = 0
                    minutes = 0.0
                    sec_per_card = 0.0
                    is_future = False
                    source = "reviewed"
        else:
            day_bucket = day_map.get(day_value) or {"cards": 0, "duration_ms": 0}
            cards = _safe_int(day_bucket.get("cards"))
            duration_ms = max(0, _safe_int(day_bucket.get("duration_ms")))
            minutes = _round2(duration_ms / 60000.0)
            sec_per_card = _round2((duration_ms / 1000.0) / cards) if cards > 0 else 0.0
            is_future = False
            source = "reviewed"
        heatmap.append(
            {
                "day": day_value.isoformat(),
                "date": day_value.isoformat(),
                "cards": cards,
                "study_time": duration_ms,
                "minutes": minutes,
                "sec_per_card": sec_per_card,
                "is_future": is_future,
                "source": source,
            }
        )

    return {
        "year": selected_year,
        "timezone": effective_timezone_name,
        "today": {
            "date": today_local.isoformat(),
            "cards": today_cards,
            "minutes": today_minutes,
            "sec_per_card": today_sec_per_card,
        },
        "heatmap": heatmap,
        "metrics": {
            "daily_average_cards": _safe_int(round(daily_average_cards)),
            "days_learned_percent": _safe_int(round(days_learned_percent)),
            "longest_streak_days": _safe_int(longest_streak_days),
            "current_streak_days": _safe_int(current_streak_days),
            "days_counted": counted_days,
        },
    }
