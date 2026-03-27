from __future__ import annotations

from datetime import datetime, timedelta
from secrets import randbelow
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.repositories import payment_repository
from app.services.payment import config as payment_config
from app.services.payment.provider import payos_provider
from app.services import flashcards_share_service
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType
from models.payment_attempt import PaymentAttempt
from models.payment_entitlement import PaymentEntitlement
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.payment_webhook_event import PaymentWebhookEvent


DEFAULT_ORDER_EXPIRY_SECONDS = 30 * 60
DEFAULT_VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}
ACTIVE_ATTEMPT_STATUSES = {"created", "pending"}
TERMINAL_ORDER_STATUSES = {"paid", "expired", "canceled", "failed", "refunded"}
PAYMENT_PROVIDER_CODE = "payos"
PAYMENT_METHOD_CODE = "payos_checkout"
PAYOS_PROVIDER_REUSABLE_STATUSES = {"PENDING", "PROCESSING"}


class PaymentServiceError(Exception):
    def __init__(
        self,
        error: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.status = status
        self.field = field


def payments_enabled() -> bool:
    return payment_config.payments_enabled()


def paid_install_interception_enabled() -> bool:
    return payment_config.paid_install_interception_enabled()


def webhook_auto_grant_enabled() -> bool:
    return payment_config.webhook_auto_grant_enabled()


def _utcnow() -> datetime:
    return datetime.utcnow()


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _product_type_label(product_type: str) -> str:
    return {
        "note_type": "template",
        "deck_marketplace_item": "deck",
    }.get(_clean_text(product_type), "sản phẩm")


def _product_title_from_order(order: PaymentOrder) -> str:
    if not order.items:
        return "Sản phẩm"
    titles = [_clean_text(item.title_snapshot) or _product_type_label(item.product_type) for item in order.items]
    if len(titles) == 1:
        return titles[0]
    return f"{titles[0]} và {len(titles) - 1} mục khác"


def _grant_status_display(grant_status: str) -> dict[str, str]:
    token = _clean_text(grant_status).lower()
    if token == "completed":
        return {
            "code": token,
            "label": "Đã cấp quyền",
            "description": "Bạn đã nhận được quyền truy cập cho sản phẩm trong đơn hàng này.",
        }
    if token == "failed":
        return {
            "code": token,
            "label": "Cấp quyền lỗi",
            "description": "Thanh toán có thể đã được xác nhận nhưng hệ thống chưa cấp quyền hoàn tất.",
        }
    return {
        "code": token or "pending",
        "label": "Chờ cấp quyền",
        "description": "Hệ thống chưa hoàn tất bước cấp quyền cho sản phẩm sau thanh toán.",
    }


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


def _build_order_status_display(order: PaymentOrder, attempt: PaymentAttempt | None) -> dict[str, str]:
    status = _clean_text(order.status).lower()
    grant_status = _clean_text(order.grant_status).lower()
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
    instructions: list[str] = []
    if status == "pending_payment":
        instructions.append("Thanh toán đúng số tiền của đơn hàng.")
        instructions.append("Giữ nguyên nội dung chuyển khoản để hệ thống đối soát tự động.")
        if attempt is not None and attempt.expires_at is not None:
            instructions.append("Hoàn tất thanh toán trước thời điểm hết hạn để tránh đơn tự đóng.")
        if attempt is not None and attempt.checkout_url:
            instructions.append("Nếu đã rời trang thanh toán, bạn có thể mở lại liên kết PayOS tại màn hình kết quả đơn hàng.")
        return instructions
    if status == "under_review":
        return [
            "Không thanh toán lại ngay để tránh bị trừ tiền nhiều lần.",
            "Giữ lại ảnh chụp giao dịch hoặc mã tham chiếu nếu ngân hàng đã báo trừ tiền.",
            "Liên hệ hỗ trợ và cung cấp mã đơn hàng để được kiểm tra thủ công nhanh hơn.",
        ]
    if status == "expired":
        return [
            "Đơn đã hết hạn nên không nên tiếp tục chuyển tiền vào thông tin cũ.",
            "Tạo đơn mới nếu bạn vẫn muốn mua sản phẩm.",
        ]
    if status == "failed":
        return [
            "Kiểm tra lại trạng thái giao dịch trên PayOS hoặc ứng dụng ngân hàng trước khi thử lại.",
            "Nếu tiền đã bị trừ nhưng đơn vẫn báo thất bại, hãy liên hệ hỗ trợ kèm mã đơn hàng.",
        ]
    if status == "paid" and _clean_text(order.grant_status).lower() != "completed":
        return [
            "Không cần thanh toán lại.",
            "Hệ thống đang hoàn tất bước cấp quyền sau thanh toán.",
        ]
    if status == "paid":
        return [
            "Quyền truy cập đã được cấp tự động.",
            "Nếu chưa thấy sản phẩm khả dụng ngay, hãy tải lại trang chi tiết sản phẩm.",
        ]
    return []


def _build_order_detail_lines(order: PaymentOrder, attempt: PaymentAttempt | None) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = [
        {
            "key": "merchant_order_code",
            "label": "Mã đơn hàng",
            "type": "text",
            "value": order.merchant_order_code,
        },
        {
            "key": "product_title",
            "label": "Sản phẩm",
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
            "label": "Trạng thái đơn",
            "type": "status",
            "value": _build_order_status_display(order, attempt)["label"],
        },
        {
            "key": "grant_status",
            "label": "Trạng thái cấp quyền",
            "type": "status",
            "value": _grant_status_display(order.grant_status)["label"],
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


def _require_payments_enabled() -> None:
    if not payments_enabled():
        raise PaymentServiceError(
            "PAYMENT_UNAVAILABLE",
            "Hệ thống thanh toán đang tạm thời không khả dụng. Vui lòng thử lại sau.",
            status=503,
        )


def _require_supported_provider() -> None:
    provider_code = payment_config.payment_provider_code()
    if provider_code != PAYMENT_PROVIDER_CODE:
        raise PaymentServiceError(
            "PAYMENT_PROVIDER_UNSUPPORTED",
            f"Cổng thanh toán '{provider_code}' hiện chưa được hỗ trợ trong môi trường này.",
            status=503,
        )
    try:
        payos_provider.assert_payos_provider_available()
    except payos_provider.PayOSProviderError as exc:
        raise PaymentServiceError(exc.code, str(exc), status=exc.status) from exc


def _build_merchant_order_code() -> str:
    return f"ORD-{_utcnow():%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}"


def _build_payment_reference() -> str:
    return f"FLAMA{uuid4().hex[:10].upper()}"


def _build_provider_order_code() -> int:
    timestamp_millis = int(time.time() * 1000)
    return int(f"{timestamp_millis}{randbelow(1000):03d}")


def _append_payment_context(url: str, *, order_id: str, product_type: str, product_ref_id: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["payment_order_id"] = order_id
    query["payment_product_type"] = product_type
    query["payment_product_ref_id"] = product_ref_id
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _latest_attempt(order: PaymentOrder) -> PaymentAttempt | None:
    if not order.attempts:
        return None
    return max(order.attempts, key=lambda row: (row.created_at or datetime.min, row.id or ""))


def _maybe_expire_order(order: PaymentOrder, *, now: datetime | None = None) -> bool:
    current_time = now or _utcnow()
    attempt = _latest_attempt(order)
    if attempt is None:
        return False
    if attempt.status not in ACTIVE_ATTEMPT_STATUSES:
        return False
    if attempt.expires_at is None or attempt.expires_at >= current_time:
        return False

    attempt.status = "expired"
    attempt.failed_at = attempt.failed_at or current_time
    attempt.failure_code = attempt.failure_code or "expired"
    attempt.failure_message = attempt.failure_message or "Lượt thanh toán đã hết hạn trước khi PayOS xác nhận thành công."

    other_non_terminal_attempts = any(
        row.id != attempt.id and row.status in ACTIVE_ATTEMPT_STATUSES.union({"manual_review"})
        for row in order.attempts
    )
    if order.status == "pending_payment" and not other_non_terminal_attempts:
        order.status = "expired"
        order.closed_at = current_time
    return True


def _serialize_order_item(item: PaymentOrderItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "product_type": item.product_type,
        "product_ref_id": item.product_ref_id,
        "quantity": int(item.quantity or 0),
        "unit_amount_minor": int(item.unit_amount_minor or 0),
        "line_total_amount_minor": int(item.line_total_amount_minor or 0),
        "title_snapshot": item.title_snapshot,
        "product_snapshot": item.product_snapshot_json or {},
        "created_at": _iso(item.created_at),
    }


def _serialize_attempt(attempt: PaymentAttempt | None) -> dict[str, Any] | None:
    if attempt is None:
        return None
    provider_metadata = attempt.provider_metadata_json or {}
    status_display = _attempt_status_display(attempt)
    return {
        "id": attempt.id,
        "provider_code": attempt.provider_code,
        "payment_method_code": attempt.payment_method_code,
        "status": attempt.status,
        "status_display": status_display,
        "amount_minor": int(attempt.amount_minor or 0),
        "currency_code": attempt.currency_code,
        "provider_payment_id": attempt.provider_payment_id,
        "provider_order_code": attempt.provider_order_code,
        "expected_payment_reference": attempt.expected_payment_reference,
        "checkout_url": attempt.checkout_url,
        "expires_at": _iso(attempt.expires_at),
        "confirmed_at": _iso(attempt.confirmed_at),
        "failed_at": _iso(attempt.failed_at),
        "failure_code": attempt.failure_code,
        "failure_message": attempt.failure_message,
        "manual_review_reason": attempt.manual_review_reason,
        "provider_metadata": provider_metadata,
        "created_at": _iso(attempt.created_at),
        "updated_at": _iso(attempt.updated_at),
        "message": status_display["description"],
        "checkout": {
            "provider": attempt.provider_code,
            "checkout_url": attempt.checkout_url,
            "payment_link_id": attempt.provider_payment_id,
            "provider_order_code": attempt.provider_order_code,
            "bank_bin": provider_metadata.get("bank_bin"),
            "account_no": provider_metadata.get("account_no"),
            "account_name": provider_metadata.get("account_name"),
            "template": provider_metadata.get("template"),
            "qr_code": provider_metadata.get("qr_code"),
            "provider_status": provider_metadata.get("provider_status"),
            "amount_minor": int(attempt.amount_minor or 0),
            "currency_code": attempt.currency_code,
            "payment_reference": attempt.expected_payment_reference,
            "merchant_order_code": provider_metadata.get("merchant_order_code"),
        },
    }


def serialize_order(order: PaymentOrder) -> dict[str, Any]:
    latest_attempt = _latest_attempt(order)
    status_display = _build_order_status_display(order, latest_attempt)
    grant_status_display = _grant_status_display(order.grant_status)
    next_action = _build_order_next_action(order, latest_attempt)
    instructions = _build_order_instructions(order, latest_attempt)
    order_detail_lines = _build_order_detail_lines(order, latest_attempt)
    return {
        "id": order.id,
        "merchant_order_code": order.merchant_order_code,
        "status": order.status,
        "status_display": status_display,
        "grant_status": order.grant_status,
        "grant_status_display": grant_status_display,
        "currency_code": order.currency_code,
        "subtotal_amount_minor": int(order.subtotal_amount_minor or 0),
        "discount_amount_minor": int(order.discount_amount_minor or 0),
        "total_amount_minor": int(order.total_amount_minor or 0),
        "paid_at": _iso(order.paid_at),
        "closed_at": _iso(order.closed_at),
        "created_at": _iso(order.created_at),
        "updated_at": _iso(order.updated_at),
        "message": status_display["description"],
        "headline": status_display["headline"],
        "next_action": next_action,
        "instructions": instructions,
        "order_detail_lines": order_detail_lines,
        "items": [_serialize_order_item(item) for item in order.items],
        "attempts": [_serialize_attempt(attempt) for attempt in order.attempts],
        "active_attempt": _serialize_attempt(latest_attempt),
    }


def _validate_note_type_for_checkout(source_note_type: NoteType, *, user_id: int) -> dict[str, Any]:
    status = str(source_note_type.publish_status or "").strip().lower()
    if status not in DEFAULT_VISIBLE_PUBLISH_STATUSES:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Template này hiện không mở bán hoặc không còn khả dụng để thanh toán.",
            status=409,
        )
    if source_note_type.user_id == user_id:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Bạn không thể mua chính template do mình phát hành.",
            status=409,
        )
    if source_note_type.pricing_mode != "paid" or int(source_note_type.price_amount_minor or 0) <= 0:
        raise PaymentServiceError(
            "PAYMENT_NOT_REQUIRED",
            "Template này hiện không yêu cầu thanh toán.",
            status=409,
        )

    existing = payment_repository.get_note_type_install(
        user_id=user_id,
        source_note_type_id=source_note_type.id,
    )
    return {
        "product_type": "note_type",
        "product_ref_id": source_note_type.id,
        "title_snapshot": source_note_type.name,
        "amount_minor": int(source_note_type.price_amount_minor or 0),
        "product_snapshot": {
            "title": source_note_type.name,
            "pricing_mode": source_note_type.pricing_mode,
            "source_price_amount_minor": int(source_note_type.price_amount_minor or 0),
            "source_price_integer": int(source_note_type.price_amount_minor or 0),
            "version": source_note_type.version,
            "owner_user_id": source_note_type.user_id,
        },
        "existing_access": (
            {
                "already_installed": True,
                "source_note_type_id": source_note_type.id,
                "installed_note_type_id": existing.installed_note_type_id,
            }
            if existing is not None
            else None
        ),
    }


def _validate_deck_item_for_checkout(deck_item: DeckMarketplaceItem, *, user_id: int) -> dict[str, Any]:
    bind_error, _ = flashcards_share_service.sync_deck_item_source_note_type(
        deck_item,
        require_source_note_type=True,
    )
    if bind_error:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            bind_error,
            status=409,
            field="source_note_type_id",
        )

    status = str(deck_item.publish_status or "").strip().lower()
    if status not in DEFAULT_VISIBLE_PUBLISH_STATUSES:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Deck này hiện không mở bán hoặc không còn khả dụng để thanh toán.",
            status=409,
        )
    if deck_item.owner_user_id == user_id:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Bạn không thể mua chính deck do mình phát hành.",
            status=409,
        )
    if deck_item.pricing_mode != "paid" or int(deck_item.price_amount_minor or 0) <= 0:
        raise PaymentServiceError(
            "PAYMENT_NOT_REQUIRED",
            "Deck này hiện không yêu cầu thanh toán.",
            status=409,
        )

    existing = payment_repository.get_deck_install(user_id=user_id, deck_item_id=deck_item.id)
    return {
        "product_type": "deck_marketplace_item",
        "product_ref_id": deck_item.id,
        "title_snapshot": deck_item.title,
        "amount_minor": int(deck_item.price_amount_minor or 0),
        "product_snapshot": {
            "title": deck_item.title,
            "pricing_mode": deck_item.pricing_mode,
            "source_price_amount_minor": int(deck_item.price_amount_minor or 0),
            "source_price_integer": int(deck_item.price_amount_minor or 0),
            "version": deck_item.version,
            "owner_user_id": deck_item.owner_user_id,
            "source_deck_id": deck_item.source_deck_id,
            "source_note_type_id": deck_item.source_note_type_id,
        },
        "existing_access": (
            {
                "already_installed": True,
                "deck_item_id": deck_item.id,
                "installed_deck_id": existing.local_deck_id,
            }
            if existing is not None
            else None
        ),
    }


