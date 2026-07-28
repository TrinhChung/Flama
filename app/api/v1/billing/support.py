"""Public support-donation REST resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, url_for
from flask_login import current_user

from app.api.common import error_response
from app.services.support_checkout_service import (
    SupportCheckoutError,
    prepare_support_checkout,
)
from app.services.rest_api_service import build_support_donation_payload

support_bp = Blueprint("api_v1_support", __name__)


@support_bp.get("")
def get_support_donation():
    return jsonify(build_support_donation_payload())


def _frontend_checkout_fields(payload: dict) -> dict:
    """Expose the active checkout URL without removing the canonical payload."""
    checkout = payload.get("checkout")
    if not isinstance(checkout, dict):
        order = payload.get("order")
        if isinstance(order, dict):
            active_attempt = order.get("active_attempt")
            if isinstance(active_attempt, dict):
                checkout = active_attempt.get("checkout")
    if not isinstance(checkout, dict):
        return payload

    result = dict(payload)
    result.setdefault("checkout_url", checkout.get("checkout_url"))
    result.setdefault("payment_link_id", checkout.get("payment_link_id"))
    result.setdefault("provider_order_code", checkout.get("provider_order_code"))
    return result


@support_bp.post("/checkout")
def create_support_checkout():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )

    try:
        result, status = prepare_support_checkout(
            payload=payload,
            authenticated=bool(current_user.is_authenticated),
            user_id=(int(current_user.id) if current_user.is_authenticated else None),
            default_return_url=url_for(
                "main.support_donation_result_page",
                _external=True,
            ),
        )
    except SupportCheckoutError as exc:
        return error_response(
            exc.code,
            exc.message,
            status=exc.status,
            field=exc.field,
        )
    return jsonify(_frontend_checkout_fields(result)), status
