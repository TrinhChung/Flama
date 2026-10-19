"""Browse REST API V1 resources."""

import io
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user, login_required

from app.services import browse_card_service, browse_voicevox_service
from app.services.stats_overview import get_effective_timezone_name
from app.utils.permissions import is_admin_user
from app.validators import RequestValidationError
from app.validators.browse_note import validate_note_delete_payload


browse_bp = Blueprint("api_v1_browse", __name__)


def _context() -> tuple[int, bool, str]:
    return (
        current_user.id,
        is_admin_user(current_user),
        get_effective_timezone_name(getattr(current_user, "timezone", "UTC")),
    )


def _browse_error(exc: browse_card_service.BrowseApiError):
    payload = {"error": str(exc)}
    if exc.field is not None:
        payload["field"] = exc.field
    if exc.code is not None:
        payload["code"] = exc.code
    return jsonify(payload), exc.status


def _voicevox_payload():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return None, (jsonify({"error": "Payload phải là JSON object."}), 400)
    return payload, None


def _voicevox_error(exc: browse_voicevox_service.BrowseVoiceVoxError):
    payload = {"error": str(exc)}
    if exc.code is not None:
        payload["code"] = exc.code
    return jsonify(payload), exc.status


@browse_bp.get("/decks/tree")
@login_required
def browse_decks_tree():
    user_id, admin_mode, timezone_name = _context()
    try:
        payload = browse_card_service.build_browse_deck_tree(
            user_id=user_id,
            admin_mode=admin_mode,
            timezone_name=timezone_name,
        )
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(payload)


@browse_bp.get("/decks")
@login_required
def browse_decks():
    user_id, admin_mode, timezone_name = _context()
    try:
        payload = browse_card_service.build_browse_decks(
            user_id=user_id,
            admin_mode=admin_mode,
            timezone_name=timezone_name,
        )
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(payload)


@browse_bp.get("/cards")
@login_required
def browse_cards():
    user_id, admin_mode, timezone_name = _context()
    try:
        payload = browse_card_service.list_browse_cards(
            user_id=user_id,
            admin_mode=admin_mode,
            timezone_name=timezone_name,
            query_args=request.args,
        )
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(payload)


@browse_bp.get("/cards/<card_id>")
@login_required
def browse_card_detail(card_id: str):
    user_id, admin_mode, timezone_name = _context()
    try:
        payload = browse_card_service.get_browse_card_detail(
            user_id=user_id,
            admin_mode=admin_mode,
            timezone_name=timezone_name,
            card_id=card_id,
        )
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(payload)


@browse_bp.patch("/cards/<card_id>")
@login_required
def browse_card_update(card_id: str):
    user_id, admin_mode, timezone_name = _context()
    try:
        payload = browse_card_service.update_browse_card(
            user_id=user_id,
            admin_mode=admin_mode,
            timezone_name=timezone_name,
            card_id=card_id,
            payload=request.get_json(silent=True) or {},
        )
    except browse_card_service.BrowseCardUpdateError as exc:
        error_payload = {"error": str(exc)}
        if exc.include_details:
            error_payload["field"] = exc.field
            error_payload["code"] = exc.code
        return jsonify(error_payload), exc.status
    return jsonify(payload)


@browse_bp.delete("/cards/<card_id>")
@login_required
def browse_card_delete(card_id: str):
    user_id, admin_mode, _timezone_name = _context()
    try:
        payload = browse_card_service.delete_browse_card(
            user_id=user_id,
            admin_mode=admin_mode,
            card_id=card_id,
        )
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(payload)


@browse_bp.post("/cards/batch-delete")
@login_required
def browse_cards_batch_delete():
    user_id, admin_mode, _timezone_name = _context()
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    try:
        if not isinstance(data, dict):
            raise browse_card_service.BrowseApiError(
                "Payload must be a JSON object.",
                status=400,
                code="VALIDATION_ERROR",
            )
        card_ids = data.get("card_ids") or []
        if not isinstance(card_ids, list):
            raise browse_card_service.BrowseApiError(
                "card_ids must be a list.",
                status=400,
                field="card_ids",
                code="VALIDATION_ERROR",
            )
        payload = browse_card_service.delete_browse_cards_batch(
            user_id=user_id,
            admin_mode=admin_mode,
            card_ids=card_ids,
        )
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(payload)


@browse_bp.get("/notes")
@login_required
def browse_notes():
    user_id, admin_mode, timezone_name = _context()
    try:
        cards_payload = browse_card_service.list_browse_cards(
            user_id=user_id,
            admin_mode=admin_mode,
            timezone_name=timezone_name,
            query_args=request.args,
        )
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(browse_card_service.build_legacy_notes_payload(cards_payload))


@browse_bp.delete("/notes/<note_id>")
@login_required
def browse_note_delete(note_id: str):
    user_id, admin_mode, _timezone_name = _context()
    try:
        payload = browse_card_service.delete_browse_notes_batch(
            user_id=user_id, admin_mode=admin_mode, note_ids=[note_id],
        )
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(payload)


@browse_bp.post("/notes/batch-delete")
@login_required
def browse_notes_batch_delete():
    user_id, admin_mode, _timezone_name = _context()
    try:
        note_ids = validate_note_delete_payload(request.get_json(silent=True))
        payload = browse_card_service.delete_browse_notes_batch(
            user_id=user_id, admin_mode=admin_mode, note_ids=note_ids,
        )
    except RequestValidationError as exc:
        return jsonify({"error": str(exc), "code": exc.code, "field": exc.field}), exc.status
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(payload)


@browse_bp.patch("/notes/<note_id>")
@login_required
def browse_update_note(note_id: str):
    user_id, admin_mode, _timezone_name = _context()
    try:
        payload = browse_card_service.update_legacy_browse_note(
            user_id=user_id,
            admin_mode=admin_mode,
            note_id=note_id,
            payload=request.get_json(silent=True) or {},
        )
    except browse_card_service.BrowseApiError as exc:
        return _browse_error(exc)
    return jsonify(payload)


@browse_bp.post("/voicevox/preview")
@login_required
def browse_voicevox_preview():
    payload = request.get_json(silent=True) or {}
    try:
        result = browse_voicevox_service.preview_voicevox(
            user_id=current_user.id,
            payload=payload,
        )
    except browse_voicevox_service.BrowseVoiceVoxError as exc:
        return _voicevox_error(exc)
    response = send_file(
        io.BytesIO(result.content),
        mimetype=result.mime_type,
        as_attachment=False,
        download_name=f"voicevox-preview.{result.extension}",
        max_age=0,
    )
    if result.warnings:
        response.headers["X-VoiceVox-Warnings"] = " | ".join(result.warnings)[:500]
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@browse_bp.post("/voicevox/precheck")
@login_required
def browse_voicevox_precheck():
    payload, error = _voicevox_payload()
    if error is not None:
        return error
    try:
        result = browse_voicevox_service.precheck_voicevox(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=payload,
        )
    except browse_voicevox_service.BrowseVoiceVoxError as exc:
        return _voicevox_error(exc)
    return jsonify(result)


@browse_bp.post("/voicevox/generate")
@login_required
def browse_voicevox_generate():
    payload = request.get_json(silent=True) or {}
    try:
        result = browse_voicevox_service.generate_voicevox(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=payload,
            upload_root=Path(
                current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
            ),
        )
    except browse_voicevox_service.BrowseVoiceVoxError as exc:
        return _voicevox_error(exc)
    return jsonify(result)
