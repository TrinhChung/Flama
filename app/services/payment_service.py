from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.repositories import payment_repository
from app.services import flashcards_share_service
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType
from models.payment_attempt import PaymentAttempt
from models.payment_entitlement import PaymentEntitlement
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.payment_webhook_event import PaymentWebhookEvent


DEFAULT_ORDER_EXPIRY_SECONDS = 30 * 60
DEFAULT_VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}
ACTIVE_ATTEMPT_STATUSES = {"created", "pending"}
TERMINAL_ORDER_STATUSES = {"paid", "expired", "canceled", "failed", "refunded"}
PAYMENT_PROVIDER_CODE = "vietqr"
PAYMENT_METHOD_CODE = "vietqr_transfer"


class PaymentServiceError(Exception):
    def __init__(
        self,
        error: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.status = status
        self.field = field


def payments_enabled() -> bool:
    return bool(current_app.config.get("PAYMENTS_V1_ENABLED", False))


def paid_install_interception_enabled() -> bool:
    return payments_enabled() and bool(current_app.config.get("PAYMENTS_PAID_INSTALL_REQUIRED", False))


def webhook_auto_grant_enabled() -> bool:
    return payments_enabled() and bool(current_app.config.get("PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED", False))


def _utcnow() -> datetime:
    return datetime.utcnow()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _require_payments_enabled() -> None:
    if not payments_enabled():
        raise PaymentServiceError(
            "PAYMENT_UNAVAILABLE",
            "Payment system is not enabled.",
            status=503,
        )


def _require_provider_configuration() -> dict[str, Any]:
    account_no = str(current_app.config.get("PAYMENTS_VIETQR_ACCOUNT_NO") or "").strip()
    bank_bin = str(current_app.config.get("PAYMENTS_VIETQR_BANK_BIN") or "").strip()
    if not account_no or not bank_bin:
        raise PaymentServiceError(
            "PAYMENT_PROVIDER_NOT_CONFIGURED",
            "Payment provider is not configured yet.",
            status=503,
        )

    return {
        "account_no": account_no,
        "account_name": str(current_app.config.get("PAYMENTS_VIETQR_ACCOUNT_NAME") or "").strip() or None,
        "bank_bin": bank_bin,
        "template": str(current_app.config.get("PAYMENTS_VIETQR_TEMPLATE") or "").strip() or None,
    }


def _build_merchant_order_code() -> str:
    return f"ORD-{_utcnow():%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}"


def _build_payment_reference() -> str:
    return f"FLAMA{uuid4().hex[:10].upper()}"


def _latest_attempt(order: PaymentOrder) -> PaymentAttempt | None:
    if not order.attempts:
        return None
    return max(order.attempts, key=lambda row: (row.created_at or datetime.min, row.id or ""))


def _maybe_expire_order(order: PaymentOrder, *, now: datetime | None = None) -> bool:
    current_time = now or _utcnow()
    attempt = _latest_attempt(order)
    if attempt is None:
        return False
    if attempt.status not in ACTIVE_ATTEMPT_STATUSES:
        return False
    if attempt.expires_at is None or attempt.expires_at >= current_time:
        return False

    attempt.status = "expired"
    attempt.failed_at = attempt.failed_at or current_time
    attempt.failure_code = attempt.failure_code or "expired"
    attempt.failure_message = attempt.failure_message or "Payment attempt expired."

    other_non_terminal_attempts = any(
        row.id != attempt.id and row.status in ACTIVE_ATTEMPT_STATUSES.union({"manual_review"})
        for row in order.attempts
    )
    if order.status == "pending_payment" and not other_non_terminal_attempts:
        order.status = "expired"
        order.closed_at = current_time
    return True


def _serialize_order_item(item: PaymentOrderItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "product_type": item.product_type,
        "product_ref_id": item.product_ref_id,
        "quantity": int(item.quantity or 0),
        "unit_amount_minor": int(item.unit_amount_minor or 0),
        "line_total_amount_minor": int(item.line_total_amount_minor or 0),
        "title_snapshot": item.title_snapshot,
        "product_snapshot": item.product_snapshot_json or {},
        "created_at": _iso(item.created_at),
    }


def _serialize_attempt(attempt: PaymentAttempt | None) -> dict[str, Any] | None:
    if attempt is None:
        return None
    provider_metadata = attempt.provider_metadata_json or {}
    return {
        "id": attempt.id,
        "provider_code": attempt.provider_code,
        "payment_method_code": attempt.payment_method_code,
        "status": attempt.status,
        "amount_minor": int(attempt.amount_minor or 0),
        "currency_code": attempt.currency_code,
        "provider_payment_id": attempt.provider_payment_id,
        "provider_order_code": attempt.provider_order_code,
        "expected_payment_reference": attempt.expected_payment_reference,
        "checkout_url": attempt.checkout_url,
        "expires_at": _iso(attempt.expires_at),
        "confirmed_at": _iso(attempt.confirmed_at),
        "failed_at": _iso(attempt.failed_at),
        "failure_code": attempt.failure_code,
        "failure_message": attempt.failure_message,
        "manual_review_reason": attempt.manual_review_reason,
        "provider_metadata": provider_metadata,
        "created_at": _iso(attempt.created_at),
        "updated_at": _iso(attempt.updated_at),
        "checkout": {
            "bank_bin": provider_metadata.get("bank_bin"),
            "account_no": provider_metadata.get("account_no"),
            "account_name": provider_metadata.get("account_name"),
            "template": provider_metadata.get("template"),
            "amount_minor": int(attempt.amount_minor or 0),
            "currency_code": attempt.currency_code,
            "payment_reference": attempt.expected_payment_reference,
            "merchant_order_code": provider_metadata.get("merchant_order_code"),
        },
    }


def serialize_order(order: PaymentOrder) -> dict[str, Any]:
    latest_attempt = _latest_attempt(order)
    return {
        "id": order.id,
        "merchant_order_code": order.merchant_order_code,
        "status": order.status,
        "grant_status": order.grant_status,
        "currency_code": order.currency_code,
        "subtotal_amount_minor": int(order.subtotal_amount_minor or 0),
        "discount_amount_minor": int(order.discount_amount_minor or 0),
        "total_amount_minor": int(order.total_amount_minor or 0),
        "paid_at": _iso(order.paid_at),
        "closed_at": _iso(order.closed_at),
        "created_at": _iso(order.created_at),
        "updated_at": _iso(order.updated_at),
        "items": [_serialize_order_item(item) for item in order.items],
        "attempts": [_serialize_attempt(attempt) for attempt in order.attempts],
        "active_attempt": _serialize_attempt(latest_attempt),
    }


def _validate_note_type_for_checkout(source_note_type: NoteType, *, user_id: int) -> dict[str, Any]:
    status = str(source_note_type.publish_status or "").strip().lower()
    if status not in DEFAULT_VISIBLE_PUBLISH_STATUSES:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "This note type is not available for purchase.",
            status=409,
        )
    if source_note_type.user_id == user_id:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Owner cannot purchase own note type.",
            status=409,
        )
    if source_note_type.pricing_mode != "paid" or int(source_note_type.price_cents or 0) <= 0:
        raise PaymentServiceError(
            "PAYMENT_NOT_REQUIRED",
            "This note type does not require payment.",
            status=409,
        )

    existing = payment_repository.get_note_type_install(
        user_id=user_id,
        source_note_type_id=source_note_type.id,
    )
    return {
        "product_type": "note_type",
        "product_ref_id": source_note_type.id,
        "title_snapshot": source_note_type.name,
        "amount_minor": int(source_note_type.price_cents or 0),
        "product_snapshot": {
            "title": source_note_type.name,
            "pricing_mode": source_note_type.pricing_mode,
            "source_price_integer": int(source_note_type.price_cents or 0),
            "version": source_note_type.version,
            "owner_user_id": source_note_type.user_id,
        },
        "existing_access": (
            {
                "already_installed": True,
                "source_note_type_id": source_note_type.id,
                "installed_note_type_id": existing.installed_note_type_id,
            }
            if existing is not None
            else None
        ),
    }


