"""Decode and re-encode image uploads before they enter shared storage."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app.validators import MediaUploadValidationResult, RequestValidationError


RASTER_MIME_TYPES = {
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def sanitize_shared_image(
    validated_upload: MediaUploadValidationResult,
    *,
    max_bytes: int,
    max_pixels: int,
) -> MediaUploadValidationResult:
    """Return a canonical image with metadata and trailing payloads removed.

    SVG inputs have already passed the strict XML validator. Raster inputs are
    fully decoded and encoded again as a fresh WebP file, which drops EXIF,
    comments, appended/polyglot bytes, animation payloads, and unknown chunks.
    """

    if validated_upload.mime_type not in RASTER_MIME_TYPES:
        return validated_upload

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(validated_upload.content)) as probe:
                width, height = probe.size
                if width < 1 or height < 1:
                    raise RequestValidationError(
                        "Kích thước hình ảnh không hợp lệ.",
                        field="file",
                        status=415,
                        code="IMAGE_DECODE_INVALID",
                    )
                if width * height > int(max_pixels):
                    raise RequestValidationError(
                        f"Hình ảnh vượt quá giới hạn {int(max_pixels)} pixels.",
                        field="file",
                        status=413,
                        code="IMAGE_DIMENSIONS_TOO_LARGE",
                    )
                probe.verify()

            with Image.open(BytesIO(validated_upload.content)) as decoded:
                decoded.seek(0)
                decoded.load()
                normalized = ImageOps.exif_transpose(decoded)
                has_alpha = normalized.mode in {"RGBA", "LA"} or (
                    normalized.mode == "P" and "transparency" in normalized.info
                )
                clean_image = normalized.convert("RGBA" if has_alpha else "RGB")
                output = BytesIO()
                clean_image.save(
                    output,
                    format="WEBP",
                    method=6,
                    quality=90,
                    lossless=has_alpha,
                )
    except RequestValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as exc:
        raise RequestValidationError(
            "Không thể giải mã hình ảnh an toàn.",
            field="file",
            status=415,
            code="IMAGE_DECODE_INVALID",
        ) from exc

    sanitized_content = output.getvalue()
    if not sanitized_content:
        raise RequestValidationError(
            "Không thể tạo bản hình ảnh an toàn.",
            field="file",
            status=415,
            code="IMAGE_DECODE_INVALID",
        )
    if len(sanitized_content) > int(max_bytes):
        raise RequestValidationError(
            f"Hình ảnh sau khi làm sạch vượt quá {int(max_bytes)} bytes.",
            field="file",
            status=413,
            code="MEDIA_TOO_LARGE",
        )

    digest = sha256(sanitized_content).hexdigest()
    original_stem = secure_filename(
        Path(validated_upload.safe_original_filename).stem
    )[:200]
    safe_original_filename = f"{original_stem or 'image'}.webp"
    return MediaUploadValidationResult(
        field_name=validated_upload.field_name,
        safe_original_filename=safe_original_filename,
        storage_filename=f"{uuid4().hex}_{digest[:12]}.webp",
        content=sanitized_content,
        mime_type="image/webp",
        size_bytes=len(sanitized_content),
        sha256=digest,
    )
