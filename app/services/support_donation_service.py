"""Service helpers for support donation public/admin pages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.validators import (
    MediaUploadValidationResult,
    RequestValidationError,
    resolve_safe_storage_path,
    sanitize_plain_text,
    validate_media_upload_request,
)
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
