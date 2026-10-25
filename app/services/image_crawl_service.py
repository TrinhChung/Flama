"""Service for crawling, sanitizing, and persisting remote images for flashcards and media."""

from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
import logging
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import urljoin

from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from app.services import deck_working_tree_service, quota_service
from app.services.image_sanitizer import sanitize_shared_image
from app.services.remote_image_fetcher import fetch_remote_html, fetch_remote_image
from app.validators import (
    MediaUploadValidationResult,
    RequestValidationError,
    resolve_safe_storage_path,
    validate_media_upload_request,
)
from app.validators.image_crawl import validate_crawl_url
from models import db
from models.audit_log import AuditLog
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note

logger = logging.getLogger(__name__)

_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^\s\)\"]+)(?:\s+\"([^\"]*)\")?\)")
_HTML_IMG_RE = re.compile(r"""(?i)<img\b([^>]*?)\bsrc=["'](https?://[^"'\s]+)["']([^>]*?)>""")


class ImageCrawlError(ValueError):
    """Exception for errors occurring during remote image crawling."""

    def __init__(
        self,
        error: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error = error
        self.status = int(status)
        self.field = field


class _PageImageExtractor(HTMLParser):
    """Safe HTML parser to extract page title, og:image, and img tags."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.title: str = ""
        self._in_title: bool = False
        self.images: list[dict[str, Any]] = []
        self._seen_urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr_dict = {str(k or "").lower(): str(v or "") for k, v in attrs if k}

        if tag_lower == "title":
            self._in_title = True
        elif tag_lower == "meta":
            prop = attr_dict.get("property", "").lower()
            name = attr_dict.get("name", "").lower()
            content = attr_dict.get("content", "").strip()
            if content and (
                prop in {"og:image", "og:image:url", "og:image:secure_url"}
                or name in {"twitter:image", "twitter:image:src"}
            ):
                abs_url = urljoin(self.base_url, content)
                if abs_url.startswith(("http://", "https://")) and abs_url not in self._seen_urls:
                    self._seen_urls.add(abs_url)
                    self.images.append({
                        "url": abs_url,
                        "alt": attr_dict.get("alt") or "",
                        "source": prop or name,
                    })
        elif tag_lower == "img":
            src = (attr_dict.get("src") or attr_dict.get("data-src") or "").strip()
            if src and not src.startswith("data:"):
                abs_url = urljoin(self.base_url, src)
                if abs_url.startswith(("http://", "https://")) and abs_url not in self._seen_urls:
                    self._seen_urls.add(abs_url)
                    self.images.append({
                        "url": abs_url,
                        "alt": attr_dict.get("alt", "").strip(),
                        "source": "img",
                    })

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = data.strip()


def crawl_remote_image(
    url: str,
    *,
    max_bytes: int = 10 * 1024 * 1024,
    max_pixels: int = 25_000_000,
    timeout_seconds: float = 6.0,
    max_redirects: int = 3,
    field_name: str = "image",
    scanner: Callable[[bytes], Any] | None = None,
    scan_enabled: bool = False,
) -> MediaUploadValidationResult:
    """Download, validate, and sanitize a remote image file from URL with SSRF protection."""
    try:
        validated_url = validate_crawl_url(url, field_name="url")
    except RequestValidationError as exc:
        raise ImageCrawlError(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        ) from exc

    try:
        remote_payload = fetch_remote_image(
            validated_url,
            max_bytes=max_bytes,
            timeout_seconds=timeout_seconds,
            max_redirects=max_redirects,
        )
    except RequestValidationError as exc:
        raise ImageCrawlError(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        ) from exc

    file_storage = FileStorage(
        stream=BytesIO(remote_payload.content),
        filename=remote_payload.filename,
        content_type=remote_payload.mime_type,
    )

    try:
        validated_upload = validate_media_upload_request(
            field_name_raw=field_name,
            field_type="image",
            uploaded=file_storage,
            max_bytes=max_bytes,
            scanner=scanner,
            scan_enabled=scan_enabled,
        )
    except RequestValidationError as exc:
        raise ImageCrawlError(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        ) from exc

    try:
        sanitized_upload = sanitize_shared_image(
            validated_upload,
            max_bytes=max_bytes,
            max_pixels=max_pixels,
        )
    except RequestValidationError as exc:
        raise ImageCrawlError(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        ) from exc

    return sanitized_upload


def extract_images_from_page(
    page_url: str,
    *,
    max_images: int = 20,
    max_bytes: int = 512 * 1024,
    timeout_seconds: float = 6.0,
    max_redirects: int = 3,
) -> dict[str, Any]:
    """Crawl a webpage HTML safely and extract image candidates (OpenGraph, Twitter, img tags)."""
    validated_url = validate_crawl_url(page_url, field_name="page_url")

    try:
        html_content = fetch_remote_html(
            validated_url,
            max_bytes=max_bytes,
            timeout_seconds=timeout_seconds,
            max_redirects=max_redirects,
        )
    except RequestValidationError as exc:
        raise ImageCrawlError(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        ) from exc

    extractor = _PageImageExtractor(base_url=validated_url)
    try:
        extractor.feed(html_content)
    except Exception as exc:
        logger.warning("Failed to parse page HTML for images: %s", exc)

    extracted_images = extractor.images[:max_images]
    return {
        "page_url": validated_url,
        "title": extractor.title,
        "total_found": len(extractor.images),
        "images": extracted_images,
    }


def crawl_and_save_note_media(
    *,
    user_id: int,
    note_id: str,
    field_name: str,
    url: str,
    upload_root: Path,
    max_bytes: int,
    scanner: Callable[[bytes], Any] | None = None,
    scan_enabled: bool = False,
    markdown_inline: bool = False,
) -> tuple[dict[str, Any], int]:
    """Crawl an image from URL and save it as a local MediaAsset for a specific Note."""
    note = Note.query.filter_by(id=note_id, user_id=user_id).first()
    if note is None:
        raise ImageCrawlError("FIELD_NOT_FOUND", "Note not found.", status=404)

    normalized_field_name = str(field_name or "").strip()
    if not normalized_field_name:
        raise ImageCrawlError("VALIDATION_ERROR", "field_name is required.", field="field_name")

    field_def = FieldDef.query.filter_by(
        note_type_id=note.note_type_id,
        name=normalized_field_name,
    ).first()
    if field_def is None:
        raise ImageCrawlError(
            "FIELD_NOT_FOUND",
            "Field not found in note type.",
            status=404,
            field="field_name",
        )

    if markdown_inline:
        if field_def.field_type != "markdown":
            raise ImageCrawlError("VALIDATION_ERROR", "Field is not markdown.", field="field_name")
    else:
        if field_def.field_type not in {"image", "diagram"}:
            raise ImageCrawlError("VALIDATION_ERROR", "Field does not accept image media.", field="field_name")

    sanitized = crawl_remote_image(
        url,
        max_bytes=max_bytes,
        field_name=normalized_field_name,
        scanner=scanner,
        scan_enabled=scan_enabled,
    )

    from app.repositories.media_field_identity_repository import find_note_field_media
    existing = find_note_field_media(
        note_id=note.id,
        field_name=sanitized.field_name,
        sha256=sanitized.sha256,
        note=note,
    )

    if existing:
        if not markdown_inline:
            values = dict(note.field_values or {})
            canonical_url = f"/media/proxy/{existing.id}"
            if values.get(sanitized.field_name) != canonical_url:
                values[sanitized.field_name] = canonical_url
                note.field_values = values
                deck_working_tree_service.mark_note_field_batches_changed(
                    mutations=[
                        {
                            "note": note,
                            "field_names": {sanitized.field_name},
                            "operation": "set",
                        }
                    ],
                )
                db.session.commit()
        payload = _media_payload(existing, source_url=url, include_filename=markdown_inline)
        return payload, 200

    resolved_root = upload_root.resolve()
    relative_path = Path(str(user_id)) / note.id / sanitized.storage_filename
    try:
        full_path = resolve_safe_storage_path(
            upload_root=resolved_root,
            relative_path=relative_path,
        )
    except RequestValidationError as exc:
        raise ImageCrawlError(exc.code, str(exc), status=exc.status, field=exc.field) from exc

    quota = quota_service.consume_media(user_id, sanitized.size_bytes)
    if not quota.allowed:
        raise ImageCrawlError("MEDIA_QUOTA_EXCEEDED", quota.message, status=429)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(sanitized.content)

    asset = MediaAsset(
        note_id=note.id,
        field_name=sanitized.field_name,
        filename=sanitized.safe_original_filename,
        mime_type=sanitized.mime_type,
        storage_path=str(relative_path).replace("\\", "/"),
        sha256=sanitized.sha256,
        size_bytes=sanitized.size_bytes,
    )

    try:
        db.session.add(asset)
        db.session.flush()
        if not markdown_inline:
            values = dict(note.field_values or {})
            values[sanitized.field_name] = f"/media/proxy/{asset.id}"
            note.field_values = values
            deck_working_tree_service.mark_note_field_batches_changed(
                mutations=[
                    {
                        "note": note,
                        "field_names": {sanitized.field_name},
                        "operation": "set",
                    }
                ],
            )
        db.session.add(
            AuditLog(
                user_id=user_id,
                action="media.crawl.inline" if markdown_inline else "media.crawl",
                payload={
                    "note_id": note.id,
                    "asset_id": asset.id,
                    "field_name": sanitized.field_name,
                    "source_url": url,
                },
            )
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        try:
            full_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to compensate crawled media file %s", full_path)
        raise

    payload = _media_payload(asset, source_url=url, include_filename=markdown_inline)
    return payload, 201


def crawl_note_media_batch(
    *,
    user_id: int,
    items: list[dict[str, Any]],
    upload_root: Path,
    max_bytes: int,
    scanner: Callable[[bytes], Any] | None = None,
    scan_enabled: bool = False,
) -> dict[str, Any]:
    """Crawl a batch of images from URLs across multiple notes with a single DB transaction."""
    if not items:
        return {"success": True, "success_count": 0, "failed_count": 0, "items": []}

    note_ids = list({str(it.get("note_id") or "").strip() for it in items if it.get("note_id")})
    if not note_ids:
        raise ImageCrawlError("VALIDATION_ERROR", "No valid note_ids provided in batch.")

    notes = Note.query.filter(Note.id.in_(note_ids), Note.user_id == user_id).all()
    note_map = {n.id: n for n in notes}

    note_type_ids = {n.note_type_id for n in notes if n.note_type_id}
    field_defs = FieldDef.query.filter(FieldDef.note_type_id.in_(note_type_ids)).all()
    field_def_map = {
        (f.note_type_id, (f.name or "").strip().lower()): f
        for f in field_defs
    }

    existing_assets = MediaAsset.query.filter(MediaAsset.note_id.in_(note_ids)).all()
    existing_map: dict[tuple[str, str, str], MediaAsset] = {
        (a.note_id, a.field_name, a.sha256): a
        for a in existing_assets
    }

    resolved_root = upload_root.resolve()
    created_file_paths: list[Path] = []
    results: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0
    dirty_field_names_by_note_id: dict[str, set[str]] = {}

    try:
        for idx, item in enumerate(items):
            item_id = str(item.get("item_id") if item.get("item_id") is not None else idx)
            raw_note_id = str(item.get("note_id") or "").strip()
            raw_field_name = str(item.get("field_name") or "").strip()
            raw_url = str(item.get("url") or item.get("source_url") or "").strip()
            markdown_inline = bool(item.get("markdown_inline", False))

            note = note_map.get(raw_note_id)
            if note is None:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": "FIELD_NOT_FOUND",
                    "message": "Note not found.",
                })
                failed_count += 1
                continue

            if not raw_field_name:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": "VALIDATION_ERROR",
                    "message": "field_name is required.",
                })
                failed_count += 1
                continue

            if not raw_url:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": "IMAGE_URL_REQUIRED",
                    "message": "url is required.",
                })
                failed_count += 1
                continue

            field_def = field_def_map.get((note.note_type_id, raw_field_name.lower()))
            if field_def is None:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": "FIELD_NOT_FOUND",
                    "message": "Field not found in note type.",
                })
                failed_count += 1
                continue

            if markdown_inline:
                if field_def.field_type != "markdown":
                    results.append({
                        "item_id": item_id,
                        "note_id": raw_note_id,
                        "field_name": raw_field_name,
                        "status": "failed",
                        "error": "VALIDATION_ERROR",
                        "message": "Field is not markdown.",
                    })
                    failed_count += 1
                    continue
            else:
                if field_def.field_type not in {"image", "diagram"}:
                    results.append({
                        "item_id": item_id,
                        "note_id": raw_note_id,
                        "field_name": raw_field_name,
                        "status": "failed",
                        "error": "VALIDATION_ERROR",
                        "message": "Field does not accept image media.",
                    })
                    failed_count += 1
                    continue

            try:
                sanitized = crawl_remote_image(
                    raw_url,
                    max_bytes=max_bytes,
                    field_name=raw_field_name,
                    scanner=scanner,
                    scan_enabled=scan_enabled,
                )
            except ImageCrawlError as exc:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": exc.error,
                    "message": str(exc),
                })
                failed_count += 1
                continue

            existing_key = (note.id, sanitized.field_name, sanitized.sha256)
            existing = existing_map.get(existing_key)
            if existing:
                if not markdown_inline:
                    values = dict(note.field_values or {})
                    canonical_url = f"/media/proxy/{existing.id}"
                    if values.get(sanitized.field_name) != canonical_url:
                        values[sanitized.field_name] = canonical_url
                        note.field_values = values
                        dirty_field_names_by_note_id.setdefault(note.id, set()).add(
                            sanitized.field_name
                        )
                payload = _media_payload(
                    existing, source_url=raw_url, include_filename=markdown_inline
                )
                payload["item_id"] = item_id
                payload["status"] = "success"
                results.append(payload)
                success_count += 1
                continue

            relative_path = Path(str(user_id)) / note.id / sanitized.storage_filename
            try:
                full_path = resolve_safe_storage_path(
                    upload_root=resolved_root,
                    relative_path=relative_path,
                )
            except RequestValidationError as exc:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": exc.code,
                    "message": str(exc),
                })
                failed_count += 1
                continue

            quota = quota_service.consume_media(user_id, sanitized.size_bytes)
            if not quota.allowed:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": "MEDIA_QUOTA_EXCEEDED",
                    "message": quota.message,
                })
                failed_count += 1
                continue

            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(sanitized.content)
            created_file_paths.append(full_path)

            asset = MediaAsset(
                note_id=note.id,
                field_name=sanitized.field_name,
                filename=sanitized.safe_original_filename,
                mime_type=sanitized.mime_type,
                storage_path=str(relative_path).replace("\\", "/"),
                sha256=sanitized.sha256,
                size_bytes=sanitized.size_bytes,
            )
            db.session.add(asset)
            db.session.flush()
            existing_map[existing_key] = asset

            if not markdown_inline:
                values = dict(note.field_values or {})
                values[sanitized.field_name] = f"/media/proxy/{asset.id}"
                note.field_values = values
                dirty_field_names_by_note_id.setdefault(note.id, set()).add(
                    sanitized.field_name
                )

            db.session.add(
                AuditLog(
                    user_id=user_id,
                    action=(
                        "media.crawl.batch.inline"
                        if markdown_inline
                        else "media.crawl.batch"
                    ),
                    payload={
                        "note_id": note.id,
                        "asset_id": asset.id,
                        "field_name": sanitized.field_name,
                        "source_url": raw_url,
                    },
                )
            )
            payload = _media_payload(
                asset, source_url=raw_url, include_filename=markdown_inline
            )
            payload["item_id"] = item_id
            payload["status"] = "success"
            results.append(payload)
            success_count += 1

        if dirty_field_names_by_note_id:
            deck_working_tree_service.mark_note_field_batches_changed(
                mutations=[
                    {
                        "note": note_map[nid],
                        "field_names": f_names,
                        "operation": "set",
                    }
                    for nid, f_names in dirty_field_names_by_note_id.items()
                ],
            )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        for p in created_file_paths:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to compensate batch crawled media file %s", p)
        raise

    return {
        "success": True,
        "success_count": success_count,
        "failed_count": failed_count,
        "items": results,
    }


def crawl_and_rewrite_markdown_media(
    *,
    user_id: int,
    note_id: str,
    markdown_text: str,
    field_name: str,
    upload_root: Path,
    max_bytes: int,
    scanner: Callable[[bytes], Any] | None = None,
    scan_enabled: bool = False,
) -> dict[str, Any]:
    """Find all external image URLs in markdown, download & save them as Note assets, and rewrite URLs."""
    note = Note.query.filter_by(id=note_id, user_id=user_id).first()
    if note is None:
        raise ImageCrawlError("FIELD_NOT_FOUND", "Note not found.", status=404)

    field_def = FieldDef.query.filter_by(
        note_type_id=note.note_type_id,
        name=field_name,
    ).first()
    if field_def is None or field_def.field_type != "markdown":
        raise ImageCrawlError("VALIDATION_ERROR", "Field is not a markdown field.", field="field_name")

    # Find external URLs from markdown image syntax ![alt](https://...)
    md_urls = [match.group(2) for match in _MD_IMAGE_RE.finditer(markdown_text)]
    # Find external URLs from HTML image syntax <img src="https://...">
    html_urls = [match.group(2) for match in _HTML_IMG_RE.finditer(markdown_text)]

    unique_urls = list(dict.fromkeys(md_urls + html_urls))
    if not unique_urls:
        return {
            "rewritten_markdown": markdown_text,
            "crawled_count": 0,
            "assets": [],
        }

    url_to_proxy: dict[str, str] = {}
    saved_assets: list[dict[str, Any]] = []

    for raw_url in unique_urls:
        try:
            payload, _ = crawl_and_save_note_media(
                user_id=user_id,
                note_id=note.id,
                field_name=field_name,
                url=raw_url,
                upload_root=upload_root,
                max_bytes=max_bytes,
                scanner=scanner,
                scan_enabled=scan_enabled,
                markdown_inline=True,
            )
            proxy_url = payload.get("url")
            if proxy_url:
                url_to_proxy[raw_url] = proxy_url
                saved_assets.append(payload)
        except Exception as exc:
            logger.warning("Failed to crawl markdown image URL %s: %s", raw_url, exc)

    # Perform rewrite
    rewritten = markdown_text
    for raw_url, proxy_url in url_to_proxy.items():
        rewritten = rewritten.replace(raw_url, proxy_url)

    return {
        "rewritten_markdown": rewritten,
        "crawled_count": len(saved_assets),
        "assets": saved_assets,
    }


def _media_payload(
    asset: MediaAsset,
    *,
    source_url: str | None = None,
    include_filename: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "asset_id": asset.id,
        "url": f"/media/proxy/{asset.id}",
        "field_name": asset.field_name,
        "sha256": asset.sha256,
        "size_bytes": asset.size_bytes,
    }
    if source_url:
        payload["source_url"] = source_url
    if include_filename:
        payload["filename"] = asset.filename
    return payload
