"""Exact due projections: bounded ready reads, offline snapshot/reconcile.

The first rollout reuses durable deck revision tokens. Invalid stamps retain
the raw API contract until a worker rebuild; old counts never appear current.
"""

from datetime import date, datetime, timezone
import math

from flask import current_app

from app.repositories import forecast_snapshot_repository as repository
from app.repositories.note_analytics_read_repository import state_interval_days
from app.repositories.stats_query_repository import _progress_due_local_day, query_consolidated_forecast_rows
from app.repositories.study_authority_repository import read_study_authority_route
from app.repositories.study_repository import REVIEW_QUEUE, normalize_progress_queue
from app.services.anki_scheduler import _day_index_to_datetime
from app.services.deck_count_snapshot_service import _fresh_session, _snapshot
from app.services.review_analytics_policy import ReviewAnalyticsPolicy, resolve_review_analytics_policy
from app.services.analytics_summary_readiness import require_ready_summary


def _utc(moment):
    return moment.astimezone(timezone.utc).replace(tzinfo=None) if moment.tzinfo else moment


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _stamp(session, *, user_id, deck_ids, policy, now):
    route = read_study_authority_route(session, learner_user_id=user_id)
    if route.mode_code != "NOTE" or route.storage_profile != "CONSOLIDATED_V1":
        return None
    day = policy.study_day(now).toordinal()
    return {"user_id": user_id, "scope_hash": repository.scope_key(deck_ids),
            "study_day": day, "policy_hash": policy.policy_hash,
            "dependency_hash": repository.dependency_hash(session, user_id=user_id, deck_ids=deck_ids),
            "valid_until_utc": _day_index_to_datetime(day + 1, policy.day_boundary_hour,
                                                      timezone_name=policy.timezone_name)}


def _valid(header, stamp, now):
    return header is not None and stamp is not None and now < header["valid_until_utc"] and all(
        header[name] == stamp[name] for name in stamp)


def _resolve(session, *, user_id, deck_ids, timezone_name, day_boundary_hour, now):
    if current_app.config.get("FORECAST_SUMMARY_READ_MODE", "raw") != "summary":
        return None
    allowlist = current_app.config.get("FORECAST_SUMMARY_READ_USER_IDS", ())
    allowlist = allowlist.split(",") if isinstance(allowlist, str) else allowlist
    if allowlist and str(user_id) not in {str(item) for item in allowlist}:
        return None
    if not current_app.config.get("DECK_COUNT_WRITE_ENABLED", False):
        require_ready_summary(user_id=user_id, metric="forecast")
        return None
    policy = ReviewAnalyticsPolicy(timezone_name, int(day_boundary_hour))
    with session.no_autoflush:
        stamp = _stamp(session, user_id=user_id, deck_ids=deck_ids, policy=policy, now=now)
        if stamp is None:
            require_ready_summary(user_id=user_id, metric="forecast")
            return None
        header = repository.read_header(session, user_id=user_id, scope_hash=stamp["scope_hash"])
        if not _valid(header, stamp, now):
            require_ready_summary(user_id=user_id, metric="forecast")
            return None
    return header


def resolve_forecast_summary(session, *, user_id, deck_ids, timezone_name, day_boundary_hour,
                             now_utc, backlog, end_offset):
    """Return the same bucket/load contract as the raw forecast, or None."""
    now = _utc(now_utc)
    header = _resolve(session, user_id=user_id, deck_ids=deck_ids, timezone_name=timezone_name,
                      day_boundary_hour=day_boundary_hour, now=now)
    if header is None:
        return None
    today = header["study_day"]
    rows = repository.read_buckets(session, user_id=user_id, scope_hash=header["scope_hash"],
        start_day=None if backlog else today,
        end_day=None if end_offset is None else today + end_offset)
    by_offset = {}
    for day, queue, count in rows:
        bucket = by_offset.setdefault(day - today, {"due_count": 0, "new": 0,
            "learning": 0, "review": 0, "relearning": 0})
        bucket["due_count"] += int(count)
        if queue in {"new", "learning", "review", "relearning"}:
            bucket[queue] += int(count)
    return by_offset, min((offset for offset in by_offset if offset < 0), default=0), header["daily_load"]


