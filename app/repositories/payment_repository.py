from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import joinedload

from models.deck_install import DeckInstall
from models.note_type_install import NoteTypeInstall
from models.payment_attempt import PaymentAttempt
from models.payment_entitlement import PaymentEntitlement
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.payment_webhook_event import PaymentWebhookEvent
from models.user import User


def lock_buyer_for_payment(user_id: int | None) -> None:
    """All receipt/quote writers serialize on buyer before locking orders."""
    if user_id is not None:
        User.query.filter_by(id=user_id).with_for_update().populate_existing().first()


def list_pending_template_orders(*, user_id: int) -> list[PaymentOrder]:
    return (PaymentOrder.query.filter(
        PaymentOrder.user_id == user_id,
        PaymentOrder.status.in_(["pending_payment", "under_review"]),
        PaymentOrder.items.any(
            (PaymentOrderItem.product_type == "template") &
            (PaymentOrderItem.line_total_amount_minor > 0)),
    ).order_by(PaymentOrder.id).with_for_update().populate_existing().all())


def get_order_for_user(order_id: str, user_id: int) -> PaymentOrder | None:
    return (
        PaymentOrder.query.options(
            joinedload(PaymentOrder.items),
            joinedload(PaymentOrder.attempts),
            joinedload(PaymentOrder.entitlements),
        )
        .filter_by(id=order_id, user_id=user_id)
        .first()
    )


def get_order_by_id(order_id: str) -> PaymentOrder | None:
    return (
        PaymentOrder.query.options(
            joinedload(PaymentOrder.items),
            joinedload(PaymentOrder.attempts),
            joinedload(PaymentOrder.entitlements),
        )
        .filter_by(id=order_id)
        .first()
    )


def list_reusable_orders_for_product(*, user_id: int | None, product_type: str, product_ref_id: str) -> list[PaymentOrder]:
    if user_id is None:
        return []
    return (
        PaymentOrder.query.options(
            joinedload(PaymentOrder.items),
            joinedload(PaymentOrder.attempts),
            joinedload(PaymentOrder.entitlements),
        )
        .join(PaymentOrderItem, PaymentOrderItem.order_id == PaymentOrder.id)
        .filter(
            PaymentOrder.user_id == user_id,
            PaymentOrder.status == "pending_payment",
            PaymentOrderItem.product_type == product_type,
            PaymentOrderItem.product_ref_id == product_ref_id,
        )
        .order_by(PaymentOrder.created_at.desc(), PaymentOrder.id.desc())
        .all()
    )


def get_note_type_install(*, user_id: int, source_note_type_id: str) -> NoteTypeInstall | None:
    return (
        NoteTypeInstall.query.filter_by(
            user_id=user_id,
            source_note_type_id=source_note_type_id,
        )
        .first()
    )


def get_deck_install(*, user_id: int, deck_item_id: str) -> DeckInstall | None:
    return (
        DeckInstall.query.filter_by(
            user_id=user_id,
            deck_item_id=deck_item_id,
        )
        .first()
    )


def get_order_and_latest_attempt_for_update(*, order_id: str, attempt_id: str) -> tuple[PaymentOrder | None, PaymentAttempt | None]:
    owner = PaymentOrder.query.with_entities(PaymentOrder.user_id).filter_by(id=order_id).first()
    if owner is not None:
        lock_buyer_for_payment(owner[0])
    order = (
        PaymentOrder.query.filter_by(id=order_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    attempt = (
        PaymentAttempt.query.filter_by(id=attempt_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    return order, attempt


def get_attempt_by_provider_payment_id(*, provider_code: str, provider_payment_id: str) -> PaymentAttempt | None:
    return (
        PaymentAttempt.query.options(joinedload(PaymentAttempt.order))
        .filter_by(provider_code=provider_code, provider_payment_id=provider_payment_id)
        .first()
    )


def get_attempt_by_provider_order_code(*, provider_code: str, provider_order_code: str) -> PaymentAttempt | None:
    return (
        PaymentAttempt.query.options(joinedload(PaymentAttempt.order))
        .filter_by(provider_code=provider_code, provider_order_code=provider_order_code)
        .first()
    )


def find_attempts_by_reference_and_amount(*, payment_reference: str, amount_minor: int) -> list[PaymentAttempt]:
    return (
        PaymentAttempt.query.options(joinedload(PaymentAttempt.order))
        .filter(
            PaymentAttempt.expected_payment_reference == payment_reference,
            PaymentAttempt.amount_minor == amount_minor,
        )
        .order_by(PaymentAttempt.created_at.desc(), PaymentAttempt.id.desc())
        .all()
    )


def get_webhook_event(*, provider_code: str, event_key: str) -> PaymentWebhookEvent | None:
    return PaymentWebhookEvent.query.filter_by(provider_code=provider_code, event_key=event_key).first()


def get_webhook_event_by_id(event_id: str) -> PaymentWebhookEvent | None:
    return PaymentWebhookEvent.query.filter_by(id=event_id).first()


def list_stale_attempts(now: datetime) -> list[PaymentAttempt]:
    return (
        PaymentAttempt.query.options(joinedload(PaymentAttempt.order))
        .filter(
            PaymentAttempt.status.in_(["created", "pending"]),
            PaymentAttempt.expires_at.isnot(None),
            PaymentAttempt.expires_at < now,
        )
        .order_by(PaymentAttempt.expires_at.asc(), PaymentAttempt.id.asc())
        .all()
    )


def list_failed_entitlements() -> list[PaymentEntitlement]:
    return (
        PaymentEntitlement.query.options(
            joinedload(PaymentEntitlement.order),
            joinedload(PaymentEntitlement.order_item),
            joinedload(PaymentEntitlement.payment_attempt),
        )
        .filter_by(status="pending")
        .order_by(PaymentEntitlement.created_at.asc(), PaymentEntitlement.id.asc())
        .all()
    )