def _resolve_existing_access_for_product(*, product_type: str, product_ref_id: str, user_id: int) -> dict[str, Any] | None:
    if product_type == "note_type":
        install = payment_repository.get_note_type_install(
            user_id=user_id,
            source_note_type_id=product_ref_id,
        )
        if install is None:
            return None
        return {
            "already_installed": True,
            "source_note_type_id": product_ref_id,
            "installed_note_type_id": install.installed_note_type_id,
        }

    if product_type == "deck_marketplace_item":
        install = payment_repository.get_deck_install(
            user_id=user_id,
            deck_item_id=product_ref_id,
        )
        if install is None:
            return None
        return {
            "already_installed": True,
            "deck_item_id": product_ref_id,
            "installed_deck_id": install.local_deck_id,
        }

    return None


def _load_checkout_context(*, product_type: str, product_ref_id: str, user_id: int) -> dict[str, Any]:
    if product_type == "note_type":
        source_note_type = NoteType.query.get(product_ref_id)
        if source_note_type is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy template cần thanh toán.", status=404)
        context = _validate_note_type_for_checkout(source_note_type, user_id=user_id)
        context["product"] = source_note_type
        return context

    if product_type == "deck_marketplace_item":
        deck_item = DeckMarketplaceItem.query.get(product_ref_id)
        if deck_item is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy deck cần thanh toán.", status=404)
        context = _validate_deck_item_for_checkout(deck_item, user_id=user_id)
        context["product"] = deck_item
        return context

    raise PaymentServiceError(
        "VALIDATION_ERROR",
        "Loại sản phẩm thanh toán không hợp lệ.",
        status=400,
        field="product_type",
    )


