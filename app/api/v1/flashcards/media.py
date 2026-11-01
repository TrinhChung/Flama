"""Flashcard media mutation REST API V1 resources."""

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.services import flashcard_media_api_service, image_crawl_service, worker_media_service
from app.validators.flashcard_input import RequestValidationError
from app.validators.image_crawl import (
    validate_batch_media_crawl_request,
    validate_markdown_crawl_request,
    validate_note_media_crawl_request,
    validate_page_crawl_request,
)


media_bp = Blueprint("api_v1_flashcard_media", __name__)


def _error(exc: flashcard_media_api_service.MediaApiError | image_crawl_service.ImageCrawlError | RequestValidationError):
    error_code = getattr(exc, "error", getattr(exc, "code", "VALIDATION_ERROR"))
    payload = {"error": error_code, "message": str(exc)}
    if getattr(exc, "field", None) is not None:
        payload["field"] = exc.field
    return jsonify(payload), getattr(exc, "status", 400)


def _upload(note_id: str, *, markdown_inline: bool):
    try:
        if request.is_json:
            payload, status = worker_media_service.attach(
                user_id=current_user.id, note_id=note_id,
                payload=request.get_json(silent=True), markdown_inline=markdown_inline,
            )
            return jsonify(payload), status
        payload, status = flashcard_media_api_service.upload_media(
            user_id=current_user.id,
            note_id=note_id,
            field_name=request.form.get("field_name") or "",
            uploaded=request.files.get("file"),
            upload_root=Path(
                current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
            ),
            max_bytes=int(
                current_app.config.get(
                    "FLASHCARD_MEDIA_MAX_BYTES",
                    10 * 1024 * 1024,
                )
            ),
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(
                current_app.config.get(
                    "FLASHCARD_MEDIA_SCAN_ENABLED",
                    False,
                )
            ),
            markdown_inline=markdown_inline,
        )
    except (flashcard_media_api_service.MediaApiError, image_crawl_service.ImageCrawlError, RequestValidationError) as exc:
        return _error(exc)
    return jsonify(payload), status


@media_bp.post("/media/upload-ticket")
@login_required
def media_upload_ticket():
    try:
        return jsonify(worker_media_service.upload_ticket(
            user_id=current_user.id, payload=request.get_json(silent=True) or {},
        ))
    except RequestValidationError as exc:
        return _error(exc)


@media_bp.post("/notes/<note_id>/media")
@login_required
def upload_note_media(note_id: str):
    return _upload(note_id, markdown_inline=False)


@media_bp.post("/notes/<note_id>/markdown-media")
@login_required
def upload_markdown_media(note_id: str):
    return _upload(note_id, markdown_inline=True)


@media_bp.post("/notes/<note_id>/media/crawl")
@login_required
def crawl_note_media(note_id: str):
    """Crawl a remote image by URL and attach it to a note field."""
    try:
        raw_payload = request.get_json(silent=True) or request.form.to_dict()
        req_data = validate_note_media_crawl_request(raw_payload)
        payload, status = image_crawl_service.crawl_and_save_note_media(
            user_id=current_user.id,
            note_id=note_id,
            field_name=req_data["field_name"],
            url=req_data["url"],
            upload_root=Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]),
            max_bytes=int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024)),
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
            markdown_inline=req_data["markdown_inline"],
        )
    except (image_crawl_service.ImageCrawlError, RequestValidationError) as exc:
        return _error(exc)
    return jsonify(payload), status


@media_bp.post("/notes/media/crawl-batch")
@login_required
def crawl_notes_media_batch():
    """Crawl multiple remote images by URL for multiple notes in batch."""
    try:
        raw_payload = request.get_json(silent=True) or request.form.to_dict()
        items = validate_batch_media_crawl_request(raw_payload)
        payload = image_crawl_service.crawl_note_media_batch(
            user_id=current_user.id,
            items=items,
            upload_root=Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]),
            max_bytes=int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024)),
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
        )
    except (image_crawl_service.ImageCrawlError, RequestValidationError) as exc:
        return _error(exc)
    return jsonify(payload), 200


