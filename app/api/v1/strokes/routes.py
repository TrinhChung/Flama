"""REST API endpoints for Kanji and Hanzi stroke diagrams."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services.strokes.stroke_service import (
    StrokeServiceError,
    batch_generate_strokes,
    resolve_stroke_items,
)
from app.utils.permissions import is_admin_user

strokes_bp = Blueprint("api_v1_strokes", __name__)


def _error_response(exc: StrokeServiceError):
    payload = {"error": str(exc)}
    if exc.code is not None:
        payload["code"] = exc.code
    return jsonify(payload), exc.status


@strokes_bp.post("/strokes/generate")
@login_required
def generate_strokes():
    """Extract CJK characters and resolve stroke diagram SVGs/HTML for a single text."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Payload phải là JSON object."}), 400

    text = str(payload.get("text") or "").strip()
    locale = str(payload.get("locale") or "ja").strip()
    output_format = str(payload.get("format") or "html").strip()
    deduplicate = bool(payload.get("deduplicate", True))
    max_characters = int(payload.get("max_characters") or 15)

    try:
        result = resolve_stroke_items(
            text=text,
            locale=locale,
            deduplicate=deduplicate,
            max_characters=max_characters,
            output_format=output_format,
        )
    except StrokeServiceError as exc:
        return _error_response(exc)

    return jsonify(result)


@strokes_bp.post("/strokes/batch-generate")
@login_required
def batch_generate_strokes_route():
    """Batch generate stroke diagrams across selected cards or notes."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Payload phải là JSON object."}), 400

    source_field = str(payload.get("source_field") or "").strip()
    target_field = str(payload.get("target_field") or "").strip()
    locale = str(payload.get("locale") or "ja").strip()
    output_format = str(payload.get("format") or "html").strip()
    overwrite = bool(payload.get("overwrite", False))
    max_characters = int(payload.get("max_characters") or 15)

    raw_card_ids = payload.get("card_ids")
    card_ids = [str(cid) for cid in raw_card_ids] if isinstance(raw_card_ids, list) else None

    raw_note_ids = payload.get("note_ids")
    note_ids = [str(nid) for nid in raw_note_ids] if isinstance(raw_note_ids, list) else None

    deck_id = payload.get("deck_id")
    deck_id_int = int(deck_id) if deck_id is not None else None

    try:
        result = batch_generate_strokes(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            source_field=source_field,
            target_field=target_field,
            locale=locale,
            deck_id=deck_id_int,
            note_ids=note_ids,
            card_ids=card_ids,
            output_format=output_format,
            overwrite=overwrite,
            max_characters=max_characters,
        )
    except StrokeServiceError as exc:
        return _error_response(exc)

    return jsonify(result)


@strokes_bp.post("/decks/<int:deck_id>/strokes/batch-generate")
@login_required
def batch_generate_deck_strokes_route(deck_id: int):
    """Batch generate stroke diagrams for all notes in a specific deck."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Payload phải là JSON object."}), 400

    source_field = str(payload.get("source_field") or "").strip()
    target_field = str(payload.get("target_field") or "").strip()
    locale = str(payload.get("locale") or "ja").strip()
    output_format = str(payload.get("format") or "html").strip()
    overwrite = bool(payload.get("overwrite", False))
    max_characters = int(payload.get("max_characters") or 15)

    raw_note_ids = payload.get("note_ids")
    note_ids = [str(nid) for nid in raw_note_ids] if isinstance(raw_note_ids, list) else None

    try:
        result = batch_generate_strokes(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            source_field=source_field,
            target_field=target_field,
            locale=locale,
            deck_id=deck_id,
            note_ids=note_ids,
            output_format=output_format,
            overwrite=overwrite,
            max_characters=max_characters,
        )
    except StrokeServiceError as exc:
        return _error_response(exc)

    return jsonify(result)