def resolve_overview_due_counts(session, *, user_id, timezone_name, day_boundary_hour,
                                start_local_day, end_local_day, now_utc):
    """Overview folds overdue buckets to its first day, in the raw forecast's unit."""
    header = _resolve(session, user_id=user_id, deck_ids=None, timezone_name=timezone_name,
                      day_boundary_hour=day_boundary_hour, now=_utc(now_utc))
    if header is None:
        return None
    rows = repository.read_buckets(session, user_id=user_id, scope_hash=header["scope_hash"],
                                   end_day=end_local_day.toordinal() - 1)
    result = {}
    for day, _queue, count in rows:
        day = date.fromordinal(max(day, start_local_day.toordinal()))
        result[day] = result.get(day, 0) + int(count)
    return result


def prewarm_forecast_summary(*, user_id, deck_ids=None, now_utc=None, session_factory=None,
                             max_buckets=4096, force=False):
    """Stream a consistent snapshot, then reject changed source stamps.

    Cap distinct buckets without loading Note entities/full scheduler payloads.
    Publication changes only projections and is atomic under crash/retry.
    """
    if not current_app.config.get("DECK_COUNT_WRITE_ENABLED", False):
        return {"ok": False, "error": "WRITER_COVERAGE_DISABLED"}
    if not 1 <= int(max_buckets) <= 65536:
        raise ValueError("max_buckets must be between 1 and 65536")
    user_id = int(user_id)
    now = _utc(now_utc or _now())
    with _fresh_session(session_factory) as session, _snapshot(session):
        policy = resolve_review_analytics_policy(session, user_id)
        captured = _stamp(session, user_id=user_id, deck_ids=deck_ids, policy=policy, now=now)
        if captured is None:
            return {"ok": False, "error": "UNSUPPORTED_AUTHORITY"}
        header = repository.read_header(session, user_id=user_id, scope_hash=captured["scope_hash"])
        if not force and _valid(header, captured, now):
            return {"ok": True, "user_id": user_id, "cached": True, "published": False,
                    "bucket_count": header["bucket_count"]}
        buckets, loads, note_rows = {}, [], 0
        rows = query_consolidated_forecast_rows(user_id=user_id, scope_deck_ids=deck_ids,
                                               session=session, stream=True)
        for _note, queue, due_at, due_day, suspended, state_type, interval, weight in rows:
            note_rows += 1
            if suspended:
                continue
            if normalize_progress_queue(state_type) == REVIEW_QUEUE:
                loads.append(int(weight) / max(1.0, state_interval_days(interval)))
            day = _progress_due_local_day(due_at=due_at, due_day=due_day, queue_value=queue,
                timezone_name=policy.timezone_name, day_boundary_hour_local=policy.day_boundary_hour)
            if day is not None:
                key = (day.toordinal(), normalize_progress_queue(queue))
                buckets[key] = buckets.get(key, 0) + int(weight)
                if len(buckets) > max_buckets:
                    return {"ok": False, "error": "BUCKET_BUDGET_EXCEEDED", "published": False}
        # The same order-free sum as the raw forecast, so both read the same load.
        load = math.fsum(loads)
        if not math.isfinite(load):
            raise ValueError("Forecast daily load must be finite")
    with _fresh_session(session_factory) as session:
        if session.get_bind().dialect.name == "mysql":
            session.connection(execution_options={"isolation_level": "READ COMMITTED"})
        policy = resolve_review_analytics_policy(session, user_id)
        published_at = _utc(now_utc or _now())
        current = _stamp(session, user_id=user_id, deck_ids=deck_ids, policy=policy, now=published_at)
        if current != captured or published_at >= captured["valid_until_utc"]:
            session.rollback()
            return {"ok": True, "user_id": user_id, "published": False, "discarded": True}
        repository.publish_snapshot(session, header={**captured, "daily_load": load,
            "bucket_count": len(buckets), "computed_at": now}, buckets=sorted(buckets.items()))
        session.commit()
    return {"ok": True, "user_id": user_id, "published": True,
            "bucket_count": len(buckets), "note_rows_examined": note_rows}
