from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.datastructures import FileStorage

from app.repositories import image_library_repository
from app.services.image_sanitizer import sanitize_shared_image
from app.services.remote_image_fetcher import fetch_remote_image
from app.validators import (
    MediaUploadValidationResult,
    RequestValidationError,
    resolve_safe_storage_path,
    validate_media_upload_request,
)
from app.validators.image_library import (
    normalize_image_description,
    normalize_image_key,
)
from models import db
from models.audit_log import AuditLog
from models.shared_image_asset import SharedImageAsset


@dataclass(frozen=True)
class ImageResolution:
    requested_key: str
    asset: SharedImageAsset | None
    file_path: Path | None
    fallback_reason: str | None

    @property
    def is_fallback(self) -> bool:
        return self.asset is None or self.file_path is None


class ImageLibraryConflictError(Exception):
    pass


class ImageLibraryPersistenceError(Exception):
    pass


def validate_image_upload(
    uploaded: Any,
    *,
    max_bytes: int,
    scanner: Callable[[bytes], Any] | None = None,
    scan_enabled: bool = False,
) -> MediaUploadValidationResult | None:
    if uploaded is None or not getattr(uploaded, "filename", ""):
        return None
    return validate_media_upload_request(
        field_name_raw="shared_image",
        field_type="image",
        uploaded=uploaded,
        max_bytes=max_bytes,
        scanner=scanner,
        scan_enabled=scan_enabled,
    )


def prepare_image_upload(
    uploaded: Any,
    *,
    source_url: str,
    max_bytes: int,
    max_pixels: int,
    remote_timeout_seconds: float,
    remote_max_redirects: int,
    scanner: Callable[[bytes], Any] | None = None,
    scan_enabled: bool = False,
) -> MediaUploadValidationResult | None:
    """Resolve one local/clipboard upload or remote URL into a clean image."""

    has_upload = bool(uploaded is not None and getattr(uploaded, "filename", ""))
    normalized_source_url = str(source_url or "").strip()
    if has_upload and normalized_source_url:
        raise RequestValidationError(
            "Chỉ chọn một nguồn ảnh: tệp dán/tải lên hoặc link hình ảnh.",
            field="source_url",
        )

    resolved_upload = uploaded
    if normalized_source_url:
        remote_payload = fetch_remote_image(
            normalized_source_url,
            max_bytes=max_bytes,
            timeout_seconds=remote_timeout_seconds,
            max_redirects=remote_max_redirects,
        )
        resolved_upload = FileStorage(
            stream=BytesIO(remote_payload.content),
            filename=remote_payload.filename,
            content_type=remote_payload.mime_type,
        )

    validated_upload = validate_image_upload(
        resolved_upload,
        max_bytes=max_bytes,
        scanner=scanner,
        scan_enabled=scan_enabled,
    )
    if validated_upload is None:
        return None
    return sanitize_shared_image(
        validated_upload,
        max_bytes=max_bytes,
        max_pixels=max_pixels,
    )


def create_image(
    *,
    image_key: str,
    description: str,
    is_enabled: bool,
    validated_upload: MediaUploadValidationResult | None,
    upload_root: Path,
    actor_user_id: int,
) -> SharedImageAsset:
    normalized_key = normalize_image_key(image_key)
    normalized_description = normalize_image_description(description)
    if image_library_repository.get_by_key(normalized_key) is not None:
        raise ImageLibraryConflictError("image_key already exists.")

    row = SharedImageAsset(
        image_key=normalized_key,
        description=normalized_description or None,
        is_enabled=bool(is_enabled),
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
    )
    new_storage_path: str | None = None
    if validated_upload is not None:
        new_storage_path = _persist_upload(
            image_key=normalized_key,
            validated_upload=validated_upload,
            upload_root=upload_root,
        )
        _apply_upload_metadata(
            row,
            validated_upload=validated_upload,
            storage_path=new_storage_path,
        )

    db.session.add(row)
    db.session.add(
        AuditLog(
            user_id=actor_user_id,
            action="image_library.create",
            payload={"image_key": normalized_key, "has_file": validated_upload is not None},
        )
    )
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        remove_storage_file(upload_root=upload_root, storage_path=new_storage_path)
        raise ImageLibraryConflictError("image_key already exists.") from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        remove_storage_file(upload_root=upload_root, storage_path=new_storage_path)
        raise ImageLibraryPersistenceError("Could not create image library entry.") from exc
    return row


