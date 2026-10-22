"""Payment service base constants, error types, and basic utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services import support_donation_service
from app.services.payment import config as payment_config
from app.services.payment.provider import payos_provider
from models.payment_order import PaymentOrder

UTC = timezone.utc

PAYMENT_PROVIDER_CODE = "payos"
PAYMENT_METHOD_CODE = "payos_checkout"
PAYOS_PROVIDER_REUSABLE_STATUSES = {"PENDING", "PROCESSING"}
ACTIVE_ATTEMPT_STATUSES = {"created", "pending"}
DEFAULT_ORDER_EXPIRY_SECONDS = 30 * 60
TERMINAL_ORDER_STATUSES = {"paid", "expired", "canceled", "failed", "refunded"}


class PaymentServiceError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.error = code
        self.message = message
        self.status = status
        self.field = field
        self.extra = extra or {}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _product_type_label(product_type: str) -> str:
    return {
        "note_type": "Note Type",
        "deck_marketplace_item": "deck",
        "template": "giao diện thẻ",
        support_donation_service.DONATION_PRODUCT_TYPE: "ủng hộ",
    }.get(_clean_text(product_type), "sản phẩm")


def _order_is_support_donation(order: PaymentOrder) -> bool:
    return bool(order.items) and all(
        _clean_text(item.product_type) == support_donation_service.DONATION_PRODUCT_TYPE for item in order.items
    )


def _product_title_from_order(order: PaymentOrder) -> str:
    if not order.items:
        return "Sản phẩm"
    titles = [_clean_text(item.title_snapshot) or _product_type_label(item.product_type) for item in order.items]
    if len(titles) == 1:
        return titles[0]
    return f"{titles[0]} và {len(titles) - 1} mục khác"


def _require_payments_enabled() -> None:
    if not payment_config.payments_enabled():
        raise PaymentServiceError(
            "PAYMENT_UNAVAILABLE",
            "Hệ thống thanh toán đang tạm thời không khả dụng. Vui lòng thử lại sau.",
            status=503,
        )


def _require_supported_provider() -> None:
    provider_code = payment_config.payment_provider_code()
    if provider_code != PAYMENT_PROVIDER_CODE:
        raise PaymentServiceError(
            "PAYMENT_PROVIDER_UNSUPPORTED",
            f"Cổng thanh toán '{provider_code}' hiện chưa được hỗ trợ trong môi trường này.",
            status=503,
        )
    try:
        payos_provider.assert_payos_provider_available()
    except payos_provider.PayOSProviderError as exc:
        raise PaymentServiceError(exc.code, str(exc), status=exc.status) from exc
