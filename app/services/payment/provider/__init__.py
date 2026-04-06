from importlib import import_module

__all__ = [
    "PayOSProviderError",
    "assert_payos_provider_available",
    "create_checkout_session",
    "get_payment_link_state",
    "verify_webhook_payload",
    "payos_provider",
]


def __getattr__(name: str):
    if name == "payos_provider":
        return import_module(f"{__name__}.payos_provider")
    if name in {
        "PayOSProviderError",
        "assert_payos_provider_available",
        "create_checkout_session",
        "get_payment_link_state",
        "verify_webhook_payload",
    }:
        module = import_module(f"{__name__}.payos_provider")
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
