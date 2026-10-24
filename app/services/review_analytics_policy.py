"""Immutable temporal policy for rebuildable ReviewEvent projections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import zoneinfo

from sqlalchemy import select


@lru_cache(maxsize=128)
def _timezone_rules_fingerprint(timezone_name: str) -> str:
    """Identify the TZif data that ZoneInfo uses, without hashing app releases.

    Offset strings have no TZif file and use the existing fixed-offset parser.
    An explicit version is useful when operators ship their own timezone data.
    """
    for root in zoneinfo.TZPATH:
        try:
            raw = Path(root).joinpath(*timezone_name.split("/")).read_bytes()
        except (OSError, ValueError):
            continue
        return "tzif:" + hashlib.sha256(raw).hexdigest()[:56]
    try:
        raw = resources.files("tzdata.zoneinfo").joinpath(*timezone_name.split("/")).read_bytes()
    except (ModuleNotFoundError, OSError, ValueError):
        return "fixed-offset-v1"
    return "tzif:" + hashlib.sha256(raw).hexdigest()[:56]


@dataclass(frozen=True)
class ReviewAnalyticsPolicy:
    timezone_name: str
    day_boundary_hour: int
    grouping_version: int = 1
    timezone_rules_version: str = ""

    def __post_init__(self) -> None:
        # Lazy imports avoid the statistics service/repository import cycle.
        from app.services.stats_overview import get_effective_timezone_name

        effective_timezone = get_effective_timezone_name(self.timezone_name)
        if isinstance(self.day_boundary_hour, bool) or not isinstance(self.day_boundary_hour, int):
            raise ValueError("day_boundary_hour must be an integer between 0 and 23")
        if not 0 <= self.day_boundary_hour <= 23:
            raise ValueError("day_boundary_hour must be an integer between 0 and 23")
        if isinstance(self.grouping_version, bool) or not isinstance(self.grouping_version, int):
            raise ValueError("grouping_version must be a positive integer")
        if not 1 <= self.grouping_version <= 65535:
            raise ValueError("grouping_version must be a positive SMALLINT")
        rules = str(self.timezone_rules_version or "").strip()
        if not rules:
            from flask import current_app, has_app_context

            if has_app_context():
                rules = str(current_app.config.get("REVIEW_ANALYTICS_TIMEZONE_RULES_VERSION") or "").strip()
        if not rules:
            rules = os.environ.get("REVIEW_ANALYTICS_TIMEZONE_RULES_VERSION", "").strip()
        if not rules:
            rules = _timezone_rules_fingerprint(effective_timezone)
        if not rules or len(rules) > 64:
            raise ValueError("timezone_rules_version must contain 1 to 64 characters")
        object.__setattr__(self, "timezone_name", effective_timezone)
        object.__setattr__(self, "timezone_rules_version", rules)

    @property
    def policy_hash(self) -> bytes:
        payload = {
            "timezone_name": self.timezone_name,
            "day_boundary_hour": self.day_boundary_hour,
            "grouping_version": self.grouping_version,
            "timezone_rules_version": self.timezone_rules_version,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).digest()

    def study_day(self, utc_naive: datetime) -> date:
        from app.repositories.stats_query_repository import _utc_to_business_day

        if not isinstance(utc_naive, datetime):
            raise TypeError("study_day requires a datetime")
        if utc_naive.tzinfo is not None:
            utc_naive = utc_naive.astimezone(timezone.utc).replace(tzinfo=None)
        return _utc_to_business_day(
            utc_naive,
            timezone_name=self.timezone_name,
            day_boundary_hour_local=self.day_boundary_hour,
        )


def policy_from_generation(generation) -> ReviewAnalyticsPolicy:
    policy = ReviewAnalyticsPolicy(
        timezone_name=generation.timezone_name,
        day_boundary_hour=int(generation.day_boundary_hour),
        grouping_version=int(generation.grouping_version),
        timezone_rules_version=generation.timezone_rules_version,
    )
    if bytes(generation.policy_hash) != policy.policy_hash:
        raise ValueError("Review analytics generation has an invalid policy hash")
    return policy


def resolve_review_analytics_policy(session, user_id: int) -> ReviewAnalyticsPolicy:
    """Resolve settings on the caller's Session, including backfill Sessions."""
    from app.services.scheduler_config_service import resolve_scheduler_runtime_settings
    from models.user import User
    from models.user_scheduler_settings import UserSchedulerSettings

    user_timezone = session.execute(
        select(User.timezone).where(User.id == int(user_id))
    ).one_or_none()
    if user_timezone is None:
        raise ValueError("Review analytics user does not exist")
    settings = session.execute(
        select(UserSchedulerSettings).where(UserSchedulerSettings.user_id == int(user_id))
    ).scalar_one_or_none()
    runtime = resolve_scheduler_runtime_settings(user_id=None, settings_row=settings)
    return ReviewAnalyticsPolicy(
        timezone_name=user_timezone[0],
        day_boundary_hour=int(runtime.day_boundary_hour_local),
    )


def uses_mysql_day_sql(policy: ReviewAnalyticsPolicy, dialect_name: str) -> bool:
    from app.repositories.stats_query_repository import fixed_utc_offset_minutes

    return dialect_name == "mysql" and fixed_utc_offset_minutes(policy.timezone_name) is not None


def passed_count_for_policy(
    policy: ReviewAnalyticsPolicy, rating, sql_passed, dialect_name: str,
) -> int:
    """Keep the existing raw SQL/Python reader's rating semantics per policy."""
    if uses_mysql_day_sql(policy, dialect_name):
        return int(sql_passed or 0)
    return int(str(rating or "").strip().lower() in {"good", "easy", "3", "4"})
