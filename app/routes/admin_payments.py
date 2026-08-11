from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, request, url_for
from flask_login import current_user, login_required
from app.spa import serve_react_spa

from app.services import admin_service
from app.services.payment import order_query_service, transaction_query_service
from app.utils.permissions import is_admin_user
from app.validators.payment_query import (
    parse_order_filters,
    parse_transaction_filters,
)


admin_payments_bp = Blueprint("admin_payments", __name__, url_prefix="/admin/payments")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _ensure_admin_access():
    if is_admin_user(current_user):
        return None
    flash("Bạn không có quyền truy cập khu vực quản trị thanh toán.", "warning")
    return redirect(url_for("main.dashboard"))


@admin_payments_bp.route("", methods=["GET"])
@login_required
def dashboard_page():
    guard = _ensure_admin_access()
    if guard is not None:
        return guard
    from app.spa import serve_react_spa
    return serve_react_spa()


@admin_payments_bp.route("/orders", methods=["GET"])
@login_required
def orders_page():
    guard = _ensure_admin_access()
    if guard is not None:
        return guard
    filters = parse_order_filters(request.args)
    page = admin_service.coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = admin_service.coerce_int(request.args.get("per_page"), default=DEFAULT_PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)
    payload = order_query_service.list_admin_orders(filters=filters, page=page, per_page=per_page)
    return serve_react_spa(
        "admin/payment/orders.html",
        items=payload["items"],
        page=payload["page"],
        per_page=payload["per_page"],
        total=payload["total"],
        total_pages=payload["pages"],
        has_prev=payload["has_prev"],
        has_next=payload["has_next"],
        prev_num=payload["prev_num"],
        next_num=payload["next_num"],
        filters=filters,
    )


@admin_payments_bp.route("/orders/<order_id>", methods=["GET"])
@login_required
def order_detail_page(order_id: str):
    guard = _ensure_admin_access()
    if guard is not None:
        return guard
    payload = order_query_service.get_admin_order_detail(order_id)
    if payload is None:
        abort(404)
    return serve_react_spa(
        "admin/payment/order_detail.html",
        order=payload,
    )


@admin_payments_bp.route("/transactions", methods=["GET"])
@login_required
def transactions_page():
    guard = _ensure_admin_access()
    if guard is not None:
        return guard
    filters = parse_transaction_filters(request.args)
    page = admin_service.coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = admin_service.coerce_int(request.args.get("per_page"), default=DEFAULT_PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)
    payload = transaction_query_service.list_admin_transactions(filters=filters, page=page, per_page=per_page)
    return serve_react_spa(
        "admin/payment/transactions.html",
        items=payload["items"],
        page=payload["page"],
        per_page=payload["per_page"],
        total=payload["total"],
        total_pages=payload["pages"],
        has_prev=payload["has_prev"],
        has_next=payload["has_next"],
        prev_num=payload["prev_num"],
        next_num=payload["next_num"],
        filters=filters,
    )


@admin_payments_bp.route("/transactions/<attempt_id>", methods=["GET"])
@login_required
def transaction_detail_page(attempt_id: str):
    guard = _ensure_admin_access()
    if guard is not None:
        return guard
    payload = transaction_query_service.get_admin_transaction_detail(attempt_id)
    if payload is None:
        abort(404)
    return serve_react_spa(
        "admin/payment/transaction_detail.html",
        attempt=payload,
    )
