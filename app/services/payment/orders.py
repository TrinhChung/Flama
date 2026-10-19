"""Payment order creation, serialization, cancellation, and expiration management."""

from __future__ import annotations

from datetime import datetime
from secrets import randbelow
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from app.repositories import payment_repository
from models import db
from models.payment_attempt import PaymentAttempt
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem

from app.services.payment.base import (
    ACTIVE_ATTEMPT_STATUSES,
    TERMINAL_ORDER_STATUSES,
    PaymentServiceError,
    _iso,
    _order_is_support_donation,
    _utcnow,
)
from app.services.payment.status_display import (
    _attempt_status_display,
    _build_order_detail_lines,
    _build_order_instructions,
    _build_order_next_action,
    _build_order_status_display,
    _grant_status_display,
)

def _build_merchant_order_code() -> str:
    return f"ORD-{_utcnow():%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}"


def _build_payment_reference() -> str:
    return f"FLAMA{uuid4().hex[:10].upper()}"


def _build_provider_order_code() -> int:
    timestamp_millis = int(time.time() * 1000)
    return int(f"{timestamp_millis}{randbelow(1000):03d}")


def _append_payment_context(url: str, *, order_id: str, product_type: str, product_ref_id: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["payment_order_id"] = order_id
    query["payment_product_type"] = product_type
    query["payment_product_ref_id"] = product_ref_id
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


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
    attempt.failure_message = attempt.failure_message or "Lượt thanh toán đã hết hạn trước khi PayOS xác nhận thành công."

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
    status_display = _attempt_status_display(attempt)
    return {
        "id": attempt.id,
        "provider_code": attempt.provider_code,
        "payment_method_code": attempt.payment_method_code,
        "status": attempt.status,
        "status_display": status_display,
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
        "message": status_display["description"],
        "checkout": {
            "provider": attempt.provider_code,
            "checkout_url": attempt.checkout_url,
            "payment_link_id": attempt.provider_payment_id,
            "provider_order_code": attempt.provider_order_code,
            "bank_bin": provider_metadata.get("bank_bin"),
            "account_no": provider_metadata.get("account_no"),
            "account_name": provider_metadata.get("account_name"),
            "template": provider_metadata.get("template"),
            "qr_code": provider_metadata.get("qr_code"),
            "provider_status": provider_metadata.get("provider_status"),
            "amount_minor": int(attempt.amount_minor or 0),
            "currency_code": attempt.currency_code,
            "payment_reference": attempt.expected_payment_reference,
            "merchant_order_code": provider_metadata.get("merchant_order_code"),
        },
    }


def serialize_order(order: PaymentOrder) -> dict[str, Any]:
    latest_attempt = _latest_attempt(order)
    status_display = _build_order_status_display(order, latest_attempt)
    grant_status_display = _grant_status_display(order.grant_status, order=order)
    next_action = _build_order_next_action(order, latest_attempt)
    instructions = _build_order_instructions(order, latest_attempt)
    order_detail_lines = _build_order_detail_lines(order, latest_attempt)
    return {
        "id": order.id,
        "is_support_donation": _order_is_support_donation(order),
        "merchant_order_code": order.merchant_order_code,
        "status": order.status,
        "status_display": status_display,
        "grant_status": order.grant_status,
        "grant_status_display": grant_status_display,
        "currency_code": order.currency_code,
        "subtotal_amount_minor": int(order.subtotal_amount_minor or 0),
        "discount_amount_minor": int(order.discount_amount_minor or 0),
        "total_amount_minor": int(order.total_amount_minor or 0),
        "paid_at": _iso(order.paid_at),
        "closed_at": _iso(order.closed_at),
        "created_at": _iso(order.created_at),
        "updated_at": _iso(order.updated_at),
        "message": status_display.get("description", ""),
        "headline": status_display.get("headline", status_display.get("title", "")),
        "next_action": next_action,
        "instructions": instructions,
        "order_detail_lines": order_detail_lines,
        "items": [_serialize_order_item(item) for item in order.items],
        "attempts": [_serialize_attempt(attempt) for attempt in order.attempts],
        "active_attempt": _serialize_attempt(latest_attempt),
    }


def sync_and_get_order(*, order_id: str) -> dict[str, Any]:
    from app.services.payment.checkout import _sync_attempt_with_payos

    order = payment_repository.get_order_by_id(order_id)
    if order is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy đơn hàng thanh toán.", status=404)
    latest_attempt = _latest_attempt(order)
    if latest_attempt is not None and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES and order.status == "pending_payment":
        resolution = _sync_attempt_with_payos(order, latest_attempt, now=_utcnow())
        if resolution in {"reuse", "completed", "block", "recreate"}:
            db.session.commit()
            order = payment_repository.get_order_by_id(order_id) or order
    if _maybe_expire_order(order):
        db.session.commit()
        order = payment_repository.get_order_by_id(order_id) or order
    return serialize_order(order)


def get_order_detail_for_user(*, order_id: str, user_id: int) -> dict[str, Any]:
    from app.services.payment.checkout import _sync_attempt_with_payos

    order = payment_repository.get_order_for_user(order_id, user_id)
    if order is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy đơn hàng thanh toán.", status=404)
    latest_attempt = _latest_attempt(order)
    if latest_attempt is not None and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES and order.status == "pending_payment":
        resolution = _sync_attempt_with_payos(order, latest_attempt, now=_utcnow())
        if resolution in {"reuse", "completed", "block", "recreate"}:
            db.session.commit()
            order = payment_repository.get_order_for_user(order_id, user_id) or order
    if _maybe_expire_order(order):
        db.session.commit()
        order = payment_repository.get_order_for_user(order_id, user_id) or order
    return serialize_order(order)


def cancel_order_for_user(*, order_id: str, user_id: int) -> dict[str, Any]:
    order = payment_repository.get_order_for_user(order_id, user_id)
    if order is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy đơn hàng thanh toán.", status=404)
    if _maybe_expire_order(order):
        db.session.commit()
        order = payment_repository.get_order_for_user(order_id, user_id) or order
    if order.status == "canceled":
        return serialize_order(order)
    if order.status in TERMINAL_ORDER_STATUSES - {"canceled"}:
        raise PaymentServiceError(
            "PAYMENT_ORDER_NOT_CANCELABLE",
            "Chỉ đơn đang chờ thanh toán mới có thể hủy. Đơn này đã ở trạng thái cuối cùng.",
            status=409,
        )

    latest_attempt = _latest_attempt(order)
    now = _utcnow()
    if latest_attempt is not None and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES.union({"manual_review"}):
        latest_attempt.status = "canceled"
        latest_attempt.failed_at = now
        latest_attempt.failure_code = "canceled"
        latest_attempt.failure_message = "Người dùng đã chủ động hủy lượt thanh toán này."

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


def admin_update_order_status(*, order_id: str, new_status: str, note: str = "") -> dict[str, Any]:
    from app.services.payment.fulfillment import _ensure_entitlements_for_confirmed_order
    
    order = payment_repository.get_order_by_id(order_id)
    if order is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy đơn hàng cần cập nhật.", status=404)
        
    valid_statuses = {"paid", "pending_payment", "under_review", "canceled", "failed", "refunded"}
    if new_status not in valid_statuses:
        raise PaymentServiceError("VALIDATION_ERROR", f"Trạng thái '{new_status}' không hợp lệ.", status=400)
        
    now = _utcnow()
    latest_attempt = _latest_attempt(order)
    
    if new_status == "paid":
        order.status = "paid"
        order.paid_at = order.paid_at or now
        order.closed_at = now
        if latest_attempt is not None:
            latest_attempt.status = "confirmed"
            latest_attempt.confirmed_at = latest_attempt.confirmed_at or now
            if note:
                meta = dict(latest_attempt.provider_metadata_json or {})
                meta["admin_note"] = note
                latest_attempt.provider_metadata_json = meta
            _ensure_entitlements_for_confirmed_order(order, latest_attempt, now=now)
            
    elif new_status == "canceled":
        order.status = "canceled"
        order.closed_at = now
        if latest_attempt is not None and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES.union({"manual_review"}):
            latest_attempt.status = "canceled"
            latest_attempt.failed_at = now
            latest_attempt.failure_code = "admin_canceled"
            latest_attempt.failure_message = note or "Quản trị viên đã chủ động hủy đơn hàng."
            
    elif new_status == "failed":
        order.status = "failed"
        order.closed_at = now
        if latest_attempt is not None and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES.union({"manual_review"}):
            latest_attempt.status = "failed"
            latest_attempt.failed_at = now
            latest_attempt.failure_code = "admin_failed"
            latest_attempt.failure_message = note or "Quản trị viên đánh dấu thanh toán thất bại."

    elif new_status == "refunded":
        order.status = "refunded"
        order.closed_at = now
        if latest_attempt is not None:
            latest_attempt.status = "refunded"
            
    elif new_status == "under_review":
        order.status = "under_review"
        if latest_attempt is not None:
            latest_attempt.status = "manual_review"
            latest_attempt.manual_review_reason = note or "Quản trị viên chuyển sang trạng thái chờ kiểm duyệt."
            
    elif new_status == "pending_payment":
        order.status = "pending_payment"
        order.closed_at = None
        order.paid_at = None
        if latest_attempt is not None:
            latest_attempt.status = "pending"
            
    db.session.commit()
    return serialize_order(order)


