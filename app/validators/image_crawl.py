"""Request validation helpers for image crawling and media processing."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from app.validators.flashcard_input import (
    MAX_FIELD_NAME_LENGTH,
    MAX_MARKDOWN_LENGTH,
    RequestValidationError,
    sanitize_markdown_text,
    sanitize_plain_text,
)

MAX_URL_LENGTH = 2048
MAX_PAGE_IMAGES_LIMIT = 50
DEFAULT_PAGE_IMAGES_LIMIT = 20
ALLOWED_URL_SCHEMES = {"http", "https"}


def validate_crawl_url(raw_url: Any, *, field_name: str = "url") -> str:
    """Validate and normalize a remote URL for image crawling."""
    value = str(raw_url or "").strip()
    if not value:
        raise RequestValidationError(
            "URL không được để trống.",
            field=field_name,
            status=400,
            code="IMAGE_URL_REQUIRED",
        )
    if len(value) > MAX_URL_LENGTH:
        raise RequestValidationError(
            f"URL vượt quá độ dài tối đa {MAX_URL_LENGTH} ký tự.",
            field=field_name,
            status=400,
            code="IMAGE_URL_TOO_LONG",
        )
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise RequestValidationError(
            "URL chứa ký tự điều khiển không hợp lệ.",
            field=field_name,
            status=400,
            code="IMAGE_URL_INVALID",
        )

    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise RequestValidationError(
            "URL không hợp lệ.",
            field=field_name,
            status=400,
            code="IMAGE_URL_INVALID",
        ) from exc

    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_URL_SCHEMES:
        raise RequestValidationError(
            "Chỉ hỗ trợ URL giao thức HTTP hoặc HTTPS.",
            field=field_name,
            status=400,
            code="IMAGE_SCHEME_NOT_ALLOWED",
        )

    hostname = (parsed.hostname or "").strip()
    if not hostname:
        raise RequestValidationError(
            "URL thiếu hostname hợp lệ.",
            field=field_name,
            status=400,
            code="IMAGE_URL_INVALID",
        )

    if hostname.lower() in {"localhost", "127.0.0.1", "0.0.0.0"} or hostname.lower().endswith(".local"):
        raise RequestValidationError(
            "Không cho phép tải hình ảnh từ địa chỉ mạng nội bộ.",
            field=field_name,
            status=400,
            code="IMAGE_REMOTE_HOST_NOT_ALLOWED",
        )

    return value


def validate_note_media_crawl_request(payload: Any) -> dict[str, Any]:
    """Validate single note media crawl payload."""
    if not isinstance(payload, dict):
        raise RequestValidationError("Payload must be a JSON object.", field="body")

    url = validate_crawl_url(payload.get("url") or payload.get("source_url"), field_name="url")
    field_name = sanitize_plain_text(
        payload.get("field_name"),
        field_name="field_name",
        max_length=MAX_FIELD_NAME_LENGTH,
    )
    if not field_name:
        raise RequestValidationError("field_name is required.", field="field_name")

    markdown_inline = bool(payload.get("markdown_inline", False))

    return {
        "url": url,
        "field_name": field_name,
        "markdown_inline": markdown_inline,
    }


def validate_batch_media_crawl_request(payload: Any) -> list[dict[str, Any]]:
    """Validate batch note media crawl payload."""
    if not isinstance(payload, dict) and not isinstance(payload, list):
        raise RequestValidationError("Payload must be a JSON object or array.", field="body")

    items_raw = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items_raw, list):
        raise RequestValidationError("Batch items must be an array.", field="items")

    if not items_raw:
        raise RequestValidationError("Batch items cannot be empty.", field="items")

    if len(items_raw) > 50:
        raise RequestValidationError("Batch cannot exceed 50 items per request.", field="items")

    validated_items: list[dict[str, Any]] = []
    for idx, item in enumerate(items_raw):
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id") if item.get("item_id") is not None else idx)
        raw_note_id = str(item.get("note_id") or "").strip()
        raw_field_name = str(item.get("field_name") or "").strip()
        raw_url = str(item.get("url") or item.get("source_url") or "").strip()
        markdown_inline = bool(item.get("markdown_inline", False))

        validated_items.append({
            "item_id": item_id,
            "note_id": raw_note_id,
            "field_name": raw_field_name,
            "url": raw_url,
            "markdown_inline": markdown_inline,
        })

    return validated_items


def validate_markdown_crawl_request(payload: Any) -> dict[str, Any]:
    """Validate markdown text image crawling and rewrite request."""
    if not isinstance(payload, dict):
        raise RequestValidationError("Payload must be a JSON object.", field="body")

    raw_markdown = payload.get("markdown") or payload.get("content") or ""
    if not isinstance(raw_markdown, str):
        raise RequestValidationError("markdown must be a string.", field="markdown")

    cleaned_markdown = sanitize_markdown_text(
        raw_markdown,
        field_name="markdown",
        max_length=MAX_MARKDOWN_LENGTH,
    )

    return {
        "markdown": cleaned_markdown,
    }


def validate_page_crawl_request(payload: Any) -> dict[str, Any]:
    """Validate webpage image extraction request."""
    if not isinstance(payload, dict):
        raise RequestValidationError("Payload must be a JSON object.", field="body")

    page_url = validate_crawl_url(
        payload.get("page_url") or payload.get("url"),
        field_name="page_url",
    )

    max_images = payload.get("max_images", DEFAULT_PAGE_IMAGES_LIMIT)
    try:
        max_images_int = int(max_images)
    except (TypeError, ValueError):
        max_images_int = DEFAULT_PAGE_IMAGES_LIMIT

    max_images_int = max(1, min(max_images_int, MAX_PAGE_IMAGES_LIMIT))

    return {
        "page_url": page_url,
        "max_images": max_images_int,
    }
