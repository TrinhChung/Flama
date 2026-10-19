"""Payment service package."""

from app.services.payment.config import (
    payments_enabled,
    paid_install_interception_enabled,
    webhook_auto_grant_enabled,
    payment_provider_code,
    order_expiry_seconds,
)
from app.services.payment.base import (
    PAYMENT_PROVIDER_CODE,
    PAYMENT_METHOD_CODE,
    PAYOS_PROVIDER_REUSABLE_STATUSES,
    ACTIVE_ATTEMPT_STATUSES,
    DEFAULT_ORDER_EXPIRY_SECONDS,
    TERMINAL_ORDER_STATUSES,
    PaymentServiceError,
    _utcnow,
    _iso,
    _clean_text,
    _product_type_label,
    _product_title_from_order,
    _order_is_support_donation,
    _require_payments_enabled,
    _require_supported_provider,
)
from app.services.payment.status_display import (
    _grant_status_display,
    _attempt_status_display,
    _build_order_status_display,
    _build_order_next_action,
    _build_order_instructions,
    _build_order_detail_lines,
)
from app.services.payment.orders import (
    _build_merchant_order_code,
    _build_payment_reference,
    _build_provider_order_code,
    _append_payment_context,
    _latest_attempt,
    _maybe_expire_order,
    _serialize_order_item,
    _serialize_attempt,
    serialize_order,
    sync_and_get_order,
    get_order_detail_for_user,
    cancel_order_for_user,
    expire_stale_orders,
    admin_update_order_status,
)
from app.services.payment.checkout import (
    _validate_note_type_for_checkout,
    _validate_deck_item_for_checkout,
    _resolve_existing_access_for_product,
    _load_checkout_context,
    _build_checkout_attempt,
    _sync_attempt_with_payos,
    _create_or_reuse_order_for_context,
    prepare_checkout_for_product,
    prepare_support_donation_checkout,
)
from app.services.payment.fulfillment import (
    _fulfill_order_item,
    _ensure_entitlements_for_confirmed_order,
    _mark_manual_review,
    _mark_failed_attempt,
)
from app.services.payment.webhook import (
    _resolve_webhook_attempt_candidates,
    _process_webhook_event,
    process_payment_webhook,
    process_payos_webhook_request,
)
