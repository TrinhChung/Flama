"""Sub-module for flashcard routes."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from flask import jsonify, request, redirect, url_for, flash, render_template, send_file, current_app
from flask_login import current_user, login_required
from sqlalchemy.exc import OperationalError
from models import db
from models.flashcard import *
from models.deck import Deck
from models.card_progress import CardProgress
from app.utils.permissions import is_admin_user

# Import everything from core module so routes can use helpers
from . import *

from app.routes.flashcards import (
    _api_error,
    _audit,
    _get_note_type_or_404,
    _serialize_template,
)
from app.validators import (
    RequestValidationError,
    build_safe_download_filename,
    resolve_safe_storage_path,
    validate_media_upload_request,
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

    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    templates = Template.query.filter_by(note_type_id=note_type.id).order_by(Template.position.asc()).all()
    return jsonify({"items": [_serialize_template(template) for template in templates]})

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

    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)
    if template.is_default:
        return _api_error("VALIDATION_ERROR", "Cannot delete default template.", status=409)
    if Template.query.filter_by(note_type_id=note_type.id).count() <= 1:
        return _api_error("VALIDATION_ERROR", "A note type requires at least one template.", status=409)
    Card.query.filter_by(template_id=template.id).delete()
    from app.services.flashcard_media_service import delete_template_and_commit
    delete_template_and_commit(template, note_type.id)
    return jsonify({"success": True})

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

    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    return jsonify(
        {
            "id": note.id,
            "note_type_id": note.note_type_id,
            "deck_id": note.deck_id,
            "field_values": note.field_values or {},
            "tags": note.tags or [],
            "media_assets": [
                {
                    "id": asset.id,
                    "field_name": asset.field_name,
                    "filename": asset.filename,
                    "mime_type": asset.mime_type,
                    "url": f"/media/proxy/{asset.id}",
                }
                for asset in note.media_assets
            ],
        }
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

    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    field_name = (request.form.get("field_name") or "").strip()
    if not field_name:
        return _api_error("VALIDATION_ERROR", "field_name is required.", field="field_name")
    field_def = FieldDef.query.filter_by(note_type_id=note.note_type_id, name=field_name).first()
    if not field_def:
        return _api_error("FIELD_NOT_FOUND", "Field not found in note type.", field="field_name", status=404)
    if field_def.field_type not in {"image", "audio", "diagram"}:
        return _api_error("VALIDATION_ERROR", "Field does not accept media.", field="field_name")

    max_bytes = int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024))
    try:
        validated_upload = validate_media_upload_request(
            field_name_raw=field_name,
            field_type=field_def.field_type,
            uploaded=request.files.get("file"),
            max_bytes=max_bytes,
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
        )
    except RequestValidationError as exc:
        return _api_error(exc.code, str(exc), field=exc.field, status=exc.status)

    existing = MediaAsset.query.filter_by(
        note_id=note.id,
        field_name=validated_upload.field_name,
        sha256=validated_upload.sha256,
    ).first()
    if existing:
        from app.services.flashcard_media_service import link_existing_media_and_commit
        link_existing_media_and_commit(note, existing, validated_upload.field_name)
        return jsonify(
            {
                "asset_id": existing.id,
                "url": f"/media/proxy/{existing.id}",
                "field_name": validated_upload.field_name,
            }
        )

    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    relative_dir = Path(str(current_user.id)) / note.id
    relative_path = relative_dir / validated_upload.storage_filename
    try:
        full_path = resolve_safe_storage_path(upload_root=upload_root, relative_path=relative_path)
    except RequestValidationError as exc:
        return _api_error(exc.code, str(exc), field=exc.field, status=exc.status)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(validated_upload.content)

    asset = MediaAsset(
        note_id=note.id,
        field_name=validated_upload.field_name,
        filename=validated_upload.safe_original_filename,
        mime_type=validated_upload.mime_type,
        storage_path=str(relative_path).replace("\\", "/"),
        sha256=validated_upload.sha256,
        size_bytes=validated_upload.size_bytes,
    )
    from app.services.flashcard_media_service import upload_note_media_and_commit
    upload_note_media_and_commit(note, asset, validated_upload.field_name)
    return jsonify(
        {
            "asset_id": asset.id,
            "url": f"/media/proxy/{asset.id}",
            "field_name": validated_upload.field_name,
        }
    ), 201


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

    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)

    field_name = (request.form.get("field_name") or "").strip()
    if not field_name:
        return _api_error("VALIDATION_ERROR", "field_name is required.", field="field_name")

    field_def = FieldDef.query.filter_by(note_type_id=note.note_type_id, name=field_name).first()
    if not field_def:
        return _api_error("FIELD_NOT_FOUND", "Field not found in note type.", field="field_name", status=404)
    if field_def.field_type != "markdown":
        return _api_error("VALIDATION_ERROR", "Field is not markdown.", field="field_name")

    max_bytes = int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024))
    try:
        validated_upload = validate_media_upload_request(
            field_name_raw=field_name,
            # Inline markdown uploads are image-only.
            field_type="image",
            uploaded=request.files.get("file"),
            max_bytes=max_bytes,
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
        )
    except RequestValidationError as exc:
        return _api_error(exc.code, str(exc), field=exc.field, status=exc.status)

    existing = MediaAsset.query.filter_by(
        note_id=note.id,
        field_name=validated_upload.field_name,
        sha256=validated_upload.sha256,
    ).first()
    if existing:
        return jsonify(
            {
                "asset_id": existing.id,
                "url": f"/media/proxy/{existing.id}",
                "field_name": validated_upload.field_name,
                "filename": existing.filename,
            }
        )

    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    relative_dir = Path(str(current_user.id)) / note.id
    relative_path = relative_dir / validated_upload.storage_filename
    try:
        full_path = resolve_safe_storage_path(upload_root=upload_root, relative_path=relative_path)
    except RequestValidationError as exc:
        return _api_error(exc.code, str(exc), field=exc.field, status=exc.status)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(validated_upload.content)

    asset = MediaAsset(
        note_id=note.id,
        field_name=validated_upload.field_name,
        filename=validated_upload.safe_original_filename,
        mime_type=validated_upload.mime_type,
        storage_path=str(relative_path).replace("\\", "/"),
        sha256=validated_upload.sha256,
        size_bytes=validated_upload.size_bytes,
    )
    from app.services.flashcard_media_service import upload_note_inline_media_and_commit

    upload_note_inline_media_and_commit(note, asset, validated_upload.field_name)
    return jsonify(
        {
            "asset_id": asset.id,
            "url": f"/media/proxy/{asset.id}",
            "field_name": validated_upload.field_name,
            "filename": asset.filename,
        }
    ), 201

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

    asset = (
        MediaAsset.query.join(Note, MediaAsset.note_id == Note.id)
        .filter(MediaAsset.id == asset_id, Note.user_id == current_user.id)
        .first()
    )
    if not asset:
        return _api_error("FIELD_NOT_FOUND", "Media asset not found.", status=404)
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    try:
        full_path = resolve_safe_storage_path(
            upload_root=upload_root,
            relative_path=Path(asset.storage_path),
        )
    except RequestValidationError:
        full_path = None
    if full_path is not None and full_path.exists():
        try:
            full_path.unlink()
        except OSError:
            logger.warning("Failed to delete media file %s", full_path)
    from app.services.flashcard_media_service import delete_media_and_commit
    delete_media_and_commit(asset)
    return jsonify({"success": True})

@flashcards_bp.route("/media/proxy/<asset_id>", methods=["GET"])
@login_required
def proxy_media(asset_id: str):
    asset = (
        MediaAsset.query.join(Note, MediaAsset.note_id == Note.id)
        .filter(MediaAsset.id == asset_id, Note.user_id == current_user.id)
        .first()
    )
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
