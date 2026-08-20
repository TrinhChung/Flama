from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.validators.flashcard_input import RequestValidationError, sanitize_plain_text


MAX_IMAGE_KEY_LENGTH = 120
MAX_IMAGE_DESCRIPTION_LENGTH = 1000
MAX_IMAGE_TAGS_COUNT = 50
MAX_IMAGE_TAG_LENGTH = 100
IMAGE_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
TAG_CLEAN_PATTERN = re.compile(r"[^a-z0-9_ -]+")


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


def normalize_image_tags(raw_tags: Any) -> list[str]:
    """Normalize English tags for shared image assets (lowercase, trimmed, deduplicated)."""
    if raw_tags is None:
        return []

    candidates: list[Any] = []
    if isinstance(raw_tags, str):
        text = raw_tags.strip()
        if text.startswith("[") and text.endswith("]"):
            import json
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    candidates = parsed
                else:
                    candidates = [text]
            except Exception:
                candidates = text.replace(";", ",").split(",")
        else:
            candidates = text.replace(";", ",").split(",")
    elif isinstance(raw_tags, (list, tuple, set)):
        candidates = list(raw_tags)
    else:
        raise RequestValidationError("tags must be a list or comma-separated string.", field="tags")

    normalized_tags: list[str] = []
    seen: set[str] = set()

    for item in candidates:
        if item is None:
            continue
        cleaned = unicodedata.normalize("NFKC", str(item)).strip().lower()
        cleaned = re.sub(r"[\s_]+", " ", cleaned).strip()
        cleaned = TAG_CLEAN_PATTERN.sub("", cleaned).strip()
        if not cleaned:
            continue
        if len(cleaned) > MAX_IMAGE_TAG_LENGTH:
            cleaned = cleaned[:MAX_IMAGE_TAG_LENGTH].strip()
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized_tags.append(cleaned)
        if len(normalized_tags) >= MAX_IMAGE_TAGS_COUNT:
            break

    return normalized_tags


def derive_image_key(
    candidate: Any = None,
    *,
    tags: list[str] | None = None,
    filename: str | None = None,
) -> str:
    """Derive a valid image_key from candidate, tags, or filename."""
    if candidate:
        try:
            return normalize_image_key(candidate, required=True)
        except RequestValidationError:
            pass

    if tags:
        for tag in tags:
            try:
                candidate_tag = re.sub(r"[\s-]+", "_", tag).strip("_")
                return normalize_image_key(candidate_tag, required=True)
            except RequestValidationError:
                continue

    if filename:
        from pathlib import Path
        stem = Path(filename).stem
        cleaned_stem = re.sub(r"[\s-]+", "_", stem).strip("_")
        try:
            return normalize_image_key(cleaned_stem[:MAX_IMAGE_KEY_LENGTH], required=True)
        except RequestValidationError:
            pass

    from uuid import uuid4
    return f"img_{uuid4().hex[:12]}"


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
