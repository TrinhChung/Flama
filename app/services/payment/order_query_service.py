from __future__ import annotations

from typing import Any

from app.repositories.payment import order_queries
from app.services.payment.presenters import build_order_detail_payload, build_order_row
from app.validators.payment_query import OrderFilterInput


def list_admin_orders(*, filters: OrderFilterInput, page: int, per_page: int) -> dict[str, Any]:
    pagination = order_queries.paginate_admin_orders(filters=filters, page=page, per_page=per_page)
    items = [build_order_row(order) for order in pagination.items]
    return _build_list_payload(items=items, pagination=pagination)


def list_user_orders(*, user_id: int, filters: OrderFilterInput, page: int, per_page: int) -> dict[str, Any]:
    pagination = order_queries.paginate_user_orders(user_id=user_id, filters=filters, page=page, per_page=per_page)
    items = [build_order_row(order) for order in pagination.items]
    return _build_list_payload(items=items, pagination=pagination)


def get_admin_order_detail(order_id: str) -> dict[str, Any] | None:
    from app.services import payment_service

    try:
        payment_service.sync_and_get_order(order_id=order_id)
    except Exception:
        pass
    order = order_queries.get_order_detail_for_admin(order_id)
    if order is None:
        return None
    return build_order_detail_payload(order)


def get_user_order_detail(*, order_id: str, user_id: int) -> dict[str, Any] | None:
    from app.services import payment_service

    try:
        payment_service.get_order_detail_for_user(order_id=order_id, user_id=user_id)
    except Exception:
        pass
    order = order_queries.get_order_detail_for_user(order_id=order_id, user_id=user_id)
    if order is None:
        return None
    return build_order_detail_payload(order)


def _build_list_payload(*, items: list[dict[str, Any]], pagination) -> dict[str, Any]:
    return {
        "items": items,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages or 1,
        "has_prev": bool(pagination.has_prev),
        "has_next": bool(pagination.has_next),
        "prev_num": pagination.prev_num,
        "next_num": pagination.next_num,
    }
