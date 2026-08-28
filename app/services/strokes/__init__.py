"""Strokes domain services package."""

from app.services.strokes.cjk_extractor import CjkExtractor, is_cjk_ideograph
from app.services.strokes.dataset_builder import (
    build_dataset_from_directory,
    populate_starter_strokes,
    sanitize_stroke_svg,
)
from app.services.strokes.stroke_service import (
    StrokeServiceError,
    batch_generate_strokes,
    check_stroke_svg_exists,
    normalize_locale,
    resolve_stroke_items,
)

__all__ = [
    "CjkExtractor",
    "is_cjk_ideograph",
    "sanitize_stroke_svg",
    "build_dataset_from_directory",
    "populate_starter_strokes",
    "StrokeServiceError",
    "resolve_stroke_items",
    "batch_generate_strokes",
    "check_stroke_svg_exists",
    "normalize_locale",
]