def _build_checkout_attempt(
    order: PaymentOrder,
    *,
    amount_minor: int,
    title_snapshot: str,
    product_type: str,
    product_ref_id: str,
    return_url: str,
    cancel_url: str,
    buyer_email: str | None = None,
) -> PaymentAttempt:
    _require_supported_provider()
    if not return_url or not cancel_url:
        raise PaymentServiceError(
            "PAYMENT_RETURN_URL_REQUIRED",
            "Không thể tạo đơn thanh toán vì thiếu liên kết quay lại sau khi rời PayOS.",
            status=400,
        )
    now = _utcnow()
    reference = _build_payment_reference()
    expires_at = now + timedelta(seconds=payment_config.order_expiry_seconds(default=DEFAULT_ORDER_EXPIRY_SECONDS))
    provider_order_code = _build_provider_order_code()
    resolved_return_url = _append_payment_context(
        return_url,
        order_id=order.id,
        product_type=product_type,
        product_ref_id=product_ref_id,
    )
    resolved_cancel_url = _append_payment_context(
        cancel_url,
        order_id=order.id,
        product_type=product_type,
        product_ref_id=product_ref_id,
    )
    try:
        checkout_session = payos_provider.create_checkout_session(
            provider_order_code=provider_order_code,
            amount_minor=int(amount_minor or 0),
            title_snapshot=title_snapshot,
            payment_reference=reference,
            return_url=resolved_return_url,
            cancel_url=resolved_cancel_url,
            expires_at=expires_at,
            buyer_email=buyer_email,
        )
    except payos_provider.PayOSProviderError as exc:
        raise PaymentServiceError(exc.code, str(exc), status=exc.status) from exc
    provider_metadata = dict(checkout_session.get("provider_metadata") or {})
    provider_metadata.update(
        {
            "merchant_order_code": order.merchant_order_code,
            "title_snapshot": title_snapshot,
            "amount_minor": int(amount_minor or 0),
            "currency_code": checkout_session.get("currency_code") or "VND",
            "payment_reference": reference,
            "return_url": resolved_return_url,
            "cancel_url": resolved_cancel_url,
            "provider_raw_response": checkout_session.get("raw_response") or {},
        }
    )
    return PaymentAttempt(
        order_id=order.id,
        provider_code=PAYMENT_PROVIDER_CODE,
        payment_method_code=PAYMENT_METHOD_CODE,
        status="pending",
        amount_minor=int(amount_minor or 0),
        currency_code=str(checkout_session.get("currency_code") or "VND"),
        provider_payment_id=str(checkout_session.get("provider_payment_id") or "") or None,
        provider_order_code=str(checkout_session.get("provider_order_code") or provider_order_code),
        expected_payment_reference=reference,
        checkout_url=str(checkout_session.get("checkout_url") or "") or None,
        provider_metadata_json=provider_metadata,
        expires_at=checkout_session.get("expires_at") or expires_at,
    )