def _validate_deck_item_for_checkout(deck_item: DeckMarketplaceItem, *, user_id: int) -> dict[str, Any]:
    bind_error, _ = flashcards_share_service.sync_deck_item_source_note_type(
        deck_item,
        require_source_note_type=True,
    )
    if bind_error:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            bind_error,
            status=409,
            field="source_note_type_id",
        )

    status = str(deck_item.publish_status or "").strip().lower()
    if status not in DEFAULT_VISIBLE_PUBLISH_STATUSES:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "This deck is not available for purchase.",
            status=409,
        )
    if deck_item.owner_user_id == user_id:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Owner cannot purchase own deck item.",
            status=409,
        )
    if deck_item.pricing_mode != "paid" or int(deck_item.price_cents or 0) <= 0:
        raise PaymentServiceError(
            "PAYMENT_NOT_REQUIRED",
            "This deck does not require payment.",
            status=409,
        )

    existing = payment_repository.get_deck_install(user_id=user_id, deck_item_id=deck_item.id)
    return {
        "product_type": "deck_marketplace_item",
        "product_ref_id": deck_item.id,
        "title_snapshot": deck_item.title,
        "amount_minor": int(deck_item.price_cents or 0),
        "product_snapshot": {
            "title": deck_item.title,
            "pricing_mode": deck_item.pricing_mode,
            "source_price_integer": int(deck_item.price_cents or 0),
            "version": deck_item.version,
            "owner_user_id": deck_item.owner_user_id,
            "source_deck_id": deck_item.source_deck_id,
            "source_note_type_id": deck_item.source_note_type_id,
        },
        "existing_access": (
            {
                "already_installed": True,
                "deck_item_id": deck_item.id,
                "installed_deck_id": existing.local_deck_id,
            }
            if existing is not None
            else None
        ),
    }


