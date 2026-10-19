"""Order and attempt user-facing status lines, instructions, and action displays."""

from __future__ import annotations

from typing import Any

from app.services.payment.base import (
    _clean_text,
    _iso,
    _order_is_support_donation,
    _product_title_from_order,
)
from models.payment_attempt import PaymentAttempt
from models.payment_order import PaymentOrder


def _attempt_status_display(attempt: PaymentAttempt) -> dict[str, str]:
    status = _clean_text(attempt.status).lower()
    if status == "confirmed":
        return {
            "code": status,
            "label": "Đã xác nhận",
            "description": "PayOS đã xác nhận thanh toán thành công cho lượt thanh toán này.",
        }
    if status == "manual_review":
        return {
            "code": status,
            "label": "Cần kiểm tra",
            "description": _clean_text(attempt.manual_review_reason)
            or "Thanh toán đã được ghi nhận nhưng chưa thể đối soát tự động.",
        }
    if status == "expired":
        return {
            "code": status,
            "label": "Đã hết hạn",
            "description": _clean_text(attempt.failure_message) or "Lượt thanh toán này đã quá hạn.",
        }
    if status == "canceled":
        return {
            "code": status,
            "label": "Đã hủy",
            "description": _clean_text(attempt.failure_message) or "Lượt thanh toán đã bị hủy.",
        }
    if status == "failed":
        return {
            "code": status,
            "label": "Thất bại",
            "description": _clean_text(attempt.failure_message) or "Lượt thanh toán này không thành công.",
        }
    return {
        "code": status or "pending",
        "label": "Đang chờ thanh toán",
        "description": "Đơn hàng đã được tạo và đang chờ thanh toán hoặc chờ PayOS xác nhận.",
    }


def _grant_status_display(grant_status: str, *, order: PaymentOrder | None = None) -> dict[str, str]:
    token = _clean_text(grant_status).lower()
    is_support_donation = order is not None and _order_is_support_donation(order)
    if token == "completed":
        return {
            "code": token,
            "label": "\u0110\u00e3 ghi nh\u1eadn" if is_support_donation else "\u0110\u00e3 c\u1ea5p quy\u1ec1n",
            "description": (
                "Kho\u1ea3n \u1ee7ng h\u1ed9 c\u1ee7a b\u1ea1n \u0111\u00e3 \u0111\u01b0\u1ee3c ghi nh\u1eadn th\u00e0nh c\u00f4ng."
                if is_support_donation
                else "B\u1ea1n \u0111\u00e3 nh\u1eadn \u0111\u01b0\u1ee3c quy\u1ec1n truy c\u1eadp cho s\u1ea3n ph\u1ea9m trong \u0111\u01a1n h\u00e0ng n\u00e0y."
            ),
        }
    if token == "failed":
        return {
            "code": token,
            "label": "Ghi nh\u1eadn l\u1ed7i" if is_support_donation else "C\u1ea5p quy\u1ec1n l\u1ed7i",
            "description": (
                "Thanh to\u00e1n c\u00f3 th\u1ec3 \u0111\u00e3 \u0111\u01b0\u1ee3c x\u00e1c nh\u1eadn nh\u01b0ng kho\u1ea3n \u1ee7ng h\u1ed9 ch\u01b0a \u0111\u01b0\u1ee3c ghi nh\u1eadn ho\u00e0n t\u1ea5t."
                if is_support_donation
                else "Thanh to\u00e1n c\u00f3 th\u1ec3 \u0111\u00e3 \u0111\u01b0\u1ee3c x\u00e1c nh\u1eadn nh\u01b0ng h\u1ec7 th\u1ed1ng ch\u01b0a c\u1ea5p quy\u1ec1n ho\u00e0n t\u1ea5t."
            ),
        }
    return {
        "code": token or "pending",
        "label": "Ch\u1edd ghi nh\u1eadn" if is_support_donation else "Ch\u1edd c\u1ea5p quy\u1ec1n",
        "description": (
            "Kho\u1ea3n \u1ee7ng h\u1ed9 \u0111ang ch\u1edd x\u00e1c nh\u1eadn cu\u1ed1i c\u00f9ng t\u1eeb PayOS."
            if is_support_donation
            else "H\u1ec7 th\u1ed1ng ch\u01b0a ho\u00e0n t\u1ea5t b\u01b0\u1edbc c\u1ea5p quy\u1ec1n cho s\u1ea3n ph\u1ea9m sau thanh to\u00e1n."
        ),
    }


