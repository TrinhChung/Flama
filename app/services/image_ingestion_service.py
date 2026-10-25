"""Unified Image Ingestion Service for Flama."""

from __future__ import annotations

import base64
from hashlib import sha256
from io import BytesIO
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.services import quota_service
from app.services.image_processor import process_image_preset
from app.services.image_queue_service import enqueue_image_job
from app.services.image_security_service import (
    ImageSecurityError,
    report_security_threat,
    validate_image_security,
)
from app.services.image_worker_service import process_single_image_asset
from app.services.remote_image_fetcher import _normalize_remote_url, _resolve_remote_target
from app.validators import RequestValidationError, resolve_safe_storage_path
from models import db
from models.image_asset import ImageAsset

logger = logging.getLogger(__name__)


def _default_upload_root() -> Path:
    if current_app:
        return Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    return Path("static/uploads/flashcard_media").resolve()


def ingest_image(
    *,
    user_id: int | None = None,
    source_type: str = "upload",
    file: Any = None,
    source_url: str | None = None,
    base64_data: str | bytes | None = None,
    filename: str | None = None,
    usage_type: str = "general",
    preset: str | None = None,
    upload_root: Path | None = None,
    max_bytes: int | None = None,
    max_pixels: int = 25_000_000,
    source_ip: str | None = None,
    async_process: bool = True,
    deduplicate: bool = True,
) -> ImageAsset:
    """Universal ingestion entry point for any image in Flama.

    Guarantees:
    - Zero trust on client-sent MIME / extension.
    - Anti-SSRF check on remote URLs before network connection.
    - Magic byte, dimensions, decompression bomb, and active payload checks.
    - Re-encode to clean, metadata-stripped WebP.
    - Safe temporary display for public URLs + async worker synchronization.
    """
    root = (upload_root or _default_upload_root()).resolve()
    limit_bytes = int(
        max_bytes
        or (current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024) if current_app else 10 * 1024 * 1024)
    )

    has_file = bool(file is not None and getattr(file, "filename", ""))
    clean_url = str(source_url or "").strip()
    has_b64 = bool(base64_data)

    sources_count = int(has_file) + int(bool(clean_url)) + int(has_b64)
    if sources_count == 0:
        raise RequestValidationError(
            "Vui lòng cung cấp một nguồn hình ảnh (tệp tải lên, link URL hoặc base64).",
            field="image",
            code="IMAGE_SOURCE_REQUIRED",
            status=400,
        )
    if sources_count > 1:
        raise RequestValidationError(
            "Chỉ được cung cấp một nguồn hình ảnh duy nhất cho mỗi yêu cầu.",
            field="image",
            code="IMAGE_MULTIPLE_SOURCES",
            status=400,
        )

    # -------------------------------------------------------------
    # CASE 1: External Public URL
    # -------------------------------------------------------------
    if clean_url:
        try:
            normalized_url = _normalize_remote_url(clean_url)
            # Pre-validate target DNS & SSRF address invariants
            _resolve_remote_target(normalized_url)
        except RequestValidationError as exc:
            if exc.code in {
                "IMAGE_REMOTE_HOST_NOT_ALLOWED",
                "IMAGE_REMOTE_DNS_FAILED",
                "IMAGE_REMOTE_PORT_NOT_ALLOWED",
                "IMAGE_REMOTE_SCHEME_NOT_ALLOWED",
            }:
                report_security_threat(
                    user_id=user_id,
                    threat_type="ssrf_attempt",
                    severity="high",
                    message=f"Phát hiện URL vi phạm chính sách bảo vệ SSRF: {exc}",
                    source_ip=source_ip,
                    source_url=clean_url,
                    details={"code": exc.code, "error": str(exc)},
                )
                raise ImageSecurityError(
                    f"Link hình ảnh không hợp lệ hoặc trỏ đến địa chỉ mạng bị cấm: {exc}",
                    threat_type="ssrf_attempt",
                    field="source_url",
                    status=400,
                    code="IMAGE_SSRF_DETECTED",
                ) from exc
            raise

        asset = ImageAsset(
            owner_user_id=user_id,
            source_type="external_url",
            source_url=normalized_url,
            display_url=normalized_url,  # Temporary display URL for immediate frontend UX
            usage_type=usage_type,
            preset=preset,
            processing_status="pending",
            security_status="safe",
        )
        db.session.add(asset)
        db.session.commit()

        if async_process:
            enqueue_image_job(
                asset.id,
                source_url=normalized_url,
                usage_type=usage_type,
                preset=preset,
            )
        else:
            process_single_image_asset(
                asset.id,
                upload_root=root,
                max_bytes=limit_bytes,
                max_pixels=max_pixels,
            )
        return asset

    # -------------------------------------------------------------
    # CASE 2: Uploaded File or Base64 Payload
    # -------------------------------------------------------------
    raw_bytes: bytes
    orig_fn: str

    if has_file:
        raw_bytes = file.read()
        orig_fn = secure_filename(getattr(file, "filename", "upload")) or "upload"
    else:
        orig_fn = filename or "base64_image"
        if isinstance(base64_data, str):
            b64_str = base64_data.strip()
            if "," in b64_str and "base64" in b64_str.split(",", 1)[0]:
                b64_str = b64_str.split(",", 1)[1]
            try:
                raw_bytes = base64.b64decode(b64_str, validate=True)
            except Exception as exc:
                raise RequestValidationError(
                    "Dữ liệu ảnh base64 không hợp lệ.",
                    field="base64_data",
                    code="IMAGE_BASE64_INVALID",
                    status=400,
                ) from exc
        elif isinstance(base64_data, bytes):
            raw_bytes = base64_data
        else:
            raise RequestValidationError("Dữ liệu ảnh không hợp lệ.", field="base64_data")

    # Perform thorough security validation
    detected_mime, orig_w, orig_h = validate_image_security(
        raw_bytes,
        filename=orig_fn,
        max_bytes=limit_bytes,
        max_pixels=max_pixels,
        user_id=user_id,
        source_ip=source_ip,
    )

    # Deduplication check if existing ready asset has identical SHA-256
    raw_digest = sha256(raw_bytes).hexdigest()
    if deduplicate:
        existing = ImageAsset.query.filter_by(
            sha256=raw_digest,
            usage_type=usage_type,
            processing_status="ready",
        ).first()
        if existing and existing.storage_path:
            full_path = resolve_safe_storage_path(
                upload_root=root,
                relative_path=Path(existing.storage_path),
            )
            if full_path.exists() and full_path.is_file():
                return existing

    # Transform and optimize immediately to clean WebP
    processed = process_image_preset(
        raw_bytes,
        preset_name=preset,
        usage_type=usage_type,
    )

    asset_id = str(uuid4())
    relative_path = Path("assets") / asset_id / f"{processed.sha256[:16]}.webp"
    managed_path = resolve_safe_storage_path(
        upload_root=root,
        relative_path=relative_path,
    )
    quota = quota_service.consume_media(user_id, processed.size_bytes)
    if not quota.allowed:
        raise RequestValidationError(quota.message, field="image", code="MEDIA_QUOTA_EXCEEDED", status=429)
    managed_path.parent.mkdir(parents=True, exist_ok=True)
    managed_path.write_bytes(processed.content)

    managed_url = f"/media/asset/{asset_id}"
    asset = ImageAsset(
        id=asset_id,
        owner_user_id=user_id,
        source_type="upload" if has_file else "base64",
        source_url=None,
        display_url=managed_url,
        managed_url=managed_url,
        storage_path=str(relative_path).replace("\\", "/"),
        original_filename=orig_fn,
        original_mime_type=detected_mime,
        output_mime_type=processed.mime_type,
        original_width=orig_w,
        original_height=orig_h,
        output_width=processed.width,
        output_height=processed.height,
        original_size_bytes=len(raw_bytes),
        output_size_bytes=processed.size_bytes,
        usage_type=usage_type,
        preset=preset,
        processing_status="ready",
        security_status="safe",
        sha256=processed.sha256,
    )
    db.session.add(asset)
    db.session.commit()
    return asset
