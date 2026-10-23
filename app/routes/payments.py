from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from app.spa import serve_react_spa

from app.validators.payment_input import (
    normalize_order_create_payload,
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


@payments_bp.route("/payments/marketplace-result", methods=["GET"])
@login_required
def marketplace_payment_result_page():
    return serve_react_spa(
        "payments/marketplace_result.html",
        payment_order_id=(request.args.get("payment_order_id") or "").strip(),
        payment_product_type=(request.args.get("payment_product_type") or "").strip(),
        payment_product_ref_id=(request.args.get("payment_product_ref_id") or "").strip(),
    )


@payments_bp.route("/api/payments/orders", methods=["POST"])
@login_required
def create_payment_order():
    from app.services import payment

    payload = request.get_json(silent=True) or {}
    normalized_payload, message, field = normalize_order_create_payload(payload)
    if normalized_payload is None:
        return _api_error("VALIDATION_ERROR", message or "Invalid payload.", field=field)

    try:
        result = payment.prepare_checkout_for_product(
            user_id=current_user.id,
            product_type=normalized_payload["product_type"],
            product_ref_id=normalized_payload["product_ref_id"],
            return_url=normalized_payload.get("return_url") or request.referrer or request.host_url,
            cancel_url=normalized_payload.get("cancel_url") or request.referrer or request.host_url,
        )
    except payment.PaymentServiceError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)

    if result.get("payment_required"):
        status = 201 if result.get("created") else 200
        return jsonify(result), status
    return jsonify(result), 200


@payments_bp.route("/api/payments/orders/<order_id>", methods=["GET"])
@login_required
def get_payment_order(order_id: str):
    from app.services import payment

    try:
        result = payment.get_order_detail_for_user(
            order_id=order_id,
            user_id=current_user.id,
        )
    except payment.PaymentServiceError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(result)


@payments_bp.route("/api/payments/orders/<order_id>/cancel", methods=["POST"])
@login_required
def cancel_payment_order(order_id: str):
    from app.services import payment

    try:
        result = payment.cancel_order_for_user(
            order_id=order_id,
            user_id=current_user.id,
        )
    except payment.PaymentServiceError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(result)


@payments_bp.route("/api/payments/providers/payos/webhook", methods=["POST"])
def payos_webhook():
    from app.services import payment

    raw_payload = request.get_data(cache=True)
    try:
        result, status = payment.process_payos_webhook_request(raw_payload)
    except payment.PaymentServiceError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(result), status
