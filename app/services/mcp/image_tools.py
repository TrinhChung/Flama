"""MCP image library and media operations: search, crawl, import, extract."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services import flashcard_content_service
from app.services.media_field_codec import shared_image_store_url
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.note import Note
from models.shared_image_asset import SharedImageAsset

logger = logging.getLogger(__name__)

def serialize_mcp_image_asset(row: SharedImageAsset) -> dict[str, Any]:
    raw_tags = row.tags
    if isinstance(raw_tags, (list, tuple, set)):
        tags_list = [str(t) for t in raw_tags if t is not None]
    elif isinstance(raw_tags, str) and raw_tags.strip().startswith("["):
        try:
            parsed = json.loads(raw_tags)
            tags_list = [str(t) for t in parsed if t is not None] if isinstance(parsed, list) else []
        except Exception:
            tags_list = []
    else:
        tags_list = []

    return {
        "id": str(row.id),
        "asset_id": str(row.id),
        "image_key": str(row.image_key or ""),
        "description": str(row.description or ""),
        "filename": str(row.filename or "") or None,
        "mime_type": str(row.mime_type or "") or None,
        "size_bytes": int(row.size_bytes or 0),
        "sha256": str(row.sha256 or "") or None,
        "is_enabled": bool(row.is_enabled),
        "tags": tags_list,
        "source_url": str(row.source_url or "") or None,
        "url": shared_image_store_url(image_key=row.image_key, asset_id=row.id),
        "preview_url": f"/admin/image-library/{row.id}/preview",
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def import_image(
    *,
    user_id: int,
    url: str | None = None,
    file_data: str | bytes | None = None,
    filename: str | None = None,
    image_key: str | None = None,
    tags: list[str] | str | None = None,
    description: str = "",
    is_enabled: bool = True,
) -> dict[str, Any]:
    from app.services import image_library_service
    from flask import current_app
    from pathlib import Path

    max_bytes = int(
        current_app.config.get(
            "IMAGE_LIBRARY_MAX_BYTES",
            current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 5 * 1024 * 1024),
        )
    )
    max_pixels = int(current_app.config.get("IMAGE_LIBRARY_MAX_PIXELS", 25_000_000))
    remote_timeout = float(current_app.config.get("IMAGE_LIBRARY_REMOTE_FETCH_TIMEOUT_SECONDS", 6))
    remote_redirects = int(current_app.config.get("IMAGE_LIBRARY_REMOTE_FETCH_MAX_REDIRECTS", 3))
    scanner = current_app.config.get("FLASHCARD_MEDIA_SCANNER")
    scan_enabled = bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False))
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()

    validated_upload = image_library_service.prepare_image_upload(
        uploaded=None,
        source_url=url or "",
        file_data=file_data,
        filename=filename,
        max_bytes=max_bytes,
        max_pixels=max_pixels,
        remote_timeout_seconds=remote_timeout,
        remote_max_redirects=remote_redirects,
        scanner=scanner,
        scan_enabled=scan_enabled,
    )

    try:
        row = image_library_service.create_image(
            image_key=image_key,
            description=description,
            is_enabled=is_enabled,
            tags=tags,
            source_url=url,
            validated_upload=validated_upload,
            upload_root=upload_root,
            actor_user_id=user_id,
            deduplicate=True,
        )
    except image_library_service.ImageLibraryConflictError as exc:
        raise RequestValidationError(
            "image_key already exists.",
            field="image_key",
            status=409,
            code="CONFLICT",
        ) from exc
    except image_library_service.ImageLibraryPersistenceError as exc:
        raise RequestValidationError(
            "Không thể lưu hình ảnh vào thư viện.",
            field="image",
            status=500,
            code="PERSISTENCE_ERROR",
        ) from exc

    return {
        "image": serialize_mcp_image_asset(row),
        "is_deduplicated": getattr(row, "_is_deduplicated", False),
    }


def crawl_note_media(
    *,
    user_id: int,
    note_id: str,
    field_name: str,
    url: str,
    markdown_inline: bool = False,
) -> dict[str, Any]:
    """Crawl a remote image from URL and attach it to a note's field with SSRF protection."""
    from app.services import image_crawl_service
    from flask import current_app
    from pathlib import Path

    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    max_bytes = int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024))
    scanner = current_app.config.get("FLASHCARD_MEDIA_SCANNER")
    scan_enabled = bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False))

    try:
        payload, status = image_crawl_service.crawl_and_save_note_media(
            user_id=user_id,
            note_id=note_id,
            field_name=field_name,
            url=url,
            upload_root=upload_root,
            max_bytes=max_bytes,
            scanner=scanner,
            scan_enabled=scan_enabled,
            markdown_inline=markdown_inline,
        )
    except image_crawl_service.ImageCrawlError as exc:
        raise RequestValidationError(
            str(exc),
            field=exc.field or "url",
            status=exc.status,
            code=exc.error,
        ) from exc

    return {
        "success": True,
        "note_id": note_id,
        "field_name": field_name,
        "asset_id": payload.get("asset_id"),
        "url": payload.get("url"),
        "sha256": payload.get("sha256"),
    }


def extract_page_images(
    *,
    user_id: int,
    page_url: str,
    max_images: int = 20,
) -> dict[str, Any]:
    """Crawl a webpage HTML safely and extract candidate image URLs (OpenGraph, Twitter, img tags)."""
    from app.services import image_crawl_service

    try:
        result = image_crawl_service.extract_images_from_page(
            page_url=page_url,
            max_images=max_images,
        )
    except image_crawl_service.ImageCrawlError as exc:
        raise RequestValidationError(
            str(exc),
            field=exc.field or "page_url",
            status=exc.status,
            code=exc.error,
        ) from exc

    return result



def search_images(
    *,
    user_id: int,
    query: str = "",
    tag: str | None = None,
    status: str = "enabled",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    from app.repositories import image_library_repository

    page = (offset // limit) + 1 if limit > 0 else 1
    per_page = limit

    filter_status = status if status in {"enabled", "disabled", "missing_file"} else ""
    if status == "all":
        filter_status = ""

    result = image_library_repository.list_assets(
        search_term=query,
        tag=tag,
        status=filter_status,
        page=page,
        per_page=per_page,
    )

    items = [serialize_mcp_image_asset(row) for row in result.items]
    return {
        "items": items,
        "total": result.total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(items)) < result.total,
    }


def get_image(
    *,
    user_id: int,
    image_key: str | None = None,
    asset_id: str | None = None,
) -> dict[str, Any]:
    from app.repositories import image_library_repository

    row = None
    if image_key:
        row = image_library_repository.get_by_key(image_key)
    if row is None and asset_id:
        row = image_library_repository.get_by_id(asset_id)

    if row is None:
        identifier = image_key or asset_id or "unknown"
        raise RequestValidationError(
            f"Không tìm thấy hình ảnh với key/id: {identifier}.",
            field="image_key" if image_key else "asset_id",
            status=404,
            code="IMAGE_NOT_FOUND",
        )

    return {
        "image": serialize_mcp_image_asset(row),
    }


# ---------------------------------------------------------------------------
