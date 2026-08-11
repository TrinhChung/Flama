"""Sub-module for flashcard routes."""

from __future__ import annotations

from pathlib import Path
from flask import jsonify, request, send_file, current_app
from flask_login import current_user, login_required
from models.flashcard import *

# Import everything from core module so routes can use helpers
from . import *

from app.routes.flashcards import (
    _api_error,
)
from app.validators import (
    RequestValidationError,
    build_safe_download_filename,
    resolve_safe_storage_path,
)



@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["GET"])
@login_required
def list_templates(note_type_id: str):
    from app.services import flashcard_content_service

    try:
        return jsonify(
            flashcard_content_service.list_templates(
                user_id=current_user.id,
                note_type_id=note_type_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>", methods=["DELETE"])
@login_required
def delete_template(note_type_id: str, template_id: str):
    from app.services import flashcard_content_service

    try:
        return jsonify(
            flashcard_content_service.delete_template(
                user_id=current_user.id,
                note_type_id=note_type_id,
                template_id=template_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

@flashcards_bp.route("/api/notes/<note_id>", methods=["GET"])
@login_required
def get_note(note_id: str):
    from app.services import flashcard_content_service

    try:
        return jsonify(
            flashcard_content_service.get_note(
                user_id=current_user.id,
                note_id=note_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

@flashcards_bp.route("/api/notes/<note_id>/media", methods=["POST"])
@login_required
def upload_note_media(note_id: str):
    from app.services import flashcard_media_api_service

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
                current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)
            ),
            markdown_inline=False,
        )
    except flashcard_media_api_service.MediaApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload), status


@flashcards_bp.route("/api/notes/<note_id>/markdown-media", methods=["POST"])
@login_required
def upload_note_markdown_media(note_id: str):
    from app.services import flashcard_media_api_service

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
                current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)
            ),
            markdown_inline=True,
        )
    except flashcard_media_api_service.MediaApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload), status

@flashcards_bp.route("/api/media/<asset_id>", methods=["DELETE"])
@login_required
def delete_media(asset_id: str):
    from app.services import flashcard_media_api_service

    try:
        return jsonify(
            flashcard_media_api_service.delete_media(
                user_id=current_user.id,
                asset_id=asset_id,
                upload_root=Path(
                    current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
                ),
            )
        )
    except flashcard_media_api_service.MediaApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

@flashcards_bp.route("/media/proxy/<asset_id>", methods=["GET"])
def proxy_media(asset_id: str):
    asset = MediaAsset.query.filter(MediaAsset.id == asset_id).first()
    if not asset:
        return _api_error("FIELD_NOT_FOUND", "Media asset not found.", status=404)
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    try:
        full_path = resolve_safe_storage_path(
            upload_root=upload_root,
            relative_path=Path(asset.storage_path),
        )
    except RequestValidationError:
        return _api_error("FIELD_NOT_FOUND", "Media file not found on disk.", status=404)
    if not full_path.exists():
        return _api_error("FIELD_NOT_FOUND", "Media file not found on disk.", status=404)
    response = send_file(full_path, mimetype=asset.mime_type, conditional=True, max_age=3600)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response.headers["Content-Disposition"] = (
        f"inline; filename=\"{build_safe_download_filename(asset.filename)}\""
    )
    return response
