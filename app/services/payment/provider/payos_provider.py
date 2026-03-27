from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from payos import APIError, InvalidSignatureError, WebhookError
from payos.types import CreatePaymentLinkRequest
from payos.types.v2.payment_requests.payment_requests import ItemData

from app.services import payos_client


class PayOSProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str, status: int) -> None:
        super().__init__(message)
        self.code = code
        self.status = int(status)


def assert_payos_provider_available() -> None:
    try:
        payos_client.get_payos_client()
    except payos_client.PayOSConfigurationError as exc:
        raise PayOSProviderError(
            "Cấu hình payOS chưa đầy đủ nên chưa thể tạo thanh toán lúc này.",
            code="PAYMENT_PROVIDER_NOT_CONFIGURED",
            status=503,
        ) from exc


def create_checkout_session(
    *,
    provider_order_code: int,
    amount_minor: int,
    title_snapshot: str,
    payment_reference: str,
    return_url: str,
    cancel_url: str,
    expires_at: datetime | None,
    buyer_email: str | None = None,
) -> dict[str, Any]:
    assert_payos_provider_available()
    try:
        response = payos_client.create_payment_link(
            payment_data=CreatePaymentLinkRequest(
                orderCode=int(provider_order_code),
                amount=int(amount_minor),
                description=payment_reference,
                cancelUrl=cancel_url,
                returnUrl=return_url,
                items=[
                    ItemData(
                        name=(title_snapshot or "FLAMA purchase")[:64],
                        quantity=1,
                        price=int(amount_minor),
                    )
                ],
                buyerEmail=buyer_email or None,
                expiredAt=_to_unix_seconds(expires_at) if expires_at is not None else None,
            )
        )
    except payos_client.PayOSConfigurationError as exc:
        raise PayOSProviderError(
            "Cấu hình payOS chưa đầy đủ nên chưa thể tạo thanh toán lúc này.",
            code="PAYMENT_PROVIDER_NOT_CONFIGURED",
            status=503,
        ) from exc
    except APIError as exc:
        raise PayOSProviderError(
            _build_provider_message(exc),
            code="PAYMENT_PROVIDER_ERROR",
            status=_map_provider_status(exc.status_code),
        ) from exc
    except Exception as exc:
        raise PayOSProviderError(
            "Không thể tạo liên kết thanh toán qua payOS lúc này. Vui lòng thử lại sau ít phút.",
            code="PAYMENT_PROVIDER_ERROR",
            status=502,
        ) from exc

    metadata = {
        "bank_bin": response.bin,
        "account_no": response.account_number,
        "account_name": response.account_name,
        "amount_minor": int(response.amount),
        "currency_code": response.currency,
        "provider_status": response.status,
        "payment_reference": response.description,
        "payment_link_id": response.payment_link_id,
        "checkout_url": response.checkout_url,
        "qr_code": response.qr_code,
    }
    provider_expires_at = (
        datetime.utcfromtimestamp(int(response.expired_at))
        if response.expired_at is not None
        else expires_at
    )
    return {
        "provider_code": "payos",
        "provider_order_code": str(response.order_code),
        "provider_payment_id": str(response.payment_link_id),
        "checkout_url": response.checkout_url,
        "amount_minor": int(response.amount),
        "currency_code": response.currency or "VND",
        "expires_at": provider_expires_at,
        "provider_metadata": metadata,
        "raw_response": _serialize_model(response),
    }


def get_payment_link_state(
    *,
    provider_payment_id: str | None = None,
    provider_order_code: str | None = None,
) -> dict[str, Any]:
    assert_payos_provider_available()
    identifier = str(provider_payment_id or "").strip() or str(provider_order_code or "").strip()
    if not identifier:
        raise PayOSProviderError(
            "Thiếu mã thanh toán PayOS để kiểm tra trạng thái phiên thanh toán cũ.",
            code="PAYMENT_PROVIDER_LOOKUP_INVALID",
            status=400,
        )
    try:
        response = payos_client.get_payment_link(identifier)
    except payos_client.PayOSConfigurationError as exc:
        raise PayOSProviderError(
            "Cấu hình payOS chưa đầy đủ nên chưa thể kiểm tra trạng thái thanh toán.",
            code="PAYMENT_PROVIDER_NOT_CONFIGURED",
            status=503,
        ) from exc
    except APIError as exc:
        raise PayOSProviderError(
            _build_provider_lookup_message(exc),
            code="PAYMENT_PROVIDER_LOOKUP_FAILED",
            status=_map_provider_status(exc.status_code),
        ) from exc
    except Exception as exc:
        raise PayOSProviderError(
            "Không thể kiểm tra trạng thái phiên thanh toán trên payOS lúc này.",
            code="PAYMENT_PROVIDER_LOOKUP_FAILED",
            status=502,
        ) from exc

    payload = _serialize_model(response)
    return {
        "provider_code": "payos",
        "provider_payment_id": str(response.id or provider_payment_id or "").strip() or None,
        "provider_order_code": str(response.order_code or provider_order_code or "").strip() or None,
        "status": str(response.status or "").strip().upper(),
        "amount_minor": int(response.amount or 0),
        "amount_paid_minor": int(response.amount_paid or 0),
        "amount_remaining_minor": int(response.amount_remaining or 0),
        "cancellation_reason": str(response.cancellation_reason or "").strip() or None,
        "canceled_at": str(response.canceled_at or "").strip() or None,
        "created_at": str(response.created_at or "").strip() or None,
        "raw_response": payload,
    }


