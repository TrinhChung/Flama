from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services import payment_service
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType
from models.payment_attempt import PaymentAttempt
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.payment_webhook_event import PaymentWebhookEvent


ATTEMPT_STATUS_LABELS = {
    "created": "Mới tạo",
    "pending": "Đang chờ thanh toán",
    "confirmed": "Đã xác nhận",
    "manual_review": "Cần kiểm tra",
    "expired": "Đã hết hạn",
    "canceled": "Đã hủy",
    "failed": "Thất bại",
    "refunded": "Đã hoàn tiền",
}

WEBHOOK_STATUS_LABELS = {
    "received": "Đã nhận",
    "processed": "Đã xử lý",
    "ignored": "Bỏ qua",
    "failed": "Xử lý lỗi",
}

PRODUCT_TYPE_LABELS = {
    "note_type": "Template",
    "deck_marketplace_item": "Deck",
    "support_donation": "Ủng hộ",
}


def build_order_row(order: PaymentOrder) -> dict[str, Any]:
    payload = payment_service.serialize_order(order)
    status_display = payload.get("status_display") or {}
    active_attempt = payload.get("active_attempt") or {}
    attempt_status_display = (active_attempt.get("status_display") or {}) if active_attempt else {}
    return {
        "id": order.id,
        "merchant_order_code": order.merchant_order_code,
        "title": _first_item_title(order),
        "item_count": len(order.items),
        "total_amount_minor": int(order.total_amount_minor or 0),
        "total_amount_display": format_minor_amount(order.total_amount_minor, currency_code=order.currency_code),
        "status": order.status,
        "status_label": status_display.get("label") or order.status,
        "status_tone": status_display.get("tone") or "secondary",
        "payment_status": active_attempt.get("status") or "",
        "payment_status_label": attempt_status_display.get("label") or "",
        "grant_status": order.grant_status,
        "grant_status_label": (payload.get("grant_status_display") or {}).get("label") or order.grant_status,
        "provider_code": active_attempt.get("provider_code") or "",
        "created_at": order.created_at,
        "created_at_display": format_datetime(order.created_at),
        "paid_at": order.paid_at,
        "paid_at_display": format_datetime(order.paid_at),
        "buyer": _build_buyer_payload(order),
        "serialized": payload,
    }


def build_order_detail_payload(order: PaymentOrder) -> dict[str, Any]:
    payload = payment_service.serialize_order(order)
    return {
        "id": order.id,
        "merchant_order_code": order.merchant_order_code,
        "buyer": _build_buyer_payload(order),
        "seller_labels": _build_seller_labels(order.items),
        "item_rows": [build_order_item_payload(item) for item in order.items],
        "attempt_rows": [build_attempt_row(attempt) for attempt in sorted(order.attempts, key=_attempt_sort_key, reverse=True)],
        "entitlement_rows": [
            {
                "id": row.id,
                "resource_type": row.resource_type,
                "resource_type_label": product_type_label(row.resource_type),
                "resource_ref_id": row.resource_ref_id,
                "status": row.status,
                "status_label": row.status.replace("_", " "),
                "granted_at_display": format_datetime(row.granted_at),
                "effective_from_display": format_datetime(row.effective_from),
            }
            for row in order.entitlements
        ],
        "serialized": payload,
    }


def build_order_item_payload(item: PaymentOrderItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "product_type": item.product_type,
        "product_type_label": product_type_label(item.product_type),
        "product_ref_id": item.product_ref_id,
        "title_snapshot": item.title_snapshot,
        "quantity": int(item.quantity or 0),
        "unit_amount_display": format_minor_amount(item.unit_amount_minor),
        "line_total_display": format_minor_amount(item.line_total_amount_minor),
        "seller_label": _resolve_item_seller_label(item),
    }


def build_attempt_row(attempt: PaymentAttempt) -> dict[str, Any]:
    events = sorted(attempt.webhook_events, key=lambda row: (row.received_at or datetime.min, row.id))
    latest_event = events[-1] if events else None
    return {
        "id": attempt.id,
        "status": attempt.status,
        "status_label": ATTEMPT_STATUS_LABELS.get(attempt.status, attempt.status),
        "provider_code": attempt.provider_code,
        "payment_method_code": attempt.payment_method_code,
        "amount_minor": int(attempt.amount_minor or 0),
        "amount_display": format_minor_amount(attempt.amount_minor, currency_code=attempt.currency_code),
        "provider_payment_id": attempt.provider_payment_id,
        "provider_order_code": attempt.provider_order_code,
        "expected_payment_reference": attempt.expected_payment_reference,
        "checkout_url": attempt.checkout_url,
        "expires_at": attempt.expires_at,
        "expires_at_display": format_datetime(attempt.expires_at),
        "confirmed_at": attempt.confirmed_at,
        "confirmed_at_display": format_datetime(attempt.confirmed_at),
        "failed_at": attempt.failed_at,
        "failed_at_display": format_datetime(attempt.failed_at),
        "failure_code": attempt.failure_code,
        "failure_message": attempt.failure_message,
        "manual_review_reason": attempt.manual_review_reason,
        "created_at": attempt.created_at,
        "created_at_display": format_datetime(attempt.created_at),
        "updated_at_display": format_datetime(attempt.updated_at),
        "provider_metadata": _mask_provider_metadata(attempt.provider_metadata_json or {}),
        "webhook_count": len(events),
        "latest_webhook_status": latest_event.processing_status if latest_event is not None else "",
        "latest_webhook_status_label": WEBHOOK_STATUS_LABELS.get(latest_event.processing_status, latest_event.processing_status)
        if latest_event is not None
        else "",
        "events": [build_webhook_event_payload(row) for row in reversed(events)],
        "order_id": attempt.order_id,
    }


