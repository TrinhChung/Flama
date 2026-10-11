"""Note type, field, and template REST API V1 resources."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services import flashcard_content_service
from app.utils.permissions import is_admin_user

from .common import content_error


note_types_bp = Blueprint("api_v1_note_types", __name__)


@note_types_bp.get("/note-types")
@login_required
def list_note_types():
    compact = request.args.get("compact") in {"1", "true"}
    return jsonify(
        flashcard_content_service.list_note_types(
            user_id=current_user.id,
            compact=compact,
        )
    )


@note_types_bp.post("/note-types")
@login_required
def create_note_type():
    try:
        payload = flashcard_content_service.create_note_type(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload), 201


@note_types_bp.get("/note-types/<note_type_id>")
@login_required
def get_note_type(note_type_id: str):
    try:
        payload = flashcard_content_service.get_note_type(
            user_id=current_user.id,
            note_type_id=note_type_id,
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.patch("/note-types/<note_type_id>")
@login_required
def update_note_type(note_type_id: str):
    try:
        payload = flashcard_content_service.update_note_type(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            note_type_id=note_type_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.delete("/note-types/<note_type_id>")
@login_required
def delete_note_type(note_type_id: str):
    try:
        purge = request.args.get("purge") == "true"
        payload = flashcard_content_service.delete_note_type(
            user_id=current_user.id,
            note_type_id=note_type_id,
            purge=purge,
            is_admin=is_admin_user(current_user),
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.get("/note-types/<note_type_id>/fields")
@login_required
def list_fields(note_type_id: str):
    try:
        payload = flashcard_content_service.list_fields(
            user_id=current_user.id,
            note_type_id=note_type_id,
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.post("/note-types/<note_type_id>/fields")
@login_required
def create_field(note_type_id: str):
    try:
        payload = flashcard_content_service.create_field(
            user_id=current_user.id,
            note_type_id=note_type_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload), 201


@note_types_bp.patch("/note-types/<note_type_id>/fields/<field_id>")
@login_required
def update_field(note_type_id: str, field_id: str):
    try:
        payload = flashcard_content_service.update_field(
            user_id=current_user.id,
            note_type_id=note_type_id,
            field_id=field_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.delete("/note-types/<note_type_id>/fields/<field_id>")
@login_required
def delete_field(note_type_id: str, field_id: str):
    try:
        payload = flashcard_content_service.delete_field(
            user_id=current_user.id,
            note_type_id=note_type_id,
            field_id=field_id,
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.post("/note-types/<note_type_id>/fields/reorder")
@login_required
def reorder_fields(note_type_id: str):
    try:
        payload = flashcard_content_service.reorder_fields(
            user_id=current_user.id,
            note_type_id=note_type_id,
            payload=request.get_json(silent=True),
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.get("/note-types/<note_type_id>/templates")
@login_required
def list_templates(note_type_id: str):
    try:
        payload = flashcard_content_service.list_templates(
            user_id=current_user.id,
            note_type_id=note_type_id,
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.post("/note-types/<note_type_id>/templates")
@login_required
def create_template(note_type_id: str):
    try:
        payload = flashcard_content_service.create_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload), 201


@note_types_bp.patch("/note-types/<note_type_id>/templates/<template_id>")
@login_required
def update_template(note_type_id: str, template_id: str):
    try:
        payload = flashcard_content_service.update_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            template_id=template_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.delete("/note-types/<note_type_id>/templates/<template_id>")
@login_required
def delete_template(note_type_id: str, template_id: str):
    try:
        payload = flashcard_content_service.delete_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            template_id=template_id,
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.post("/note-types/<note_type_id>/templates/<template_id>/reset")
@login_required
def reset_template(note_type_id: str, template_id: str):
    try:
        payload = flashcard_content_service.reset_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            template_id=template_id,
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@note_types_bp.post("/note-types/<note_type_id>/templates/<template_id>/preview")
@login_required
def preview_template(note_type_id: str, template_id: str):
    try:
        payload = flashcard_content_service.preview_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            template_id=template_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)
