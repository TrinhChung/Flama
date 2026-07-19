from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from flask import current_app, has_app_context

try:
    from payos import PayOS
    from payos.types import CreatePaymentLinkRequest, CreatePaymentLinkResponse, PaymentLink, Payout, PayoutBatchRequest, Webhook
    _PAYOS_SDK_AVAILABLE = True
except ModuleNotFoundError:
    PayOS = Any  # type: ignore[misc,assignment]
    CreatePaymentLinkRequest = Any  # type: ignore[misc,assignment]
    CreatePaymentLinkResponse = Any  # type: ignore[misc,assignment]
    PaymentLink = Any  # type: ignore[misc,assignment]
    Payout = Any  # type: ignore[misc,assignment]
    PayoutBatchRequest = Any  # type: ignore[misc,assignment]
    Webhook = Any  # type: ignore[misc,assignment]
    _PAYOS_SDK_AVAILABLE = False


class PayOSConfigurationError(RuntimeError):
    pass


def create_payout_batch(*, batch_data: PayoutBatchRequest, idempotency_key: str) -> Payout:
    _require_payos_sdk()
    client = get_payos_client()
    return client.payouts.batch.create(batch_data=batch_data, idempotency_key=idempotency_key)


def create_payment_link(*, payment_data: CreatePaymentLinkRequest) -> CreatePaymentLinkResponse:
    _require_payos_sdk()
    client = get_payos_client()
    return client.payment_requests.create(payment_data=payment_data)


def get_payment_link(identifier: str | int) -> PaymentLink:
    _require_payos_sdk()
    client = get_payos_client()
    return client.payment_requests.get(identifier)


def cancel_payment_link(identifier: str | int, *, cancellation_reason: str | None = None) -> PaymentLink:
    _require_payos_sdk()
    client = get_payos_client()
    return client.payment_requests.cancel(identifier, cancellation_reason=cancellation_reason)


def verify_webhook_data(payload: bytes | str) -> Webhook:
    _require_payos_sdk()
    client = get_payos_client()
    return client.webhooks.verify(payload)


def get_payout(identifier: str) -> Payout:
    _require_payos_sdk()
    client = get_payos_client()
    return client.payouts.get(identifier)


def get_payos_client() -> PayOS:
    _require_payos_sdk()
    client_id, api_key, checksum_key = validate_payos_configuration()
    return _build_payos_client(client_id=client_id, api_key=api_key, checksum_key=checksum_key)


@lru_cache(maxsize=1)
def _build_payos_client(*, client_id: str, api_key: str, checksum_key: str) -> PayOS:
    return PayOS(
        client_id=client_id,
        api_key=api_key,
        checksum_key=checksum_key,
    )


def _get_required_env(name: str) -> str:
    value = _get_config_value(name)
    if value:
        return value
    raise PayOSConfigurationError(f"Missing required payOS configuration: {name}")


def _get_config_value(name: str) -> str:
    if has_app_context():
        value = str(current_app.config.get(name, "")).strip()
        if value:
            return value
    return os.getenv(name, "").strip()


def _require_payos_sdk() -> None:
    if _PAYOS_SDK_AVAILABLE:
        return
    raise PayOSConfigurationError("payOS SDK is not installed in the current environment.")


def validate_payos_configuration() -> tuple[str, str, str]:
    client_id = _get_required_env("PAYOS_CLIENT_ID")
    api_key = _get_required_env("PAYOS_API_KEY")
    checksum_key = _get_required_env("PAYOS_CHECKSUM_KEY")
    return client_id, api_key, checksum_key
