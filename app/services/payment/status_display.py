"""Order and attempt user-facing status lines, instructions, and action displays."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flask import current_app
from sqlalchemy import and_, asc, desc, func, or_

from app.services import support_donation_service
from app.services.payment.base import (
    PaymentServiceError,
    _clean_text,
    _iso,
    _order_is_support_donation,
    _product_title_from_order,
    _product_type_label,
    _utcnow,
)
from models.payment_attempt import PaymentAttempt
from models.payment_order import PaymentOrder

logger = logging.getLogger(__name__)


def _attempt_status_display(attempt: PaymentAttempt) -> dict[str, str]:
    status = _clean_text(attempt.status).lower()
    if status == "success":
        return {
            "status": "success",
            "badge_variant": "success",
            "title": "Thanh toán thành công",
            "description": "Giao dịch đã được ghi nhận thành công từ cổng thanh toán.",
        }
    if status in {"pending", "processing"}:
        return {
            "status": "pending",
            "badge_variant": "warning",
            "title": "Đang chờ thanh toán",
            "description": "Cổng thanh toán đang chờ bạn hoàn tất chuyển khoản/quét QR.",
        }
    if status in {"cancelled", "canceled"}:
        return {
            "status": "cancelled",
            "badge_variant": "secondary",
            "title": "Giao dịch đã hủy",
            "description": "Phiên thanh toán này đã bị hủy hoặc hết hạn.",
        }
    if status in {"failed", "error"}:
        return {
            "status": "failed",
            "badge_variant": "destructive",
            "title": "Thanh toán thất bại",
            "description": "Giao dịch không thành công hoặc bị từ chối.",
        }
    return {
        "status": status or "unknown",
        "badge_variant": "secondary",
        "title": "Trạng thái giao dịch",
        "description": "Đang cập nhật trạng thái từ cổng thanh toán.",
    }


def _grant_status_display(grant_status: str, *, order: PaymentOrder | None = None) -> dict[str, str]:
    normalized_status = _clean_text(grant_status).lower()
    is_donation = bool(order and _order_is_support_donation(order))
    product_title = _product_title_from_order(order) if order else "sản phẩm"
    product_kind = _product_type_label(order.items[0].product_type) if order and order.items else "sản phẩm"

    if normalized_status == "completed":
        if is_donation:
            return {
                "grant_status": "completed",
                "badge_variant": "success",
                "title": "Ủng hộ thành công",
                "description": f"Khoản ủng hộ cho dự án Flama đã được ghi nhận. Cảm ơn bạn rất nhiều!",
            }
        return {
            "grant_status": "completed",
            "badge_variant": "success",
            "title": "Đã cấp quyền truy cập",
            "description": f"Bạn đã sở hữu {product_kind} '{product_title}'. Bạn có thể bắt đầu cài đặt và sử dụng ngay bây giờ.",
        }
    if normalized_status == "pending":
        if is_donation:
            return {
                "grant_status": "pending",
                "badge_variant": "warning",
                "title": "Chờ ghi nhận ủng hộ",
                "description": "Khoản ủng hộ của bạn đang chờ hệ thống xác nhận thanh toán.",
            }
        return {
            "grant_status": "pending",
            "badge_variant": "warning",
            "title": "Đang chờ thanh toán",
            "description": f"Hệ thống sẽ tự động cấp quyền truy cập {product_kind} '{product_title}' ngay khi thanh toán hoàn tất.",
        }
    if normalized_status == "manual_review":
        return {
            "grant_status": "manual_review",
            "badge_variant": "destructive",
            "title": "Cần kiểm tra thủ công",
            "description": "Thanh toán đã được ghi nhận nhưng hệ thống gặp sự cố khi kích hoạt tự động. Quản trị viên đang hỗ trợ xử lý.",
        }
    if normalized_status in {"cancelled", "canceled"}:
        return {
            "grant_status": "cancelled",
            "badge_variant": "secondary",
            "title": "Đơn hàng đã hủy",
            "description": "Đơn hàng đã được hủy hoặc hết thời hạn thanh toán.",
        }
    if normalized_status in {"failed", "error"}:
        return {
            "grant_status": "failed",
            "badge_variant": "destructive",
            "title": "Không thể hoàn tất",
            "description": "Đơn hàng không thể hoàn tất. Bạn có thể tạo đơn hàng mới để thử lại.",
        }
    return {
        "grant_status": normalized_status or "unknown",
        "badge_variant": "secondary",
        "title": "Đang xử lý đơn hàng",
        "description": "Hệ thống đang cập nhật trạng thái đơn hàng của bạn.",
    }


def _build_order_status_display(order: PaymentOrder, attempt: PaymentAttempt | None) -> dict[str, str]:
    order_status = _clean_text(order.status).lower()
    attempt_status = _clean_text(attempt.status).lower() if attempt else None
    grant_status = _clean_text(order.grant_status).lower()
    is_donation = _order_is_support_donation(order)
    product_title = _product_title_from_order(order)
    product_kind = _product_type_label(order.items[0].product_type) if order.items else "sản phẩm"

    if order_status == "completed" or grant_status == "completed":
        if is_donation:
            return {
                "badge_variant": "success",
                "title": "Ủng hộ thành công",
                "description": "Khoản ủng hộ của bạn đã được ghi nhận vào hệ thống. Chân thành cảm ơn sự đồng hành của bạn!",
            }
        return {
            "badge_variant": "success",
            "title": "Thanh toán thành công",
            "description": f"Đơn hàng đã hoàn tất. Quyền truy cập {product_kind} '{product_title}' đã sẵn sàng trong tài khoản của bạn.",
        }

    if grant_status == "manual_review":
        return {
            "badge_variant": "destructive",
            "title": "Cần kiểm tra thủ công",
            "description": "Hệ thống đã nhận thanh toán nhưng cần kiểm tra thêm để hoàn tất việc cấp quyền. Bạn vui lòng đợi trong giây lát.",
        }

    if order_status in {"expired", "cancelled", "canceled"}:
        if attempt_status == "success":
            return {
                "badge_variant": "warning",
                "title": "Đang xác minh giao dịch",
                "description": "Đơn hàng đã quá hạn trong lúc thanh toán đang được xử lý. Hệ thống đang tiến hành đối soát.",
            }
        return {
            "badge_variant": "secondary",
            "title": "Đơn hàng đã kết thúc",
            "description": "Đơn hàng đã hết hạn hoặc bị hủy. Bạn có thể mở thanh toán mới bất cứ lúc nào.",
        }

    if attempt_status == "success":
        return {
            "badge_variant": "success",
            "title": "Thanh toán thành công",
            "description": "Đang kích hoạt quyền truy cập vào tài khoản của bạn...",
        }

    if attempt_status in {"failed", "error"}:
        return {
            "badge_variant": "destructive",
            "title": "Thanh toán thất bại",
            "description": "Giao dịch gần nhất không thành công. Bạn có thể thử lại qua cổng thanh toán.",
        }

    return {
        "badge_variant": "warning",
        "title": "Đang chờ thanh toán",
        "description": "Vui lòng quét mã QR hoặc chuyển khoản chính xác nội dung hiển thị bên dưới.",
    }


def _build_order_next_action(order: PaymentOrder, attempt: PaymentAttempt | None) -> str:
    order_status = _clean_text(order.status).lower()
    attempt_status = _clean_text(attempt.status).lower() if attempt else None
    grant_status = _clean_text(order.grant_status).lower()
    is_donation = _order_is_support_donation(order)

    if order_status == "completed" or grant_status == "completed":
        return "view_donations" if is_donation else "open_deck"

    if grant_status == "manual_review":
        return "contact_support"

    if order_status in {"expired", "cancelled", "canceled"}:
        return "retry_checkout"

    if attempt and attempt.checkout_url and attempt_status in {"pending", "processing"}:
        return "pay_with_payos"

    return "retry_checkout"


def _build_order_instructions(order: PaymentOrder, attempt: PaymentAttempt | None) -> list[str]:
    is_donation = _order_is_support_donation(order)
    order_status = _clean_text(order.status).lower()
    grant_status = _clean_text(order.grant_status).lower()

    if order_status == "completed" or grant_status == "completed":
        if is_donation:
            return [
                "Giao dịch đã được đối soát thành công.",
                "Bạn có thể xem lại lịch sử ủng hộ bất cứ lúc nào trong trang cá nhân.",
            ]
        return [
            "Đơn hàng đã được kích hoạt thành công.",
            "Bạn có thể vào thư viện để bắt đầu học bộ thẻ hoặc áp dụng mẫu thẻ này.",
        ]

    return [
        "Mở ứng dụng ngân hàng hoặc ví điện tử hỗ trợ VietQR.",
        "Quét mã QR hiển thị trên màn hình hoặc mở trang thanh toán ngân hàng.",
        "Không thay đổi nội dung chuyển khoản để hệ thống tự động nhận diện giao dịch.",
        "Hệ thống sẽ cập nhật trạng thái ngay lập tức khi nhận được tiền.",
    ]


def _build_order_detail_lines(order: PaymentOrder, attempt: PaymentAttempt | None) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    lines.append({
        "label": "Mã đơn hàng",
        "value": order.merchant_order_code or order.id,
        "copyable": True,
    })
    lines.append({
        "label": "Thời gian tạo",
        "value": _iso(order.created_at),
    })
    if order.expires_at:
        lines.append({
            "label": "Hạn thanh toán",
            "value": _iso(order.expires_at),
        })
    if attempt and attempt.provider_payment_link_id:
        lines.append({
            "label": "Mã giao dịch",
            "value": attempt.provider_payment_link_id,
            "copyable": True,
        })
    return lines
