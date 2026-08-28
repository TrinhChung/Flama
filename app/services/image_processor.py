"""Image transformation, preset-based resizing, metadata stripping and WebP optimization."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import logging
from typing import Literal

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImagePreset:
    name: str
    max_width: int
    max_height: int
    crop_mode: Literal["fit", "square_crop", "cover_crop"]
    quality: int
    lossless_alpha: bool = False


PRESETS: dict[str, ImagePreset] = {
    "avatar": ImagePreset(
        name="avatar",
        max_width=256,
        max_height=256,
        crop_mode="square_crop",
        quality=85,
    ),
    "avatar_hd": ImagePreset(
        name="avatar_hd",
        max_width=512,
        max_height=512,
        crop_mode="square_crop",
        quality=85,
    ),
    "deck_cover": ImagePreset(
        name="deck_cover",
        max_width=1200,
        max_height=675,
        crop_mode="cover_crop",
        quality=85,
    ),
    "note_image": ImagePreset(
        name="note_image",
        max_width=1600,
        max_height=1600,
        crop_mode="fit",
        quality=90,
        lossless_alpha=True,
    ),
    "image_library": ImagePreset(
        name="image_library",
        max_width=2048,
        max_height=2048,
        crop_mode="fit",
        quality=90,
    ),
    "thumbnail": ImagePreset(
        name="thumbnail",
        max_width=256,
        max_height=256,
        crop_mode="fit",
        quality=80,
    ),
    "general": ImagePreset(
        name="general",
        max_width=1920,
        max_height=1080,
        crop_mode="fit",
        quality=85,
    ),
}

USAGE_TYPE_DEFAULT_PRESETS: dict[str, str] = {
    "avatar": "avatar",
    "deck_cover": "deck_cover",
    "marketplace": "deck_cover",
    "note_image": "note_image",
    "flashcard_media": "note_image",
    "image_library": "image_library",
    "general": "general",
}


@dataclass(frozen=True)
class ProcessedImageResult:
    content: bytes
    mime_type: str
    width: int
    height: int
    sha256: str
    size_bytes: int


def resolve_preset(preset_name: str | None, usage_type: str | None) -> ImagePreset:
    if preset_name and preset_name in PRESETS:
        return PRESETS[preset_name]
    norm_usage = str(usage_type or "general").strip().lower()
    default_preset_name = USAGE_TYPE_DEFAULT_PRESETS.get(norm_usage, "general")
    return PRESETS.get(default_preset_name, PRESETS["general"])


def _apply_square_crop(image: Image.Image, size: int) -> Image.Image:
    """Center square crop and resize."""
    width, height = image.size
    min_dim = min(width, height)
    left = (width - min_dim) // 2
    top = (height - min_dim) // 2
    right = left + min_dim
    bottom = top + min_dim
    cropped = image.crop((left, top, right, bottom))
    if min_dim > size:
        return cropped.resize((size, size), Image.Resampling.LANCZOS)
    return cropped


def _apply_cover_crop(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Aspect-ratio cover crop and resize."""
    width, height = image.size
    target_aspect = target_w / target_h
    current_aspect = width / height

    if current_aspect > target_aspect:
        # Image is wider: crop sides
        new_width = int(height * target_aspect)
        left = (width - new_width) // 2
        cropped = image.crop((left, 0, left + new_width, height))
    else:
        # Image is taller: crop top/bottom
        new_height = int(width / target_aspect)
        top = (height - new_height) // 2
        cropped = image.crop((0, top, width, top + new_height))

    if cropped.width > target_w or cropped.height > target_h:
        return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
    return cropped


def _apply_fit_resize(image: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Fit inside bounding box maintaining original aspect ratio without upscaling."""
    width, height = image.size
    if width <= max_w and height <= max_h:
        return image

    scale = min(max_w / width, max_h / height)
    new_w = max(1, int(width * scale))
    new_h = max(1, int(height * scale))
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)


def process_image_preset(
    raw_bytes: bytes,
    *,
    preset_name: str | None = None,
    usage_type: str = "general",
) -> ProcessedImageResult:
    """Decode, auto-orient, strip metadata, resize by preset, and re-encode to clean WebP."""
    preset = resolve_preset(preset_name, usage_type)

    with Image.open(BytesIO(raw_bytes)) as decoded:
        decoded.seek(0)
        decoded.load()

        # 1. Auto-orient according to EXIF
        normalized = ImageOps.exif_transpose(decoded)

        # 2. Check for alpha transparency
        has_alpha = normalized.mode in {"RGBA", "LA"} or (
            normalized.mode == "P" and "transparency" in normalized.info
        )

        # 3. Apply sizing and crop according to preset
        if preset.crop_mode == "square_crop":
            resized = _apply_square_crop(normalized, preset.max_width)
        elif preset.crop_mode == "cover_crop":
            resized = _apply_cover_crop(normalized, preset.max_width, preset.max_height)
        else:
            resized = _apply_fit_resize(normalized, preset.max_width, preset.max_height)

        # 4. Color mode conversion for safe WebP encoding
        clean_image = resized.convert("RGBA" if has_alpha else "RGB")

        # 5. Encode clean WebP (dropping all original metadata)
        output_io = BytesIO()
        use_lossless = bool(has_alpha and preset.lossless_alpha)
        clean_image.save(
            output_io,
            format="WEBP",
            method=6,
            quality=preset.quality,
            lossless=use_lossless,
        )

        processed_bytes = output_io.getvalue()
        final_width, final_height = clean_image.size
        digest = sha256(processed_bytes).hexdigest()

    return ProcessedImageResult(
        content=processed_bytes,
        mime_type="image/webp",
        width=final_width,
        height=final_height,
        sha256=digest,
        size_bytes=len(processed_bytes),
    )
