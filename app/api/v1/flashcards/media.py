"""Flashcard media mutation REST API V1 resources."""

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.services import flashcard_media_api_service


media_bp = Blueprint("api_v1_flashcard_media", __name__)


def _error(exc: flashcard_media_api_service.MediaApiError):
    payload = {"error": exc.error, "message": str(exc)}
    if exc.field is not None:
        payload["field"] = exc.field
    return jsonify(payload), exc.status


def _upload(note_id: str, *, markdown_inline: bool):
    try:
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
    except flashcard_media_api_service.MediaApiError as exc:
        return _error(exc)
    return jsonify(payload), status


@media_bp.post("/notes/<note_id>/media")
@login_required
def upload_note_media(note_id: str):
    return _upload(note_id, markdown_inline=False)


@media_bp.post("/notes/<note_id>/markdown-media")
@login_required
def upload_markdown_media(note_id: str):
    return _upload(note_id, markdown_inline=True)


@media_bp.post("/notes/media/batch")
@login_required
def upload_notes_media_batch():
    import json

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
