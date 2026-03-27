from __future__ import annotations

import os
from functools import lru_cache

from payos import PayOS
from payos.types import Payout, PayoutBatchRequest


class PayOSConfigurationError(RuntimeError):
    pass


def create_payout_batch(*, batch_data: PayoutBatchRequest, idempotency_key: str) -> Payout:
    client = get_payos_client()
    return client.payouts.batch.create(batch_data=batch_data, idempotency_key=idempotency_key)


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