def _build_order_status_display(order: PaymentOrder, attempt: PaymentAttempt | None) -> dict[str, str]:
    status = _clean_text(order.status).lower()
    grant_status = _clean_text(order.grant_status).lower()
    if _order_is_support_donation(order):
        if status == "paid" and grant_status == "completed":
            return {
                "code": status,
                "tone": "success",
                "label": "Thanh to\u00e1n th\u00e0nh c\u00f4ng",
                "headline": "C\u1ea3m \u01a1n b\u1ea1n \u0111\u00e3 \u1ee7ng h\u1ed9 Flama.",
                "description": "Kho\u1ea3n \u0111\u00f3ng g\u00f3p c\u1ee7a b\u1ea1n \u0111\u00e3 \u0111\u01b0\u1ee3c ghi nh\u1eadn th\u00e0nh c\u00f4ng. S\u1ef1 \u0111\u1ed3ng h\u00e0nh c\u1ee7a b\u1ea1n l\u00e0 ngu\u1ed3n \u0111\u1ed9ng l\u1ef1c r\u1ea5t l\u1edbn \u0111\u1ec3 ch\u00fang t\u00f4i ti\u1ebfp t\u1ee5c ph\u00e1t tri\u1ec3n c\u1ed9ng \u0111\u1ed3ng.",
            }
        if status == "paid":
            return {
                "code": status,
                "tone": "warning",
                "label": "\u0110\u00e3 thanh to\u00e1n",
                "headline": "Ch\u00fang t\u00f4i \u0111\u00e3 nh\u1eadn \u0111\u01b0\u1ee3c thanh to\u00e1n c\u1ee7a b\u1ea1n.",
                "description": "H\u1ec7 th\u1ed1ng \u0111ang ho\u00e0n t\u1ea5t b\u01b0\u1edbc ghi nh\u1eadn kho\u1ea3n \u1ee7ng h\u1ed9 n\u00e0y. B\u1ea1n kh\u00f4ng c\u1ea7n thanh to\u00e1n l\u1ea1i.",
            }
        if status == "under_review":
            reason = _clean_text(attempt.manual_review_reason if attempt is not None else "")
            return {
                "code": status,
                "tone": "warning",
                "label": "C\u1ea7n ki\u1ec3m tra th\u1ee7 c\u00f4ng",
                "headline": "Giao d\u1ecbch c\u1ea7n \u0111\u01b0\u1ee3c ki\u1ec3m tra th\u00eam.",
                "description": reason or "Ch\u00fang t\u00f4i \u0111\u00e3 nh\u1eadn \u0111\u01b0\u1ee3c t\u00edn hi\u1ec7u thanh to\u00e1n nh\u01b0ng c\u1ea7n ki\u1ec3m tra th\u00eam tr\u01b0\u1edbc khi x\u00e1c nh\u1eadn kho\u1ea3n \u1ee7ng h\u1ed9 n\u00e0y.",
            }
        if status == "expired":
            return {
                "code": status,
                "tone": "secondary",
                "label": "Phi\u00ean \u0111\u00e3 h\u1ebft h\u1ea1n",
                "headline": "Phi\u00ean thanh to\u00e1n \u0111\u00e3 h\u1ebft h\u1ea1n.",
                "description": "B\u1ea1n c\u00f3 th\u1ec3 t\u1ea1o m\u1ed9t phi\u00ean m\u1edbi b\u1ea5t c\u1ee9 l\u00fac n\u00e0o n\u1ebfu v\u1eabn mu\u1ed1n ti\u1ebfp t\u1ee5c \u1ee7ng h\u1ed9.",
            }
        if status == "canceled":
            return {
                "code": status,
                "tone": "secondary",
                "label": "\u0110\u00e3 h\u1ee7y",
                "headline": "Phi\u00ean \u1ee7ng h\u1ed9 \u0111\u00e3 \u0111\u01b0\u1ee3c d\u1eebng.",
                "description": "Khi thu\u1eadn ti\u1ec7n, b\u1ea1n c\u00f3 th\u1ec3 b\u1eaft \u0111\u1ea7u l\u1ea1i b\u1eb1ng m\u1ed9t phi\u00ean m\u1edbi.",
            }
        if status == "failed":
            reason = _clean_text((attempt.failure_message if attempt is not None else "") or "")
            return {
                "code": status,
                "tone": "danger",
                "label": "Thanh to\u00e1n th\u1ea5t b\u1ea1i",
                "headline": "R\u1ea5t ti\u1ebfc, giao d\u1ecbch ch\u01b0a ho\u00e0n t\u1ea5t.",
                "description": reason or "Kho\u1ea3n \u1ee7ng h\u1ed9 n\u00e0y ch\u01b0a \u0111\u01b0\u1ee3c ghi nh\u1eadn. B\u1ea1n c\u00f3 th\u1ec3 th\u1eed l\u1ea1i b\u1eb1ng m\u1ed9t phi\u00ean m\u1edbi khi s\u1eb5n s\u00e0ng.",
            }
        if status == "refunded":
            return {
                "code": status,
                "tone": "secondary",
                "label": "\u0110\u00e3 ho\u00e0n ti\u1ec1n",
                "headline": "Kho\u1ea3n \u1ee7ng h\u1ed9 \u0111\u00e3 \u0111\u01b0\u1ee3c ho\u00e0n ti\u1ec1n.",
                "description": "N\u1ebfu \u0111\u00e2y kh\u00f4ng ph\u1ea3i giao d\u1ecbch b\u1ea1n mong mu\u1ed1n, h\u00e3y li\u00ean h\u1ec7 v\u1edbi ch\u00fang t\u00f4i \u0111\u1ec3 \u0111\u01b0\u1ee3c h\u1ed7 tr\u1ee3.",
            }
        return {
            "code": status or "pending_payment",
            "tone": "info",
            "label": "\u0110ang ch\u1edd thanh to\u00e1n",
            "headline": "Phi\u00ean \u1ee7ng h\u1ed9 \u0111\u00e3 s\u1eb5n s\u00e0ng.",
            "description": "Sau khi ho\u00e0n t\u1ea5t thanh to\u00e1n, h\u1ec7 th\u1ed1ng s\u1ebd c\u1eadp nh\u1eadt k\u1ebft qu\u1ea3 m\u1edbi nh\u1ea5t cho b\u1ea1n t\u1ea1i \u0111\u00e2y.",
        }
    if status == "paid" and grant_status == "completed":
        return {
            "code": status,
            "tone": "success",
            "label": "Thanh toán thành công",
            "headline": "Đơn hàng đã được thanh toán và cấp quyền thành công.",
            "description": "Bạn có thể sử dụng ngay sản phẩm vừa mua mà không cần thao tác thêm.",
        }
    if status == "paid":
        return {
            "code": status,
            "tone": "warning",
            "label": "Đã thanh toán",
            "headline": "Thanh toán đã được xác nhận nhưng cấp quyền chưa hoàn tất.",
            "description": "Hệ thống đang xử lý bước cấp quyền cho sản phẩm. Không cần thanh toán lại.",
        }
    if status == "under_review":
        reason = _clean_text(attempt.manual_review_reason if attempt is not None else "")
        return {
            "code": status,
            "tone": "warning",
            "label": "Cần kiểm tra thủ công",
            "headline": "Đơn hàng cần được kiểm tra thêm trước khi cấp quyền.",
            "description": reason or "Thanh toán đã được ghi nhận nhưng chưa thể đối soát tự động.",
        }
    if status == "expired":
        return {
            "code": status,
            "tone": "secondary",
            "label": "Đơn đã hết hạn",
            "headline": "Đơn hàng này không còn hiệu lực để thanh toán tự động.",
            "description": "Nếu bạn vẫn muốn mua, hãy tạo đơn mới. Không nên chuyển tiền vào đơn đã hết hạn.",
        }
    if status == "canceled":
        return {
            "code": status,
            "tone": "secondary",
            "label": "Đơn đã hủy",
            "headline": "Đơn hàng đã được hủy.",
            "description": "Đơn này sẽ không tiếp tục xử lý thanh toán hoặc cấp quyền.",
        }
    if status == "failed":
        reason = _clean_text((attempt.failure_message if attempt is not None else "") or "")
        return {
            "code": status,
            "tone": "danger",
            "label": "Thanh toán thất bại",
            "headline": "Đơn hàng không thể xác nhận thanh toán thành công.",
            "description": reason or "PayOS không trả về trạng thái thanh toán thành công cho đơn này.",
        }
    if status == "refunded":
        return {
            "code": status,
            "tone": "secondary",
            "label": "Đã hoàn tiền",
            "headline": "Đơn hàng đã được hoàn tiền.",
            "description": "Quyền truy cập liên quan đến đơn này có thể đã bị thu hồi hoặc sẽ được xử lý riêng.",
        }
    return {
        "code": status or "pending_payment",
        "tone": "info",
        "label": "Đang chờ thanh toán",
        "headline": "Đơn hàng đã được tạo và đang chờ PayOS xác nhận.",
        "description": "Sau khi thanh toán đúng thông tin, hệ thống sẽ tự động cấp quyền khi PayOS gửi xác nhận.",
    }


