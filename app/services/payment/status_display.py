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
    if status in {"confirmed", "success"}:
        return {
            "status": status,
            "code": status,
            "tone": "success",
            "badge_variant": "success",
            "label": "Thanh toán thành công",
            "title": "Thanh toán thành công",
            "headline": "Thanh toán thành công",
            "description": "Giao dịch đã được ghi nhận thành công từ cổng thanh toán.",
        }
    if status in {"pending", "processing", "created"}:
        return {
            "status": status,
            "code": status,
            "tone": "warning",
            "badge_variant": "warning",
            "label": "Đang chờ thanh toán",
            "title": "Đang chờ thanh toán",
            "headline": "Đang chờ thanh toán",
            "description": "Cổng thanh toán đang chờ bạn hoàn tất chuyển khoản/quét QR.",
        }
    if status in {"cancelled", "canceled"}:
        return {
            "status": status,
            "code": status,
            "tone": "secondary",
            "badge_variant": "secondary",
            "label": "Giao dịch đã hủy",
            "title": "Giao dịch đã hủy",
            "headline": "Giao dịch đã hủy",
            "description": "Phiên thanh toán này đã bị hủy hoặc hết hạn.",
        }
    if status in {"failed", "error"}:
        return {
            "status": status,
            "code": status,
            "tone": "danger",
            "badge_variant": "destructive",
            "label": "Thanh toán thất bại",
            "title": "Thanh toán thất bại",
            "headline": "Thanh toán thất bại",
            "description": "Giao dịch không thành công hoặc bị từ chối.",
        }
    if status == "manual_review":
        return {
            "status": status,
            "code": status,
            "tone": "warning",
            "badge_variant": "destructive",
            "label": "Cần kiểm tra",
            "title": "Cần kiểm tra",
            "headline": "Cần kiểm tra",
            "description": "Giao dịch cần được quản trị viên kiểm tra thủ công.",
        }
    if status == "refunded":
        return {
            "status": status,
            "code": status,
            "tone": "secondary",
            "badge_variant": "secondary",
            "label": "Đã hoàn tiền",
            "title": "Đã hoàn tiền",
            "headline": "Đã hoàn tiền",
            "description": "Giao dịch đã được hoàn tiền.",
        }
    return {
        "status": status or "unknown",
        "code": status or "unknown",
        "tone": "secondary",
        "badge_variant": "secondary",
        "label": "Trạng thái giao dịch",
        "title": "Trạng thái giao dịch",
        "headline": "Trạng thái giao dịch",
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
                "code": "completed",
                "grant_status": "completed",
                "label": "Ủng hộ thành công",
                "title": "Ủng hộ thành công",
                "headline": "Ủng hộ thành công",
                "badge_variant": "success",
                "description": "Khoản ủng hộ cho dự án Flama đã được ghi nhận. Cảm ơn bạn rất nhiều!",
            }
        return {
            "code": "completed",
            "grant_status": "completed",
            "label": "Đã cấp quyền truy cập",
            "title": "Đã cấp quyền truy cập",
            "headline": "Đã cấp quyền truy cập",
            "badge_variant": "success",
            "description": f"Bạn đã sở hữu {product_kind} '{product_title}'. Bạn có thể bắt đầu cài đặt và sử dụng ngay bây giờ.",
        }
    if normalized_status == "pending":
        if is_donation:
            return {
                "code": "pending",
                "grant_status": "pending",
                "label": "Chờ ghi nhận ủng hộ",
                "title": "Chờ ghi nhận ủng hộ",
                "headline": "Chờ ghi nhận ủng hộ",
                "badge_variant": "warning",
                "description": "Khoản ủng hộ của bạn đang chờ hệ thống xác nhận thanh toán.",
            }
        return {
            "code": "pending",
            "grant_status": "pending",
            "label": "Đang chờ thanh toán",
            "title": "Đang chờ thanh toán",
            "headline": "Đang chờ thanh toán",
            "badge_variant": "warning",
            "description": f"Hệ thống sẽ tự động cấp quyền truy cập {product_kind} '{product_title}' ngay khi thanh toán hoàn tất.",
        }
    if normalized_status == "manual_review":
        return {
            "code": "manual_review",
            "grant_status": "manual_review",
            "label": "Cần kiểm tra thủ công",
            "title": "Cần kiểm tra thủ công",
            "headline": "Cần kiểm tra thủ công",
            "badge_variant": "destructive",
            "description": "Thanh toán đã được ghi nhận nhưng hệ thống gặp sự cố khi kích hoạt tự động. Quản trị viên đang hỗ trợ xử lý.",
        }
    if normalized_status in {"cancelled", "canceled"}:
        return {
            "code": "cancelled",
            "grant_status": "cancelled",
            "label": "Đơn hàng đã hủy",
            "title": "Đơn hàng đã hủy",
            "headline": "Đơn hàng đã hủy",
            "badge_variant": "secondary",
            "description": "Đơn hàng đã được hủy hoặc hết thời hạn thanh toán.",
        }
    if normalized_status in {"failed", "error"}:
        return {
            "code": "failed",
            "grant_status": "failed",
            "label": "Không thể hoàn tất",
            "title": "Không thể hoàn tất",
            "headline": "Không thể hoàn tất",
            "badge_variant": "destructive",
            "description": "Đơn hàng không thể hoàn tất. Bạn có thể tạo đơn hàng mới để thử lại.",
        }
    return {
        "code": normalized_status or "unknown",
        "grant_status": normalized_status or "unknown",
        "label": "Đang xử lý đơn hàng",
        "title": "Đang xử lý đơn hàng",
        "headline": "Đang xử lý đơn hàng",
        "badge_variant": "secondary",
        "description": "Hệ thống đang cập nhật trạng thái đơn hàng của bạn.",
    }


