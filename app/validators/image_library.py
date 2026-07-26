from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.validators.flashcard_input import RequestValidationError, sanitize_plain_text


MAX_IMAGE_KEY_LENGTH = 120
MAX_IMAGE_DESCRIPTION_LENGTH = 1000
IMAGE_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def normalize_image_key(raw_value: Any, *, required: bool = True) -> str:
    raw_text = unicodedata.normalize("NFKC", str(raw_value or "")).strip().lower()
    normalized = re.sub(r"[\s-]+", "_", raw_text).strip("_")
    if not normalized:
        if required:
            raise RequestValidationError(
                "image_key is required.",
                field="image_key",
            )
        return ""
    if len(normalized) > MAX_IMAGE_KEY_LENGTH:
        raise RequestValidationError(
            f"image_key exceeds max length {MAX_IMAGE_KEY_LENGTH}.",
            field="image_key",
        )
    if not IMAGE_KEY_PATTERN.fullmatch(normalized):
        raise RequestValidationError(
            "image_key may contain only lowercase letters, numbers, and single underscores.",
            field="image_key",
        )
    return normalized


def normalize_image_description(raw_value: Any) -> str:
    return sanitize_plain_text(
        raw_value,
        field_name="description",
        max_length=MAX_IMAGE_DESCRIPTION_LENGTH,
    )


def parse_enabled_value(raw_value: Any, *, default: bool = True) -> bool:
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}
