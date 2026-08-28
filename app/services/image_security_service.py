"""Security validation and threat detection for image ingestion."""

from __future__ import annotations

from io import BytesIO
import logging
from typing import Any
from urllib.parse import urlsplit, urlunsplit
import warnings

from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import SQLAlchemyError

from app.validators import RequestValidationError
from models import db
from models.admin_security_alert import AdminSecurityAlert
from models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# Standard image signatures
SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]

# Signatures / markers of dangerous disguised content
DANGEROUS_PAYLOAD_MARKERS = [
    b"\x4d\x5a",  # MZ executable / DLL
    b"\x7fELF",  # Linux ELF
    b"<?php",
    b"<%",
    b"#!/bin/",
    b"#!/usr/",
    b"<script",
    b"javascript:",
    b"<html",
    b"<iframe",
]


class ImageSecurityError(RequestValidationError):
    """Raised when an image fails security checks or triggers attack detection."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "IMAGE_SECURITY_VIOLATION",
        status: int = 415,
        field: str | None = "image",
        threat_type: str | None = None,
    ) -> None:
        super().__init__(message, status=status, field=field, code=code)
        self.threat_type = threat_type


def sanitize_source_url_for_audit(raw_url: str | None) -> str | None:
    """Strip passwords, tokens, and sensitive query parameters from logged URLs."""
    if not raw_url:
        return None
    try:
        parsed = urlsplit(str(raw_url).strip())
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        # Keep path, strip query params and fragments to avoid logging access tokens
        return urlunsplit((parsed.scheme, netloc, parsed.path or "/", "", ""))
    except Exception:
        return "invalid-url"


def report_security_threat(
    *,
    user_id: int | None = None,
    threat_type: str,
    severity: str = "warning",
    message: str,
    source_ip: str | None = None,
    source_url: str | None = None,
    details: dict[str, Any] | None = None,
) -> AdminSecurityAlert:
    """Create a persistent AdminSecurityAlert and audit log entry."""
    sanitized_url = sanitize_source_url_for_audit(source_url)
    clean_details = dict(details or {})

    logger.warning(
        "Security threat detected [%s, severity=%s]: %s (url=%s, user=%s)",
        threat_type,
        severity,
        message,
        sanitized_url,
        user_id,
    )

    alert = AdminSecurityAlert(
        user_id=user_id,
        severity=severity,
        threat_type=threat_type,
        source_ip=source_ip,
        source_url=sanitized_url,
        message=message,
        details=clean_details,
    )
    db.session.add(alert)
    db.session.add(
        AuditLog(
            user_id=user_id,
            action="security.alert.triggered",
            payload={
                "threat_type": threat_type,
                "severity": severity,
                "message": message,
                "source_url": sanitized_url,
                "details": clean_details,
            },
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("Failed to persist AdminSecurityAlert to database.")
    return alert


def detect_image_mime_from_magic_bytes(raw_bytes: bytes) -> str | None:
    """Detect image MIME type purely from byte signatures."""
    if not raw_bytes:
        return None
    for sig, mime in SIGNATURES:
        if raw_bytes.startswith(sig):
            return mime
    # WebP: RIFF ... WEBP
    if len(raw_bytes) >= 12 and raw_bytes.startswith(b"RIFF") and raw_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_image_security(
    raw_bytes: bytes,
    *,
    filename: str | None = None,
    max_bytes: int = 10 * 1024 * 1024,
    max_pixels: int = 25_000_000,
    user_id: int | None = None,
    source_ip: str | None = None,
    source_url: str | None = None,
    field_name: str = "image",
    allow_svg: bool = False,
) -> tuple[str, int, int]:
    """Validate image bytes against format, polyglot payloads, and decompression bombs.

    Returns:
        (detected_mime_type, width, height)
    """
    if not raw_bytes:
        raise RequestValidationError(
            "Tệp hình ảnh rỗng.",
            field=field_name,
            status=400,
            code="IMAGE_EMPTY",
        )

    if len(raw_bytes) > int(max_bytes):
        raise RequestValidationError(
            f"Hình ảnh vượt quá dung lượng cho phép {int(max_bytes)} bytes.",
            field=field_name,
            status=413,
            code="MEDIA_TOO_LARGE",
        )

    # 1. Polyglot / disguised executable payload check
    prefix_sample = raw_bytes[:1024].lower()
    for marker in DANGEROUS_PAYLOAD_MARKERS:
        if marker.lower() in prefix_sample:
            report_security_threat(
                user_id=user_id,
                threat_type="disguised_file",
                severity="high",
                message=f"Phát hiện tệp giả mạo có chứa payload nguy hiểm: {marker.decode('latin1', errors='replace')}",
                source_ip=source_ip,
                source_url=source_url,
                details={"filename": filename, "size_bytes": len(raw_bytes), "matched_marker": marker.decode('latin1', errors='replace')},
            )
            raise ImageSecurityError(
                "Tệp không phải là hình ảnh hợp lệ hoặc chứa mã không an toàn.",
                threat_type="disguised_file",
                field=field_name,
                status=415,
                code="IMAGE_DISGUISED_PAYLOAD",
            )

    # 2. Magic byte check
    detected_mime = detect_image_mime_from_magic_bytes(raw_bytes)
    if not detected_mime:
        if allow_svg and b"<svg" in prefix_sample:
            detected_mime = "image/svg+xml"
        else:
            report_security_threat(
                user_id=user_id,
                threat_type="disguised_file",
                severity="warning",
                message="Tệp tải lên không có header định dạng ảnh hợp lệ (chỉ chấp nhận JPEG, PNG, WebP, GIF).",
                source_ip=source_ip,
                source_url=source_url,
                details={"filename": filename, "size_bytes": len(raw_bytes)},
            )
            raise ImageSecurityError(
                "Định dạng tệp không được hỗ trợ hoặc không phải là hình ảnh hợp lệ.",
                threat_type="disguised_file",
                field=field_name,
                status=415,
                code="IMAGE_INVALID_MAGIC_BYTES",
            )

    if detected_mime == "image/svg+xml":
        if not allow_svg:
            report_security_threat(
                user_id=user_id,
                threat_type="unsafe_svg",
                severity="warning",
                message="Người dùng cố tình tải lên định dạng SVG trong luồng không cho phép.",
                source_ip=source_ip,
                source_url=source_url,
                details={"filename": filename},
            )
            raise ImageSecurityError(
                "Không hỗ trợ tệp định dạng SVG.",
                threat_type="unsafe_svg",
                field=field_name,
                status=415,
                code="IMAGE_SVG_NOT_ALLOWED",
            )
        return detected_mime, 0, 0

    # 3. Pillow Decoder + Decompression Bomb Detection
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw_bytes)) as probe:
                width, height = probe.size
                if width < 1 or height < 1:
                    raise ImageSecurityError(
                        "Kích thước pixel của hình ảnh không hợp lệ.",
                        threat_type="disguised_file",
                        field=field_name,
                        status=415,
                        code="IMAGE_DIMENSIONS_INVALID",
                    )
                pixels = width * height
                if pixels > int(max_pixels):
                    report_security_threat(
                        user_id=user_id,
                        threat_type="decompression_bomb",
                        severity="high",
                        message=f"Phát hiện ảnh có số lượng pixel quá lớn ({width}x{height} = {pixels:,} pixels > {max_pixels:,}).",
                        source_ip=source_ip,
                        source_url=source_url,
                        details={"width": width, "height": height, "pixels": pixels, "max_pixels": max_pixels},
                    )
                    raise ImageSecurityError(
                        f"Kích thước ảnh vượt quá giới hạn tối đa {int(max_pixels):,} pixels.",
                        threat_type="decompression_bomb",
                        field=field_name,
                        status=413,
                        code="IMAGE_DIMENSIONS_TOO_LARGE",
                    )
                probe.verify()

            # Load actual image data to ensure complete raster validity
            with Image.open(BytesIO(raw_bytes)) as decoded:
                decoded.seek(0)
                decoded.load()
                actual_width, actual_height = decoded.size

        return detected_mime, actual_width, actual_height

    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as bomb_exc:
        report_security_threat(
            user_id=user_id,
            threat_type="decompression_bomb",
            severity="critical",
            message=f"Phát hiện tấn công Image Decompression Bomb: {bomb_exc}",
            source_ip=source_ip,
            source_url=source_url,
            details={"filename": filename, "error": str(bomb_exc)},
        )
        raise ImageSecurityError(
            "Hình ảnh bị từ chối do có dấu hiệu Image Decompression Bomb.",
            threat_type="decompression_bomb",
            field=field_name,
            status=413,
            code="IMAGE_DECOMPRESSION_BOMB",
        ) from bomb_exc

    except ImageSecurityError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as decode_err:
        report_security_threat(
            user_id=user_id,
            threat_type="disguised_file",
            severity="warning",
            message=f"Không thể giải mã dữ liệu hình ảnh (có thể là tệp giả mạo hoặc hỏng): {decode_err}",
            source_ip=source_ip,
            source_url=source_url,
            details={"filename": filename, "error": str(decode_err)},
        )
        raise ImageSecurityError(
            "Không thể giải mã hình ảnh an toàn.",
            threat_type="disguised_file",
            field=field_name,
            status=415,
            code="IMAGE_DECODE_INVALID",
        ) from decode_err