def _load_checkout_context(*, product_type: str, product_ref_id: str, user_id: int) -> dict[str, Any]:
    if product_type == "note_type":
        source_note_type = NoteType.query.get(product_ref_id)
        if source_note_type is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Note type not found.", status=404)
        context = _validate_note_type_for_checkout(source_note_type, user_id=user_id)
        context["product"] = source_note_type
        return context

    if product_type == "deck_marketplace_item":
        deck_item = DeckMarketplaceItem.query.get(product_ref_id)
        if deck_item is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Deck item not found.", status=404)
        context = _validate_deck_item_for_checkout(deck_item, user_id=user_id)
        context["product"] = deck_item
        return context

    raise PaymentServiceError(
        "VALIDATION_ERROR",
        "Unsupported product_type.",
        status=400,
        field="product_type",
    )


def _build_checkout_attempt(order: PaymentOrder, *, amount_minor: int, title_snapshot: str) -> PaymentAttempt:
    provider_metadata = _require_provider_configuration()
    now = _utcnow()
    reference = _build_payment_reference()
    expires_at = now + timedelta(seconds=int(current_app.config.get("PAYMENTS_ORDER_EXPIRY_SECONDS", DEFAULT_ORDER_EXPIRY_SECONDS)))
    provider_metadata.update(
        {
            "merchant_order_code": order.merchant_order_code,
            "title_snapshot": title_snapshot,
            "amount_minor": int(amount_minor or 0),
            "currency_code": "VND",
            "payment_reference": reference,
        }
    )
    return PaymentAttempt(
        order_id=order.id,
        provider_code=PAYMENT_PROVIDER_CODE,
        payment_method_code=PAYMENT_METHOD_CODE,
        status="pending",
        amount_minor=int(amount_minor or 0),
        currency_code="VND",
        provider_order_code=order.merchant_order_code,
        expected_payment_reference=reference,
        checkout_url=None,
        provider_metadata_json=provider_metadata,
        expires_at=expires_at,
    )


