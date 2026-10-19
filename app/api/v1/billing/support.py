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


@support_bp.get("/status")
def get_support_donation_status():
    from app.repositories import payment_repository
    from app.services import payment, support_donation_service
    from app.services.payment.provider.payos_provider import PayOSProviderError

    order_id = (request.args.get("payment_order_id") or request.args.get("order_id") or "").strip()
    provider_order_code = (
        request.args.get("support_provider_order_code")
        or request.args.get("provider_order_code")
        or ""
    ).strip()

    if order_id:
        order = payment_repository.get_order_by_id(order_id)
        if order is None:
            return error_response("NOT_FOUND", "Không tìm thấy đơn hàng thanh toán.", status=404)
        if order.user_id is not None:
            if not current_user.is_authenticated or (
                int(current_user.id) != int(order.user_id) and not getattr(current_user, "is_admin", False)
            ):
                return error_response(
                    "AUTHENTICATION_REQUIRED",
                    "Authentication is required to view saved donation order status.",
                    status=401,
                )
        order = payment.sync_order_and_commit(order=order)
        return jsonify(payment.serialize_order(order))

    if provider_order_code:
        attempt = payment_repository.get_attempt_by_provider_order_code(
            provider_code=payment.PAYMENT_PROVIDER_CODE,
            provider_order_code=provider_order_code,
        )
        if attempt is not None and attempt.order is not None:
            order = attempt.order
            if order.user_id is not None and (
                not current_user.is_authenticated
                or (int(current_user.id) != int(order.user_id) and not getattr(current_user, "is_admin", False))
            ):
                return error_response(
                    "AUTHENTICATION_REQUIRED",
                    "Authentication is required to view saved donation order status.",
                    status=401,
                )
            order = payment.sync_attempt_order_and_commit(attempt=attempt)
            return jsonify(payment.serialize_order(order))

        try:
            result = support_donation_service.get_anonymous_checkout_status(
                provider_order_code=provider_order_code
            )
            return jsonify(result)
        except PayOSProviderError as exc:
            return error_response(exc.code, str(exc), status=exc.status)
        except Exception:
            return error_response(
                "PAYMENT_LOOKUP_FAILED",
                "Không thể kiểm tra trạng thái đóng góp lúc này.",
                status=502,
            )

    return error_response(
        "VALIDATION_ERROR",
        "Cần cung cấp payment_order_id hoặc support_provider_order_code.",
        status=400,
    )
