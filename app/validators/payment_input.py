from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


SUPPORTED_PAYMENT_PRODUCT_TYPES = {"deck_marketplace_item", "note_type", "template"}


def normalize_order_create_payload(payload: Any) -> tuple[dict[str, str] | None, str | None, str | None]:
    if not isinstance(payload, dict):
        return None, "Payload must be an object.", None

    product_type = str(payload.get("product_type") or "").strip().lower()
    product_ref_id = str(payload.get("product_ref_id") or payload.get("product_id") or "").strip()
    return_url = _normalize_url(payload.get("return_url"))
    cancel_url = _normalize_url(payload.get("cancel_url"))

    if product_type not in SUPPORTED_PAYMENT_PRODUCT_TYPES:
        return None, "product_type must be 'note_type', 'deck_marketplace_item' or 'template'.", "product_type"
    if not product_ref_id:
        return None, "product_ref_id is required.", "product_ref_id"
    if payload.get("return_url") not in (None, "") and return_url is None:
        return None, "return_url must be an absolute http(s) URL.", "return_url"
    if payload.get("cancel_url") not in (None, "") and cancel_url is None:
        return None, "cancel_url must be an absolute http(s) URL.", "cancel_url"

    return {
        "product_type": product_type,
        "product_ref_id": product_ref_id,
        "return_url": return_url or "",
        "cancel_url": cancel_url or "",
    }, None, None


def _normalize_url(raw_value: Any) -> str | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text
