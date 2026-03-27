from __future__ import annotations

from flask import current_app


def payments_enabled() -> bool:
    return bool(
        current_app.config.get(
            "PAYMENTS_ENABLED",
            current_app.config.get("PAYMENTS_V1_ENABLED", False),
        )
    )


def paid_install_interception_enabled() -> bool:
    return payments_enabled() and bool(current_app.config.get("PAYMENTS_PAID_INSTALL_REQUIRED", False))


def webhook_auto_grant_enabled() -> bool:
    return payments_enabled() and bool(current_app.config.get("PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED", False))


def payment_provider_code() -> str:
    return str(current_app.config.get("PAYMENTS_PROVIDER") or "payos").strip().lower() or "payos"


def order_expiry_seconds(*, default: int) -> int:
    raw_value = current_app.config.get("PAYMENTS_ORDER_EXPIRY_SECONDS", default)
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return int(default)