def _create_or_reuse_order_for_context(context: dict[str, Any], *, user_id: int) -> tuple[PaymentOrder, bool]:
    now = _utcnow()
    pending_orders = payment_repository.list_reusable_orders_for_product(
        user_id=user_id,
        product_type=context["product_type"],
        product_ref_id=context["product_ref_id"],
    )
    dirty = False
    for order in pending_orders:
        dirty = _maybe_expire_order(order, now=now) or dirty
        latest_attempt = _latest_attempt(order)
        if latest_attempt and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES and order.status == "pending_payment":
            if dirty:
                db.session.commit()
            return order, False

    order = PaymentOrder(
        user_id=user_id,
        merchant_order_code=_build_merchant_order_code(),
        status="pending_payment",
        grant_status="pending",
        currency_code="VND",
        subtotal_amount_minor=context["amount_minor"],
        discount_amount_minor=0,
        total_amount_minor=context["amount_minor"],
    )
    db.session.add(order)
    db.session.flush()

    order_item = PaymentOrderItem(
        order_id=order.id,
        product_type=context["product_type"],
        product_ref_id=context["product_ref_id"],
        quantity=1,
        unit_amount_minor=context["amount_minor"],
        line_total_amount_minor=context["amount_minor"],
        title_snapshot=context["title_snapshot"],
        product_snapshot_json=context["product_snapshot"],
    )
    db.session.add(order_item)
    db.session.flush()

    attempt = _build_checkout_attempt(
        order,
        amount_minor=context["amount_minor"],
        title_snapshot=context["title_snapshot"],
    )
    db.session.add(attempt)
    db.session.commit()
    return order, True


def prepare_checkout_for_product(*, user_id: int, product_type: str, product_ref_id: str) -> dict[str, Any]:
    _require_payments_enabled()
    context = _load_checkout_context(
        product_type=product_type,
        product_ref_id=product_ref_id,
        user_id=user_id,
    )
    existing_access = context.get("existing_access")
    if existing_access is not None:
        return {
            "payment_required": False,
            **existing_access,
        }

    order, created = _create_or_reuse_order_for_context(context, user_id=user_id)
    fresh_order = payment_repository.get_order_by_id(order.id) or order
    return {
        "payment_required": True,
        "created": created,
        "order": serialize_order(fresh_order),
    }


def get_order_detail_for_user(*, order_id: str, user_id: int) -> dict[str, Any]:
    order = payment_repository.get_order_for_user(order_id, user_id)
    if order is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Payment order not found.", status=404)
    if _maybe_expire_order(order):
        db.session.commit()
    return serialize_order(order)


def cancel_order_for_user(*, order_id: str, user_id: int) -> dict[str, Any]:
    order = payment_repository.get_order_for_user(order_id, user_id)
    if order is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Payment order not found.", status=404)
    if _maybe_expire_order(order):
        db.session.commit()
        order = payment_repository.get_order_for_user(order_id, user_id) or order
    if order.status == "canceled":
        return serialize_order(order)
    if order.status in TERMINAL_ORDER_STATUSES - {"canceled"}:
        raise PaymentServiceError(
            "PAYMENT_ORDER_NOT_CANCELABLE",
            "Only pending payment orders can be canceled.",
            status=409,
        )

    latest_attempt = _latest_attempt(order)
    now = _utcnow()
    if latest_attempt is not None and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES.union({"manual_review"}):
        latest_attempt.status = "canceled"
        latest_attempt.failed_at = now
        latest_attempt.failure_code = "canceled"
        latest_attempt.failure_message = "Canceled by user."

    order.status = "canceled"
    order.closed_at = now
    db.session.commit()
    return serialize_order(order)


