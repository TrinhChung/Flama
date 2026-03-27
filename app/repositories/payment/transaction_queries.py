from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.validators import escape_like_pattern
from app.validators.payment_query import TransactionFilterInput, resolve_date_window
from models.payment_attempt import PaymentAttempt
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.payment_webhook_event import PaymentWebhookEvent
from models.user import User


def paginate_admin_transactions(*, filters: TransactionFilterInput, page: int, per_page: int):
    query = _build_attempt_query(filters=filters)
    query = _apply_attempt_sort(query, sort=filters.sort)
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_attempt_detail_for_admin(attempt_id: str) -> PaymentAttempt | None:
    return (
        PaymentAttempt.query.options(
            selectinload(PaymentAttempt.order).selectinload(PaymentOrder.user),
            selectinload(PaymentAttempt.order).selectinload(PaymentOrder.items),
            selectinload(PaymentAttempt.webhook_events),
            selectinload(PaymentAttempt.entitlements),
        )
        .filter(PaymentAttempt.id == attempt_id)
        .first()
    )


def list_recent_abnormal_attempts(*, limit: int = 8, since=None) -> list[PaymentAttempt]:
    query = (
        PaymentAttempt.query.options(
            selectinload(PaymentAttempt.order).selectinload(PaymentOrder.user),
            selectinload(PaymentAttempt.order).selectinload(PaymentOrder.items),
            selectinload(PaymentAttempt.webhook_events),
        )
        .filter(PaymentAttempt.status.in_(["manual_review", "failed", "expired", "canceled"]))
    )
    if since is not None:
        query = query.filter(PaymentAttempt.created_at >= since)
    return query.order_by(PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc()).limit(limit).all()


def list_recent_webhook_failures(*, limit: int = 8, since=None) -> list[PaymentWebhookEvent]:
    query = (
        PaymentWebhookEvent.query.options(
            selectinload(PaymentWebhookEvent.payment_attempt).selectinload(PaymentAttempt.order),
            selectinload(PaymentWebhookEvent.payment_order).selectinload(PaymentOrder.user),
        )
        .filter(
            or_(
                PaymentWebhookEvent.processing_status == "failed",
                PaymentWebhookEvent.signature_valid.is_(False),
            )
        )
    )
    if since is not None:
        query = query.filter(PaymentWebhookEvent.received_at >= since)
    return query.order_by(PaymentWebhookEvent.received_at.desc(), PaymentWebhookEvent.id.desc()).limit(limit).all()


def _build_attempt_query(*, filters: TransactionFilterInput):
    query = (
        PaymentAttempt.query.options(
            selectinload(PaymentAttempt.order).selectinload(PaymentOrder.user),
            selectinload(PaymentAttempt.order).selectinload(PaymentOrder.items),
            selectinload(PaymentAttempt.webhook_events),
            selectinload(PaymentAttempt.entitlements),
        )
        .join(PaymentOrder, PaymentOrder.id == PaymentAttempt.order_id)
        .join(User, User.id == PaymentOrder.user_id)
    )

    if filters.q:
        like_pattern = _like(filters.q)
        query = query.filter(
            or_(
                PaymentAttempt.id.ilike(like_pattern, escape="\\"),
                PaymentAttempt.provider_payment_id.ilike(like_pattern, escape="\\"),
                PaymentAttempt.provider_order_code.ilike(like_pattern, escape="\\"),
                PaymentAttempt.expected_payment_reference.ilike(like_pattern, escape="\\"),
                PaymentOrder.merchant_order_code.ilike(like_pattern, escape="\\"),
                User.username.ilike(like_pattern, escape="\\"),
                User.email.ilike(like_pattern, escape="\\"),
                _order_item_search_exists(like_pattern),
                _webhook_search_exists(like_pattern),
            )
        )

    if filters.buyer:
        buyer_like = _like(filters.buyer)
        query = query.filter(
            or_(
                User.username.ilike(buyer_like, escape="\\"),
                User.email.ilike(buyer_like, escape="\\"),
            )
        )

    if filters.order_code:
        order_like = _like(filters.order_code)
        query = query.filter(PaymentOrder.merchant_order_code.ilike(order_like, escape="\\"))

    if filters.status != "all":
        query = query.filter(PaymentAttempt.status == filters.status)
    if filters.provider != "all":
        query = query.filter(PaymentAttempt.provider_code == filters.provider)
    if filters.payment_method != "all":
        query = query.filter(PaymentAttempt.payment_method_code == filters.payment_method)
    if filters.webhook_status != "all":
        query = query.filter(_webhook_status_exists(filters.webhook_status))

    start_at, end_before = resolve_date_window(filters.date_from, filters.date_to)
    if start_at is not None:
        query = query.filter(PaymentAttempt.created_at >= start_at)
    if end_before is not None:
        query = query.filter(PaymentAttempt.created_at < end_before)

    if filters.min_amount_minor is not None:
        query = query.filter(PaymentAttempt.amount_minor >= filters.min_amount_minor)
    if filters.max_amount_minor is not None:
        query = query.filter(PaymentAttempt.amount_minor <= filters.max_amount_minor)

    return query


def _apply_attempt_sort(query, *, sort: str):
    if sort == "created_asc":
        return query.order_by(PaymentAttempt.created_at.asc(), PaymentAttempt.id.asc())
    if sort == "amount_desc":
        return query.order_by(PaymentAttempt.amount_minor.desc(), PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc())
    if sort == "amount_asc":
        return query.order_by(PaymentAttempt.amount_minor.asc(), PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc())
    return query.order_by(PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc())


def _order_item_search_exists(like_pattern: str):
    return (
        PaymentOrderItem.query.filter(
            PaymentOrderItem.order_id == PaymentAttempt.order_id,
            or_(
                PaymentOrderItem.title_snapshot.ilike(like_pattern, escape="\\"),
                PaymentOrderItem.product_ref_id.ilike(like_pattern, escape="\\"),
            ),
        )
        .exists()
    )


def _webhook_status_exists(status: str):
    return (
        PaymentWebhookEvent.query.filter(
            PaymentWebhookEvent.payment_attempt_id == PaymentAttempt.id,
            PaymentWebhookEvent.processing_status == status,
        )
        .exists()
    )


def _webhook_search_exists(like_pattern: str):
    return (
        PaymentWebhookEvent.query.filter(
            PaymentWebhookEvent.payment_attempt_id == PaymentAttempt.id,
            or_(
                PaymentWebhookEvent.event_key.ilike(like_pattern, escape="\\"),
                PaymentWebhookEvent.event_type.ilike(like_pattern, escape="\\"),
                PaymentWebhookEvent.error_message.ilike(like_pattern, escape="\\"),
            ),
        )
        .exists()
    )


def _like(value: str) -> str:
    return f"%{escape_like_pattern(value)}%"
