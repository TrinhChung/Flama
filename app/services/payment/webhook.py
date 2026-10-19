"""Webhook event processing, idempotency checks, and PayOS webhook handler."""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError

from app.repositories import payment_repository
from app.services.payment.provider import payos_provider
from models import db
from models.payment_attempt import PaymentAttempt
from models.payment_webhook_event import PaymentWebhookEvent

from app.services.payment.base import (
    PAYMENT_PROVIDER_CODE,
    PaymentServiceError,
    _require_payments_enabled,
    _require_supported_provider,
    _utcnow,
)
from app.services.payment.config import payments_enabled, webhook_auto_grant_enabled
from app.services.payment.fulfillment import (
    _ensure_entitlements_for_confirmed_order,
    _mark_failed_attempt,
    _mark_manual_review,
)
from app.services.payment.orders import (
    _maybe_expire_order,
    serialize_order,
)

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
        raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy sự kiện webhook cần xử lý.", status=404)

    attempts = _resolve_webhook_attempt_candidates(normalized_payload)
    if not attempts:
        event.processing_status = "ignored"
        event.error_message = "Không tìm thấy đơn hàng hoặc lượt thanh toán khớp với webhook này."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    if len(attempts) != 1:
        event.processing_status = "ignored"
        event.error_message = "Webhook khớp với nhiều lượt thanh toán nên cần bỏ qua để tránh đối soát sai."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    initial_attempt = attempts[0]
    initial_order = initial_attempt.order
    if initial_order is None:
        event.processing_status = "ignored"
        event.error_message = "Lượt thanh toán khớp được tìm thấy nhưng không còn gắn với đơn hàng hợp lệ."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    order, attempt = payment_repository.get_order_and_latest_attempt_for_update(
        order_id=initial_order.id,
        attempt_id=initial_attempt.id,
    )
    if order is None or attempt is None:
        event.processing_status = "ignored"
        event.error_message = "Không thể tải lại đơn hàng hoặc lượt thanh toán để xử lý webhook."
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
            reason="Webhook từ PayOS không vượt qua bước xác minh chữ ký nên cần kiểm tra thủ công.",
            now=now,
        )
        db.session.commit()
        return {"status": "manual_review", "order": serialize_order(order)}, 202

    if order.status in {"canceled", "failed", "refunded"}:
        event.processing_status = "ignored"
        event.error_message = f"Đơn hàng đã đóng trước đó với trạng thái '{order.status}'."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "order": serialize_order(order)}, 200

    if not normalized_payload.get("success"):
        _mark_failed_attempt(
            order=order,
            attempt=attempt,
            event=event,
            reason=(
                "PayOS trả về trạng thái không thành công"
                f" ('{normalized_payload.get('status') or 'unknown'}') cho đơn hàng này."
            ),
            now=now,
        )
        db.session.commit()
        return {"status": "failed", "order": serialize_order(order)}, 200

    if int(attempt.amount_minor or 0) != int(normalized_payload.get("amount_minor") or 0):
        _mark_manual_review(
            order=order,
            attempt=attempt,
            event=event,
            reason="Số tiền PayOS gửi về không khớp với số tiền của đơn hàng nên cần kiểm tra thủ công.",
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
            reason="Nội dung chuyển khoản PayOS gửi về không khớp với mã tham chiếu của đơn hàng.",
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


def process_payment_webhook(normalized_payload: dict[str, Any], *, signature_valid: bool) -> tuple[dict[str, Any], int]:
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
            event.error_message = "Hệ thống thanh toán đang tắt nên webhook chỉ được ghi nhận chứ không xử lý."
            event.processed_at = now
            db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    if not webhook_auto_grant_enabled():
        event = payment_repository.get_webhook_event_by_id(event.id)
        if event is not None:
            event.processing_status = "ignored"
            event.error_message = "Chế độ tự cấp quyền từ webhook đang tắt nên cần xử lý thủ công."
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
            "message": "Webhook đã được lưu để kiểm tra và xử lý lại thủ công.",
        }, 200


def process_payos_webhook_request(raw_payload: bytes | str) -> tuple[dict[str, Any], int]:
    _require_payments_enabled()
    _require_supported_provider()
    try:
        normalized_payload = payos_provider.verify_webhook_payload(raw_payload)
    except payos_provider.PayOSProviderError as exc:
        raise PaymentServiceError(exc.code, str(exc), status=exc.status) from exc
    return process_payment_webhook(normalized_payload, signature_valid=True)

