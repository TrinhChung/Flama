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
