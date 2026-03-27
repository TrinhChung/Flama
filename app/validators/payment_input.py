from __future__ import annotations

import hashlib
from typing import Any


SUPPORTED_PAYMENT_PRODUCT_TYPES = {"deck_marketplace_item", "note_type"}
SUCCESS_PAYMENT_STATUSES = {"paid", "confirmed", "success", "succeeded"}


def normalize_order_create_payload(payload: Any) -> tuple[dict[str, str] | None, str | None, str | None]:
    if not isinstance(payload, dict):
        return None, "Payload must be an object.", None

    product_type = str(payload.get("product_type") or "").strip().lower()
    product_ref_id = str(payload.get("product_ref_id") or payload.get("product_id") or "").strip()

    if product_type not in SUPPORTED_PAYMENT_PRODUCT_TYPES:
        return None, "product_type must be 'note_type' or 'deck_marketplace_item'.", "product_type"
    if not product_ref_id:
        return None, "product_ref_id is required.", "product_ref_id"

    return {
        "product_type": product_type,
        "product_ref_id": product_ref_id,
    }, None, None


def normalize_vietqr_webhook_payload(payload: Any) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if not isinstance(payload, dict):
        return None, "Payload must be an object.", None

    raw_amount = payload.get("amount_minor", payload.get("amount"))
    try:
        amount_minor = int(raw_amount)
    except (TypeError, ValueError):
        return None, "amount_minor is required and must be an integer.", "amount_minor"
    if amount_minor <= 0:
        return None, "amount_minor must be > 0.", "amount_minor"

    provider_order_code = str(
        payload.get("provider_order_code")
        or payload.get("order_code")
        or payload.get("orderCode")
        or ""
    ).strip()
    payment_reference = str(
        payload.get("payment_reference")
        or payload.get("reference")
        or payload.get("description")
        or ""
    ).strip()
    provider_payment_id = str(
        payload.get("provider_payment_id")
        or payload.get("payment_id")
        or payload.get("paymentLinkId")
        or ""
    ).strip()
    provider_transaction_ref = str(
        payload.get("provider_transaction_ref")
        or payload.get("transaction_ref")
        or payload.get("transactionRef")
        or payload.get("transaction_id")
        or ""
    ).strip()
    event_type = str(payload.get("event_type") or payload.get("type") or "payment.unknown").strip() or "payment.unknown"
    raw_status = str(payload.get("status") or payload.get("result") or "").strip().lower()
    success = bool(payload.get("success")) or raw_status in SUCCESS_PAYMENT_STATUSES

    if not provider_order_code and not payment_reference:
        return None, "provider_order_code or payment_reference is required.", "provider_order_code"

    event_key = str(payload.get("event_id") or payload.get("id") or "").strip()
    if not event_key:
        digest_input = "|".join(
            [
                provider_order_code,
                provider_payment_id,
                provider_transaction_ref,
                payment_reference,
                str(amount_minor),
                raw_status,
                event_type,
            ]
        )
        event_key = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()

    return {
        "provider_code": "vietqr",
        "event_key": event_key,
        "event_type": event_type,
        "provider_order_code": provider_order_code or None,
        "provider_payment_id": provider_payment_id or None,
        "provider_transaction_ref": provider_transaction_ref or None,
        "payment_reference": payment_reference or None,
        "amount_minor": amount_minor,
        "currency_code": str(payload.get("currency_code") or payload.get("currency") or "VND").strip() or "VND",
        "success": success,
        "status": raw_status or ("success" if success else "unknown"),
        "raw_payload": payload,
    }, None, None