def build_webhook_event_payload(event: PaymentWebhookEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "event_key": event.event_key,
        "event_type": event.event_type,
        "processing_status": event.processing_status,
        "processing_status_label": WEBHOOK_STATUS_LABELS.get(event.processing_status, event.processing_status),
        "signature_valid": bool(event.signature_valid),
        "error_message": event.error_message,
        "received_at_display": format_datetime(event.received_at),
        "processed_at_display": format_datetime(event.processed_at),
    }


def build_transaction_row(attempt: PaymentAttempt) -> dict[str, Any]:
    order = attempt.order
    buyer = _build_buyer_payload(order) if order is not None else {"username": "", "email": ""}
    items = list(order.items) if order is not None else []
    latest_event = None
    if attempt.webhook_events:
        latest_event = sorted(attempt.webhook_events, key=lambda row: (row.received_at or datetime.min, row.id))[-1]
    return {
        "id": attempt.id,
        "status": attempt.status,
        "status_label": ATTEMPT_STATUS_LABELS.get(attempt.status, attempt.status),
        "provider_code": attempt.provider_code,
        "payment_method_code": attempt.payment_method_code,
        "amount_display": format_minor_amount(attempt.amount_minor, currency_code=attempt.currency_code),
        "order_id": attempt.order_id,
        "merchant_order_code": order.merchant_order_code if order is not None else "",
        "buyer": buyer,
        "title": _first_item_title(order) if order is not None else "",
        "created_at_display": format_datetime(attempt.created_at),
        "provider_payment_id": attempt.provider_payment_id,
        "provider_order_code": attempt.provider_order_code,
        "expected_payment_reference": attempt.expected_payment_reference,
        "webhook_status": latest_event.processing_status if latest_event is not None else "",
        "webhook_status_label": WEBHOOK_STATUS_LABELS.get(latest_event.processing_status, latest_event.processing_status)
        if latest_event is not None
        else "",
        "webhook_count": len(attempt.webhook_events),
        "item_count": len(items),
    }


def format_minor_amount(amount_minor: int | None, *, currency_code: str | None = "VND") -> str:
    amount = int(amount_minor or 0)
    return f"{amount:,.0f} {currency_code or 'VND'}"


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d %H:%M")


def product_type_label(value: str) -> str:
    token = str(value or "").strip().lower()
    return PRODUCT_TYPE_LABELS.get(token, token or "Khác")


def _build_buyer_payload(order: PaymentOrder | None) -> dict[str, Any]:
    user = order.user if order is not None else None
    if user is None:
        return {"id": None, "username": "", "email": ""}
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }


def _build_seller_labels(items: list[PaymentOrderItem]) -> list[str]:
    labels: list[str] = []
    for item in items:
        label = _resolve_item_seller_label(item)
        if label and label not in labels:
            labels.append(label)
    return labels


def _resolve_item_seller_label(item: PaymentOrderItem) -> str:
    if item.product_type == "note_type":
        note_type = NoteType.query.get(item.product_ref_id)
        if note_type is not None and note_type.owner is not None:
            return note_type.owner.username or note_type.owner.email or ""
    if item.product_type == "deck_marketplace_item":
        deck_item = DeckMarketplaceItem.query.get(item.product_ref_id)
        if deck_item is not None and deck_item.owner is not None:
            return deck_item.owner.username or deck_item.owner.email or ""
    snapshot = item.product_snapshot_json if isinstance(item.product_snapshot_json, dict) else {}
    return str(snapshot.get("owner_name") or snapshot.get("seller_name") or "").strip()


def _mask_provider_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in metadata.items():
        token = str(key or "").strip().lower()
        if token in {"account_no", "account_number"}:
            payload[key] = _mask_suffix(value)
        else:
            payload[key] = value
    return payload


def _mask_suffix(value: Any) -> str:
    token = str(value or "").strip()
    if len(token) <= 4:
        return "*" * len(token)
    return f"{'*' * (len(token) - 4)}{token[-4:]}"


def _first_item_title(order: PaymentOrder | None) -> str:
    if order is None or not order.items:
        return "San pham"
    if len(order.items) == 1:
        return order.items[0].title_snapshot
    return f"{order.items[0].title_snapshot} +{len(order.items) - 1}"


def _attempt_sort_key(attempt: PaymentAttempt):
    return attempt.created_at or datetime.min