def _build_order_status_display(order: PaymentOrder, attempt: PaymentAttempt | None) -> dict[str, str]:
    order_status = _clean_text(order.status).lower()
    attempt_status = _clean_text(attempt.status).lower() if attempt else None
    grant_status = _clean_text(order.grant_status).lower()
    is_donation = _order_is_support_donation(order)
    product_title = _product_title_from_order(order)
    product_kind = _product_type_label(order.items[0].product_type) if order.items else "sản phẩm"

    if order_status in {"completed", "paid"} or grant_status == "completed":
        if is_donation:
            return {
                "code": "paid",
                "tone": "success",
                "badge_variant": "success",
                "label": "Ủng hộ thành công",
                "title": "Ủng hộ thành công",
                "headline": "Cảm ơn bạn đã ủng hộ Flama.",
                "description": "Khoản ủng hộ của bạn đã được ghi nhận vào hệ thống. Chân thành cảm ơn sự đồng hành của bạn!",
            }
        return {
            "code": "paid",
            "tone": "success",
            "badge_variant": "success",
            "label": "Thanh toán thành công",
            "title": "Thanh toán thành công",
            "headline": "Thanh toán thành công",
            "description": f"Đơn hàng đã hoàn tất. Quyền truy cập {product_kind} '{product_title}' đã sẵn sàng trong tài khoản của bạn.",
        }

    if grant_status == "manual_review" or order_status == "under_review":
        return {
            "code": "under_review",
            "tone": "warning",
            "badge_variant": "destructive",
            "label": "Cần kiểm tra thủ công",
            "title": "Cần kiểm tra thủ công",
            "headline": "Giao dịch cần được kiểm tra thêm.",
            "description": "Hệ thống đã nhận thanh toán nhưng cần kiểm tra thêm để hoàn tất việc cấp quyền. Bạn vui lòng đợi trong giây lát.",
        }

    if order_status in {"expired", "cancelled", "canceled"}:
        if attempt_status in {"confirmed", "success"}:
            return {
                "code": "under_review",
                "tone": "warning",
                "badge_variant": "warning",
                "label": "Đang xác minh giao dịch",
                "title": "Đang xác minh giao dịch",
                "headline": "Đang xác minh giao dịch",
                "description": "Đơn hàng đã quá hạn trong lúc thanh toán đang được xử lý. Hệ thống đang tiến hành đối soát.",
            }
        is_canceled = order_status in {"cancelled", "canceled"}
        return {
            "code": "canceled" if is_canceled else "expired",
            "tone": "secondary",
            "badge_variant": "secondary",
            "label": "Đã hủy" if is_canceled else "Phiên đã hết hạn",
            "title": "Đã hủy" if is_canceled else "Đơn hàng đã hết hạn",
            "headline": "Phiên thanh toán đã kết thúc.",
            "description": "Đơn hàng đã hết hạn hoặc bị hủy. Bạn có thể mở thanh toán mới bất cứ lúc nào.",
        }

    if attempt_status in {"confirmed", "success"}:
        return {
            "code": "paid",
            "tone": "success",
            "badge_variant": "success",
            "label": "Thanh toán thành công",
            "title": "Thanh toán thành công",
            "headline": "Thanh toán thành công",
            "description": "Đang kích hoạt quyền truy cập vào tài khoản của bạn...",
        }

    if attempt_status in {"failed", "error"}:
        return {
            "code": "failed",
            "tone": "danger",
            "badge_variant": "destructive",
            "label": "Thanh toán thất bại",
            "title": "Thanh toán thất bại",
            "headline": "Rất tiếc, giao dịch chưa hoàn tất.",
            "description": "Giao dịch gần nhất không thành công. Bạn có thể thử lại qua cổng thanh toán.",
        }

    return {
        "code": "pending_payment",
        "tone": "warning",
        "badge_variant": "warning",
        "label": "Đang chờ thanh toán",
        "title": "Đang chờ thanh toán",
        "headline": "Vui lòng hoàn tất thanh toán",
        "description": "Vui lòng quét mã QR hoặc chuyển khoản chính xác nội dung hiển thị bên dưới.",
    }


