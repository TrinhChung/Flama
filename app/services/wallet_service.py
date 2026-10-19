"""Wallet and creator revenue service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.repositories import wallet_repository
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.user import User
from models.user_balance_transaction import UserBalanceTransaction

UTC = timezone.utc
DEFAULT_PLATFORM_FEE_PERCENT = 10.0


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def format_currency_vnd(amount_minor: int) -> str:
    """Format an integer amount (minor unit / VND) as readable currency string."""
    return f"{amount_minor:,.0f} ₫".replace(",", ".")


def get_user_platform_fee_percent(user: User) -> float:
    """Determine the platform fee percent applicable to a user.

    Resolution precedence:
    1. user.custom_platform_fee_percent (if set by Admin)
    2. user.role.default_platform_fee_percent (if defined on role)
    3. DEFAULT_PLATFORM_FEE_PERCENT (10.0%)
    """
    if getattr(user, "custom_platform_fee_percent", None) is not None:
        try:
            val = float(user.custom_platform_fee_percent)
            return max(0.0, min(100.0, val))
        except (TypeError, ValueError):
            pass

    role = getattr(user, "role", None)
    if role is not None and getattr(role, "default_platform_fee_percent", None) is not None:
        try:
            val = float(role.default_platform_fee_percent)
            return max(0.0, min(100.0, val))
        except (TypeError, ValueError):
            pass

    return DEFAULT_PLATFORM_FEE_PERCENT


def credit_creator_for_deck_sale(
    *,
    order: PaymentOrder,
    order_item: PaymentOrderItem,
    now: datetime,
) -> UserBalanceTransaction | None:
    """Credit author's wallet balance when a paid deck (or note type) order is confirmed.

    This function is idempotent: re-calling it for the same order_item will not
    duplicate the balance credit.
    """
    owner_user_id: int | None = None

    if order_item.product_type == "deck_marketplace_item":
        deck_item = db.session.get(DeckMarketplaceItem, order_item.product_ref_id)
        if deck_item is not None:
            owner_user_id = deck_item.owner_user_id
    elif order_item.product_type == "note_type":
        source_note_type = db.session.get(NoteType, order_item.product_ref_id)
        if source_note_type is not None:
            owner_user_id = getattr(source_note_type, "owner_user_id", None)
    elif order_item.product_type == "template":
        from app.services import template_marketplace_service

        owner_user_id = template_marketplace_service.seller_user_id(order_item.product_ref_id)

    if owner_user_id is None or owner_user_id == order.user_id:
        return None

    gross_amount = int(order_item.line_total_amount_minor or order_item.unit_amount_minor or 0)
    if gross_amount <= 0:
        return None

    # Idempotency check: check if already credited
    existing = wallet_repository.get_transaction_by_order_item(
        order_item_id=order_item.id,
        user_id=owner_user_id,
        transaction_type="deck_sale",
    )
    if existing is not None:
        return existing

    seller = wallet_repository.get_user_by_id(owner_user_id)
    if seller is None:
        return None

    fee_percent = get_user_platform_fee_percent(seller)
    fee_amount = int(round(gross_amount * (fee_percent / 100.0)))
    fee_amount = max(0, min(fee_amount, gross_amount))
    net_amount = gross_amount - fee_amount

    current_balance = int(seller.balance_amount_minor or 0)
    new_balance = current_balance + net_amount
    seller.balance_amount_minor = new_balance

    item_title = str(order_item.title_snapshot or "Bộ thẻ").strip()
    tx = UserBalanceTransaction(
        user_id=seller.id,
        buyer_user_id=order.user_id,
        payment_order_id=order.id,
        payment_order_item_id=order_item.id,
        transaction_type="deck_sale",
        gross_amount_minor=gross_amount,
        platform_fee_percent=fee_percent,
        platform_fee_amount_minor=fee_amount,
        net_amount_minor=net_amount,
        balance_after_minor=new_balance,
        description=f"Doanh thu từ bộ thẻ '{item_title}'",
        created_at=now,
    )
    wallet_repository.save_balance_transaction(tx)
    return tx


def serialize_balance_transaction(tx: UserBalanceTransaction) -> dict[str, Any]:
    buyer_name = "Khách hàng"
    if tx.buyer:
        buyer_name = tx.buyer.username
    elif tx.buyer_user_id:
        buyer_name = f"User #{tx.buyer_user_id}"

    order_code = tx.order.merchant_order_code if tx.order else None

    return {
        "id": tx.id,
        "transaction_type": tx.transaction_type,
        "transaction_type_label": "Doanh thu bán Deck" if tx.transaction_type == "deck_sale" else tx.transaction_type,
        "gross_amount_minor": tx.gross_amount_minor,
        "gross_amount_display": format_currency_vnd(tx.gross_amount_minor),
        "platform_fee_percent": tx.platform_fee_percent,
        "platform_fee_amount_minor": tx.platform_fee_amount_minor,
        "platform_fee_amount_display": format_currency_vnd(tx.platform_fee_amount_minor),
        "net_amount_minor": tx.net_amount_minor,
        "net_amount_display": f"+{format_currency_vnd(tx.net_amount_minor)}" if tx.net_amount_minor > 0 else format_currency_vnd(tx.net_amount_minor),
        "balance_after_minor": tx.balance_after_minor,
        "balance_after_display": format_currency_vnd(tx.balance_after_minor),
        "description": tx.description,
        "buyer_user_id": tx.buyer_user_id,
        "buyer_username": buyer_name,
        "payment_order_id": tx.payment_order_id,
        "merchant_order_code": order_code,
        "payment_order_item_id": tx.payment_order_item_id,
        "created_at": _iso(tx.created_at),
    }


def get_user_wallet_summary(user: User) -> dict[str, Any]:
    """Return aggregated wallet balance and earnings info for a user."""
    balance = int(getattr(user, "balance_amount_minor", 0) or 0)
    fee_percent = get_user_platform_fee_percent(user)
    has_custom_fee = getattr(user, "custom_platform_fee_percent", None) is not None

    earnings = wallet_repository.get_user_earnings_summary(user.id)

    return {
        "balance_amount_minor": balance,
        "balance_amount_display": format_currency_vnd(balance),
        "currency_code": "VND",
        "platform_fee_percent": fee_percent,
        "is_custom_fee": has_custom_fee,
        "payout_enabled": False,
        "payout_status_message": "Chức năng rút tiền đang trong quá trình phát triển. Toàn bộ số dư của bạn được lưu trữ an toàn.",
        "earnings": {
            "total_gross_amount_minor": earnings["total_gross_amount_minor"],
            "total_gross_display": format_currency_vnd(earnings["total_gross_amount_minor"]),
            "total_platform_fee_amount_minor": earnings["total_platform_fee_amount_minor"],
            "total_platform_fee_display": format_currency_vnd(earnings["total_platform_fee_amount_minor"]),
            "total_net_amount_minor": earnings["total_net_amount_minor"],
            "total_net_display": format_currency_vnd(earnings["total_net_amount_minor"]),
            "total_sales_count": earnings["total_sales_count"],
        },
    }


def list_user_transactions(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 10,
    transaction_type: str | None = None,
) -> dict[str, Any]:
    pagination = wallet_repository.build_user_transactions_query(
        user_id=user_id,
        transaction_type=transaction_type,
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [serialize_balance_transaction(tx) for tx in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": per_page,
        "pages": max(pagination.pages, 1),
    }
