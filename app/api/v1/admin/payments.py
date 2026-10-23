"""Administrative payment read resources."""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, jsonify, request

from app.api.common import admin_required, error_response
from app.services import admin_service
from app.services.payment import (
    dashboard_service,
    order_query_service,
    transaction_query_service,
)
from app.validators.payment_query import (
    parse_dashboard_filters,
    parse_order_filters,
    parse_transaction_filters,
)


admin_payments_bp = Blueprint("api_v1_admin_payments", __name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@admin_payments_bp.get("")
@admin_required
def get_dashboard():
    filters = parse_dashboard_filters(request.args)
    payload = dashboard_service.build_admin_dashboard(filters=filters)
    payload["filters"] = asdict(filters)
    return jsonify(payload)


@admin_payments_bp.get("/orders")
@admin_required
def list_orders():
    filters = parse_order_filters(request.args)
    payload = order_query_service.list_admin_orders(
        filters=filters,
        page=admin_service.coerce_int(
            request.args.get("page"),
            default=1,
            minimum=1,
        ),
        per_page=admin_service.coerce_int(
            request.args.get("per_page"),
            default=DEFAULT_PAGE_SIZE,
            minimum=1,
            maximum=MAX_PAGE_SIZE,
        ),
    )
    payload["filters"] = asdict(filters)
    return jsonify(payload)


@admin_payments_bp.get("/orders/<order_id>")
@admin_required
def get_order(order_id: str):
    payload = order_query_service.get_admin_order_detail(order_id)
    if payload is None:
        return error_response(
            "NOT_FOUND",
            "Order not found.",
            status=404,
        )
    return jsonify(payload)


@admin_payments_bp.post("/orders/<order_id>/sync")
@admin_required
def sync_order(order_id: str):
    from app.services import payment

    try:
        payment.sync_and_get_order(order_id=order_id)
    except payment.PaymentServiceError as exc:
        return error_response(exc.error, exc.message, status=exc.status, field=exc.field)
    payload = order_query_service.get_admin_order_detail(order_id)
    if payload is None:
        return error_response("NOT_FOUND", "Order not found.", status=404)
    return jsonify({
        "order": payload,
        "message": "Đồng bộ đơn hàng với cổng thanh toán thành công.",
    })


@admin_payments_bp.patch("/orders/<order_id>/status")
@admin_required
def update_order_status(order_id: str):
    from app.services.payment.base import PaymentServiceError
    from app.services.payment.orders import admin_update_order_status

    body = request.get_json(silent=True) or {}
    new_status = str(body.get("status") or "").strip().lower()
    note = str(body.get("note") or "").strip()

    if not new_status:
        return error_response("VALIDATION_ERROR", "Vui lòng chỉ định trạng thái mới.", status=400)

    try:
        admin_update_order_status(order_id=order_id, new_status=new_status, note=note)
    except PaymentServiceError as exc:
        return error_response(exc.error, exc.message, status=exc.status, field=exc.field)

    payload = order_query_service.get_admin_order_detail(order_id)
    if payload is None:
        return error_response("NOT_FOUND", "Order not found.", status=404)

    return jsonify({
        "order": payload,
        "message": f"Đã cập nhật trạng thái đơn hàng sang '{new_status}' thành công.",
    })


@admin_payments_bp.get("/transactions")
@admin_required
def list_transactions():
    filters = parse_transaction_filters(request.args)
    payload = transaction_query_service.list_admin_transactions(
        filters=filters,
        page=admin_service.coerce_int(
            request.args.get("page"),
            default=1,
            minimum=1,
        ),
        per_page=admin_service.coerce_int(
            request.args.get("per_page"),
            default=DEFAULT_PAGE_SIZE,
            minimum=1,
            maximum=MAX_PAGE_SIZE,
        ),
    )
    payload["filters"] = asdict(filters)
    return jsonify(payload)


@admin_payments_bp.get("/transactions/<attempt_id>")
@admin_required
def get_transaction(attempt_id: str):
    payload = transaction_query_service.get_admin_transaction_detail(attempt_id)
    if payload is None:
        return error_response(
            "NOT_FOUND",
            "Transaction not found.",
            status=404,
        )
    return jsonify(payload)
