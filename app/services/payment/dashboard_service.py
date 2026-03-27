from __future__ import annotations

from typing import Any

from app.repositories.payment import dashboard_queries
from app.services.payment.presenters import build_order_row, format_minor_amount
from app.services.payment.transaction_query_service import (
    list_recent_abnormal_attempts,
    list_recent_webhook_failures,
)
from app.validators.payment_query import DashboardFilterInput, resolve_dashboard_since


def build_admin_dashboard(*, filters: DashboardFilterInput) -> dict[str, Any]:
    since = resolve_dashboard_since(filters.period)
    order_metrics = dashboard_queries.load_order_metrics(since=since)
    attempt_metrics = dashboard_queries.load_attempt_metrics(since=since)

    closed_attempts = int(attempt_metrics.get("closed_attempts") or 0)
    total_attempts = int(attempt_metrics.get("total_attempts") or 0)
    denominator = closed_attempts if closed_attempts > 0 else total_attempts
    confirmed_attempts = int(attempt_metrics.get("confirmed_attempts") or 0)
    success_rate = round((confirmed_attempts / denominator) * 100, 1) if denominator > 0 else 0.0

    daily_volume = dashboard_queries.list_daily_attempt_volume(since=since)
    max_attempts = max((row["attempt_count"] for row in daily_volume), default=0)
    for row in daily_volume:
        row["attempt_bar_pct"] = round((row["attempt_count"] / max_attempts) * 100, 1) if max_attempts > 0 else 0.0

    recent_orders = [build_order_row(row) for row in dashboard_queries.list_recent_orders(since=since)]

    return {
        "period": filters.period,
        "cards": [
            {
                "label": "Tổng đơn hàng",
                "value": f"{order_metrics['total_orders']:,}",
                "tone": "primary",
                "hint": "Số đơn phát sinh trong khoảng thời gian đang xem.",
            },
            {
                "label": "Đã thanh toán",
                "value": f"{order_metrics['paid_orders']:,}",
                "tone": "success",
                "hint": "Đơn đã được xác nhận thanh toán thành công.",
            },
            {
                "label": "Đang chờ",
                "value": f"{order_metrics['pending_orders']:,}",
                "tone": "warning",
                "hint": "Đơn đang chờ người dùng thanh toán hoặc chờ provider xác nhận.",
            },
            {
                "label": "Thất bại / Hết hạn",
                "value": f"{order_metrics['failed_orders']:,}",
                "tone": "danger",
                "hint": "Các đơn có vấn đề cần được kiểm tra sớm.",
            },
            {
                "label": "Cần kiểm tra",
                "value": f"{order_metrics['review_orders']:,}",
                "tone": "warning",
                "hint": "Đơn đã vào nhóm cần đối soát thủ công.",
            },
            {
                "label": "Doanh thu",
                "value": format_minor_amount(order_metrics["total_revenue_minor"]),
                "tone": "success",
                "hint": "Chỉ tính các đơn đang ở trạng thái đã thanh toán.",
            },
            {
                "label": "Tỷ lệ thành công",
                "value": f"{success_rate:.1f}%",
                "tone": "primary",
                "hint": "Tỷ lệ giao dịch confirmed trên tổng giao dịch đã đóng.",
            },
            {
                "label": "Hoàn tiền",
                "value": f"{order_metrics['refunded_orders']:,}",
                "tone": "secondary",
                "hint": "Các đơn đã được đánh dấu hoàn tiền.",
            },
        ],
        "order_metrics": order_metrics,
        "attempt_metrics": attempt_metrics,
        "order_status_distribution": dashboard_queries.list_order_status_distribution(since=since),
        "attempt_status_distribution": dashboard_queries.list_attempt_status_distribution(since=since),
        "provider_breakdown": dashboard_queries.list_provider_breakdown(since=since),
        "daily_volume": daily_volume,
        "recent_orders": recent_orders,
        "recent_abnormal_attempts": list_recent_abnormal_attempts(limit=8, since=since),
        "recent_webhook_failures": list_recent_webhook_failures(limit=8, since=since),
    }