def expire_stale_orders(*, now: datetime | None = None) -> dict[str, int]:
    current_time = now or _utcnow()
    attempts = payment_repository.list_stale_attempts(current_time)
    expired_attempts = 0
    expired_orders = 0
    for attempt in attempts:
        order = attempt.order
        if order is None:
            continue
        was_order_expired = order.status == "expired"
        if _maybe_expire_order(order, now=current_time):
            expired_attempts += 1
            if order.status == "expired" and not was_order_expired:
                expired_orders += 1
    if expired_attempts > 0:
        db.session.commit()
    return {
        "expired_attempts": expired_attempts,
        "expired_orders": expired_orders,
    }


def _fulfill_order_item(*, order: PaymentOrder, order_item: PaymentOrderItem, attempt: PaymentAttempt, now: datetime) -> dict[str, Any]:
    if order_item.product_type == "note_type":
        source_note_type = NoteType.query.get(order_item.product_ref_id)
        if source_note_type is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Purchased note type no longer exists.", status=404)
        install_row = flashcards_share_service.ensure_note_type_install_for_user(
            source_note_type=source_note_type,
            user_id=order.user_id,
            installed_at=now,
        )
        return {
            "source_note_type_id": source_note_type.id,
            "note_type_install_id": install_row.id,
            "installed_note_type_id": install_row.installed_note_type_id,
        }

    if order_item.product_type == "deck_marketplace_item":
        deck_item = DeckMarketplaceItem.query.get(order_item.product_ref_id)
        if deck_item is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Purchased deck no longer exists.", status=404)
        install_result = flashcards_share_service.install_shared_deck_item_for_user(
            deck_item,
            user_id=order.user_id,
            publish_statuses_visible=DEFAULT_VISIBLE_PUBLISH_STATUSES,
        )
        deck_install = payment_repository.get_deck_install(
            user_id=order.user_id,
            deck_item_id=deck_item.id,
        )
        grant_data: dict[str, Any] = {
            "deck_item_id": deck_item.id,
            "deck_install_id": deck_install.id if deck_install is not None else None,
            "local_deck_id": (
                deck_install.local_deck_id
                if deck_install is not None
                else (install_result.get("response") or {}).get("installed_deck_id")
            ),
            "install_created": bool(install_result.get("created")),
        }
        source_note_type_id = str(deck_item.source_note_type_id or "").strip()
        if source_note_type_id:
            note_type_install = payment_repository.get_note_type_install(
                user_id=order.user_id,
                source_note_type_id=source_note_type_id,
            )
            if note_type_install is not None:
                grant_data["note_type_install_id"] = note_type_install.id
                grant_data["installed_note_type_id"] = note_type_install.installed_note_type_id
        return grant_data

    raise PaymentServiceError("VALIDATION_ERROR", "Unsupported product type in order.", status=400)


def _ensure_entitlements_for_confirmed_order(order: PaymentOrder, attempt: PaymentAttempt, *, now: datetime) -> None:
    existing_by_item_id = {
        row.payment_order_item_id: row
        for row in order.entitlements
    }
    for order_item in order.items:
        entitlement = existing_by_item_id.get(order_item.id)
        if entitlement is None:
            entitlement = PaymentEntitlement(
                user_id=order.user_id,
                payment_order_id=order.id,
                payment_order_item_id=order_item.id,
                payment_attempt_id=attempt.id,
                entitlement_type=(
                    "shared_deck_install"
                    if order_item.product_type == "deck_marketplace_item"
                    else "shared_note_type_install"
                ),
                resource_type=order_item.product_type,
                resource_ref_id=order_item.product_ref_id,
                status="pending",
                grant_data_json={},
            )
            db.session.add(entitlement)
            db.session.flush()

        if entitlement.status == "active":
            continue

        entitlement.payment_attempt_id = attempt.id
        entitlement.status = "pending"
        entitlement.grant_data_json = _fulfill_order_item(
            order=order,
            order_item=order_item,
            attempt=attempt,
            now=now,
        )
        entitlement.status = "active"
        entitlement.granted_at = now
        entitlement.effective_from = now

    order.grant_status = "completed"


