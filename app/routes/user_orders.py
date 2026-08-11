from __future__ import annotations

from flask import Blueprint, abort
from flask_login import current_user, login_required
from app.spa import serve_react_spa

from app.services.payment import order_query_service


user_orders_bp = Blueprint("user_orders", __name__)


@user_orders_bp.route("/orders", methods=["GET"])
@login_required
def order_history_page():
    from app.spa import serve_react_spa
    return serve_react_spa()


@user_orders_bp.route("/orders/<order_id>", methods=["GET"])
@login_required
def order_detail_page(order_id: str):
    payload = order_query_service.get_user_order_detail(order_id=order_id, user_id=current_user.id)
    if payload is None:
        abort(404)
    return serve_react_spa(
        "user/orders/detail.html",
        order=payload,
    )
