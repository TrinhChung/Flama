from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


MIN_DONATION_AMOUNT_MINOR = 1_000
MAX_DONATION_AMOUNT_MINOR = 50_000_000
SUGGESTED_DONATION_AMOUNTS = (50_000, 100_000, 200_000, 500_000)


@dataclass(frozen=True)
class SupportDonationCheckoutInput:
    amount_minor: int
    return_url: str
    cancel_url: str
    anonymous: bool = False


def normalize_support_donation_checkout_payload(
    payload: Any,
) -> tuple[SupportDonationCheckoutInput | None, str | None, str | None]:
    if not isinstance(payload, dict):
        return None, "Payload must be an object.", None

    amount_minor = _normalize_amount_minor(payload.get("amount_minor") or payload.get("amount"))
    return_url = _normalize_url(payload.get("return_url"))
    cancel_url = _normalize_url(payload.get("cancel_url"))
    anonymous = _normalize_bool(payload.get("anonymous"))

    if amount_minor is None:
        return None, "amount_minor must be a positive integer.", "amount_minor"
    if amount_minor < MIN_DONATION_AMOUNT_MINOR:
        return None, f"amount_minor must be at least {MIN_DONATION_AMOUNT_MINOR}.", "amount_minor"
    if amount_minor > MAX_DONATION_AMOUNT_MINOR:
        return None, f"amount_minor must not exceed {MAX_DONATION_AMOUNT_MINOR}.", "amount_minor"
    if payload.get("return_url") not in (None, "") and return_url is None:
        return None, "return_url must be an absolute http(s) URL.", "return_url"
    if payload.get("cancel_url") not in (None, "") and cancel_url is None:
        return None, "cancel_url must be an absolute http(s) URL.", "cancel_url"

    return (
        SupportDonationCheckoutInput(
            amount_minor=amount_minor,
            return_url=return_url or "",
            cancel_url=cancel_url or "",
            anonymous=anonymous,
        ),
        None,
        None,
    )


def _normalize_amount_minor(value: Any) -> int | None:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        amount_minor = int(raw)
    except (TypeError, ValueError):
        return None
    if amount_minor <= 0:
        return None
    return amount_minor


def _normalize_url(raw_value: Any) -> str | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
