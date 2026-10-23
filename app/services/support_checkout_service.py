"""Application boundary shared by legacy and REST support checkout routes."""

from __future__ import annotations

from typing import Any

from app.services import payment, support_donation_service
from app.services.payment.provider import payos_provider
from app.validators.support_donation import normalize_support_donation_checkout_payload


class SupportCheckoutError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.field = field


def prepare_support_checkout(
    *,
    payload: dict[str, Any],
    authenticated: bool,
    user_id: int | None,
    default_return_url: str,
) -> tuple[dict[str, Any], int]:
    normalized, message, field = normalize_support_donation_checkout_payload(payload)
    if normalized is None:
        raise SupportCheckoutError(
            "VALIDATION_ERROR",
            message or "Invalid payload.",
            field=field,
        )

    if not payment.payments_enabled():
        raise SupportCheckoutError(
            "PAYMENT_UNAVAILABLE",
            "Payment is temporarily unavailable. Please try again later.",
            status=503,
        )

    return_url = normalized.return_url or default_return_url
    cancel_url = normalized.cancel_url or return_url
    effective_user_id = user_id if (authenticated and not normalized.anonymous) else None

    try:
        result = payment.prepare_support_donation_checkout(
            user_id=effective_user_id,
            amount_minor=normalized.amount_minor,
            return_url=return_url,
            cancel_url=cancel_url,
        )
    except payment.PaymentServiceError as exc:
        raise SupportCheckoutError(
            exc.error,
            exc.message,
            status=exc.status,
            field=exc.field,
        ) from exc
    except payos_provider.PayOSProviderError as exc:
        raise SupportCheckoutError(
            exc.code,
            str(exc),
            status=exc.status,
        ) from exc

    return result, 201 if result.get("created") else 200