def _sync_attempt_with_payos(order: PaymentOrder, attempt: PaymentAttempt, *, now: datetime) -> str:
    if attempt.provider_code != PAYMENT_PROVIDER_CODE or not attempt.checkout_url:
        attempt.status = "failed"
        attempt.failed_at = now
        attempt.failure_code = "superseded"
        attempt.failure_message = "Lượt thanh toán cũ không còn đủ dữ liệu để tiếp tục nên hệ thống sẽ tạo lượt mới."
        order.status = "failed"
        order.closed_at = now
        return "recreate"

    provider_payment_id = _clean_text(attempt.provider_payment_id)
    provider_order_code = _clean_text(attempt.provider_order_code)
    if not provider_payment_id and not provider_order_code:
        return "reuse"

    try:
        provider_state = payos_provider.get_payment_link_state(
            provider_payment_id=provider_payment_id or None,
            provider_order_code=provider_order_code or None,
        )
    except payos_provider.PayOSProviderError as exc:
        if exc.status in {400, 404, 409}:
            attempt.status = "failed"
            attempt.failed_at = now
            attempt.failure_code = "provider_link_unavailable"
            attempt.failure_message = "Liên kết thanh toán cũ không còn khả dụng trên PayOS nên hệ thống sẽ tạo đơn mới."
            order.status = "failed"
            order.closed_at = now
            return "recreate"
        return "reuse"

    provider_status = _clean_text(provider_state.get("status")).upper()
    provider_metadata = dict(attempt.provider_metadata_json or {})
    provider_metadata["provider_status"] = provider_status or provider_metadata.get("provider_status")
    provider_metadata["payment_link_state"] = provider_state.get("raw_response") or {}
    provider_metadata["amount_paid_minor"] = int(provider_state.get("amount_paid_minor") or 0)
    provider_metadata["amount_remaining_minor"] = int(provider_state.get("amount_remaining_minor") or 0)
    provider_metadata["provider_state_checked_at"] = _iso(now)
    if provider_state.get("cancellation_reason"):
        provider_metadata["provider_cancellation_reason"] = provider_state["cancellation_reason"]
    if provider_state.get("canceled_at"):
        provider_metadata["provider_canceled_at"] = provider_state["canceled_at"]
    attempt.provider_metadata_json = provider_metadata

    if provider_status in PAYOS_PROVIDER_REUSABLE_STATUSES:
        attempt.status = "pending"
        return "reuse"

    if provider_status == "EXPIRED":
        attempt.status = "expired"
        attempt.failed_at = attempt.failed_at or now
        attempt.failure_code = "expired"
        attempt.failure_message = "Lượt thanh toán cũ đã hết hạn trên PayOS."
        order.status = "expired"
        order.closed_at = now
        return "recreate"

    if provider_status == "CANCELLED":
        attempt.status = "canceled"
        attempt.failed_at = attempt.failed_at or now
        attempt.failure_code = "canceled"
        attempt.failure_message = (
            _clean_text(provider_state.get("cancellation_reason"))
            or "Phiên thanh toán cũ đã bị hủy hoặc đóng trên PayOS."
        )
        order.status = "canceled"
        order.closed_at = now
        return "recreate"

    if provider_status == "FAILED":
        attempt.status = "failed"
        attempt.failed_at = attempt.failed_at or now
        attempt.failure_code = "provider_failed"
        attempt.failure_message = "PayOS báo phiên thanh toán cũ không còn xử lý được."
        order.status = "failed"
        order.closed_at = now
        return "recreate"

    if provider_status == "UNDERPAID":
        attempt.status = "manual_review"
        attempt.manual_review_reason = "PayOS ghi nhận giao dịch chưa đủ số tiền nên cần kiểm tra thủ công."
        order.status = "under_review"
        order.closed_at = None
        return "block"

    if provider_status == "PAID":
        provider_amount_minor = int(provider_state.get("amount_minor") or 0)
        provider_amount_paid_minor = int(provider_state.get("amount_paid_minor") or 0)
        if provider_amount_minor and provider_amount_minor != int(attempt.amount_minor or 0):
            attempt.status = "manual_review"
            attempt.manual_review_reason = (
                "PayOS xác nhận thanh toán thành công nhưng số tiền trên PayOS không khớp với đơn hàng."
            )
            order.status = "under_review"
            order.closed_at = None
            return "block"
        if provider_amount_paid_minor and provider_amount_paid_minor != int(attempt.amount_minor or 0):
            attempt.status = "manual_review"
            attempt.manual_review_reason = (
                "PayOS xác nhận thanh toán thành công nhưng số tiền thực nhận không khớp với đơn hàng."
            )
            order.status = "under_review"
            order.closed_at = None
            return "block"

        attempt.status = "confirmed"
        attempt.confirmed_at = attempt.confirmed_at or now
        attempt.failed_at = None
        attempt.failure_code = None
        attempt.failure_message = None
        attempt.manual_review_reason = None
        order.status = "paid"
        order.paid_at = order.paid_at or now
        order.closed_at = now
        _ensure_entitlements_for_confirmed_order(order, attempt, now=now)
        return "completed"

    attempt.status = "manual_review"
    attempt.manual_review_reason = (
        f"PayOS trả về trạng thái '{provider_status or 'UNKNOWN'}' nên hệ thống không tự động tái sử dụng lượt thanh toán này."
    )
    order.status = "under_review"
    order.closed_at = None
    return "block"


