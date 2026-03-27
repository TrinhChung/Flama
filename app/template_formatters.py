"""Template helpers for comma-separated numeric display."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

_PRICE_DISPLAY_RE = re.compile(r"^(\D*?)([-+]?\d[\d,]*(?:\.\d+)?)(\D*)$")


def _to_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def format_number(value: object, digits: int | None = None) -> str:
    """Format integers/decimals with comma thousands separators."""
    if value in (None, ""):
        return ""

    decimal_value = _to_decimal(value)
    if decimal_value is None:
        return str(value)

    if digits is not None:
        quantizer = Decimal("1").scaleb(-digits)
        rounded = decimal_value.quantize(quantizer, rounding=ROUND_HALF_UP)
        return format(rounded, f",.{digits}f")

    if decimal_value == decimal_value.to_integral():
        return format(int(decimal_value), ",")

    normalized = format(decimal_value.normalize(), "f")
    whole, _, fraction = normalized.partition(".")
    fraction = fraction.rstrip("0")
    if not fraction:
        return format(int(whole), ",")
    return f"{format(int(whole), ',')}.{fraction}"


def format_vnd(value: object) -> str:
    formatted = format_number(value)
    if not formatted:
        return ""
    return f"{formatted} VNĐ"


def format_price_display(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    match = _PRICE_DISPLAY_RE.match(text)
    if not match:
        return text

    prefix, raw_number, suffix = match.groups()
    digits = len(raw_number.split(".", 1)[1]) if "." in raw_number else None
    formatted_number = format_number(raw_number, digits=digits)
    return f"{prefix}{formatted_number}{suffix}".strip()
