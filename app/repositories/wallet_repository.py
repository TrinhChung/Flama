"""Repository for user wallet balance and ledger transactions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from models import db
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.user import User
from models.user_balance_transaction import UserBalanceTransaction


def get_user_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def get_transaction_by_order_item(
    *,
    order_item_id: str,
    user_id: int,
    transaction_type: str = "deck_sale",
) -> UserBalanceTransaction | None:
    return (
        UserBalanceTransaction.query.filter_by(
            payment_order_item_id=order_item_id,
            user_id=user_id,
            transaction_type=transaction_type,
        ).first()
    )


def save_balance_transaction(transaction: UserBalanceTransaction) -> UserBalanceTransaction:
    db.session.add(transaction)
    db.session.flush()
    return transaction


def build_user_transactions_query(
    user_id: int,
    transaction_type: str | None = None,
):
    query = (
        UserBalanceTransaction.query.options(
            selectinload(UserBalanceTransaction.buyer),
            selectinload(UserBalanceTransaction.order),
            selectinload(UserBalanceTransaction.order_item),
        )
        .filter(UserBalanceTransaction.user_id == user_id)
    )
    if transaction_type:
        query = query.filter(UserBalanceTransaction.transaction_type == transaction_type)

    return query.order_by(UserBalanceTransaction.created_at.desc(), UserBalanceTransaction.id.desc())


def get_user_earnings_summary(user_id: int) -> dict[str, int]:
    """Calculate aggregated earnings metrics for a seller."""
    result = (
        db.session.query(
            func.coalesce(func.sum(UserBalanceTransaction.gross_amount_minor), 0).label("total_gross"),
            func.coalesce(func.sum(UserBalanceTransaction.platform_fee_amount_minor), 0).label("total_fees"),
            func.coalesce(func.sum(UserBalanceTransaction.net_amount_minor), 0).label("total_net"),
            func.count(UserBalanceTransaction.id).label("total_sales_count"),
        )
        .filter(
            UserBalanceTransaction.user_id == user_id,
            UserBalanceTransaction.transaction_type == "deck_sale",
        )
        .one()
    )
    return {
        "total_gross_amount_minor": int(result.total_gross),
        "total_platform_fee_amount_minor": int(result.total_fees),
        "total_net_amount_minor": int(result.total_net),
        "total_sales_count": int(result.total_sales_count),
    }
