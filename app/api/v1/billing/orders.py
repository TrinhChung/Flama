"""Authenticated order read resources."""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common import error_response
from app.services import admin_service
from app.services.payment import order_query_service
from app.validators.payment_query import parse_order_filters


orders_bp = Blueprint("api_v1_orders", __name__)

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50


@orders_bp.get("")
@login_required
def list_orders():
    filters = parse_order_filters(request.args)
    payload = order_query_service.list_user_orders(
        user_id=current_user.id,
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


@orders_bp.get("/<order_id>")
@login_required
def get_order(order_id: str):
    payload = order_query_service.get_user_order_detail(
        order_id=order_id,
        user_id=current_user.id,
    )
    if payload is None:
        return error_response(
            "NOT_FOUND",
            "Order not found.",
            status=404,
        )
    return jsonify(payload)