@media_bp.post("/notes/<note_id>/markdown/crawl-images")
@login_required
def crawl_and_rewrite_markdown(note_id: str):
    """Find all remote image URLs in markdown, download & save as note media, and rewrite markdown."""
    try:
        raw_payload = request.get_json(silent=True) or request.form.to_dict()
        req_data = validate_markdown_crawl_request(raw_payload)
        field_name = str(raw_payload.get("field_name") or "").strip()
        if not field_name:
            return jsonify({"error": "VALIDATION_ERROR", "message": "field_name is required.", "field": "field_name"}), 400

        payload = image_crawl_service.crawl_and_rewrite_markdown_media(
            user_id=current_user.id,
            note_id=note_id,
            markdown_text=req_data["markdown"],
            field_name=field_name,
            upload_root=Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]),
            max_bytes=int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024)),
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
        )
    except (image_crawl_service.ImageCrawlError, RequestValidationError) as exc:
        return _error(exc)
    return jsonify(payload), 200


@media_bp.post("/media/crawl-page")
@login_required
def crawl_page_images():
    """Extract all candidate images from a webpage HTML safely."""
    try:
        raw_payload = request.get_json(silent=True) or request.form.to_dict()
        req_data = validate_page_crawl_request(raw_payload)
        payload = image_crawl_service.extract_images_from_page(
            page_url=req_data["page_url"],
            max_images=req_data["max_images"],
        )
    except (image_crawl_service.ImageCrawlError, RequestValidationError) as exc:
        return _error(exc)
    return jsonify(payload), 200


@media_bp.post("/notes/media/batch")
@login_required
def upload_notes_media_batch():
    import json

    if request.is_json:
        try:
            return jsonify(worker_media_service.attach_batch(
                user_id=current_user.id, payload=request.get_json(silent=True),
            ))
        except RequestValidationError as exc:
            return _error(exc)

    manifest_raw = request.form.get("manifest")
    items_input = []
    if manifest_raw:
        try:
            items_input = json.loads(manifest_raw)
            if not isinstance(items_input, list):
                return jsonify({"error": "VALIDATION_ERROR", "message": "manifest must be a JSON array."}), 400
        except (json.JSONDecodeError, TypeError) as exc:
            return jsonify({"error": "VALIDATION_ERROR", "message": f"Invalid manifest JSON: {exc}"}), 400

    batch_items = []
    for idx, item in enumerate(items_input):
        if not isinstance(item, dict):
            continue
        file_key = str(item.get("file_key") or f"file_{idx}")
        uploaded = request.files.get(file_key)
        if not uploaded and f"files[{idx}]" in request.files:
            uploaded = request.files.get(f"files[{idx}]")
        if not uploaded and "files" in request.files:
            files_list = request.files.getlist("files")
            if idx < len(files_list):
                uploaded = files_list[idx]

        batch_items.append({
            "item_id": item.get("item_id", str(idx)),
            "note_id": item.get("note_id"),
            "field_name": item.get("field_name"),
            "uploaded": uploaded,
            "markdown_inline": bool(item.get("markdown_inline", False)),
        })

    if not batch_items:
        return jsonify({"error": "VALIDATION_ERROR", "message": "No items provided in batch."}), 400

    try:
        payload = flashcard_media_api_service.upload_media_batch(
            user_id=current_user.id,
            items=batch_items,
            upload_root=Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]),
            max_bytes=int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024)),
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
        )
    except flashcard_media_api_service.MediaApiError as exc:
        return _error(exc)

    return jsonify(payload), 200


@media_bp.delete("/media/<asset_id>")
@login_required
def delete_media(asset_id: str):
    try:
        payload = flashcard_media_api_service.delete_media(
            user_id=current_user.id,
            asset_id=asset_id,
            upload_root=Path(
                current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
            ),
        )
    except flashcard_media_api_service.MediaApiError as exc:
        return _error(exc)
    return jsonify(payload)