def _create_or_reuse_order_for_context(
    context: dict[str, Any],
    *,
    user_id: int,
    return_url: str,
    cancel_url: str,
    buyer_email: str | None = None,
) -> tuple[PaymentOrder, bool]:
    now = _utcnow()
    pending_orders = payment_repository.list_reusable_orders_for_product(
        user_id=user_id,
        product_type=context["product_type"],
        product_ref_id=context["product_ref_id"],
    )
    dirty = False
    for order in pending_orders:
        dirty = _maybe_expire_order(order, now=now) or dirty
        latest_attempt = _latest_attempt(order)
        if latest_attempt and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES and order.status == "pending_payment":
            resolution = _sync_attempt_with_payos(order, latest_attempt, now=now)
            dirty = dirty or resolution != "reuse"
            if resolution == "reuse":
                db.session.commit()
                return order, False
            if resolution == "completed":
                db.session.commit()
                return order, False
            if resolution == "block":
                db.session.commit()
                return order, False
            if resolution == "recreate":
                continue

    order = PaymentOrder(
        user_id=user_id,
        merchant_order_code=_build_merchant_order_code(),
        status="pending_payment",
        grant_status="pending",
        currency_code="VND",
        subtotal_amount_minor=context["amount_minor"],
        discount_amount_minor=0,
        total_amount_minor=context["amount_minor"],
    )
    db.session.add(order)
    db.session.flush()

    order_item = PaymentOrderItem(
        order_id=order.id,
        product_type=context["product_type"],
        product_ref_id=context["product_ref_id"],
        quantity=1,
        unit_amount_minor=context["amount_minor"],
        line_total_amount_minor=context["amount_minor"],
        title_snapshot=context["title_snapshot"],
        product_snapshot_json=context["product_snapshot"],
    )
    db.session.add(order_item)
    db.session.flush()

    attempt = _build_checkout_attempt(
        order,
        amount_minor=context["amount_minor"],
        title_snapshot=context["title_snapshot"],
        product_type=context["product_type"],
        product_ref_id=context["product_ref_id"],
        return_url=return_url,
        cancel_url=cancel_url,
        buyer_email=buyer_email,
    )
    db.session.add(attempt)
    db.session.commit()
    return order, True


