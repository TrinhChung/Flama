from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

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
    derive_image_key,
    normalize_image_description,
    normalize_image_key,
    normalize_image_tags,
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
    uploaded: Any = None,
    *,
    source_url: str = "",
    file_data: str | bytes | None = None,
    filename: str | None = None,
    max_bytes: int,
    max_pixels: int,
    remote_timeout_seconds: float,
    remote_max_redirects: int,
    scanner: Callable[[bytes], Any] | None = None,
    scan_enabled: bool = False,
) -> MediaUploadValidationResult | None:
    """Resolve one local/clipboard upload, base64 payload, or remote URL into a clean image."""

    has_upload = bool(uploaded is not None and getattr(uploaded, "filename", ""))
    normalized_source_url = str(source_url or "").strip()
    has_file_data = bool(file_data)
    sources_count = int(has_upload) + int(bool(normalized_source_url)) + int(has_file_data)
    if sources_count > 1:
        raise RequestValidationError(
            "Chỉ chọn một nguồn ảnh: tệp tải lên, link hình ảnh, hoặc dữ liệu ảnh base64.",
            field="source_url" if normalized_source_url else "image",
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
    elif has_file_data:
        raw_bytes: bytes
        if isinstance(file_data, str):
            b64_str = file_data.strip()
            if "," in b64_str and "base64" in b64_str.split(",", 1)[0]:
                b64_str = b64_str.split(",", 1)[1]
            try:
                raw_bytes = base64.b64decode(b64_str, validate=True)
            except Exception as exc:
                raise RequestValidationError("Dữ liệu ảnh base64 không hợp lệ.", field="file_data") from exc
        elif isinstance(file_data, bytes):
            raw_bytes = file_data
        else:
            raise RequestValidationError("Dữ liệu ảnh không hợp lệ.", field="file_data")

        if len(raw_bytes) > max_bytes:
            raise RequestValidationError(
                f"Dữ liệu ảnh vượt quá {int(max_bytes)} bytes.",
                field="file_data",
                status=413,
                code="MEDIA_TOO_LARGE",
            )

        detected_mime = "image/png"
        detected_ext = "png"
        if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            detected_mime, detected_ext = "image/png", "png"
        elif raw_bytes.startswith(b"\xff\xd8\xff"):
            detected_mime, detected_ext = "image/jpeg", "jpg"
        elif raw_bytes.startswith((b"GIF87a", b"GIF89a")):
            detected_mime, detected_ext = "image/gif", "gif"
        elif len(raw_bytes) >= 12 and raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP":
            detected_mime, detected_ext = "image/webp", "webp"
        elif b"<svg" in raw_bytes[:500].lower():
            detected_mime, detected_ext = "image/svg+xml", "svg"

        safe_fn = filename or f"upload.{detected_ext}"
        if not any(safe_fn.lower().endswith(f".{ext}") for ext in ("png", "jpg", "jpeg", "webp", "gif", "svg")):
            safe_fn = f"{safe_fn}.{detected_ext}"

        resolved_upload = FileStorage(
            stream=BytesIO(raw_bytes),
            filename=safe_fn,
            content_type=detected_mime,
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
    image_key: str | None = None,
    description: str = "",
    is_enabled: bool = True,
    tags: list[str] | str | None = None,
    source_url: str | None = None,
    validated_upload: MediaUploadValidationResult | None = None,
    upload_root: Path,
    actor_user_id: int,
    deduplicate: bool = True,
) -> SharedImageAsset:
    normalized_tags = normalize_image_tags(tags)
    normalized_description = normalize_image_description(description)
    clean_source_url = str(source_url or "").strip() or None

    # Deduplication check via SHA-256 content hash
    if deduplicate and validated_upload is not None and validated_upload.sha256:
        existing = image_library_repository.get_by_sha256(validated_upload.sha256)
        if existing is not None:
            existing_tags = list(existing.tags or [])
            merged_tags = list(dict.fromkeys(existing_tags + normalized_tags))
            tags_changed = merged_tags != existing_tags
            if tags_changed:
                existing.tags = merged_tags
            if clean_source_url and not existing.source_url:
                existing.source_url = clean_source_url
            if normalized_description and not existing.description:
                existing.description = normalized_description
            existing.updated_by_user_id = actor_user_id
            db.session.add(
                AuditLog(
                    user_id=actor_user_id,
                    action="image_library.deduplicate",
                    payload={
                        "image_key": existing.image_key,
                        "merged_tags": normalized_tags,
                        "sha256": existing.sha256,
                    },
                )
            )
            try:
                db.session.commit()
            except SQLAlchemyError as exc:
                db.session.rollback()
                raise ImageLibraryPersistenceError("Could not update deduplicated image asset.") from exc
            setattr(existing, "_is_deduplicated", True)
            return existing

    # Key resolution
    raw_key = str(image_key or "").strip()
    if raw_key:
        normalized_key = normalize_image_key(raw_key, required=True)
        if image_library_repository.get_by_key(normalized_key) is not None:
            raise ImageLibraryConflictError("image_key already exists.")
    else:
        derived = derive_image_key(
            None,
            tags=normalized_tags,
            filename=validated_upload.safe_original_filename if validated_upload else None,
        )
        if image_library_repository.get_by_key(derived) is not None:
            normalized_key = f"{derived}_{uuid4().hex[:6]}"
        else:
            normalized_key = derived

    row = SharedImageAsset(
        image_key=normalized_key,
        description=normalized_description or None,
        is_enabled=bool(is_enabled),
        tags=normalized_tags,
        source_url=clean_source_url,
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
            payload={"image_key": normalized_key, "has_file": validated_upload is not None, "tags": normalized_tags},
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
    setattr(row, "_is_deduplicated", False)
    return row


def update_image(
    *,
    row: SharedImageAsset,
    description: str,
    is_enabled: bool,
    tags: list[str] | str | None = None,
    source_url: str | None = None,
    validated_upload: MediaUploadValidationResult | None = None,
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

    if tags is not None:
        row.tags = normalize_image_tags(tags)
    if source_url is not None:
        row.source_url = str(source_url).strip() or None

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
                "tags": row.tags,
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


def delete_image(
    *,
    row: SharedImageAsset,
    upload_root: Path,
    actor_user_id: int,
) -> None:
    storage_path = row.storage_path
    image_key = row.image_key
    db.session.delete(row)
    db.session.add(
        AuditLog(
            user_id=actor_user_id,
            action="image_library.delete",
            payload={"image_key": image_key, "storage_path": storage_path},
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise ImageLibraryPersistenceError("Could not delete image library entry.") from exc

    if storage_path:
        remove_storage_file(upload_root=upload_root, storage_path=storage_path)


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
        "tags": list(row.tags or []) if row is not None else [],
        "source_url": row.source_url if row is not None else None,
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
