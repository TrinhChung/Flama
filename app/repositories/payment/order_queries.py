from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.orm import aliased, selectinload

from app.validators import escape_like_pattern
from app.validators.payment_query import OrderFilterInput, resolve_date_window
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType
from models.payment_attempt import PaymentAttempt
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.user import User


def paginate_admin_orders(*, filters: OrderFilterInput, page: int, per_page: int):
    latest_attempt = aliased(PaymentAttempt)
    query = _build_order_query(filters=filters, latest_attempt=latest_attempt)
    query = _apply_order_sort(query, latest_attempt=latest_attempt, sort=filters.sort)
    return query.paginate(page=page, per_page=per_page, error_out=False)


def paginate_user_orders(*, user_id: int, filters: OrderFilterInput, page: int, per_page: int):
    latest_attempt = aliased(PaymentAttempt)
    query = _build_order_query(filters=filters, latest_attempt=latest_attempt)
    query = query.filter(PaymentOrder.user_id == user_id)
    query = _apply_order_sort(query, latest_attempt=latest_attempt, sort=filters.sort)
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_order_detail_for_admin(order_id: str) -> PaymentOrder | None:
    return _detail_query().filter(PaymentOrder.id == order_id).first()


def get_order_detail_for_user(*, order_id: str, user_id: int) -> PaymentOrder | None:
    return _detail_query().filter(PaymentOrder.id == order_id, PaymentOrder.user_id == user_id).first()


def _detail_query():
    return PaymentOrder.query.options(
        selectinload(PaymentOrder.user),
        selectinload(PaymentOrder.items),
        selectinload(PaymentOrder.attempts).selectinload(PaymentAttempt.webhook_events),
        selectinload(PaymentOrder.entitlements),
    )


def _build_order_query(*, filters: OrderFilterInput, latest_attempt):
    latest_attempt_id = (
        db.session.query(PaymentAttempt.id)
        .filter(PaymentAttempt.order_id == PaymentOrder.id)
        .order_by(PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc())
        .limit(1)
        .correlate(PaymentOrder)
        .scalar_subquery()
    )

    query = (
        PaymentOrder.query.options(
            selectinload(PaymentOrder.user),
            selectinload(PaymentOrder.items),
            selectinload(PaymentOrder.attempts),
            selectinload(PaymentOrder.entitlements),
        )
        .join(User, User.id == PaymentOrder.user_id)
        .outerjoin(latest_attempt, latest_attempt.id == latest_attempt_id)
    )

    if filters.q:
        like_pattern = _like(filters.q)
        query = query.filter(
            or_(
                PaymentOrder.merchant_order_code.ilike(like_pattern, escape="\\"),
                User.username.ilike(like_pattern, escape="\\"),
                User.email.ilike(like_pattern, escape="\\"),
                latest_attempt.provider_payment_id.ilike(like_pattern, escape="\\"),
                latest_attempt.provider_order_code.ilike(like_pattern, escape="\\"),
                latest_attempt.expected_payment_reference.ilike(like_pattern, escape="\\"),
                _order_item_search_exists(like_pattern),
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

    if filters.seller:
        query = query.filter(_seller_search_expression(filters.seller))

    if filters.order_status != "all":
        query = query.filter(PaymentOrder.status == filters.order_status)
    if filters.payment_status != "all":
        query = query.filter(latest_attempt.status == filters.payment_status)
    if filters.grant_status != "all":
        query = query.filter(PaymentOrder.grant_status == filters.grant_status)
    if filters.provider != "all":
        query = query.filter(latest_attempt.provider_code == filters.provider)
    if filters.product_type != "all":
        query = query.filter(
            _order_item_exists(
                PaymentOrderItem.product_type == filters.product_type,
            )
        )

    start_at, end_before = resolve_date_window(filters.date_from, filters.date_to)
    if start_at is not None:
        query = query.filter(PaymentOrder.created_at >= start_at)
    if end_before is not None:
        query = query.filter(PaymentOrder.created_at < end_before)

    if filters.min_amount_minor is not None:
        query = query.filter(PaymentOrder.total_amount_minor >= filters.min_amount_minor)
    if filters.max_amount_minor is not None:
        query = query.filter(PaymentOrder.total_amount_minor <= filters.max_amount_minor)

    return query


def _apply_order_sort(query, *, latest_attempt, sort: str):
    if sort == "created_asc":
        return query.order_by(PaymentOrder.created_at.asc(), PaymentOrder.id.asc())
    if sort == "amount_desc":
        return query.order_by(PaymentOrder.total_amount_minor.desc(), PaymentOrder.created_at.desc(), PaymentOrder.id.desc())
    if sort == "amount_asc":
        return query.order_by(PaymentOrder.total_amount_minor.asc(), PaymentOrder.created_at.desc(), PaymentOrder.id.desc())
    return query.order_by(
        PaymentOrder.created_at.desc(),
        latest_attempt.created_at.desc(),
        PaymentOrder.id.desc(),
    )


def _order_item_search_exists(like_pattern: str):
    return _order_item_exists(
        or_(
            PaymentOrderItem.title_snapshot.ilike(like_pattern, escape="\\"),
            PaymentOrderItem.product_ref_id.ilike(like_pattern, escape="\\"),
        )
    )


def _seller_search_expression(raw_seller: str):
    like_pattern = _like(raw_seller)
    note_type_match = (
        NoteType.query.join(User, User.id == NoteType.user_id)
        .join(
            PaymentOrderItem,
            and_(
                PaymentOrderItem.product_type == "note_type",
                PaymentOrderItem.product_ref_id == NoteType.id,
            ),
        )
        .filter(
            PaymentOrderItem.order_id == PaymentOrder.id,
            or_(
                User.username.ilike(like_pattern, escape="\\"),
                User.email.ilike(like_pattern, escape="\\"),
                NoteType.name.ilike(like_pattern, escape="\\"),
            ),
        )
        .exists()
    )
    deck_match = (
        DeckMarketplaceItem.query.join(User, User.id == DeckMarketplaceItem.owner_user_id)
        .join(
            PaymentOrderItem,
            and_(
                PaymentOrderItem.product_type == "deck_marketplace_item",
                PaymentOrderItem.product_ref_id == DeckMarketplaceItem.id,
            ),
        )
        .filter(
            PaymentOrderItem.order_id == PaymentOrder.id,
            or_(
                User.username.ilike(like_pattern, escape="\\"),
                User.email.ilike(like_pattern, escape="\\"),
                DeckMarketplaceItem.title.ilike(like_pattern, escape="\\"),
            ),
        )
        .exists()
    )
    return or_(note_type_match, deck_match)


def _order_item_exists(*criteria):
    return (
        PaymentOrderItem.query.filter(
            PaymentOrderItem.order_id == PaymentOrder.id,
            *criteria,
        )
        .exists()
    )


def _like(value: str) -> str:
    return f"%{escape_like_pattern(value)}%"