def _build_order_next_action(order: PaymentOrder, attempt: PaymentAttempt | None) -> str:
    status = _clean_text(order.status).lower()
    grant_status = _clean_text(order.grant_status).lower()
    if _order_is_support_donation(order):
        if status == "pending_payment":
            if attempt is not None and attempt.checkout_url:
                if attempt.expires_at is not None:
                    return "M\u1edf l\u1ea1i trang thanh to\u00e1n v\u00e0 ho\u00e0n t\u1ea5t tr\u01b0\u1edbc khi phi\u00ean h\u1ebft h\u1ea1n."
                return "M\u1edf l\u1ea1i trang thanh to\u00e1n \u0111\u1ec3 ho\u00e0n t\u1ea5t kho\u1ea3n \u1ee7ng h\u1ed9 n\u00e0y."
            return "T\u1ea1o l\u1ea1i m\u1ed9t phi\u00ean m\u1edbi n\u1ebfu b\u1ea1n ch\u01b0a th\u1ea5y li\u00ean k\u1ebft thanh to\u00e1n."
        if status == "under_review":
            return "Kh\u00f4ng thanh to\u00e1n l\u1ea1i ngay. N\u1ebfu ti\u1ec1n \u0111\u00e3 b\u1ecb tr\u1eeb, h\u00e3y gi\u1eef l\u1ea1i bi\u00ean nh\u1eadn v\u00e0 li\u00ean h\u1ec7 v\u1edbi ch\u00fang t\u00f4i \u0111\u1ec3 ki\u1ec3m tra."
        if status == "paid" and grant_status != "completed":
            return "B\u1ea1n kh\u00f4ng c\u1ea7n thanh to\u00e1n l\u1ea1i. H\u1ec7 th\u1ed1ng \u0111ang ho\u00e0n t\u1ea5t ghi nh\u1eadn kho\u1ea3n \u1ee7ng h\u1ed9 n\u00e0y."
        if status == "expired":
            return "T\u1ea1o m\u1ed9t phi\u00ean \u1ee7ng h\u1ed9 m\u1edbi khi b\u1ea1n s\u1eb5n s\u00e0ng ti\u1ebfp t\u1ee5c."
        if status in {"failed", "canceled"}:
            return "B\u1ea1n c\u00f3 th\u1ec3 b\u1eaft \u0111\u1ea7u l\u1ea1i b\u1eb1ng m\u1ed9t phi\u00ean m\u1edbi ngay tr\u00ean trang n\u00e0y."
        if status == "paid":
            return "C\u1ea3m \u01a1n b\u1ea1n \u0111\u00e3 \u0111\u1ed3ng h\u00e0nh c\u00f9ng Flama."
        return "Ho\u00e0n t\u1ea5t thanh to\u00e1n r\u1ed3i quay l\u1ea1i \u0111\u00e2y \u0111\u1ec3 xem k\u1ebft qu\u1ea3 m\u1edbi nh\u1ea5t."
    if status == "pending_payment":
        if attempt is not None and attempt.checkout_url:
            if attempt.expires_at is not None:
                return "Mở lại liên kết PayOS hoặc thanh toán đúng thông tin trước thời điểm hết hạn của đơn."
            return "Mở lại liên kết PayOS và thanh toán đúng số tiền cùng nội dung chuyển khoản đã hiển thị."
        return "Tạo lại đơn hoặc liên hệ hỗ trợ nếu bạn không thấy liên kết thanh toán hợp lệ."
    if status == "under_review":
        return "Không thanh toán lại ngay. Nếu tiền đã bị trừ, hãy liên hệ hỗ trợ và gửi kèm mã đơn hàng để đối soát."
    if status == "paid" and grant_status != "completed":
        return "Không cần thanh toán lại. Hãy chờ hệ thống hoàn tất bước cấp quyền hoặc liên hệ hỗ trợ nếu chậm bất thường."
    if status == "expired":
        return "Tạo một đơn hàng mới nếu bạn vẫn muốn mua sản phẩm này."
    if status == "failed":
        return "Kiểm tra lại thông tin thanh toán rồi tạo đơn mới. Nếu đã bị trừ tiền, hãy liên hệ hỗ trợ."
    if status == "canceled":
        return "Tạo đơn mới nếu bạn muốn tiếp tục mua sản phẩm."
    if status == "paid":
        return "Bạn có thể quay lại trang chi tiết sản phẩm và sử dụng ngay nội dung đã mua."
    return "Theo dõi trạng thái đơn hàng trên trang này cho đến khi PayOS gửi xác nhận cuối cùng."


