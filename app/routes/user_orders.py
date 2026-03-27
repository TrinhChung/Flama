from __future__ import annotations

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.services import admin_service
from app.services.payment import order_query_service
from app.validators.payment_query import parse_order_filters


user_orders_bp = Blueprint("user_orders", __name__)

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50


@user_orders_bp.route("/orders", methods=["GET"])
@login_required
def order_history_page():
    filters = parse_order_filters(request.args)
    page = admin_service.coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = admin_service.coerce_int(request.args.get("per_page"), default=DEFAULT_PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)
    payload = order_query_service.list_user_orders(
        user_id=current_user.id,
        filters=filters,
        page=page,
        per_page=per_page,
    )
    return render_template(
        "user/orders/index.html",
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


@user_orders_bp.route("/orders/<order_id>", methods=["GET"])
@login_required
def order_detail_page(order_id: str):
    payload = order_query_service.get_user_order_detail(order_id=order_id, user_id=current_user.id)
    if payload is None:
        abort(404)
    return render_template(
        "user/orders/detail.html",
        order=payload,
    )
