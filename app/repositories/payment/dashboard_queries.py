from __future__ import annotations

from sqlalchemy import case, func
from sqlalchemy.orm import selectinload

from models import db
from models.payment_attempt import PaymentAttempt
from models.payment_order import PaymentOrder


TERMINAL_ATTEMPT_STATUSES = ["confirmed", "manual_review", "expired", "canceled", "failed", "refunded"]


def load_order_metrics(*, since=None) -> dict[str, int]:
    query = PaymentOrder.query
    if since is not None:
        query = query.filter(PaymentOrder.created_at >= since)

    total_orders = query.count()
    paid_orders = query.filter(PaymentOrder.status == "paid").count()
    pending_orders = query.filter(PaymentOrder.status == "pending_payment").count()
    failed_orders = query.filter(PaymentOrder.status.in_(["failed", "expired"])).count()
    review_orders = query.filter(PaymentOrder.status == "under_review").count()
    refunded_orders = query.filter(PaymentOrder.status == "refunded").count()
    total_revenue_minor = (
        query.with_entities(func.coalesce(func.sum(PaymentOrder.total_amount_minor), 0))
        .filter(PaymentOrder.status == "paid")
        .scalar()
        or 0
    )
    return {
        "total_orders": int(total_orders or 0),
        "paid_orders": int(paid_orders or 0),
        "pending_orders": int(pending_orders or 0),
        "failed_orders": int(failed_orders or 0),
        "review_orders": int(review_orders or 0),
        "refunded_orders": int(refunded_orders or 0),
        "total_revenue_minor": int(total_revenue_minor or 0),
    }


def load_attempt_metrics(*, since=None) -> dict[str, int]:
    query = PaymentAttempt.query
    if since is not None:
        query = query.filter(PaymentAttempt.created_at >= since)

    total_attempts = query.count()
    open_attempts = query.filter(PaymentAttempt.status.in_(["created", "pending"])).count()
    closed_attempts = query.filter(PaymentAttempt.status.in_(TERMINAL_ATTEMPT_STATUSES)).count()
    confirmed_attempts = query.filter(PaymentAttempt.status == "confirmed").count()
    failed_attempts = query.filter(PaymentAttempt.status.in_(["failed", "expired", "canceled"])).count()
    review_attempts = query.filter(PaymentAttempt.status == "manual_review").count()
    return {
        "total_attempts": int(total_attempts or 0),
        "open_attempts": int(open_attempts or 0),
        "closed_attempts": int(closed_attempts or 0),
        "confirmed_attempts": int(confirmed_attempts or 0),
        "failed_attempts": int(failed_attempts or 0),
        "review_attempts": int(review_attempts or 0),
    }


def list_recent_orders(*, limit: int = 8, since=None) -> list[PaymentOrder]:
    query = PaymentOrder.query.options(
        selectinload(PaymentOrder.user),
        selectinload(PaymentOrder.items),
        selectinload(PaymentOrder.attempts),
    )
    if since is not None:
        query = query.filter(PaymentOrder.created_at >= since)
    return query.order_by(PaymentOrder.created_at.desc(), PaymentOrder.id.desc()).limit(limit).all()


def list_order_status_distribution(*, since=None) -> list[dict[str, int | str]]:
    query = db.session.query(PaymentOrder.status, func.count(PaymentOrder.id))
    if since is not None:
        query = query.filter(PaymentOrder.created_at >= since)
    rows = query.group_by(PaymentOrder.status).order_by(func.count(PaymentOrder.id).desc(), PaymentOrder.status.asc()).all()
    return [{"status": status, "count": int(count or 0)} for status, count in rows]


def list_attempt_status_distribution(*, since=None) -> list[dict[str, int | str]]:
    query = db.session.query(PaymentAttempt.status, func.count(PaymentAttempt.id))
    if since is not None:
        query = query.filter(PaymentAttempt.created_at >= since)
    rows = query.group_by(PaymentAttempt.status).order_by(func.count(PaymentAttempt.id).desc(), PaymentAttempt.status.asc()).all()
    return [{"status": status, "count": int(count or 0)} for status, count in rows]


def list_provider_breakdown(*, since=None) -> list[dict[str, int | str]]:
    query = db.session.query(
        PaymentAttempt.provider_code,
        func.count(PaymentAttempt.id),
        func.coalesce(func.sum(PaymentAttempt.amount_minor), 0),
    )
    if since is not None:
        query = query.filter(PaymentAttempt.created_at >= since)
    rows = query.group_by(PaymentAttempt.provider_code).order_by(func.count(PaymentAttempt.id).desc()).all()
    return [
        {
            "provider_code": provider_code or "unknown",
            "attempt_count": int(attempt_count or 0),
            "attempt_amount_minor": int(amount_minor or 0),
        }
        for provider_code, attempt_count, amount_minor in rows
    ]


def list_daily_attempt_volume(*, limit_days: int = 14, since=None) -> list[dict[str, int | str]]:
    query = db.session.query(
        func.date(PaymentAttempt.created_at),
        func.count(PaymentAttempt.id),
        func.sum(case((PaymentAttempt.status == "confirmed", 1), else_=0)),
    )
    if since is not None:
        query = query.filter(PaymentAttempt.created_at >= since)
    rows = (
        query.group_by(func.date(PaymentAttempt.created_at))
        .order_by(func.date(PaymentAttempt.created_at).desc())
        .limit(limit_days)
        .all()
    )
    payload = [
        {
            "day": str(day),
            "attempt_count": int(attempt_count or 0),
            "confirmed_count": int(confirmed_count or 0),
        }
        for day, attempt_count, confirmed_count in rows
    ]
    payload.reverse()
    return payload
