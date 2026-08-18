"""Service layer for Admin Analytics and Growth metrics orchestration."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from app.repositories import admin_analytics_repository

UTC = timezone.utc


def _compute_delta_percent(current: float | int, previous: float | int) -> Optional[float]:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((float(current) - float(previous)) / float(previous)) * 100.0, 1)


def parse_date_range(
    range_preset: Optional[str] = "7d",
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> Tuple[datetime, datetime, datetime, datetime, str]:
    """Resolve start/end UTC datetimes for the current window and previous comparison window.

    Returns: (start_utc, end_utc, prev_start_utc, prev_end_utc, resolved_preset)
    """
    now = datetime.now(UTC).replace(tzinfo=None)
    today_end = datetime.combine(now.date(), time.max)

    if start_date_str and end_date_str:
        try:
            s_date = date.fromisoformat(start_date_str[:10])
            e_date = date.fromisoformat(end_date_str[:10])
            start_utc = datetime.combine(s_date, time.min)
            end_utc = datetime.combine(e_date, time.max)
            duration = end_utc - start_utc
            prev_start_utc = start_utc - duration
            prev_end_utc = start_utc
            return start_utc, end_utc, prev_start_utc, prev_end_utc, "custom"
        except (TypeError, ValueError):
            pass

    preset = (range_preset or "7d").strip().lower()
    if preset == "today":
        start_utc = datetime.combine(now.date(), time.min)
        end_utc = today_end
        prev_start_utc = start_utc - timedelta(days=1)
        prev_end_utc = start_utc
    elif preset == "30d":
        start_utc = datetime.combine(now.date() - timedelta(days=29), time.min)
        end_utc = today_end
        prev_start_utc = start_utc - timedelta(days=30)
        prev_end_utc = start_utc
    elif preset == "90d":
        start_utc = datetime.combine(now.date() - timedelta(days=89), time.min)
        end_utc = today_end
        prev_start_utc = start_utc - timedelta(days=90)
        prev_end_utc = start_utc
    elif preset == "12m":
        start_utc = datetime.combine(now.date() - timedelta(days=364), time.min)
        end_utc = today_end
        prev_start_utc = start_utc - timedelta(days=365)
        prev_end_utc = start_utc
    elif preset == "all":
        start_utc = datetime(2020, 1, 1)
        end_utc = today_end
        prev_start_utc = datetime(2019, 1, 1)
        prev_end_utc = datetime(2020, 1, 1)
    else:  # default "7d"
        preset = "7d"
        start_utc = datetime.combine(now.date() - timedelta(days=6), time.min)
        end_utc = today_end
        prev_start_utc = start_utc - timedelta(days=7)
        prev_end_utc = start_utc

    return start_utc, end_utc, prev_start_utc, prev_end_utc, preset


def get_analytics_overview(
    range_preset: Optional[str] = "7d",
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Build high-level executive KPI overview with delta comparisons."""
    start_utc, end_utc, prev_start_utc, prev_end_utc, resolved_preset = parse_date_range(
        range_preset, start_date_str, end_date_str
    )

    kpis = admin_analytics_repository.query_overall_kpis(
        start_utc=start_utc,
        end_utc=end_utc,
        prev_start_utc=prev_start_utc,
        prev_end_utc=prev_end_utc,
    )

    curr = kpis["current"]
    prev = kpis["previous"]

    deltas = {
        "new_users_delta_pct": _compute_delta_percent(curr["new_users"], prev["new_users"]),
        "active_users_delta_pct": _compute_delta_percent(curr["active_users"], prev["active_users"]),
        "total_reviews_delta_pct": _compute_delta_percent(curr["total_reviews"], prev["total_reviews"]),
        "total_duration_delta_pct": _compute_delta_percent(curr["total_duration_minutes"], prev["total_duration_minutes"]),
        "avg_study_time_delta_pct": _compute_delta_percent(
            curr["avg_study_minutes_per_active_user"], prev["avg_study_minutes_per_active_user"]
        ),
        "revenue_delta_pct": _compute_delta_percent(curr["revenue_minor"], prev["revenue_minor"]),
    }

    top_learners = admin_analytics_repository.query_top_active_learners(start_utc, end_utc, limit=5)

    return {
        "range_preset": resolved_preset,
        "start_date": start_utc.date().isoformat(),
        "end_date": end_utc.date().isoformat(),
        "totals": {
            "users": kpis["total_users"],
            "decks": kpis["total_decks"],
            "notes": kpis["total_notes"],
            "cards": kpis["total_cards"],
            "dau": kpis["dau"],
            "mau": kpis["mau"],
            "stickiness_ratio": kpis["stickiness_ratio"],
        },
        "period_metrics": curr,
        "deltas": deltas,
        "top_learners": top_learners,
    }


