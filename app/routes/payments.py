from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.services import payment_service
from app.validators.payment_input import (
    normalize_order_create_payload,
    normalize_vietqr_webhook_payload,
)


payments_bp = Blueprint("payments", __name__)


def _api_error(
    error: str,
    message: str,
    *,
    status: int = 400,
    field: str | None = None,
):
    payload: dict[str, Any] = {"error": error, "message": message}
    if field is not None:
        payload["field"] = field
    return jsonify(payload), status


def _resolve_vietqr_signature_valid() -> bool:
    expected_secret = str(current_app.config.get("PAYMENTS_VIETQR_WEBHOOK_SECRET") or "").strip()
    header_value = (
        request.headers.get("X-Flama-Vietqr-Webhook-Secret")
        or request.headers.get("X-Flama-Webhook-Secret")
        or ""
    ).strip()
    if not expected_secret:
        return False
    return header_value == expected_secret


@payments_bp.route("/api/payments/orders", methods=["POST"])
@login_required
def create_payment_order():
    payload = request.get_json(silent=True) or {}
    normalized_payload, message, field = normalize_order_create_payload(payload)
    if normalized_payload is None:
        return _api_error("VALIDATION_ERROR", message or "Invalid payload.", field=field)

    try:
        result = payment_service.prepare_checkout_for_product(
            user_id=current_user.id,
            product_type=normalized_payload["product_type"],
            product_ref_id=normalized_payload["product_ref_id"],
        )
    except payment_service.PaymentServiceError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)

    if result.get("payment_required"):
        status = 201 if result.get("created") else 200
        return jsonify(result), status
    return jsonify(result), 200


@payments_bp.route("/api/payments/orders/<order_id>", methods=["GET"])
@login_required
def get_payment_order(order_id: str):
    try:
        result = payment_service.get_order_detail_for_user(
            order_id=order_id,
            user_id=current_user.id,
        )
    except payment_service.PaymentServiceError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(result)


@payments_bp.route("/api/payments/orders/<order_id>/cancel", methods=["POST"])
@login_required
def cancel_payment_order(order_id: str):
    try:
        result = payment_service.cancel_order_for_user(
            order_id=order_id,
            user_id=current_user.id,
        )
    except payment_service.PaymentServiceError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(result)


@payments_bp.route("/api/payments/providers/vietqr/webhook", methods=["POST"])
def vietqr_webhook():
    payload = request.get_json(silent=True) or {}
    normalized_payload, message, field = normalize_vietqr_webhook_payload(payload)
    if normalized_payload is None:
        return _api_error("VALIDATION_ERROR", message or "Invalid payload.", field=field)

    expected_secret = str(current_app.config.get("PAYMENTS_VIETQR_WEBHOOK_SECRET") or "").strip()
    signature_valid = _resolve_vietqr_signature_valid()
    if expected_secret and not signature_valid:
        return _api_error(
            "INVALID_WEBHOOK_SIGNATURE",
            "Webhook signature is invalid.",
            status=403,
        )

    result, status = payment_service.process_vietqr_webhook(
        normalized_payload,
        signature_valid=signature_valid,
    )
    return jsonify(result), status
