"""Note REST API V1 resources."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services import flashcard_content_service

from .common import content_error


notes_bp = Blueprint("api_v1_notes", __name__)


@notes_bp.get("/notes")
@login_required
def list_notes():
    try:
        payload = flashcard_content_service.list_notes(
            user_id=current_user.id,
            query_args=request.args,
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@notes_bp.post("/notes")
@login_required
def create_note():
    try:
        payload = flashcard_content_service.create_note(
            user_id=current_user.id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload), 201


@notes_bp.get("/notes/<note_id>")
@login_required
def get_note(note_id: str):
    try:
        payload = flashcard_content_service.get_note(
            user_id=current_user.id,
            note_id=note_id,
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@notes_bp.patch("/notes/<note_id>")
@login_required
def update_note(note_id: str):
    try:
        payload = flashcard_content_service.update_note(
            user_id=current_user.id,
            note_id=note_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)


@notes_bp.delete("/notes/<note_id>")
@login_required
def delete_note(note_id: str):
    try:
        payload = flashcard_content_service.delete_note(
            user_id=current_user.id,
            note_id=note_id,
        )
    except flashcard_content_service.ContentApiError as exc:
        return content_error(exc)
    return jsonify(payload)
