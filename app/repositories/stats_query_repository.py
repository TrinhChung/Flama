"""Repository for statistics queries."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from sqlalchemy import and_, case, func, literal, or_, select, text, union_all

from models import db
from models.card import Card
from models.flashcard import DeckCloneDeckMap, DeckInstall, Note
from models.flashcard import ReviewEvent
from app.services.anki_scheduler import _day_index
from app.repositories.study_repository import REVIEW_QUEUE, normalize_progress_queue

UTC = timezone.utc
# Reviews and due dates of this app fall in these years. Sampling the 1st and
# 15th of every month catches DST and any offset change lasting 16+ days.
_FIXED_OFFSET_SAMPLE_YEARS = range(2000, 2041)


def forecast_counts_notes() -> bool:
    """Due forecasts count what the learner answers, as the dashboard does.

    With Note-unit counting (D6-04) a Note's Cards share one state and one
    answer, so each scheduled Note is one item; otherwise each Card counts.
    """
    from flask import current_app, has_app_context

    return has_app_context() and bool(current_app.config.get("STUDY_NOTE_COUNT_ENABLED", False))


@lru_cache(maxsize=1)
def _zone_names_by_upper() -> dict[str, str]:
    return {name.upper(): name for name in available_timezones()}


@lru_cache(maxsize=512)
def fixed_utc_offset_minutes(timezone_name: str | None) -> int | None:
    """The zone's constant UTC offset in minutes, or None if it ever changes.

    A constant offset lets SQL group local days with plain arithmetic, with
    no MySQL timezone tables. Decided from the zone's rules rather than a
    name list, so aliases (Asia/Saigon) and half-hour zones qualify too.
    Names match case-insensitively, as the former fixed-offset table did.
    """
    name = str(timezone_name or "").strip()
    if not name:
        return None
    try:
        zone = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        canonical = _zone_names_by_upper().get(name.upper())
        if canonical is None:
            return None
        zone = ZoneInfo(canonical)
    offsets = {
        datetime(year, month, day, 12, tzinfo=UTC).astimezone(zone).utcoffset()
        for year in _FIXED_OFFSET_SAMPLE_YEARS for month in range(1, 13) for day in (1, 15)
    }
    if len(offsets) != 1:
        return None
    return int(offsets.pop().total_seconds() // 60)


def learner_presentation_scope(*, learner_user_id: int, scope_deck_ids: list[int] | None = None):
    """Owned active presentations and installed release presentations.

    Source Notes are mapped onto each install's local decks. A release may pin
    a retired application; local-added Notes are included in the owned branch.
    Consumers embedding this subquery must set include_retired_cards=True on
    their outer statement. The owned branch explicitly limits applications to
    ACTIVE, so propagating that option never revives retired owned cards.
    """
    from app.repositories.flashcards_share_repository import clone_source_card_visibility

    owned = select(Note.deck_id.label("deck_id"), Card.id.label("card_id"),
                   Card.note_id.label("note_id")).select_from(Card).join(Note, Card.note_id == Note.id).where(
        Note.user_id == int(learner_user_id), Card.application_status == "ACTIVE",
    )
    installed = select(DeckCloneDeckMap.local_deck_id.label("deck_id"), Card.id.label("card_id"),
                       Card.note_id.label("note_id")).select_from(Card).join(Note, Card.note_id == Note.id).join(
        DeckCloneDeckMap, DeckCloneDeckMap.source_deck_id == Note.deck_id,
    ).join(DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id).where(
        DeckInstall.user_id == int(learner_user_id), DeckInstall.clone_mode == "logical_overlay",
        DeckInstall.local_deck_id.isnot(None), DeckCloneDeckMap.local_deck_id.isnot(None),
        or_(DeckInstall.source_owner_user_id.is_(None), Note.user_id == DeckInstall.source_owner_user_id),
        clone_source_card_visibility(DeckInstall),
    )
    if scope_deck_ids is not None:
        owned = owned.where(Note.deck_id.in_(scope_deck_ids))
        installed = installed.where(DeckCloneDeckMap.local_deck_id.in_(scope_deck_ids))
    rows = union_all(owned, installed).subquery("learner_presentations_all")
    return select(rows.c.deck_id, rows.c.card_id, rows.c.note_id).distinct().subquery("learner_presentations")


def query_consolidated_forecast_rows(*, user_id: int, scope_deck_ids: list[int] | None, session=None, stream=False):
    """Current availability/interval once per scoped Note, with its forecast weight.

    The weight is 1 under :func:`forecast_counts_notes`, else the Card count.
    Multiple installs of the same source presentation contribute once to a
    collection forecast; a scoped local deck still resolves its own install.
    """
    from app.repositories.note_analytics_read_repository import note_rows
    from app.repositories.note_analytics_scope_repository import collection_note_scope

    session = db.session if session is None else session
    by_note = forecast_counts_notes()
    scope = collection_note_scope(session, learner_user_id=user_id, deck_ids=scope_deck_ids, by_note=by_note)
    rows = note_rows(scope, learner_user_id=user_id, include_state=True).subquery("forecast_notes")
    statement = select(
        rows.c.note_id, rows.c.queue, rows.c.due_at,
        rows.c.due_day, rows.c.is_suspended, rows.c.state_type,
        rows.c.interval_token, literal(1).label("card_count") if by_note else rows.c.card_count,
    ).execution_options(include_retired_cards=True)
    if stream:
        return session.execute(statement.execution_options(yield_per=500))
    return session.execute(statement).all()


def can_use_mysql_local_day_sql(*, timezone_name: str) -> bool:
    """Use SQL for fixed-offset zones without requiring MySQL timezone tables."""
    bind = db.session.get_bind()
    if bind is None or bind.dialect.name != "mysql":
        return False
    return fixed_utc_offset_minutes(timezone_name) is not None


def _mysql_local_timestamp(timezone_name: str):
    offset = fixed_utc_offset_minutes(timezone_name)
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


def _utc_to_business_day(
    moment: datetime,
    *,
    timezone_name: str,
    day_boundary_hour_local: int,
) -> date:
    offset_min = fixed_utc_offset_minutes(timezone_name)
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


def query_canonical_future_due_day_counts_mysql(
    *,
    user_id: int,
    timezone_name: str,
    day_boundary_hour_local: int,
    start_local_day: date,
    end_local_day: date,
) -> dict[date, int]:
    """Group the existing NOTE Card availability scope for fixed-offset zones.

    Keep the canonical scope and availability joins: ``live_note_id`` and
    ``logical_note_key`` agree on valid rows, but the database does not enforce
    that identity relationship. Collapsing the joins would change reads of
    detached or drifted evidence. Sibling Cards each contribute one count
    unless :func:`forecast_counts_notes`, then each Note does.
    """
    from app.repositories import note_analytics_read_repository as note_reads
    from app.repositories.note_analytics_scope_repository import collection_note_scope

    offset = fixed_utc_offset_minutes(timezone_name)
    shift = int(offset) - int(day_boundary_hour_local) * 60
    by_note = forecast_counts_notes()
    # A due value implies current state (ck_sp_subject_progress_group), so the
    # due filter below alone keeps the scheduled Notes.
    scope = collection_note_scope(db.session, learner_user_id=user_id, by_note=by_note)
    rows = note_reads.note_rows(scope, learner_user_id=user_id).subquery("availability")
    # TO_DAYS has a year-zero origin; Python date ordinals start at 0001-01-01.
    # Review due_day overrides due_at; every other queue uses its UTC timestamp.
    day = case(
        (
            and_(
                func.lower(func.trim(rows.c.queue)) == REVIEW_QUEUE,
                rows.c.due_day.isnot(None),
            ),
            rows.c.due_day,
        ),
        else_=func.to_days(
            func.date_add(rows.c.due_at, text(f"INTERVAL {shift} MINUTE"))
        ) - 365,
    )
    folded = func.greatest(day, start_local_day.toordinal())
    statement = (
        select(folded.label("day_index"),
               (func.count() if by_note else func.sum(rows.c.card_count)).label("cards"))
        .select_from(rows)
        .where(
            or_(rows.c.is_suspended.is_(False), rows.c.is_suspended.is_(None)),
            or_(rows.c.due_at.isnot(None), rows.c.due_day.isnot(None)),
            # Match date.fromordinal's invalid-date rejection in the Python path.
            day.between(1, date.max.toordinal()),
            day < end_local_day.toordinal(),
        )
        .group_by(folded)
        .execution_options(include_retired_cards=True)
    )
    return {
        date.fromordinal(int(day_index)): int(count)
        for day_index, count in db.session.execute(statement).all()
    }


# For a learner's months-long day range MySQL picks (user_id, client_event_id),
# a prefix match that reads every review of the learner before filtering the
# days (one-day ranges already use this index). The hint reads only the
# requested days; MySQL ignores it if the index is missing.
_USER_DAY_RANGE_HINT = "/*+ INDEX(review_events ix_review_events_user_reviewed_at) */"


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
        .prefix_with(_USER_DAY_RANGE_HINT, dialect="mysql")
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
        .prefix_with(_USER_DAY_RANGE_HINT, dialect="mysql")
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


def _query_daily_review_aggregates_raw(
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


def _query_active_review_days_raw(
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


def _query_today_review_summary_raw(
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


def _query_user_daily_study_time_mysql(
    *,
    user_id: int,
    scope_deck_ids: list[int] | None,
    timezone_name: str,
    start_utc: datetime,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> dict[date, dict[str, Any]]:
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
    passed_expr = db.func.coalesce(
        db.func.sum(
            db.case(
                (ReviewEvent.rating.in_(["good", "easy", "3", "4"]), 1),
                else_=0,
            )
        ),
        0,
    )

    query = (
        db.session.query(
            local_day_expr.label("local_day"),
            db.func.count(ReviewEvent.id).label("total_reviews"),
            duration_expr.label("total_duration_ms"),
            passed_expr.label("passed_reviews"),
        )
        .prefix_with(_USER_DAY_RANGE_HINT, dialect="mysql")
        .filter(
            ReviewEvent.user_id == user_id,
            ReviewEvent.reviewed_at >= start_utc,
            ReviewEvent.reviewed_at < end_utc,
        )
    )

    if scope_deck_ids is not None:
        if not scope_deck_ids:
            return {}
        query = query.filter(ReviewEvent.deck_id.in_(scope_deck_ids))

    rows = query.group_by(local_day_expr).all()

    by_day: dict[date, dict[str, Any]] = {}
    for local_day, total_reviews, total_duration_ms, passed_reviews in rows:
        parsed_day = _parse_sql_day(local_day)
        if not parsed_day:
            continue
        tot_rev = _safe_int(total_reviews)
        dur_ms = max(0, _safe_int(total_duration_ms))
        pass_rev = _safe_int(passed_reviews)
        dur_min = round(dur_ms / 60000.0, 1)
        dur_hrs = round(dur_ms / 3600000.0, 2)
        pass_rate = round((pass_rev / float(tot_rev)) * 100.0, 1) if tot_rev > 0 else 0.0

        by_day[parsed_day] = {
            "total_reviews": tot_rev,
            "total_duration_ms": dur_ms,
            "total_duration_minutes": dur_min,
            "total_duration_hours": dur_hrs,
            "avg_study_minutes": dur_min,
            "passed_reviews": pass_rev,
            "retention_pass_rate": pass_rate,
        }
    return by_day


def _query_user_daily_study_time_python(
    *,
    user_id: int,
    scope_deck_ids: list[int] | None,
    timezone_name: str,
    start_utc: datetime,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> dict[date, dict[str, Any]]:
    query = db.session.query(
        ReviewEvent.reviewed_at,
        ReviewEvent.duration_ms,
        ReviewEvent.rating,
        ReviewEvent.deck_id,
    ).prefix_with(_USER_DAY_RANGE_HINT, dialect="mysql").filter(
        ReviewEvent.user_id == user_id,
        ReviewEvent.reviewed_at >= start_utc,
        ReviewEvent.reviewed_at < end_utc,
    )

    if scope_deck_ids is not None:
        if not scope_deck_ids:
            return {}
        query = query.filter(ReviewEvent.deck_id.in_(scope_deck_ids))

    rows = query.all()

    temp_by_day: dict[date, dict[str, int]] = {}
    for reviewed_at, duration_ms, rating, _ in rows:
        if reviewed_at is None:
            continue
        local_day = _utc_to_business_day(
            reviewed_at,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour_local,
        )
        bucket = temp_by_day.setdefault(
            local_day,
            {"total_reviews": 0, "total_duration_ms": 0, "passed_reviews": 0},
        )
        bucket["total_reviews"] += 1
        dur = _safe_int(duration_ms)
        if dur > 0:
            bucket["total_duration_ms"] += dur
        if str(rating or "").strip().lower() in {"good", "easy", "3", "4"}:
            bucket["passed_reviews"] += 1

    by_day: dict[date, dict[str, Any]] = {}
    for day, data in temp_by_day.items():
        tot_rev = data["total_reviews"]
        dur_ms = data["total_duration_ms"]
        pass_rev = data["passed_reviews"]
        dur_min = round(dur_ms / 60000.0, 1)
        dur_hrs = round(dur_ms / 3600000.0, 2)
        pass_rate = round((pass_rev / float(tot_rev)) * 100.0, 1) if tot_rev > 0 else 0.0

        by_day[day] = {
            "total_reviews": tot_rev,
            "total_duration_ms": dur_ms,
            "total_duration_minutes": dur_min,
            "total_duration_hours": dur_hrs,
            "avg_study_minutes": dur_min,
            "passed_reviews": pass_rev,
            "retention_pass_rate": pass_rate,
        }
    return by_day


def _query_user_daily_study_time_raw(
    *,
    user_id: int,
    scope_deck_ids: list[int] | None,
    timezone_name: str,
    start_utc: datetime,
    end_utc: datetime,
    day_boundary_hour_local: int,
) -> dict[date, dict[str, Any]]:
    if can_use_mysql_local_day_sql(timezone_name=timezone_name):
        return _query_user_daily_study_time_mysql(
            user_id=user_id,
            scope_deck_ids=scope_deck_ids,
            timezone_name=timezone_name,
            start_utc=start_utc,
            end_utc=end_utc,
            day_boundary_hour_local=day_boundary_hour_local,
        )
    return _query_user_daily_study_time_python(
        user_id=user_id,
        scope_deck_ids=scope_deck_ids,
        timezone_name=timezone_name,
        start_utc=start_utc,
        end_utc=end_utc,
        day_boundary_hour_local=day_boundary_hour_local,
    )


def query_daily_review_aggregates(
    *, user_id: int, timezone_name: str, timezone_obj,
    start_utc: datetime, end_utc: datetime, day_boundary_hour_local: int,
) -> dict[date, dict[str, int]]:
    from app.repositories import review_analytics_read_repository as projection

    def summary(generation, policy):
        rows = projection.daily_measures(
            user_id=user_id, generation=generation, policy=policy,
            start_utc=start_utc, end_utc=end_utc,
        )
        if rows is None:
            return None
        return {day: {"cards": row["count"], "duration_ms": row["duration_ms"]}
                for day, row in rows.items()}

    return projection.read_or_raw(
        metric="daily_reviews", user_id=user_id, timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local, summary=summary,
        raw=lambda: _query_daily_review_aggregates_raw(
            user_id=user_id, timezone_name=timezone_name, timezone_obj=timezone_obj,
            start_utc=start_utc, end_utc=end_utc,
            day_boundary_hour_local=day_boundary_hour_local,
        ),
    )


def query_active_review_days(
    *, user_id: int, timezone_name: str, timezone_obj,
    end_utc: datetime, day_boundary_hour_local: int,
) -> set[date]:
    from app.repositories import review_analytics_read_repository as projection

    return projection.read_or_raw(
        metric="active_days", user_id=user_id, timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local,
        summary=lambda generation, policy: projection.active_days(
            user_id=user_id, generation=generation, policy=policy, end_utc=end_utc,
        ),
        raw=lambda: _query_active_review_days_raw(
            user_id=user_id, timezone_name=timezone_name, timezone_obj=timezone_obj,
            end_utc=end_utc, day_boundary_hour_local=day_boundary_hour_local,
        ),
    )


def query_today_review_summary(
    *, user_id: int, scope_deck_ids: list[int] | None,
    today_start_utc: datetime, tomorrow_start_utc: datetime,
    timezone_name: str | None = None, day_boundary_hour_local: int | None = None,
) -> tuple[int, int]:
    from app.repositories import review_analytics_read_repository as projection

    if scope_deck_ids is not None and not scope_deck_ids:
        return 0, 0

    def summary(generation, policy):
        rows = projection.daily_measures(
            user_id=user_id, generation=generation, policy=policy,
            start_utc=today_start_utc, end_utc=tomorrow_start_utc,
            scope_deck_ids=scope_deck_ids,
        )
        if rows is None:
            return None
        return sum(row["count"] for row in rows.values()), sum(
            row["duration_ms"] for row in rows.values()
        )

    return projection.read_or_raw(
        metric="today_reviews", user_id=user_id, timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local, summary=summary,
        raw=lambda: _query_today_review_summary_raw(
            user_id=user_id, scope_deck_ids=scope_deck_ids,
            today_start_utc=today_start_utc, tomorrow_start_utc=tomorrow_start_utc,
        ),
    )


def query_user_daily_study_time(
    *, user_id: int, scope_deck_ids: list[int] | None, timezone_name: str,
    start_utc: datetime, end_utc: datetime, day_boundary_hour_local: int,
) -> dict[date, dict[str, Any]]:
    from app.repositories import review_analytics_read_repository as projection

    if scope_deck_ids is not None and not scope_deck_ids:
        return {}

    def summary(generation, policy):
        rows = projection.daily_measures(
            user_id=user_id, generation=generation, policy=policy,
            start_utc=start_utc, end_utc=end_utc, scope_deck_ids=scope_deck_ids,
        )
        if rows is None:
            return None
        result = {}
        for day, row in rows.items():
            total, duration, passed = row["count"], row["duration_ms"], row["passed"]
            minutes = round(duration / 60000.0, 1)
            result[day] = {
                "total_reviews": total,
                "total_duration_ms": duration,
                "total_duration_minutes": minutes,
                "total_duration_hours": round(duration / 3600000.0, 2),
                "avg_study_minutes": minutes,
                "passed_reviews": passed,
                "retention_pass_rate": round(passed / float(total) * 100.0, 1)
                if total > 0 else 0.0,
            }
        return result

    return projection.read_or_raw(
        metric="study_time", user_id=user_id, timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour_local, summary=summary,
        raw=lambda: _query_user_daily_study_time_raw(
            user_id=user_id, scope_deck_ids=scope_deck_ids, timezone_name=timezone_name,
            start_utc=start_utc, end_utc=end_utc,
            day_boundary_hour_local=day_boundary_hour_local,
        ),
    )
