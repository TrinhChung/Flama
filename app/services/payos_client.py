from __future__ import annotations

import os
from functools import lru_cache

from payos import PayOS
from payos.types import CreatePaymentLinkRequest, CreatePaymentLinkResponse, PaymentLink, Payout, PayoutBatchRequest, Webhook


class PayOSConfigurationError(RuntimeError):
    pass


def create_payout_batch(*, batch_data: PayoutBatchRequest, idempotency_key: str) -> Payout:
    client = get_payos_client()
    return client.payouts.batch.create(batch_data=batch_data, idempotency_key=idempotency_key)


def create_payment_link(*, payment_data: CreatePaymentLinkRequest) -> CreatePaymentLinkResponse:
    client = get_payos_client()
    return client.payment_requests.create(payment_data=payment_data)


def get_payment_link(identifier: str | int) -> PaymentLink:
    client = get_payos_client()
    return client.payment_requests.get(identifier)


def cancel_payment_link(identifier: str | int, *, cancellation_reason: str | None = None) -> PaymentLink:
    client = get_payos_client()
    return client.payment_requests.cancel(identifier, cancellation_reason=cancellation_reason)


def verify_webhook_data(payload: bytes | str) -> Webhook:
    client = get_payos_client()
    return client.webhooks.verify(payload)


def get_payout(identifier: str) -> Payout:
    client = get_payos_client()
    return client.payouts.get(identifier)


def get_payos_client() -> PayOS:
    client_id = _get_required_env("PAYOS_CLIENT_ID")
    api_key = _get_required_env("PAYOS_API_KEY")
    checksum_key = _get_required_env("PAYOS_CHECKSUM_KEY")
    return _build_payos_client(client_id=client_id, api_key=api_key, checksum_key=checksum_key)


@lru_cache(maxsize=1)
def _build_payos_client(*, client_id: str, api_key: str, checksum_key: str) -> PayOS:
    return PayOS(
        client_id=client_id,
        api_key=api_key,
        checksum_key=checksum_key,
    )


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    raise PayOSConfigurationError(f"Missing required payOS configuration: {name}")
