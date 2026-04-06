"""Service helpers for support donation public/admin pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from secrets import randbelow
import time
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from app.validators import (
    MediaUploadValidationResult,
    RequestValidationError,
    resolve_safe_storage_path,
    sanitize_plain_text,
    validate_media_upload_request,
)
from app.validators.support_donation import (
    MAX_DONATION_AMOUNT_MINOR,
    MIN_DONATION_AMOUNT_MINOR,
    SUGGESTED_DONATION_AMOUNTS,
)
from app.services.payment import config as payment_config
from models.support_donation_config import SupportDonationConfig

DEFAULT_TITLE = "Ủng hộ duy trì hệ thống"
DEFAULT_DESCRIPTION = (
    "Đây là một website phi lợi nhuận. Hiện tại chi phí duy trì hạ tầng đang được hỗ trợ từ sự đóng góp của mọi người. "
    "Nếu bạn thấy hệ thống hữu ích và muốn chung tay duy trì, rất mong nhận được sự hỗ trợ."
)
DEFAULT_THANK_YOU = (
    "Xin chân thành cảm ơn sự ủng hộ của bạn. Mọi sự giúp đỡ đều rất quý giá để website có thể tiếp tục duy trì và phát triển."
)

MAX_TITLE_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 5000
MAX_ACCOUNT_NAME_LENGTH = 255
MAX_ACCOUNT_NUMBER_LENGTH = 64
MAX_THANK_YOU_LENGTH = 3000
DEFAULT_QR_MAX_BYTES = 5 * 1024 * 1024
DONATION_PRODUCT_TYPE = "support_donation"
DONATION_SELLER_NAME = "Flama"
DEFAULT_DONATION_EXPIRY_SECONDS = 30 * 60


@dataclass(slots=True)
class SupportDonationFormPayload:
    title: str
    description: str
    account_name: str
    account_number: str
    thank_you_message: str


def get_latest_config() -> SupportDonationConfig | None:
    return (
        SupportDonationConfig.query.order_by(
            SupportDonationConfig.updated_at.desc(),
            SupportDonationConfig.id.desc(),
        ).first()
    )


def parse_form_payload(form: dict[str, Any]) -> tuple[SupportDonationFormPayload, list[str]]:
    errors: list[str] = []

    title = _sanitize_field(
        form.get("title"),
        field_name="title",
        max_length=MAX_TITLE_LENGTH,
        errors=errors,
    )
    description = _sanitize_field(
        form.get("description"),
        field_name="description",
        max_length=MAX_DESCRIPTION_LENGTH,
        errors=errors,
    )
    account_name = _sanitize_field(
        form.get("account_name"),
        field_name="account_name",
        max_length=MAX_ACCOUNT_NAME_LENGTH,
        errors=errors,
    )
    account_number = _sanitize_field(
        form.get("account_number"),
        field_name="account_number",
        max_length=MAX_ACCOUNT_NUMBER_LENGTH,
        errors=errors,
    )
    thank_you_message = _sanitize_field(
        form.get("thank_you_message"),
        field_name="thank_you_message",
        max_length=MAX_THANK_YOU_LENGTH,
        errors=errors,
    )

    if not account_name:
        errors.append("Tên tài khoản là bắt buộc.")
    if not account_number:
        errors.append("Số tài khoản là bắt buộc.")

    payload = SupportDonationFormPayload(
        title=title or DEFAULT_TITLE,
        description=description or DEFAULT_DESCRIPTION,
        account_name=account_name,
        account_number=account_number,
        thank_you_message=thank_you_message or DEFAULT_THANK_YOU,
    )
    return payload, errors


def is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def validate_qr_upload(
    uploaded: Any,
    *,
    max_bytes: int,
    scanner: Callable[[bytes], Any] | None = None,
    scan_enabled: bool = False,
) -> tuple[MediaUploadValidationResult | None, list[str]]:
    if uploaded is None or not getattr(uploaded, "filename", ""):
        return None, []

    try:
        validated = validate_media_upload_request(
            field_name_raw="qr_image",
            field_type="image",
            uploaded=uploaded,
            max_bytes=max_bytes,
            scanner=scanner,
            scan_enabled=scan_enabled,
        )
    except RequestValidationError as exc:
        return None, [str(exc)]
    return validated, []


def persist_qr_upload(
    *,
    validated_upload: MediaUploadValidationResult,
    upload_root: Path,
) -> tuple[str, str, str]:
    relative_path = Path("support_donation") / validated_upload.storage_filename
    full_path = resolve_safe_storage_path(upload_root=upload_root, relative_path=relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(validated_upload.content)
    return (
        str(relative_path).replace("\\", "/"),
        validated_upload.safe_original_filename,
        validated_upload.mime_type,
    )


def resolve_qr_file_path(*, upload_root: Path, storage_path: str) -> Path:
    return resolve_safe_storage_path(upload_root=upload_root, relative_path=Path(storage_path))


def remove_qr_file(*, upload_root: Path, storage_path: str | None) -> None:
    if not storage_path:
        return
    try:
        full_path = resolve_qr_file_path(upload_root=upload_root, storage_path=storage_path)
    except RequestValidationError:
        return
    if not full_path.exists() or not full_path.is_file():
        return
    try:
        full_path.unlink()
    except OSError:
        return


def build_donation_product_ref(amount_minor: int) -> str:
    return f"support_donation_{int(amount_minor or 0)}"


def parse_donation_product_ref(product_ref_id: str) -> int | None:
    token = str(product_ref_id or "").strip().lower()
    prefix = "support_donation_"
    if not token.startswith(prefix):
        return None
    raw_amount = token[len(prefix) :]
    if not raw_amount.isdigit():
        return None
    amount_minor = int(raw_amount)
    if amount_minor < MIN_DONATION_AMOUNT_MINOR or amount_minor > MAX_DONATION_AMOUNT_MINOR:
        return None
    return amount_minor


def get_suggested_amounts() -> tuple[int, ...]:
    return tuple(int(value) for value in SUGGESTED_DONATION_AMOUNTS)


def build_saved_donation_checkout_context(*, amount_minor: int) -> dict[str, Any]:
    row = get_latest_config()
    title = _clean_text(row.title if row is not None else "") or DEFAULT_TITLE
    thank_you_message = _clean_text(row.thank_you_message if row is not None else "") or DEFAULT_THANK_YOU
    return {
        "product_type": DONATION_PRODUCT_TYPE,
        "product_ref_id": build_donation_product_ref(amount_minor),
        "title_snapshot": title,
        "amount_minor": int(amount_minor or 0),
        "product_snapshot": {
            "title": title,
            "kind": DONATION_PRODUCT_TYPE,
            "seller_name": DONATION_SELLER_NAME,
            "donation_amount_minor": int(amount_minor or 0),
            "thank_you_message": thank_you_message,
        },
    }


def create_anonymous_checkout(
    *,
    amount_minor: int,
    return_url: str,
    cancel_url: str,
    buyer_email: str | None = None,
) -> dict[str, Any]:
    from app.services.payment.provider import payos_provider

    row = get_latest_config()
    title = _clean_text(row.title if row is not None else "") or DEFAULT_TITLE
    provider_order_code = _build_provider_order_code()
    payment_reference = _build_payment_reference()
    expires_at = datetime.utcnow() + timedelta(
        seconds=payment_config.order_expiry_seconds(default=DEFAULT_DONATION_EXPIRY_SECONDS)
    )
    resolved_return_url = _append_query_params(
        return_url,
        support_checkout_mode="anonymous",
        support_provider_order_code=str(provider_order_code),
    )
    resolved_cancel_url = _append_query_params(
        cancel_url,
        support_checkout_mode="anonymous",
        support_provider_order_code=str(provider_order_code),
    )

    session = payos_provider.create_checkout_session(
        provider_order_code=provider_order_code,
        amount_minor=int(amount_minor or 0),
        title_snapshot=title,
        payment_reference=payment_reference,
        return_url=resolved_return_url,
        cancel_url=resolved_cancel_url,
        expires_at=expires_at,
        buyer_email=buyer_email,
    )
    provider_metadata = dict(session.get("provider_metadata") or {})
    provider_metadata.update(
        {
            "payment_reference": payment_reference,
            "return_url": resolved_return_url,
            "cancel_url": resolved_cancel_url,
            "merchant_order_code": str(provider_order_code),
        }
    )
    return {
        "checkout_mode": "anonymous",
        "payment_required": True,
        "created": True,
        "checkout": {
            "provider": session.get("provider_code") or "payos",
            "checkout_url": session.get("checkout_url"),
            "payment_link_id": session.get("provider_payment_id"),
            "provider_order_code": session.get("provider_order_code") or str(provider_order_code),
            "bank_bin": provider_metadata.get("bank_bin"),
            "account_no": provider_metadata.get("account_no"),
            "account_name": provider_metadata.get("account_name"),
            "qr_code": provider_metadata.get("qr_code"),
            "provider_status": provider_metadata.get("provider_status"),
            "amount_minor": int(session.get("amount_minor") or amount_minor or 0),
            "currency_code": session.get("currency_code") or "VND",
            "payment_reference": payment_reference,
            "merchant_order_code": str(provider_order_code),
            "expires_at": _iso(session.get("expires_at") or expires_at),
            "provider_metadata": provider_metadata,
        },
    }


def get_anonymous_checkout_status(*, provider_order_code: str) -> dict[str, Any]:
    from app.services.payment.provider import payos_provider

    provider_state = payos_provider.get_payment_link_state(provider_order_code=provider_order_code)
    provider_status = _clean_text(provider_state.get("status")).upper() or "PENDING"
    amount_minor = int(provider_state.get("amount_minor") or 0)
    currency_code = _clean_text(provider_state.get("currency_code")) or "VND"
    payment_reference = _clean_text(provider_state.get("payment_reference"))
    checkout_url = _clean_text(provider_state.get("checkout_url")) or None
    created_at = _clean_text(provider_state.get("created_at")) or None
    status_display = _anonymous_status_display(provider_status)
    paid_at = _iso(datetime.utcnow()) if status_display["grant_status"] == "completed" else None
    order_code = str(provider_state.get("provider_order_code") or provider_order_code)
    return {
        "checkout_mode": "anonymous",
        "is_support_donation": True,
        "id": None,
        "merchant_order_code": order_code,
        "status": status_display["code"],
        "status_display": {
            "code": status_display["code"],
            "tone": status_display["tone"],
            "label": status_display["label"],
            "headline": status_display["headline"],
            "description": status_display["description"],
        },
        "grant_status": status_display["grant_status"],
        "grant_status_display": _anonymous_grant_status_display(status_display["grant_status"]),
        "currency_code": currency_code,
        "subtotal_amount_minor": amount_minor,
        "discount_amount_minor": 0,
        "total_amount_minor": amount_minor,
        "paid_at": paid_at,
        "closed_at": None,
        "created_at": created_at,
        "updated_at": _iso(datetime.utcnow()),
        "message": status_display["description"],
        "headline": status_display["headline"],
        "next_action": _anonymous_next_action(provider_status),
        "instructions": _anonymous_instructions(provider_status, has_checkout_url=bool(checkout_url)),
        "order_detail_lines": _anonymous_detail_lines(
            provider_order_code=order_code,
            amount_minor=amount_minor,
            currency_code=currency_code,
            payment_reference=payment_reference,
            checkout_url=checkout_url,
            created_at=created_at,
        ),
        "items": [
            {
                "id": None,
                "product_type": DONATION_PRODUCT_TYPE,
                "product_ref_id": build_donation_product_ref(amount_minor),
                "quantity": 1,
                "unit_amount_minor": amount_minor,
                "line_total_amount_minor": amount_minor,
                "title_snapshot": DEFAULT_TITLE,
                "product_snapshot": {"seller_name": DONATION_SELLER_NAME},
                "created_at": created_at,
            }
        ],
        "attempts": [],
        "active_attempt": {
            "id": None,
            "provider_code": provider_state.get("provider_code") or "payos",
            "payment_method_code": "payos_checkout",
            "status": status_display["attempt_status"],
            "status_display": {
                "code": status_display["attempt_status"],
                "label": status_display["attempt_label"],
                "description": status_display["description"],
            },
            "amount_minor": amount_minor,
            "currency_code": currency_code,
            "provider_payment_id": provider_state.get("provider_payment_id"),
            "provider_order_code": order_code,
            "expected_payment_reference": payment_reference or None,
            "checkout_url": checkout_url,
            "expires_at": None,
            "confirmed_at": paid_at,
            "failed_at": None,
            "failure_code": None,
            "failure_message": None,
            "manual_review_reason": None,
            "provider_metadata": provider_state.get("raw_response") or {},
            "created_at": created_at,
            "updated_at": _iso(datetime.utcnow()),
            "message": status_display["description"],
            "checkout": {
                "provider": provider_state.get("provider_code") or "payos",
                "checkout_url": checkout_url,
                "payment_link_id": provider_state.get("provider_payment_id"),
                "provider_order_code": order_code,
                "amount_minor": amount_minor,
                "currency_code": currency_code,
                "payment_reference": payment_reference or None,
                "merchant_order_code": order_code,
            },
        },
    }


def _sanitize_field(
    raw_value: Any,
    *,
    field_name: str,
    max_length: int,
    errors: list[str],
) -> str:
    try:
        return sanitize_plain_text(raw_value, field_name=field_name, max_length=max_length)
    except RequestValidationError as exc:
        errors.append(str(exc))
        return ""


def _anonymous_status_display(provider_status: str) -> dict[str, str]:
    token = _clean_text(provider_status).upper() or "PENDING"
    if token == "PAID":
        return {
            "code": "paid",
            "tone": "success",
            "label": "Thanh toán thành công",
            "headline": "Cảm ơn bạn đã ủng hộ Flama.",
            "description": "Khoản đóng góp của bạn đã được ghi nhận thành công. Sự đồng hành của bạn là nguồn động lực rất lớn để chúng tôi tiếp tục phát triển cộng đồng.",
            "grant_status": "completed",
            "attempt_status": "confirmed",
            "attempt_label": "Đã xác nhận",
        }
    if token == "UNDERPAID":
        return {
            "code": "under_review",
            "tone": "warning",
            "label": "Cần kiểm tra thủ công",
            "headline": "Giao dịch cần được kiểm tra thêm.",
            "description": "Chúng tôi đã nhận được tín hiệu thanh toán nhưng cần kiểm tra thêm trước khi xác nhận khoản ủng hộ này.",
            "grant_status": "pending",
            "attempt_status": "manual_review",
            "attempt_label": "Cần kiểm tra",
        }
    if token == "EXPIRED":
        return {
            "code": "expired",
            "tone": "secondary",
            "label": "Phiên đã hết hạn",
            "headline": "Phiên thanh toán đã hết hạn.",
            "description": "Bạn có thể tạo một phiên mới bất cứ lúc nào nếu vẫn muốn tiếp tục ủng hộ.",
            "grant_status": "pending",
            "attempt_status": "expired",
            "attempt_label": "Đã hết hạn",
        }
    if token in {"CANCELLED", "CANCELED"}:
        return {
            "code": "canceled",
            "tone": "secondary",
            "label": "Đã hủy",
            "headline": "Phiên ủng hộ đã được dừng.",
            "description": "Khi thuận tiện, bạn có thể bắt đầu lại bằng một phiên mới.",
            "grant_status": "pending",
            "attempt_status": "canceled",
            "attempt_label": "Đã hủy",
        }
    if token == "FAILED":
        return {
            "code": "failed",
            "tone": "danger",
            "label": "Thanh toán thất bại",
            "headline": "Rất tiếc, giao dịch chưa hoàn tất.",
            "description": "Khoản ủng hộ này chưa được ghi nhận. Bạn có thể thử lại bằng một phiên mới khi sẵn sàng.",
            "grant_status": "failed",
            "attempt_status": "failed",
            "attempt_label": "Thất bại",
        }
    return {
        "code": "pending_payment",
        "tone": "info",
        "label": "Đang chờ thanh toán",
        "headline": "Phiên ủng hộ đã sẵn sàng.",
        "description": "Sau khi hoàn tất thanh toán, hệ thống sẽ cập nhật kết quả mới nhất cho bạn tại đây.",
        "grant_status": "pending",
        "attempt_status": "pending",
        "attempt_label": "Đang chờ thanh toán",
    }


def _anonymous_grant_status_display(grant_status: str) -> dict[str, str]:
    token = _clean_text(grant_status).lower()
    if token == "completed":
        return {
            "code": token,
            "label": "Đã ghi nhận",
            "description": "Khoản ủng hộ đã được ghi nhận thành công.",
        }
    if token == "failed":
        return {
            "code": token,
            "label": "Ghi nhận lỗi",
            "description": "Khoản ủng hộ này chưa được ghi nhận hoàn tất.",
        }
    return {
        "code": token or "pending",
        "label": "Chờ ghi nhận",
        "description": "Khoản ủng hộ đang chờ xác nhận cuối cùng.",
    }


def _anonymous_next_action(provider_status: str) -> str:
    token = _clean_text(provider_status).upper()
    if token == "PAID":
        return "Bạn có thể tiếp tục sử dụng Flama như bình thường. Cảm ơn bạn đã đồng hành."
    if token == "UNDERPAID":
        return "Không thanh toán lại ngay. Nếu tiền đã bị trừ, hãy giữ lại biên nhận và liên hệ với chúng tôi để kiểm tra."
    if token == "EXPIRED":
        return "Tạo một phiên ủng hộ mới khi bạn sẵn sàng tiếp tục."
    if token in {"CANCELLED", "CANCELED", "FAILED"}:
        return "Bạn có thể bắt đầu lại bằng một phiên mới ngay trên trang này."
    return "Hoàn tất thanh toán rồi quay lại đây để xem kết quả mới nhất."


def _anonymous_instructions(provider_status: str, *, has_checkout_url: bool) -> list[str]:
    token = _clean_text(provider_status).upper()
    if token == "PAID":
        return [
            "Cảm ơn bạn đã ủng hộ Flama.",
            "Nếu bạn đang đăng nhập và không bật ẩn danh, khoản donate sẽ xuất hiện trong lịch sử đơn hàng.",
        ]
    if token == "UNDERPAID":
        return [
            "Không thanh toán lại ngay để tránh bị trừ tiền nhiều lần.",
            "Nếu ngân hàng đã báo trừ tiền, hãy giữ lại biên nhận hoặc ảnh chụp giao dịch để chúng tôi hỗ trợ nhanh hơn.",
        ]
    if token == "EXPIRED":
        return [
            "Phiên cũ đã hết hạn nên bạn không cần chuyển tiền vào thông tin thanh toán trước đó.",
            "Tạo một phiên mới nếu bạn vẫn muốn tiếp tục ủng hộ.",
        ]
    if token in {"CANCELLED", "CANCELED", "FAILED"}:
        return [
            "Bạn có thể tạo lại một phiên mới ngay trên trang này khi sẵn sàng.",
            "Nếu ngân hàng đã báo trừ tiền nhưng trạng thái vẫn lỗi, hãy liên hệ với chúng tôi để kiểm tra.",
        ]
    instructions = [
        "Thanh toán đúng số tiền bạn muốn ủng hộ.",
        "Giữ nguyên nội dung chuyển khoản để hệ thống đối soát nhanh hơn.",
    ]
    if has_checkout_url:
        instructions.append("Nếu bạn rời trang thanh toán, vẫn có thể mở lại liên kết bất cứ lúc nào.")
    return instructions


def _anonymous_detail_lines(
    *,
    provider_order_code: str,
    amount_minor: int,
    currency_code: str,
    payment_reference: str,
    checkout_url: str | None,
    created_at: str | None,
) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = [
        {
            "key": "merchant_order_code",
            "label": "Mã phiên PayOS",
            "type": "text",
            "value": provider_order_code,
        },
        {
            "key": "product_title",
            "label": "Khoản ủng hộ",
            "type": "amount_minor",
            "value_minor": int(amount_minor or 0),
            "currency_code": currency_code or "VND",
        },
    ]
    if payment_reference:
        lines.append(
            {
                "key": "payment_reference",
                "label": "Nội dung chuyển khoản",
                "type": "text",
                "value": payment_reference,
            }
        )
    if checkout_url:
        lines.append(
            {
                "key": "checkout_url",
                "label": "Liên kết thanh toán",
                "type": "url",
                "value": checkout_url,
            }
        )
    if created_at:
        lines.append(
            {
                "key": "created_at",
                "label": "Tạo lúc",
                "type": "datetime",
                "value": created_at,
            }
        )
    return lines


def _append_query_params(url: str, **params: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in params.items():
        if value is not None:
            query[key] = str(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _build_payment_reference() -> str:
    return f"DONATE{uuid4().hex[:10].upper()}"


def _build_provider_order_code() -> int:
    timestamp_millis = int(time.time() * 1000)
    return int(f"{timestamp_millis}{randbelow(1000):03d}")


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    text = _clean_text(value)
    return text or None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()