def prepare_checkout_for_product(
    *,
    user_id: int,
    product_type: str,
    product_ref_id: str,
    return_url: str | None = None,
    cancel_url: str | None = None,
) -> dict[str, Any]:
    _require_payments_enabled()
    context = _load_checkout_context(
        product_type=product_type,
        product_ref_id=product_ref_id,
        user_id=user_id,
    )
    existing_access = context.get("existing_access")
    if existing_access is not None:
        return {
            "payment_required": False,
            **existing_access,
        }

    buyer_email = None
    product = context.get("product")
    if product_type == "note_type" and product is not None:
        buyer_email = None
    order, created = _create_or_reuse_order_for_context(
        context,
        user_id=user_id,
        return_url=str(return_url or "").strip(),
        cancel_url=str(cancel_url or return_url or "").strip(),
        buyer_email=buyer_email,
    )
    fresh_order = payment_repository.get_order_by_id(order.id) or order
    if fresh_order.status == "paid" and fresh_order.grant_status == "completed":
        existing_access = _resolve_existing_access_for_product(
            product_type=product_type,
            product_ref_id=product_ref_id,
            user_id=user_id,
        )
        if existing_access is not None:
            return {
                "payment_required": False,
                **existing_access,
            }
    return {
        "payment_required": True,
        "created": created,
        "order": serialize_order(fresh_order),
    }


def get_order_detail_for_user(*, order_id: str, user_id: int) -> dict[str, Any]:
    order = payment_repository.get_order_for_user(order_id, user_id)
    if order is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy đơn hàng thanh toán.", status=404)
    if _maybe_expire_order(order):
        db.session.commit()
        order = payment_repository.get_order_for_user(order_id, user_id) or order
    latest_attempt = _latest_attempt(order)
    if latest_attempt is not None and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES and order.status == "pending_payment":
        resolution = _sync_attempt_with_payos(order, latest_attempt, now=_utcnow())
        if resolution in {"reuse", "completed", "block", "recreate"}:
            db.session.commit()
            order = payment_repository.get_order_for_user(order_id, user_id) or order
    return serialize_order(order)


def cancel_order_for_user(*, order_id: str, user_id: int) -> dict[str, Any]:
    order = payment_repository.get_order_for_user(order_id, user_id)
    if order is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy đơn hàng thanh toán.", status=404)
    if _maybe_expire_order(order):
        db.session.commit()
        order = payment_repository.get_order_for_user(order_id, user_id) or order
    if order.status == "canceled":
        return serialize_order(order)
    if order.status in TERMINAL_ORDER_STATUSES - {"canceled"}:
        raise PaymentServiceError(
            "PAYMENT_ORDER_NOT_CANCELABLE",
            "Chỉ đơn đang chờ thanh toán mới có thể hủy. Đơn này đã ở trạng thái cuối cùng.",
            status=409,
        )

    latest_attempt = _latest_attempt(order)
    now = _utcnow()
    if latest_attempt is not None and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES.union({"manual_review"}):
        latest_attempt.status = "canceled"
        latest_attempt.failed_at = now
        latest_attempt.failure_code = "canceled"
        latest_attempt.failure_message = "Người dùng đã chủ động hủy lượt thanh toán này."

    order.status = "canceled"
    order.closed_at = now
    db.session.commit()
    return serialize_order(order)


def expire_stale_orders(*, now: datetime | None = None) -> dict[str, int]:
    current_time = now or _utcnow()
    attempts = payment_repository.list_stale_attempts(current_time)
    expired_attempts = 0
    expired_orders = 0
    for attempt in attempts:
        order = attempt.order
        if order is None:
            continue
        was_order_expired = order.status == "expired"
        if _maybe_expire_order(order, now=current_time):
            expired_attempts += 1
            if order.status == "expired" and not was_order_expired:
                expired_orders += 1
    if expired_attempts > 0:
        db.session.commit()
    return {
        "expired_attempts": expired_attempts,
        "expired_orders": expired_orders,
    }


def _fulfill_order_item(*, order: PaymentOrder, order_item: PaymentOrderItem, attempt: PaymentAttempt, now: datetime) -> dict[str, Any]:
    if order_item.product_type == "note_type":
        source_note_type = NoteType.query.get(order_item.product_ref_id)
        if source_note_type is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Template đã thanh toán không còn tồn tại để cấp quyền.", status=404)
        install_row = flashcards_share_service.ensure_note_type_install_for_user(
            source_note_type=source_note_type,
            user_id=order.user_id,
            installed_at=now,
        )
        return {
            "source_note_type_id": source_note_type.id,
            "note_type_install_id": install_row.id,
            "installed_note_type_id": install_row.installed_note_type_id,
        }

    if order_item.product_type == "deck_marketplace_item":
        deck_item = DeckMarketplaceItem.query.get(order_item.product_ref_id)
        if deck_item is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Deck đã thanh toán không còn tồn tại để cấp quyền.", status=404)
        install_result = flashcards_share_service.install_shared_deck_item_for_user(
            deck_item,
            user_id=order.user_id,
            publish_statuses_visible=DEFAULT_VISIBLE_PUBLISH_STATUSES,
        )
        deck_install = payment_repository.get_deck_install(
            user_id=order.user_id,
            deck_item_id=deck_item.id,
        )
        grant_data: dict[str, Any] = {
            "deck_item_id": deck_item.id,
            "deck_install_id": deck_install.id if deck_install is not None else None,
            "local_deck_id": (
                deck_install.local_deck_id
                if deck_install is not None
                else (install_result.get("response") or {}).get("installed_deck_id")
            ),
            "install_created": bool(install_result.get("created")),
        }
        source_note_type_id = str(deck_item.source_note_type_id or "").strip()
        if source_note_type_id:
            note_type_install = payment_repository.get_note_type_install(
                user_id=order.user_id,
                source_note_type_id=source_note_type_id,
            )
            if note_type_install is not None:
                grant_data["note_type_install_id"] = note_type_install.id
                grant_data["installed_note_type_id"] = note_type_install.installed_note_type_id
        return grant_data

    raise PaymentServiceError("VALIDATION_ERROR", "Đơn hàng chứa loại sản phẩm không được hỗ trợ.", status=400)


