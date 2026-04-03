"""Payment domain helpers."""

from importlib import import_module

from .config import (
    order_expiry_seconds,
    paid_install_interception_enabled,
    payment_provider_code,
    payments_enabled,
    webhook_auto_grant_enabled,
)

__all__ = [
    "order_expiry_seconds",
    "paid_install_interception_enabled",
    "payment_provider_code",
    "payments_enabled",
    "webhook_auto_grant_enabled",
]


def __getattr__(name: str):
    if name == "provider":
        return import_module(f"{__name__}.provider")
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