def verify_webhook_payload(raw_payload: bytes | str) -> dict[str, Any]:
    assert_payos_provider_available()
    try:
        webhook = payos_client.verify_webhook_data(raw_payload)
    except (InvalidSignatureError, WebhookError) as exc:
        raise PayOSProviderError(
            "Dữ liệu webhook từ payOS không hợp lệ hoặc không vượt qua bước xác minh chữ ký.",
            code="INVALID_WEBHOOK_SIGNATURE",
            status=400,
        ) from exc
    except payos_client.PayOSConfigurationError as exc:
        raise PayOSProviderError(
            "Cấu hình payOS chưa đầy đủ nên chưa thể xác minh webhook.",
            code="PAYMENT_PROVIDER_NOT_CONFIGURED",
            status=503,
        ) from exc
    except Exception as exc:
        raise PayOSProviderError(
            "Không thể xác minh webhook từ payOS ở thời điểm này.",
            code="PAYMENT_PROVIDER_ERROR",
            status=502,
        ) from exc

    payload = _serialize_model(webhook)
    data = webhook.data
    success = bool(getattr(webhook, "success", False)) and str(data.code or "").strip() == "00"
    event_key = _build_event_key(
        provider_payment_id=str(data.payment_link_id or "").strip(),
        provider_order_code=str(data.order_code or "").strip(),
        provider_transaction_ref=str(data.reference or "").strip(),
        payment_reference=str(data.description or "").strip(),
        amount_minor=int(data.amount or 0),
        transaction_datetime=str(data.transaction_date_time or "").strip(),
        status_code=str(data.code or "").strip(),
    )

    return {
        "provider_code": "payos",
        "event_key": event_key,
        "event_type": "payment.succeeded" if success else "payment.updated",
        "provider_order_code": str(data.order_code or "").strip() or None,
        "provider_payment_id": str(data.payment_link_id or "").strip() or None,
        "provider_transaction_ref": str(data.reference or "").strip() or None,
        "payment_reference": str(data.description or "").strip() or None,
        "amount_minor": int(data.amount or 0),
        "currency_code": str(data.currency or "VND").strip() or "VND",
        "success": success,
        "status": (str(data.code or "").strip() or ("success" if success else "unknown")).lower(),
        "raw_payload": payload,
    }


def _serialize_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump_camel_case"):
        return model.model_dump_camel_case()
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return dict(model)


def _to_unix_seconds(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return int(value.timestamp())


def _build_event_key(
    *,
    provider_payment_id: str,
    provider_order_code: str,
    provider_transaction_ref: str,
    payment_reference: str,
    amount_minor: int,
    transaction_datetime: str,
    status_code: str,
) -> str:
    digest_input = "|".join(
        [
            provider_payment_id,
            provider_order_code,
            provider_transaction_ref,
            payment_reference,
            str(int(amount_minor or 0)),
            transaction_datetime,
            status_code,
        ]
    )
    return hashlib.sha256(digest_input.encode("utf-8")).hexdigest()


def _map_provider_status(status_code: int | None) -> int:
    if status_code is None:
        return 502
    if status_code in {400, 401, 403, 404, 409, 429}:
        return int(status_code)
    if status_code >= 500:
        return 502
    return 502


def _build_provider_message(exc: APIError) -> str:
    if exc.error_desc:
        return f"payOS từ chối tạo thanh toán: {str(exc.error_desc).strip()}"
    if exc.error_code:
        return f"payOS từ chối tạo thanh toán với mã lỗi {exc.error_code}."
    return "payOS không thể tạo liên kết thanh toán cho yêu cầu này."


def _build_provider_lookup_message(exc: APIError) -> str:
    if exc.error_desc:
        return f"payOS từ chối kiểm tra trạng thái thanh toán: {str(exc.error_desc).strip()}"
    if exc.error_code:
        return f"payOS từ chối kiểm tra trạng thái với mã lỗi {exc.error_code}."
    return "payOS không thể trả về trạng thái của phiên thanh toán này."