def _mark_manual_review(
    *,
    order: PaymentOrder,
    attempt: PaymentAttempt,
    event: PaymentWebhookEvent,
    reason: str,
    now: datetime,
) -> None:
    attempt.status = "manual_review"
    attempt.manual_review_reason = reason
    order.status = "under_review"
    event.payment_attempt_id = attempt.id
    event.payment_order_id = order.id
    event.processing_status = "processed"
    event.error_message = reason
    event.processed_at = now


def _mark_failed_attempt(
    *,
    order: PaymentOrder,
    attempt: PaymentAttempt,
    event: PaymentWebhookEvent,
    reason: str,
    now: datetime,
) -> None:
    attempt.status = "failed"
    attempt.failed_at = now
    attempt.failure_code = "provider_failed"
    attempt.failure_message = reason
    order.status = "failed"
    order.closed_at = now
    event.payment_attempt_id = attempt.id
    event.payment_order_id = order.id
    event.processing_status = "processed"
    event.error_message = reason
    event.processed_at = now


def _resolve_webhook_attempt_candidates(normalized_payload: dict[str, Any]) -> list[PaymentAttempt]:
    provider_payment_id = normalized_payload.get("provider_payment_id")
    provider_order_code = normalized_payload.get("provider_order_code")
    payment_reference = normalized_payload.get("payment_reference")
    amount_minor = int(normalized_payload.get("amount_minor") or 0)

    if provider_payment_id:
        attempt = payment_repository.get_attempt_by_provider_payment_id(
            provider_code=PAYMENT_PROVIDER_CODE,
            provider_payment_id=provider_payment_id,
        )
        if attempt is not None:
            return [attempt]

    if provider_order_code:
        attempt = payment_repository.get_attempt_by_provider_order_code(
            provider_code=PAYMENT_PROVIDER_CODE,
            provider_order_code=provider_order_code,
        )
        if attempt is not None:
            return [attempt]

    if payment_reference:
        return payment_repository.find_attempts_by_reference_and_amount(
            payment_reference=payment_reference,
            amount_minor=amount_minor,
        )

    return []