def _build_order_next_action(order: PaymentOrder, attempt: PaymentAttempt | None) -> str:
    order_status = _clean_text(order.status).lower()
    attempt_status = _clean_text(attempt.status).lower() if attempt else None
    grant_status = _clean_text(order.grant_status).lower()
    is_donation = _order_is_support_donation(order)

    if order_status in {"completed", "paid"} or grant_status == "completed":
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

    if order_status in {"completed", "paid"} or grant_status == "completed":
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
    is_donation = _order_is_support_donation(order)
    lines: list[dict[str, Any]] = [
        {
            "key": "merchant_order_code",
            "label": "Mã phiên" if is_donation else "Mã đơn hàng",
            "type": "text",
            "value": order.merchant_order_code or order.id,
            "copyable": True,
        },
        {
            "key": "product_title",
            "label": "Khoản ủng hộ" if is_donation else "Sản phẩm",
            "type": "text",
            "value": _product_title_from_order(order),
        },
        {
            "key": "total_amount_minor",
            "label": "Tổng thanh toán",
            "type": "amount_minor",
            "value_minor": int(order.total_amount_minor or 0),
            "currency_code": order.currency_code or "VND",
        },
        {
            "key": "created_at",
            "label": "Thời gian tạo",
            "type": "datetime",
            "value": _iso(order.created_at),
        },
    ]

    expires_at = getattr(attempt, "expires_at", None)
    if expires_at:
        lines.append({
            "key": "expires_at",
            "label": "Hạn thanh toán",
            "type": "datetime",
            "value": _iso(expires_at),
        })

    provider_payment_id = getattr(attempt, "provider_payment_id", None)
    if provider_payment_id:
        lines.append({
            "key": "provider_payment_id",
            "label": "Mã giao dịch PayOS",
            "type": "text",
            "value": provider_payment_id,
            "copyable": True,
        })

    return lines