def _build_order_instructions(order: PaymentOrder, attempt: PaymentAttempt | None) -> list[str]:
    status = _clean_text(order.status).lower()
    is_support_donation = _order_is_support_donation(order)
    instructions: list[str] = []
    if status == "pending_payment":
        instructions.append(
            "Thanh toán đúng số tiền của phiên hiện tại."
            if is_support_donation
            else "Thanh toán đúng số tiền của đơn hàng."
        )
        instructions.append("Giữ nguyên nội dung chuyển khoản để hệ thống đối soát tự động.")
        if attempt is not None and attempt.expires_at is not None:
            instructions.append(
                "Hoàn tất thanh toán trước thời điểm hết hạn để tránh phiên tự đóng."
                if is_support_donation
                else "Hoàn tất thanh toán trước thời điểm hết hạn để tránh đơn tự đóng."
            )
        if attempt is not None and attempt.checkout_url:
            instructions.append(
                "Nếu đã rời trang thanh toán, bạn có thể mở lại liên kết PayOS bất cứ lúc nào."
                if is_support_donation
                else "Nếu đã rời trang thanh toán, bạn có thể mở lại liên kết PayOS tại màn hình kết quả đơn hàng."
            )
        return instructions
    if status == "under_review":
        return [
            "Không thanh toán lại ngay để tránh bị trừ tiền nhiều lần.",
            "Giữ lại ảnh chụp giao dịch hoặc mã tham chiếu nếu ngân hàng đã báo trừ tiền.",
            "Liên hệ hỗ trợ và cung cấp mã đơn hoặc mã phiên để được kiểm tra thủ công nhanh hơn.",
        ]
    if status == "expired":
        return [
            "Phiên cũ đã hết hạn nên không nên tiếp tục chuyển tiền vào thông tin cũ."
            if is_support_donation
            else "Đơn đã hết hạn nên không nên tiếp tục chuyển tiền vào thông tin cũ.",
            "Tạo phiên mới nếu bạn vẫn muốn tiếp tục."
            if is_support_donation
            else "Tạo đơn mới nếu bạn vẫn muốn mua sản phẩm.",
        ]
    if status == "failed":
        return [
            "Kiểm tra lại trạng thái giao dịch trên PayOS hoặc ứng dụng ngân hàng trước khi thử lại.",
            "Nếu tiền đã bị trừ nhưng trạng thái vẫn thất bại, hãy liên hệ hỗ trợ kèm mã phiên hoặc mã đơn."
            if is_support_donation
            else "Nếu tiền đã bị trừ nhưng đơn vẫn báo thất bại, hãy liên hệ hỗ trợ kèm mã đơn hàng.",
        ]
    if status == "paid" and _clean_text(order.grant_status).lower() != "completed":
        return [
            "Không cần thanh toán lại.",
            "Hệ thống đang hoàn tất bước ghi nhận sau thanh toán."
            if is_support_donation
            else "Hệ thống đang hoàn tất bước cấp quyền sau thanh toán.",
        ]
    if status == "paid" and is_support_donation:
        return [
            "Cảm ơn bạn đã ủng hộ dự án.",
            "Nếu bạn đang đăng nhập và không bật ẩn danh, khoản donate sẽ xuất hiện trong lịch sử đơn hàng.",
        ]
    if status == "paid":
        return [
            "Quyền truy cập đã được cấp tự động.",
            "Nếu chưa thấy sản phẩm khả dụng ngay, hãy tải lại trang chi tiết sản phẩm.",
        ]
    return []


