"""Repository for administrative analytics, growth metrics, and study time aggregations."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, distinct, func, or_

from models import db
from models.card import Card
from models.connect_import_session import ConnectImportSession
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.payment_order import PaymentOrder
from models.review_event import ReviewEvent
from models.user import User

UTC = timezone.utc


def _safe_int(val: Any) -> int:
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(val: Any) -> float:
    try:
        return float(val or 0.0)
    except (TypeError, ValueError):
        return 0.0


def query_overall_kpis(
    start_utc: datetime,
    end_utc: datetime,
    prev_start_utc: datetime,
    prev_end_utc: datetime,
) -> Dict[str, Any]:
    """Calculate core KPIs for the current window and previous window for delta calculations."""
    total_users_count = db.session.query(func.count(User.id)).filter(User.is_disabled.is_(False)).scalar() or 0
    total_decks_count = db.session.query(func.count(Deck.id)).filter(Deck.deleted_at.is_(None)).scalar() or 0
    total_notes_count = db.session.query(func.count(Note.id)).scalar() or 0
    total_cards_count = db.session.query(func.count(Card.id)).scalar() or 0

    # Current window metrics
    curr_new_users = (
        db.session.query(func.count(User.id))
        .filter(User.created_at >= start_utc, User.created_at < end_utc)
        .scalar()
        or 0
    )

    curr_active_users = (
        db.session.query(func.count(distinct(ReviewEvent.user_id)))
        .filter(ReviewEvent.reviewed_at >= start_utc, ReviewEvent.reviewed_at < end_utc)
        .scalar()
        or 0
    )

    curr_review_stats = (
        db.session.query(
            func.count(ReviewEvent.id).label("total_reviews"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                ReviewEvent.duration_ms.isnot(None),
                                ReviewEvent.duration_ms > 0,
                            ),
                            ReviewEvent.duration_ms,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("total_duration_ms"),
            func.coalesce(
                func.sum(
                    case(
                        (ReviewEvent.rating.in_(["good", "easy", "3", "4"]), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("passed_reviews"),
        )
        .filter(ReviewEvent.reviewed_at >= start_utc, ReviewEvent.reviewed_at < end_utc)
        .one()
    )
    curr_total_reviews = _safe_int(curr_review_stats.total_reviews)
    curr_total_duration_ms = _safe_int(curr_review_stats.total_duration_ms)
    curr_passed_reviews = _safe_int(curr_review_stats.passed_reviews)

    curr_revenue_stats = (
        db.session.query(
            func.count(PaymentOrder.id).label("paid_orders"),
            func.coalesce(func.sum(PaymentOrder.total_amount_minor), 0).label("total_amount"),
        )
        .filter(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= start_utc,
            PaymentOrder.paid_at < end_utc,
        )
        .one()
    )
    curr_paid_orders = _safe_int(curr_revenue_stats.paid_orders)
    curr_revenue_minor = _safe_int(curr_revenue_stats.total_amount)

    curr_new_cards = (
        db.session.query(func.count(Card.id))
        .filter(Card.created_at >= start_utc, Card.created_at < end_utc)
        .scalar()
        or 0
    )

    # Previous window metrics for delta
    prev_new_users = (
        db.session.query(func.count(User.id))
        .filter(User.created_at >= prev_start_utc, User.created_at < prev_end_utc)
        .scalar()
        or 0
    )

    prev_active_users = (
        db.session.query(func.count(distinct(ReviewEvent.user_id)))
        .filter(ReviewEvent.reviewed_at >= prev_start_utc, ReviewEvent.reviewed_at < prev_end_utc)
        .scalar()
        or 0
    )

    prev_review_stats = (
        db.session.query(
            func.count(ReviewEvent.id).label("total_reviews"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                ReviewEvent.duration_ms.isnot(None),
                                ReviewEvent.duration_ms > 0,
                            ),
                            ReviewEvent.duration_ms,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("total_duration_ms"),
        )
        .filter(ReviewEvent.reviewed_at >= prev_start_utc, ReviewEvent.reviewed_at < prev_end_utc)
        .one()
    )
    prev_total_reviews = _safe_int(prev_review_stats.total_reviews)
    prev_total_duration_ms = _safe_int(prev_review_stats.total_duration_ms)

    prev_revenue_stats = (
        db.session.query(
            func.count(PaymentOrder.id).label("paid_orders"),
            func.coalesce(func.sum(PaymentOrder.total_amount_minor), 0).label("total_amount"),
        )
        .filter(
            PaymentOrder.status == "paid",
            PaymentOrder.paid_at >= prev_start_utc,
            PaymentOrder.paid_at < prev_end_utc,
        )
        .one()
    )
    prev_revenue_minor = _safe_int(prev_revenue_stats.total_amount)

    # Calculate average study time (minutes) per active user
    curr_avg_study_minutes_per_active_user = (
        round((curr_total_duration_ms / 60000.0) / max(1, curr_active_users), 1)
        if curr_active_users > 0
        else 0.0
    )
    prev_avg_study_minutes_per_active_user = (
        round((prev_total_duration_ms / 60000.0) / max(1, prev_active_users), 1)
        if prev_active_users > 0
        else 0.0
    )

    # Calculate retention pass rate %
    retention_pass_rate = (
        round((curr_passed_reviews / float(curr_total_reviews)) * 100.0, 1)
        if curr_total_reviews > 0
        else 0.0
    )

    # MAU and 30-day active for Stickiness
    thirty_days_ago = end_utc - timedelta(days=30)
    mau_count = (
        db.session.query(func.count(distinct(ReviewEvent.user_id)))
        .filter(ReviewEvent.reviewed_at >= thirty_days_ago, ReviewEvent.reviewed_at < end_utc)
        .scalar()
        or 0
    )

    # DAU (last 24 hours of window)
    one_day_ago = end_utc - timedelta(days=1)
    dau_count = (
        db.session.query(func.count(distinct(ReviewEvent.user_id)))
        .filter(ReviewEvent.reviewed_at >= one_day_ago, ReviewEvent.reviewed_at < end_utc)
        .scalar()
        or 0
    )

    stickiness_ratio = (
        round((float(dau_count) / float(mau_count)) * 100.0, 1)
        if mau_count > 0
        else 0.0
    )

    return {
        "total_users": total_users_count,
        "total_decks": total_decks_count,
        "total_notes": total_notes_count,
        "total_cards": total_cards_count,
        "dau": dau_count,
        "mau": mau_count,
        "stickiness_ratio": stickiness_ratio,
        "current": {
            "new_users": curr_new_users,
            "active_users": curr_active_users,
            "total_reviews": curr_total_reviews,
            "total_duration_minutes": round(curr_total_duration_ms / 60000.0, 1),
            "total_duration_hours": round(curr_total_duration_ms / 3600000.0, 2),
            "avg_study_minutes_per_active_user": curr_avg_study_minutes_per_active_user,
            "retention_pass_rate": retention_pass_rate,
            "paid_orders": curr_paid_orders,
            "revenue_minor": curr_revenue_minor,
            "new_cards": curr_new_cards,
        },
        "previous": {
            "new_users": prev_new_users,
            "active_users": prev_active_users,
            "total_reviews": prev_total_reviews,
            "total_duration_minutes": round(prev_total_duration_ms / 60000.0, 1),
            "avg_study_minutes_per_active_user": prev_avg_study_minutes_per_active_user,
            "revenue_minor": prev_revenue_minor,
        },
    }


def query_daily_user_growth(start_utc: datetime, end_utc: datetime) -> List[Dict[str, Any]]:
    """Query daily new user registrations and cumulative active count."""
    date_col = func.date(User.created_at)
    user_rows = (
        db.session.query(
            date_col.label("day"),
            func.count(User.id).label("new_users"),
        )
        .filter(User.created_at >= start_utc, User.created_at < end_utc)
        .group_by(date_col)
        .order_by(date_col.asc())
        .all()
    )

    review_date_col = func.date(ReviewEvent.reviewed_at)
    active_rows = (
        db.session.query(
            review_date_col.label("day"),
            func.count(distinct(ReviewEvent.user_id)).label("active_users"),
            func.count(ReviewEvent.id).label("reviews_count"),
        )
        .filter(ReviewEvent.reviewed_at >= start_utc, ReviewEvent.reviewed_at < end_utc)
        .group_by(review_date_col)
        .order_by(review_date_col.asc())
        .all()
    )

    active_map = {str(r.day)[:10]: (_safe_int(r.active_users), _safe_int(r.reviews_count)) for r in active_rows if r.day}
    new_user_map = {str(r.day)[:10]: _safe_int(r.new_users) for r in user_rows if r.day}

    # Count total users created before start_utc
    base_cumulative = (
        db.session.query(func.count(User.id))
        .filter(User.created_at < start_utc)
        .scalar()
        or 0
    )

    # Build continuous day list
    results: List[Dict[str, Any]] = []
    current_day = start_utc.date()
    end_day = end_utc.date()
    cum_users = base_cumulative

    while current_day <= end_day:
        day_str = current_day.isoformat()
        new_cnt = new_user_map.get(day_str, 0)
        cum_users += new_cnt
        active_cnt, reviews_cnt = active_map.get(day_str, (0, 0))

        results.append({
            "date": day_str,
            "new_users": new_cnt,
            "cumulative_users": cum_users,
            "active_users": active_cnt,
            "reviews_count": reviews_cnt,
        })
        current_day += timedelta(days=1)

    return results


def query_daily_study_time_breakdown(start_utc: datetime, end_utc: datetime) -> List[Dict[str, Any]]:
    """Query daily study duration, active user count, and average study minutes per active user."""
    review_date_col = func.date(ReviewEvent.reviewed_at)
    rows = (
        db.session.query(
            review_date_col.label("day"),
            func.count(distinct(ReviewEvent.user_id)).label("active_users"),
            func.count(ReviewEvent.id).label("total_reviews"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                ReviewEvent.duration_ms.isnot(None),
                                ReviewEvent.duration_ms > 0,
                            ),
                            ReviewEvent.duration_ms,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("total_duration_ms"),
            func.coalesce(
                func.sum(
                    case(
                        (ReviewEvent.rating.in_(["good", "easy", "3", "4"]), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("passed_reviews"),
        )
        .filter(ReviewEvent.reviewed_at >= start_utc, ReviewEvent.reviewed_at < end_utc)
        .group_by(review_date_col)
        .order_by(review_date_col.asc())
        .all()
    )

    data_map: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if not r.day:
            continue
        day_str = str(r.day)[:10]
        act_users = _safe_int(r.active_users)
        tot_revs = _safe_int(r.total_reviews)
        dur_ms = _safe_int(r.total_duration_ms)
        passed = _safe_int(r.passed_reviews)
        dur_min = round(dur_ms / 60000.0, 1)
        dur_hrs = round(dur_ms / 3600000.0, 2)
        avg_min = round(dur_min / max(1, act_users), 1) if act_users > 0 else 0.0
        pass_rate = round((passed / float(tot_revs)) * 100.0, 1) if tot_revs > 0 else 0.0
        cards_per_user = round(tot_revs / float(max(1, act_users)), 1) if act_users > 0 else 0.0

        data_map[day_str] = {
            "date": day_str,
            "active_users": act_users,
            "total_reviews": tot_revs,
            "total_duration_minutes": dur_min,
            "total_duration_hours": dur_hrs,
            "avg_study_minutes_per_user": avg_min,
            "retention_pass_rate": pass_rate,
            "cards_per_user": cards_per_user,
        }

    # Continuous date range
    results: List[Dict[str, Any]] = []
    current_day = start_utc.date()
    end_day = end_utc.date()

    while current_day <= end_day:
        day_str = current_day.isoformat()
        if day_str in data_map:
            results.append(data_map[day_str])
        else:
            results.append({
                "date": day_str,
                "active_users": 0,
                "total_reviews": 0,
                "total_duration_minutes": 0.0,
                "total_duration_hours": 0.0,
                "avg_study_minutes_per_user": 0.0,
                "retention_pass_rate": 0.0,
                "cards_per_user": 0.0,
            })
        current_day += timedelta(days=1)

    return results


def query_hourly_study_distribution(start_utc: datetime, end_utc: datetime) -> List[Dict[str, Any]]:
    """Query review events distribution across the 24 hours of the day (0h to 23h)."""
    hour_col = func.extract("hour", ReviewEvent.reviewed_at)
    rows = (
        db.session.query(
            hour_col.label("hour"),
            func.count(ReviewEvent.id).label("reviews_count"),
            func.count(distinct(ReviewEvent.user_id)).label("unique_users"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                ReviewEvent.duration_ms.isnot(None),
                                ReviewEvent.duration_ms > 0,
                            ),
                            ReviewEvent.duration_ms,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("duration_ms"),
        )
        .filter(ReviewEvent.reviewed_at >= start_utc, ReviewEvent.reviewed_at < end_utc)
        .group_by(hour_col)
        .order_by(hour_col.asc())
        .all()
    )

    hour_map: Dict[int, Tuple[int, int, int]] = {}
    for r in rows:
        if r.hour is not None:
            hour_val = int(r.hour)
            hour_map[hour_val] = (
                _safe_int(r.reviews_count),
                _safe_int(r.unique_users),
                _safe_int(r.duration_ms),
            )

    results: List[Dict[str, Any]] = []
    for h in range(24):
        revs, users, dur_ms = hour_map.get(h, (0, 0, 0))
        results.append({
            "hour": h,
            "hour_label": f"{h:02d}:00",
            "reviews_count": revs,
            "unique_users": users,
            "duration_minutes": round(dur_ms / 60000.0, 1),
        })

    return results


def query_study_mode_and_scheduler_distribution(start_utc: datetime, end_utc: datetime) -> Dict[str, Any]:
    """Query breakdown by study mode (review/learn/relearn/cram) and scheduler algorithm."""
    mode_rows = (
        db.session.query(
            ReviewEvent.mode.label("mode"),
            func.count(ReviewEvent.id).label("count"),
        )
        .filter(ReviewEvent.reviewed_at >= start_utc, ReviewEvent.reviewed_at < end_utc)
        .group_by(ReviewEvent.mode)
        .all()
    )
    modes = [{"mode": r.mode or "review", "count": _safe_int(r.count)} for r in mode_rows]

    rating_rows = (
        db.session.query(
            ReviewEvent.rating.label("rating"),
            func.count(ReviewEvent.id).label("count"),
        )
        .filter(ReviewEvent.reviewed_at >= start_utc, ReviewEvent.reviewed_at < end_utc)
        .group_by(ReviewEvent.rating)
        .all()
    )
    ratings = [{"rating": r.rating or "unknown", "count": _safe_int(r.count)} for r in rating_rows]

    scheduler_rows = (
        db.session.query(
            ReviewEvent.scheduler_mode.label("scheduler"),
            func.count(ReviewEvent.id).label("count"),
        )
        .filter(ReviewEvent.reviewed_at >= start_utc, ReviewEvent.reviewed_at < end_utc)
        .group_by(ReviewEvent.scheduler_mode)
        .all()
    )
    schedulers = [{"scheduler": r.scheduler or "legacy", "count": _safe_int(r.count)} for r in scheduler_rows]

    return {
        "modes": modes,
        "ratings": ratings,
        "schedulers": schedulers,
    }


def query_content_growth_breakdown(start_utc: datetime, end_utc: datetime) -> List[Dict[str, Any]]:
    """Query daily creation of decks, notes, cards, and imports."""
    deck_date = func.date(Deck.created_at)
    deck_rows = (
        db.session.query(deck_date.label("day"), func.count(Deck.id).label("count"))
        .filter(Deck.created_at >= start_utc, Deck.created_at < end_utc)
        .group_by(deck_date)
        .all()
    )
    deck_map = {str(r.day)[:10]: _safe_int(r.count) for r in deck_rows if r.day}

    note_date = func.date(Note.created_at)
    note_rows = (
        db.session.query(note_date.label("day"), func.count(Note.id).label("count"))
        .filter(Note.created_at >= start_utc, Note.created_at < end_utc)
        .group_by(note_date)
        .all()
    )
    note_map = {str(r.day)[:10]: _safe_int(r.count) for r in note_rows if r.day}

    card_date = func.date(Card.created_at)
    card_rows = (
        db.session.query(card_date.label("day"), func.count(Card.id).label("count"))
        .filter(Card.created_at >= start_utc, Card.created_at < end_utc)
        .group_by(card_date)
        .all()
    )
    card_map = {str(r.day)[:10]: _safe_int(r.count) for r in card_rows if r.day}

    install_date = func.date(DeckInstall.created_at)
    install_rows = (
        db.session.query(install_date.label("day"), func.count(DeckInstall.id).label("count"))
        .filter(DeckInstall.created_at >= start_utc, DeckInstall.created_at < end_utc)
        .group_by(install_date)
        .all()
    )
    install_map = {str(r.day)[:10]: _safe_int(r.count) for r in install_rows if r.day}

    import_date = func.date(ConnectImportSession.created_at)
    import_rows = (
        db.session.query(import_date.label("day"), func.count(ConnectImportSession.id).label("count"))
        .filter(ConnectImportSession.created_at >= start_utc, ConnectImportSession.created_at < end_utc)
        .group_by(import_date)
        .all()
    )
    import_map = {str(r.day)[:10]: _safe_int(r.count) for r in import_rows if r.day}

    results: List[Dict[str, Any]] = []
    current_day = start_utc.date()
    end_day = end_utc.date()

    while current_day <= end_day:
        day_str = current_day.isoformat()
        results.append({
            "date": day_str,
            "new_decks": deck_map.get(day_str, 0),
            "new_notes": note_map.get(day_str, 0),
            "new_cards": card_map.get(day_str, 0),
            "deck_installs": install_map.get(day_str, 0),
            "connect_imports": import_map.get(day_str, 0),
        })
        current_day += timedelta(days=1)

    return results


def query_retention_cohorts(num_weeks: int = 8) -> List[Dict[str, Any]]:
    """Query user retention cohorts (D1, D7, D14, D30) for past registration weeks."""
    now = datetime.now(UTC).replace(tzinfo=None)
    cohorts: List[Dict[str, Any]] = []

    for w in range(num_weeks - 1, -1, -1):
        week_start = (now - timedelta(days=(w + 1) * 7)).replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        cohort_label = f"W{w+1} ({week_start.strftime('%d/%m')})"

        cohort_users = [
            u.id
            for u in db.session.query(User.id)
            .filter(User.created_at >= week_start, User.created_at < week_end)
            .all()
        ]
        cohort_size = len(cohort_users)
        if cohort_size == 0:
            cohorts.append({
                "cohort": cohort_label,
                "cohort_size": 0,
                "d1_retained": 0,
                "d1_rate": 0.0,
                "d7_retained": 0,
                "d7_rate": 0.0,
                "d14_retained": 0,
                "d14_rate": 0.0,
                "d30_retained": 0,
                "d30_rate": 0.0,
            })
            continue

        # D1 retention: active between 1 and 2 days after registration
        d1_start = week_start + timedelta(days=1)
        d1_end = week_end + timedelta(days=2)
        d1_active = (
            db.session.query(func.count(distinct(ReviewEvent.user_id)))
            .filter(
                ReviewEvent.user_id.in_(cohort_users),
                ReviewEvent.reviewed_at >= d1_start,
                ReviewEvent.reviewed_at < d1_end,
            )
            .scalar()
            or 0
        )

        # D7 retention: active between 7 and 14 days after registration
        d7_start = week_start + timedelta(days=7)
        d7_end = week_end + timedelta(days=8)
        d7_active = (
            db.session.query(func.count(distinct(ReviewEvent.user_id)))
            .filter(
                ReviewEvent.user_id.in_(cohort_users),
                ReviewEvent.reviewed_at >= d7_start,
                ReviewEvent.reviewed_at < d7_end,
            )
            .scalar()
            or 0
        )

        # D14 retention: active between 14 and 21 days after registration
        d14_start = week_start + timedelta(days=14)
        d14_end = week_end + timedelta(days=15)
        d14_active = (
            db.session.query(func.count(distinct(ReviewEvent.user_id)))
            .filter(
                ReviewEvent.user_id.in_(cohort_users),
                ReviewEvent.reviewed_at >= d14_start,
                ReviewEvent.reviewed_at < d14_end,
            )
            .scalar()
            or 0
        )

        # D30 retention: active around 30 days after registration
        d30_start = week_start + timedelta(days=30)
        d30_end = week_end + timedelta(days=31)
        d30_active = (
            db.session.query(func.count(distinct(ReviewEvent.user_id)))
            .filter(
                ReviewEvent.user_id.in_(cohort_users),
                ReviewEvent.reviewed_at >= d30_start,
                ReviewEvent.reviewed_at < d30_end,
            )
            .scalar()
            or 0
        )

        cohorts.append({
            "cohort": cohort_label,
            "cohort_size": cohort_size,
            "d1_retained": d1_active,
            "d1_rate": round((d1_active / float(cohort_size)) * 100.0, 1),
            "d7_retained": d7_active,
            "d7_rate": round((d7_active / float(cohort_size)) * 100.0, 1),
            "d14_retained": d14_active,
            "d14_rate": round((d14_active / float(cohort_size)) * 100.0, 1),
            "d30_retained": d30_active,
            "d30_rate": round((d30_active / float(cohort_size)) * 100.0, 1),
        })

    return cohorts


def query_top_active_learners(start_utc: datetime, end_utc: datetime, limit: int = 10) -> List[Dict[str, Any]]:
    """Query most active learners in period by study duration and card reviews."""
    rows = (
        db.session.query(
            ReviewEvent.user_id,
            User.username,
            User.email,
            func.count(ReviewEvent.id).label("reviews_count"),
            func.coalesce(func.sum(ReviewEvent.duration_ms), 0).label("duration_ms"),
            func.max(ReviewEvent.reviewed_at).label("last_active_at"),
        )
        .join(User, User.id == ReviewEvent.user_id)
        .filter(ReviewEvent.reviewed_at >= start_utc, ReviewEvent.reviewed_at < end_utc)
        .group_by(ReviewEvent.user_id, User.username, User.email)
        .order_by(func.sum(ReviewEvent.duration_ms).desc())
        .limit(limit)
        .all()
    )

    results: List[Dict[str, Any]] = []
    for r in rows:
        dur_ms = _safe_int(r.duration_ms)
        results.append({
            "user_id": r.user_id,
            "username": r.username,
            "email": r.email,
            "reviews_count": _safe_int(r.reviews_count),
            "total_study_minutes": round(dur_ms / 60000.0, 1),
            "last_active_at": r.last_active_at.isoformat() if r.last_active_at else None,
        })
    return results