def _process_webhook_event(event_id: str, normalized_payload: dict[str, Any], *, signature_valid: bool) -> tuple[dict[str, Any], int]:
    now = _utcnow()
    event = payment_repository.get_webhook_event_by_id(event_id)
    if event is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Webhook event not found.", status=404)

    attempts = _resolve_webhook_attempt_candidates(normalized_payload)
    if not attempts:
        event.processing_status = "ignored"
        event.error_message = "No matching order or attempt found."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    if len(attempts) != 1:
        event.processing_status = "ignored"
        event.error_message = "Webhook matched multiple payment attempts."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    initial_attempt = attempts[0]
    initial_order = initial_attempt.order
    if initial_order is None:
        event.processing_status = "ignored"
        event.error_message = "Matched payment attempt has no parent order."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    order, attempt = payment_repository.get_order_and_latest_attempt_for_update(
        order_id=initial_order.id,
        attempt_id=initial_attempt.id,
    )
    if order is None or attempt is None:
        event.processing_status = "ignored"
        event.error_message = "Payment attempt could not be reloaded."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    event.payment_attempt_id = attempt.id
    event.payment_order_id = order.id

    if _maybe_expire_order(order, now=now):
        db.session.flush()

    if order.status == "paid" and order.grant_status == "completed":
        event.processing_status = "processed"
        event.processed_at = now
        db.session.commit()
        return {"status": "already_processed", "order": serialize_order(order)}, 200

    if not signature_valid and not normalized_payload.get("provider_payment_id"):
        _mark_manual_review(
            order=order,
            attempt=attempt,
            event=event,
            reason="Webhook signature missing or invalid.",
            now=now,
        )
        db.session.commit()
        return {"status": "manual_review", "order": serialize_order(order)}, 202

    if order.status in {"canceled", "failed", "refunded"}:
        event.processing_status = "ignored"
        event.error_message = f"Order is already closed with status '{order.status}'."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "order": serialize_order(order)}, 200

    if not normalized_payload.get("success"):
        _mark_failed_attempt(
            order=order,
            attempt=attempt,
            event=event,
            reason=f"Provider reported non-success status '{normalized_payload.get('status') or 'unknown'}'.",
            now=now,
        )
        db.session.commit()
        return {"status": "failed", "order": serialize_order(order)}, 200

    if int(attempt.amount_minor or 0) != int(normalized_payload.get("amount_minor") or 0):
        _mark_manual_review(
            order=order,
            attempt=attempt,
            event=event,
            reason="Payment amount mismatch.",
            now=now,
        )
        db.session.commit()
        return {"status": "manual_review", "order": serialize_order(order)}, 202

    payment_reference = str(normalized_payload.get("payment_reference") or "").strip()
    expected_reference = str(attempt.expected_payment_reference or "").strip()
    if payment_reference and expected_reference and payment_reference != expected_reference:
        _mark_manual_review(
            order=order,
            attempt=attempt,
            event=event,
            reason="Payment reference mismatch.",
            now=now,
        )
        db.session.commit()
        return {"status": "manual_review", "order": serialize_order(order)}, 202

    attempt.status = "confirmed"
    attempt.confirmed_at = now
    attempt.provider_payment_id = normalized_payload.get("provider_payment_id") or attempt.provider_payment_id
    attempt.provider_order_code = normalized_payload.get("provider_order_code") or attempt.provider_order_code
    provider_metadata = dict(attempt.provider_metadata_json or {})
    if normalized_payload.get("provider_transaction_ref"):
        provider_metadata["provider_transaction_ref"] = normalized_payload["provider_transaction_ref"]
    if normalized_payload.get("payment_reference"):
        provider_metadata["payment_reference_confirmed"] = normalized_payload["payment_reference"]
    attempt.provider_metadata_json = provider_metadata

    order.status = "paid"
    order.paid_at = order.paid_at or now
    order.closed_at = now
    _ensure_entitlements_for_confirmed_order(order, attempt, now=now)

    event.processing_status = "processed"
    event.error_message = None
    event.processed_at = now
    db.session.commit()
    return {"status": "processed", "order": serialize_order(order)}, 200


def process_vietqr_webhook(normalized_payload: dict[str, Any], *, signature_valid: bool) -> tuple[dict[str, Any], int]:
    now = _utcnow()
    event = PaymentWebhookEvent(
        provider_code=PAYMENT_PROVIDER_CODE,
        event_key=normalized_payload["event_key"],
        event_type=normalized_payload.get("event_type") or "payment.unknown",
        signature_valid=bool(signature_valid),
        processing_status="received",
        payload_json=normalized_payload.get("raw_payload") or {},
        received_at=now,
    )
    db.session.add(event)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {
            "status": "duplicate",
            "event_key": normalized_payload["event_key"],
        }, 200

    if not payments_enabled():
        event = payment_repository.get_webhook_event_by_id(event.id)
        if event is not None:
            event.processing_status = "ignored"
            event.error_message = "Payments are disabled."
            event.processed_at = now
            db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    if not webhook_auto_grant_enabled():
        event = payment_repository.get_webhook_event_by_id(event.id)
        if event is not None:
            event.processing_status = "ignored"
            event.error_message = "Webhook auto grant is disabled."
            event.processed_at = now
            db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 202

    try:
        return _process_webhook_event(
            event.id,
            normalized_payload,
            signature_valid=signature_valid,
        )
    except Exception as exc:
        db.session.rollback()
        failed_event = payment_repository.get_webhook_event_by_id(event.id)
        if failed_event is not None:
            failed_event.processing_status = "failed"
            failed_event.error_message = str(exc)
            failed_event.processed_at = _utcnow()
            db.session.commit()
        return {
            "status": "failed",
            "event_id": event.id,
            "message": "Webhook logged for manual retry.",
        }, 200