def update_image(
    *,
    row: SharedImageAsset,
    description: str,
    is_enabled: bool,
    validated_upload: MediaUploadValidationResult | None,
    upload_root: Path,
    actor_user_id: int,
) -> SharedImageAsset:
    normalized_description = normalize_image_description(description)
    old_storage_path = row.storage_path
    new_storage_path: str | None = None

    if validated_upload is not None:
        new_storage_path = _persist_upload(
            image_key=row.image_key,
            validated_upload=validated_upload,
            upload_root=upload_root,
        )
        _apply_upload_metadata(
            row,
            validated_upload=validated_upload,
            storage_path=new_storage_path,
        )

    row.description = normalized_description or None
    row.is_enabled = bool(is_enabled)
    row.updated_by_user_id = actor_user_id
    db.session.add(
        AuditLog(
            user_id=actor_user_id,
            action="image_library.update",
            payload={
                "image_key": row.image_key,
                "replaced_file": validated_upload is not None,
                "is_enabled": row.is_enabled,
            },
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        remove_storage_file(upload_root=upload_root, storage_path=new_storage_path)
        raise ImageLibraryPersistenceError("Could not update image library entry.") from exc

    if new_storage_path and old_storage_path and old_storage_path != new_storage_path:
        remove_storage_file(upload_root=upload_root, storage_path=old_storage_path)
    return row


def set_enabled(
    *,
    row: SharedImageAsset,
    is_enabled: bool,
    actor_user_id: int,
) -> SharedImageAsset:
    row.is_enabled = bool(is_enabled)
    row.updated_by_user_id = actor_user_id
    db.session.add(
        AuditLog(
            user_id=actor_user_id,
            action="image_library.status",
            payload={"image_key": row.image_key, "is_enabled": row.is_enabled},
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ImageLibraryPersistenceError("Could not update image status.") from exc
    return row


def resolve_image(*, image_key: str, upload_root: Path) -> ImageResolution:
    normalized_key = normalize_image_key(image_key)
    row = image_library_repository.get_by_key(normalized_key)
    if row is None:
        return ImageResolution(normalized_key, None, None, "missing")
    if not row.is_enabled:
        return ImageResolution(normalized_key, row, None, "disabled")
    if not row.storage_path:
        return ImageResolution(normalized_key, row, None, "missing_file")
    try:
        file_path = resolve_safe_storage_path(
            upload_root=upload_root,
            relative_path=Path(row.storage_path),
        )
    except RequestValidationError:
        return ImageResolution(normalized_key, row, None, "invalid_path")
    if not file_path.exists() or not file_path.is_file():
        return ImageResolution(normalized_key, row, None, "missing_file")
    return ImageResolution(normalized_key, row, file_path, None)


def resolve_admin_preview(
    *,
    row: SharedImageAsset,
    upload_root: Path,
) -> Path | None:
    if not row.storage_path:
        return None
    try:
        file_path = resolve_safe_storage_path(
            upload_root=upload_root,
            relative_path=Path(row.storage_path),
        )
    except RequestValidationError:
        return None
    if not file_path.exists() or not file_path.is_file():
        return None
    return file_path


def serialize_resolution(resolution: ImageResolution, *, url: str) -> dict[str, Any]:
    row = resolution.asset
    return {
        "requested_key": resolution.requested_key,
        "image_key": row.image_key if row is not None else resolution.requested_key,
        "asset_id": row.id if row is not None else None,
        "url": url,
        "is_fallback": resolution.is_fallback,
        "fallback_reason": resolution.fallback_reason,
        "is_enabled": bool(row.is_enabled) if row is not None else False,
        "mime_type": (
            "image/svg+xml"
            if resolution.is_fallback
            else row.mime_type if row is not None else "image/svg+xml"
        ),
        "updated_at": row.updated_at.isoformat() if row is not None and row.updated_at else None,
    }


def remove_storage_file(*, upload_root: Path, storage_path: str | None) -> None:
    if not storage_path:
        return
    try:
        file_path = resolve_safe_storage_path(
            upload_root=upload_root,
            relative_path=Path(storage_path),
        )
    except RequestValidationError:
        return
    if not file_path.exists() or not file_path.is_file():
        return
    try:
        file_path.unlink()
    except OSError:
        return


def _persist_upload(
    *,
    image_key: str,
    validated_upload: MediaUploadValidationResult,
    upload_root: Path,
) -> str:
    relative_path = (
        Path("image_library")
        / image_key
        / validated_upload.storage_filename
    )
    file_path = resolve_safe_storage_path(
        upload_root=upload_root,
        relative_path=relative_path,
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(validated_upload.content)
    return str(relative_path).replace("\\", "/")


def _apply_upload_metadata(
    row: SharedImageAsset,
    *,
    validated_upload: MediaUploadValidationResult,
    storage_path: str,
) -> None:
    row.filename = validated_upload.safe_original_filename
    row.mime_type = validated_upload.mime_type
    row.storage_path = storage_path
    row.sha256 = validated_upload.sha256
    row.size_bytes = validated_upload.size_bytes