def _ensure_entitlements_for_confirmed_order(order: PaymentOrder, attempt: PaymentAttempt, *, now: datetime) -> None:
    existing_by_item_id = {
        row.payment_order_item_id: row
        for row in order.entitlements
    }
    for order_item in order.items:
        entitlement = existing_by_item_id.get(order_item.id)
        if entitlement is None:
            entitlement = PaymentEntitlement(
                user_id=order.user_id,
                payment_order_id=order.id,
                payment_order_item_id=order_item.id,
                payment_attempt_id=attempt.id,
                entitlement_type=(
                    "shared_deck_install"
                    if order_item.product_type == "deck_marketplace_item"
                    else "shared_note_type_install"
                ),
                resource_type=order_item.product_type,
                resource_ref_id=order_item.product_ref_id,
                status="pending",
                grant_data_json={},
            )
            db.session.add(entitlement)
            db.session.flush()

        if entitlement.status == "active":
            continue

        entitlement.payment_attempt_id = attempt.id
        entitlement.status = "pending"
        entitlement.grant_data_json = _fulfill_order_item(
            order=order,
            order_item=order_item,
            attempt=attempt,
            now=now,
        )
        entitlement.status = "active"
        entitlement.granted_at = now
        entitlement.effective_from = now

    order.grant_status = "completed"


def _mark_manual_review(
    *,
    order: PaymentOrder,
    attempt: PaymentAttempt,
    event: PaymentWebhookEvent,
    reason: str,
    now: datetime,
) -> None:
    attempt.status = "manual_review"
    attempt.manual_review_reason = reason
    order.status = "under_review"
    event.payment_attempt_id = attempt.id
    event.payment_order_id = order.id
    event.processing_status = "processed"
    event.error_message = reason
    event.processed_at = now


def _mark_failed_attempt(
    *,
    order: PaymentOrder,
    attempt: PaymentAttempt,
    event: PaymentWebhookEvent,
    reason: str,
    now: datetime,
) -> None:
    attempt.status = "failed"
    attempt.failed_at = now
    attempt.failure_code = "provider_failed"
    attempt.failure_message = reason
    order.status = "failed"
    order.closed_at = now
    event.payment_attempt_id = attempt.id
    event.payment_order_id = order.id
    event.processing_status = "processed"
    event.error_message = reason
    event.processed_at = now


def _resolve_webhook_attempt_candidates(normalized_payload: dict[str, Any]) -> list[PaymentAttempt]:
    provider_payment_id = normalized_payload.get("provider_payment_id")
    provider_order_code = normalized_payload.get("provider_order_code")
    payment_reference = normalized_payload.get("payment_reference")
    amount_minor = int(normalized_payload.get("amount_minor") or 0)

    if provider_payment_id:
        attempt = payment_repository.get_attempt_by_provider_payment_id(
            provider_code=PAYMENT_PROVIDER_CODE,
            provider_payment_id=provider_payment_id,
        )
        if attempt is not None:
            return [attempt]

    if provider_order_code:
        attempt = payment_repository.get_attempt_by_provider_order_code(
            provider_code=PAYMENT_PROVIDER_CODE,
            provider_order_code=provider_order_code,
        )
        if attempt is not None:
            return [attempt]

    if payment_reference:
        return payment_repository.find_attempts_by_reference_and_amount(
            payment_reference=payment_reference,
            amount_minor=amount_minor,
        )

    return []