def _build_order_detail_lines(order: PaymentOrder, attempt: PaymentAttempt | None) -> list[dict[str, Any]]:
    is_support_donation = _order_is_support_donation(order)
    lines: list[dict[str, Any]] = [
        {
            "key": "merchant_order_code",
            "label": "M\u00e3 phi\u00ean" if is_support_donation else "Mã đơn hàng",
            "type": "text",
            "value": order.merchant_order_code,
        },
        {
            "key": "product_title",
            "label": "Kho\u1ea3n \u1ee7ng h\u1ed9" if is_support_donation else "Sản phẩm",
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
            "key": "order_status",
            "label": "Trạng thái",
            "type": "status",
            "value": _build_order_status_display(order, attempt)["label"],
        },
        {
            "key": "grant_status",
            "label": "Tr\u1ea1ng th\u00e1i ghi nh\u1eadn" if is_support_donation else "Trạng thái cấp quyền",
            "type": "status",
            "value": _grant_status_display(order.grant_status, order=order)["label"],
        },
    ]
    if attempt is not None:
        lines.append(
            {
                "key": "attempt_status",
                "label": "Trạng thái thanh toán",
                "type": "status",
                "value": _attempt_status_display(attempt)["label"],
            }
        )
        if attempt.expected_payment_reference:
            lines.append(
                {
                    "key": "payment_reference",
                    "label": "Nội dung chuyển khoản",
                    "type": "text",
                    "value": attempt.expected_payment_reference,
                }
            )
        if attempt.checkout_url:
            lines.append(
                {
                    "key": "checkout_url",
                    "label": "Liên kết thanh toán",
                    "type": "url",
                    "value": attempt.checkout_url,
                }
            )
        if attempt.expires_at is not None:
            lines.append(
                {
                    "key": "expires_at",
                    "label": "Hạn thanh toán",
                    "type": "datetime",
                    "value": _iso(attempt.expires_at),
                }
            )
        if attempt.confirmed_at is not None:
            lines.append(
                {
                    "key": "confirmed_at",
                    "label": "Thời điểm xác nhận",
                    "type": "datetime",
                    "value": _iso(attempt.confirmed_at),
                }
            )
    if order.paid_at is not None:
        lines.append(
            {
                "key": "paid_at",
                "label": "Thời điểm thanh toán",
                "type": "datetime",
                "value": _iso(order.paid_at),
            }
        )
    return lines
