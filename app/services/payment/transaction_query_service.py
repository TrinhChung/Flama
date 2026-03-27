from __future__ import annotations

from typing import Any

from app.repositories.payment import transaction_queries
from app.services.payment.presenters import build_attempt_row, build_transaction_row
from app.validators.payment_query import TransactionFilterInput


def list_admin_transactions(*, filters: TransactionFilterInput, page: int, per_page: int) -> dict[str, Any]:
    pagination = transaction_queries.paginate_admin_transactions(filters=filters, page=page, per_page=per_page)
    items = [build_transaction_row(attempt) for attempt in pagination.items]
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


def get_admin_transaction_detail(attempt_id: str) -> dict[str, Any] | None:
    attempt = transaction_queries.get_attempt_detail_for_admin(attempt_id)
    if attempt is None:
        return None
    payload = build_attempt_row(attempt)
    payload["order"] = (
        {
            "id": attempt.order.id,
            "merchant_order_code": attempt.order.merchant_order_code,
            "buyer": {
                "id": attempt.order.user.id if attempt.order.user is not None else None,
                "username": attempt.order.user.username if attempt.order.user is not None else "",
                "email": attempt.order.user.email if attempt.order.user is not None else "",
            },
            "item_rows": [
                {
                    "title_snapshot": item.title_snapshot,
                    "product_type": item.product_type,
                    "product_ref_id": item.product_ref_id,
                }
                for item in attempt.order.items
            ],
        }
        if attempt.order is not None
        else None
    )
    return payload


def list_recent_abnormal_attempts(*, limit: int = 8, since=None) -> list[dict[str, Any]]:
    return [build_transaction_row(row) for row in transaction_queries.list_recent_abnormal_attempts(limit=limit, since=since)]


def list_recent_webhook_failures(*, limit: int = 8, since=None) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for event in transaction_queries.list_recent_webhook_failures(limit=limit, since=since):
        payload.append(
            {
                "id": event.id,
                "event_type": event.event_type,
                "processing_status": event.processing_status,
                "signature_valid": bool(event.signature_valid),
                "received_at": event.received_at,
                "received_at_display": event.received_at.strftime("%Y-%m-%d %H:%M") if event.received_at else "-",
                "error_message": event.error_message,
                "payment_attempt_id": event.payment_attempt_id,
                "payment_order_id": event.payment_order_id,
                "merchant_order_code": event.payment_order.merchant_order_code if event.payment_order is not None else "",
                "buyer_username": event.payment_order.user.username
                if event.payment_order is not None and event.payment_order.user is not None
                else "",
            }
        )
    return payload