def _process_webhook_event(event_id: str, normalized_payload: dict[str, Any], *, signature_valid: bool) -> tuple[dict[str, Any], int]:
    now = _utcnow()
    event = payment_repository.get_webhook_event_by_id(event_id)
    if event is None:
        raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy sự kiện webhook cần xử lý.", status=404)

    attempts = _resolve_webhook_attempt_candidates(normalized_payload)
    if not attempts:
        event.processing_status = "ignored"
        event.error_message = "Không tìm thấy đơn hàng hoặc lượt thanh toán khớp với webhook này."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    if len(attempts) != 1:
        event.processing_status = "ignored"
        event.error_message = "Webhook khớp với nhiều lượt thanh toán nên cần bỏ qua để tránh đối soát sai."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    initial_attempt = attempts[0]
    initial_order = initial_attempt.order
    if initial_order is None:
        event.processing_status = "ignored"
        event.error_message = "Lượt thanh toán khớp được tìm thấy nhưng không còn gắn với đơn hàng hợp lệ."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    order, attempt = payment_repository.get_order_and_latest_attempt_for_update(
        order_id=initial_order.id,
        attempt_id=initial_attempt.id,
    )
    if order is None or attempt is None:
        event.processing_status = "ignored"
        event.error_message = "Không thể tải lại đơn hàng hoặc lượt thanh toán để xử lý webhook."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    event.payment_attempt_id = attempt.id
    event.payment_order_id = order.id

    if _maybe_expire_order(order, now=now):
        db.session.flush()

    if order.status == "paid" and order.grant_status == "completed":
        event.processing_status = "processed"
        event.processed_at = now
        db.session.commit()
        return {"status": "already_processed", "order": serialize_order(order)}, 200

    if not signature_valid and not normalized_payload.get("provider_payment_id"):
        _mark_manual_review(
            order=order,
            attempt=attempt,
            event=event,
            reason="Webhook từ PayOS không vượt qua bước xác minh chữ ký nên cần kiểm tra thủ công.",
            now=now,
        )
        db.session.commit()
        return {"status": "manual_review", "order": serialize_order(order)}, 202

    if order.status in {"canceled", "failed", "refunded"}:
        event.processing_status = "ignored"
        event.error_message = f"Đơn hàng đã đóng trước đó với trạng thái '{order.status}'."
        event.processed_at = now
        db.session.commit()
        return {"status": "ignored", "order": serialize_order(order)}, 200

    if not normalized_payload.get("success"):
        _mark_failed_attempt(
            order=order,
            attempt=attempt,
            event=event,
            reason=(
                "PayOS trả về trạng thái không thành công"
                f" ('{normalized_payload.get('status') or 'unknown'}') cho đơn hàng này."
            ),
            now=now,
        )
        db.session.commit()
        return {"status": "failed", "order": serialize_order(order)}, 200

    if int(attempt.amount_minor or 0) != int(normalized_payload.get("amount_minor") or 0):
        _mark_manual_review(
            order=order,
            attempt=attempt,
            event=event,
            reason="Số tiền PayOS gửi về không khớp với số tiền của đơn hàng nên cần kiểm tra thủ công.",
            now=now,
        )
        db.session.commit()
        return {"status": "manual_review", "order": serialize_order(order)}, 202

    payment_reference = str(normalized_payload.get("payment_reference") or "").strip()
    expected_reference = str(attempt.expected_payment_reference or "").strip()
    if payment_reference and expected_reference and payment_reference != expected_reference:
        _mark_manual_review(
            order=order,
            attempt=attempt,
            event=event,
            reason="Nội dung chuyển khoản PayOS gửi về không khớp với mã tham chiếu của đơn hàng.",
            now=now,
        )
        db.session.commit()
        return {"status": "manual_review", "order": serialize_order(order)}, 202

    attempt.status = "confirmed"
    attempt.confirmed_at = now
    attempt.provider_payment_id = normalized_payload.get("provider_payment_id") or attempt.provider_payment_id
    attempt.provider_order_code = normalized_payload.get("provider_order_code") or attempt.provider_order_code
    provider_metadata = dict(attempt.provider_metadata_json or {})
    if normalized_payload.get("provider_transaction_ref"):
        provider_metadata["provider_transaction_ref"] = normalized_payload["provider_transaction_ref"]
    if normalized_payload.get("payment_reference"):
        provider_metadata["payment_reference_confirmed"] = normalized_payload["payment_reference"]
    attempt.provider_metadata_json = provider_metadata

    order.status = "paid"
    order.paid_at = order.paid_at or now
    order.closed_at = now
    _ensure_entitlements_for_confirmed_order(order, attempt, now=now)

    event.processing_status = "processed"
    event.error_message = None
    event.processed_at = now
    db.session.commit()
    return {"status": "processed", "order": serialize_order(order)}, 200


def process_payment_webhook(normalized_payload: dict[str, Any], *, signature_valid: bool) -> tuple[dict[str, Any], int]:
    now = _utcnow()
    event = PaymentWebhookEvent(
        provider_code=PAYMENT_PROVIDER_CODE,
        event_key=normalized_payload["event_key"],
        event_type=normalized_payload.get("event_type") or "payment.unknown",
        signature_valid=bool(signature_valid),
        processing_status="received",
        payload_json=normalized_payload.get("raw_payload") or {},
        received_at=now,
    )
    db.session.add(event)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return {
            "status": "duplicate",
            "event_key": normalized_payload["event_key"],
        }, 200

    if not payments_enabled():
        event = payment_repository.get_webhook_event_by_id(event.id)
        if event is not None:
            event.processing_status = "ignored"
            event.error_message = "Hệ thống thanh toán đang tắt nên webhook chỉ được ghi nhận chứ không xử lý."
            event.processed_at = now
            db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 200

    if not webhook_auto_grant_enabled():
        event = payment_repository.get_webhook_event_by_id(event.id)
        if event is not None:
            event.processing_status = "ignored"
            event.error_message = "Chế độ tự cấp quyền từ webhook đang tắt nên cần xử lý thủ công."
            event.processed_at = now
            db.session.commit()
        return {"status": "ignored", "event_id": event.id}, 202

    try:
        return _process_webhook_event(
            event.id,
            normalized_payload,
            signature_valid=signature_valid,
        )
    except Exception as exc:
        db.session.rollback()
        failed_event = payment_repository.get_webhook_event_by_id(event.id)
        if failed_event is not None:
            failed_event.processing_status = "failed"
            failed_event.error_message = str(exc)
            failed_event.processed_at = _utcnow()
            db.session.commit()
        return {
            "status": "failed",
            "event_id": event.id,
            "message": "Webhook đã được lưu để kiểm tra và xử lý lại thủ công.",
        }, 200


def process_payos_webhook_request(raw_payload: bytes | str) -> tuple[dict[str, Any], int]:
    _require_payments_enabled()
    _require_supported_provider()
    try:
        normalized_payload = payos_provider.verify_webhook_payload(raw_payload)
    except payos_provider.PayOSProviderError as exc:
        raise PaymentServiceError(exc.code, str(exc), status=exc.status) from exc
    return process_payment_webhook(normalized_payload, signature_valid=True)


def process_vietqr_webhook(normalized_payload: dict[str, Any], *, signature_valid: bool) -> tuple[dict[str, Any], int]:
    """Deprecated compatibility wrapper kept during the payOS-first recovery."""
    return process_payment_webhook(normalized_payload, signature_valid=signature_valid)
