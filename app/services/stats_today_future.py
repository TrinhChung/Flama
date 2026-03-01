"""Statistics helpers for Today and Future Due sections."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask_login import current_user

from app.repositories.stats_query_repository import query_today_review_summary
from app.repositories.deck_tree_query import (
    collect_subtree_ids,
    query_accessible_stats_decks,
)
from app.repositories.stats_query_repository import (
    aggregate_future_due_offsets_mysql,
    query_due_queue_rows_python,
    query_interval_days_rows,
)
from app.utils.permissions import is_admin_user
from models import db

UTC = timezone.utc
DEFAULT_TIMEZONE = "UTC"
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


def _ensure_naive_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


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


def _effective_timezone_name(raw_timezone: Any) -> str:
    candidate = str(raw_timezone or "").strip()
    if not candidate:
        return DEFAULT_TIMEZONE
    if candidate.upper() in {"UTC", "ETC/UTC", "GMT"}:
        return DEFAULT_TIMEZONE
    if not _is_supported_timezone_name(candidate):
        return DEFAULT_TIMEZONE
    return candidate


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round2(value: float) -> float:
    return round(float(value) + 1e-12, 2)


def _local_start_to_utc_naive(day_value: date, timezone_obj) -> datetime:
    local_start = datetime.combine(day_value, time.min, tzinfo=timezone_obj)
    return local_start.astimezone(UTC).replace(tzinfo=None)


def _parse_bool(raw_value: Any, default: bool = False) -> bool:
    if raw_value is None:
        return default
    text = str(raw_value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_scope(scope: Any) -> str:
    text = str(scope or "").strip().lower()
    if text in {"deck", "collection"}:
        return text
    return "deck"


def _normalize_history_range(history_range: Any) -> str:
    text = str(history_range or "").strip().lower()
    if text in {"12m", "all"}:
        return text
    return "12m"


def _normalize_future_range(future_range: Any) -> str:
    text = str(future_range or "").strip().lower()
    if text in {"30", "90", "365", "all"}:
        return text
    return "30"


def list_stats_decks(user_id: int) -> list[dict[str, Any]]:
    decks = query_accessible_stats_decks(
        user_id=user_id,
        admin_mode=is_admin_user(current_user),
    )
    return [
        {
            "id": int(deck.id),
            "name": deck.name,
            "parent_id": int(deck.parent_id) if deck.parent_id is not None else None,
        }
        for deck in decks
    ]


def _resolve_scope_deck_ids(*, scope: str, deck_id: int | None) -> list[int] | None:
    if scope != "deck":
        return None
    if deck_id is None:
        return []
    return collect_subtree_ids(deck_id)


def _future_window_end_offset(future_range: str) -> int | None:
    if future_range == "30":
        return 29
    if future_range == "90":
        return 89
    if future_range == "365":
        return 364
    return None


def _aggregate_future_due_python(
    *,
    rows: list[tuple[Any, Any]],
    timezone_obj,
    today_local: date,
    backlog: bool,
    end_offset: int | None,
) -> tuple[dict[int, dict[str, int]], int]:
    by_offset: dict[int, dict[str, int]] = {}

    for due_at, queue_value in rows:
        if due_at is None:
            continue

        due_utc = due_at if due_at.tzinfo else due_at.replace(tzinfo=UTC)
        due_local_day = due_utc.astimezone(timezone_obj).date()
        day_offset = (due_local_day - today_local).days

        if not backlog and day_offset < 0:
            continue
        if end_offset is not None and day_offset > end_offset:
            continue

        queue_norm = str(queue_value or "").strip().lower()
        if queue_norm == "learn":
            queue_norm = "learning"
        bucket = by_offset.setdefault(
            int(day_offset),
            {
                "due_count": 0,
                "new": 0,
                "learning": 0,
                "review": 0,
                "relearning": 0,
            },
        )
        bucket["due_count"] += 1
        if queue_norm in {"new", "learning", "review", "relearning"}:
            bucket[queue_norm] += 1

    min_offset = min((offset for offset in by_offset if offset < 0), default=0)
    return by_offset, min_offset


def _build_future_series(
    *,
    by_offset: dict[int, dict[str, int]],
    today_local: date,
    backlog: bool,
    future_range: str,
    min_negative_offset: int,
    end_offset: int | None,
) -> tuple[list[dict[str, Any]], int, int]:
    if future_range == "all":
        if not by_offset:
            return [], 0, 0
        if backlog:
            start_offset = min(min(by_offset.keys()), 0)
        else:
            start_offset = 0
        end_offset_final = max(by_offset.keys())
    else:
        end_offset_final = end_offset if end_offset is not None else 29
        start_offset = min_negative_offset if backlog else 0
        if start_offset > end_offset_final:
            start_offset = end_offset_final

    series: list[dict[str, Any]] = []
    cumulative = 0
    for offset in range(int(start_offset), int(end_offset_final) + 1):
        bucket = by_offset.get(offset) or {
            "due_count": 0,
            "new": 0,
            "learning": 0,
            "review": 0,
            "relearning": 0,
        }
        due_count = _safe_int(bucket.get("due_count"))
        cumulative += due_count
        series.append(
            {
                "day_offset": offset,
                "date": (today_local + timedelta(days=offset)).isoformat(),
                "due_count": due_count,
                "cumulative": cumulative,
                "breakdown": {
                    "new": _safe_int(bucket.get("new")),
                    "learn": _safe_int(bucket.get("learning")) + _safe_int(bucket.get("relearning")),
                    "review": _safe_int(bucket.get("review")),
                    "relearn": _safe_int(bucket.get("relearning")),
                },
            }
        )

    window_days = len(series)
    return series, window_days, cumulative


def _compute_daily_load(*, user_id: int, scope_deck_ids: list[int] | None) -> float:
    rows = query_interval_days_rows(
        user_id=user_id,
        scope_deck_ids=scope_deck_ids,
    )

    total = 0.0
    for (interval_days,) in rows:
        interval_value = float(interval_days or 0)
        total += 1.0 / max(1.0, interval_value)
    return total


def build_today_future_stats(
    *,
    user_id: int,
    timezone_name: str | None,
    scope: Any,
    deck_id: Any,
    history_range: Any,
    future_range: Any,
    backlog: Any,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    effective_scope = _normalize_scope(scope)
    effective_history_range = _normalize_history_range(history_range)
    effective_future_range = _normalize_future_range(future_range)
    effective_backlog = _parse_bool(backlog, default=False)

    parsed_deck_id: int | None = None
    if deck_id not in (None, ""):
        try:
            parsed_deck_id = int(deck_id)
        except (TypeError, ValueError):
            parsed_deck_id = None

    timezone_effective = _effective_timezone_name(timezone_name)
    timezone_obj = _build_timezone_obj(timezone_effective)
    now_utc_naive = _ensure_naive_utc(now_utc or datetime.utcnow())
    now_local = now_utc_naive.replace(tzinfo=UTC).astimezone(timezone_obj)
    today_local = now_local.date()

    today_start_utc = _local_start_to_utc_naive(today_local, timezone_obj)
    tomorrow_start_utc = _local_start_to_utc_naive(today_local + timedelta(days=1), timezone_obj)

    scope_deck_ids = _resolve_scope_deck_ids(scope=effective_scope, deck_id=parsed_deck_id)

    today_cards, today_duration_ms = query_today_review_summary(
        user_id=user_id,
        scope_deck_ids=scope_deck_ids,
        today_start_utc=today_start_utc,
        tomorrow_start_utc=tomorrow_start_utc,
    )
    today_minutes = _round2(today_duration_ms / 60000.0)
    today_sec_per_card = _round2((today_duration_ms / 1000.0) / today_cards) if today_cards > 0 else 0.0

    end_offset = _future_window_end_offset(effective_future_range)

    dialect = db.session.get_bind().dialect.name if db.session.get_bind() is not None else ""
    if dialect == "mysql":
        due_by_offset, min_negative_offset = aggregate_future_due_offsets_mysql(
            user_id=user_id,
            scope_deck_ids=scope_deck_ids,
            timezone_name=timezone_effective,
            backlog=effective_backlog,
            end_offset=end_offset,
            today_local=today_local,
        )
    else:
        end_utc_exclusive = None
        if end_offset is not None:
            end_utc_exclusive = _local_start_to_utc_naive(today_local + timedelta(days=end_offset + 1), timezone_obj)

        rows = query_due_queue_rows_python(
            user_id=user_id,
            scope_deck_ids=scope_deck_ids,
            today_start_utc=today_start_utc,
            end_utc_exclusive=end_utc_exclusive,
            include_backlog=effective_backlog,
        )
        due_by_offset, min_negative_offset = _aggregate_future_due_python(
            rows=rows,
            timezone_obj=timezone_obj,
            today_local=today_local,
            backlog=effective_backlog,
            end_offset=end_offset,
        )

    series, window_days, total_reviews = _build_future_series(
        by_offset=due_by_offset,
        today_local=today_local,
        backlog=effective_backlog,
        future_range=effective_future_range,
        min_negative_offset=min_negative_offset,
        end_offset=end_offset,
    )
    due_tomorrow = _safe_int((due_by_offset.get(1) or {}).get("due_count"))
    average = (float(total_reviews) / float(window_days)) if window_days > 0 else 0.0
    daily_load = _compute_daily_load(user_id=user_id, scope_deck_ids=scope_deck_ids)

    return {
        "scope": effective_scope,
        "deck_id": parsed_deck_id,
        "history_range": effective_history_range,
        "future_range": effective_future_range,
        "backlog": effective_backlog,
        "timezone": timezone_effective,
        "today": {
            "cards": today_cards,
            "minutes": today_minutes,
            "sec_per_card": today_sec_per_card,
            "has_studied": today_cards > 0,
            "message": (
                f"Studied {today_cards} cards in {today_minutes:.2f} minutes today ({today_sec_per_card:.2f}s/card)"
                if today_cards > 0
                else "No cards have been studied today."
            ),
        },
        "future_due": {
            "series": series,
            "window_days": window_days,
        },
        "totals": {
            "total_reviews": int(total_reviews),
            "avg_reviews_per_day": average,
            "due_tomorrow": int(due_tomorrow),
            "daily_load": daily_load,
        },
    }
