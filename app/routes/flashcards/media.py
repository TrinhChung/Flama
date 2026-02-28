"""Sub-module for flashcard routes."""

from __future__ import annotations

import logging
from datetime import datetime
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



@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["GET"])
@login_required
def list_templates(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    templates = Template.query.filter_by(note_type_id=note_type.id).order_by(Template.position.asc()).all()
    return jsonify({"items": [_serialize_template(template) for template in templates]})

@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>", methods=["DELETE"])
@login_required
def delete_template(note_type_id: str, template_id: str):
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
    db.session.delete(template)
    _audit("template.delete", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify({"success": True})

@flashcards_bp.route("/api/notes/<note_id>", methods=["GET"])
@login_required
def get_note(note_id: str):
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

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return _api_error("VALIDATION_ERROR", "Missing uploaded file.", field="file")

    content = uploaded.read()
    if not content:
        return _api_error("VALIDATION_ERROR", "Uploaded file is empty.", field="file")

    max_bytes = int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024))
    if len(content) > max_bytes:
        return _api_error("MEDIA_TOO_LARGE", f"File exceeds {max_bytes} bytes.", field="file", status=413)

    mime_type = uploaded.mimetype or "application/octet-stream"
    if mime_type not in ALLOWED_MEDIA_MIME_TYPES:
        return _api_error("MEDIA_TYPE_NOT_ALLOWED", f"Unsupported media type: {mime_type}", field="file", status=415)

    digest = hashlib.sha256(content).hexdigest()
    existing = MediaAsset.query.filter_by(note_id=note.id, field_name=field_name, sha256=digest).first()
    if existing:
        values = dict(note.field_values or {})
        values[field_name] = existing.id
        note.field_values = values
        db.session.commit()
        return jsonify({"asset_id": existing.id, "url": f"/media/proxy/{existing.id}", "field_name": field_name})

    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"])
    safe_name = Path(uploaded.filename).name.replace(" ", "_")
    relative_dir = Path(str(current_user.id)) / note.id
    final_dir = upload_root / relative_dir
    final_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{digest[:8]}_{safe_name}"
    relative_path = relative_dir / filename
    full_path = upload_root / relative_path
    full_path.write_bytes(content)

    asset = MediaAsset(
        note_id=note.id,
        field_name=field_name,
        filename=safe_name,
        mime_type=mime_type,
        storage_path=str(relative_path).replace("\\", "/"),
        sha256=digest,
        size_bytes=len(content),
    )
    db.session.add(asset)
    db.session.flush()
    values = dict(note.field_values or {})
    values[field_name] = asset.id
    note.field_values = values
    _audit("media.upload", {"note_id": note.id, "asset_id": asset.id, "field_name": field_name})
    db.session.commit()
    return jsonify({"asset_id": asset.id, "url": f"/media/proxy/{asset.id}", "field_name": field_name}), 201

@flashcards_bp.route("/api/media/<asset_id>", methods=["DELETE"])
@login_required
def delete_media(asset_id: str):
    asset = (
        MediaAsset.query.join(Note, MediaAsset.note_id == Note.id)
        .filter(MediaAsset.id == asset_id, Note.user_id == current_user.id)
        .first()
    )
    if not asset:
        return _api_error("FIELD_NOT_FOUND", "Media asset not found.", status=404)
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"])
    full_path = (upload_root / asset.storage_path).resolve()
    if full_path.exists():
        try:
            full_path.unlink()
        except OSError:
            logger.warning("Failed to delete media file %s", full_path)
    note = asset.note
    values = dict(note.field_values or {})
    if values.get(asset.field_name) == asset.id:
        values[asset.field_name] = ""
        note.field_values = values
    db.session.delete(asset)
    _audit("media.delete", {"asset_id": asset_id, "note_id": note.id})
    db.session.commit()
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
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"])
    full_path = (upload_root / asset.storage_path).resolve()
    if not full_path.exists():
        return _api_error("FIELD_NOT_FOUND", "Media file not found on disk.", status=404)
    return send_file(full_path, mimetype=asset.mime_type, conditional=True, max_age=3600)