def get_user_growth_analytics(
    range_preset: Optional[str] = "7d",
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Build time series for user registrations, cumulative users, and daily active users."""
    start_utc, end_utc, _, _, resolved_preset = parse_date_range(
        range_preset, start_date_str, end_date_str
    )

    time_series = admin_analytics_repository.query_daily_user_growth(start_utc, end_utc)

    return {
        "range_preset": resolved_preset,
        "start_date": start_utc.date().isoformat(),
        "end_date": end_utc.date().isoformat(),
        "data": time_series,
    }


def get_study_time_analytics(
    range_preset: Optional[str] = "7d",
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Build daily study duration breakdown, hourly 24h heatmap, and mode distribution."""
    start_utc, end_utc, _, _, resolved_preset = parse_date_range(
        range_preset, start_date_str, end_date_str
    )

    daily_data = admin_analytics_repository.query_daily_study_time_breakdown(start_utc, end_utc)
    hourly_distribution = admin_analytics_repository.query_hourly_study_distribution(start_utc, end_utc)
    modes_distribution = admin_analytics_repository.query_study_mode_and_scheduler_distribution(start_utc, end_utc)

    # Compute overall period summary
    total_minutes = sum(d["total_duration_minutes"] for d in daily_data)
    total_reviews = sum(d["total_reviews"] for d in daily_data)
    active_days_count = len([d for d in daily_data if d["active_users"] > 0])
    avg_minutes_overall = (
        round(total_minutes / float(max(1, active_days_count)), 1)
        if active_days_count > 0
        else 0.0
    )

    return {
        "range_preset": resolved_preset,
        "start_date": start_utc.date().isoformat(),
        "end_date": end_utc.date().isoformat(),
        "summary": {
            "total_study_minutes": round(total_minutes, 1),
            "total_study_hours": round(total_minutes / 60.0, 2),
            "total_reviews": total_reviews,
            "avg_daily_minutes_system": avg_minutes_overall,
        },
        "daily_time_series": daily_data,
        "hourly_distribution": hourly_distribution,
        "modes_breakdown": modes_distribution["modes"],
        "ratings_breakdown": modes_distribution["ratings"],
        "schedulers_breakdown": modes_distribution["schedulers"],
    }


def get_content_growth_analytics(
    range_preset: Optional[str] = "7d",
    start_date_str: Optional[str] = None,
    end_date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """Build time series for deck, note, card creation and Yomitan/Anki imports."""
    start_utc, end_utc, _, _, resolved_preset = parse_date_range(
        range_preset, start_date_str, end_date_str
    )

    content_series = admin_analytics_repository.query_content_growth_breakdown(start_utc, end_utc)

    return {
        "range_preset": resolved_preset,
        "start_date": start_utc.date().isoformat(),
        "end_date": end_utc.date().isoformat(),
        "data": content_series,
    }


def get_retention_cohorts_analytics(num_weeks: int = 8) -> Dict[str, Any]:
    """Build user retention cohort table."""
    cohorts = admin_analytics_repository.query_retention_cohorts(num_weeks=num_weeks)
    return {
        "cohorts": cohorts,
        "intervals": ["D1", "D7", "D14", "D30"],
    }
