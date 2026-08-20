"""Deck audio scan REST API V1 resources."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.services import flashcard_audio_scan_service
from app.utils.permissions import is_admin_user

audio_scan_bp = Blueprint("api_v1_flashcard_audio_scan", __name__)


def _error(exc: flashcard_audio_scan_service.AudioScanError):
    return jsonify({"error": exc.code, "message": str(exc)}), exc.status


@audio_scan_bp.post("/audio/deck-scan")
@audio_scan_bp.post("/flashcards/audio/deck-scan")
@audio_scan_bp.post("/decks/<int:deck_id>/audio-scan")
@login_required
def scan_deck_audio(deck_id: int | None = None):
    payload = request.get_json(silent=True) or {}
    deck_id_raw = deck_id or payload.get("deck_id") or request.args.get("deck_id")
    if not deck_id_raw:
        return jsonify({"error": "VALIDATION_ERROR", "message": "deck_id là bắt buộc."}), 400

    try:
        deck_id = int(deck_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "VALIDATION_ERROR", "message": "deck_id phải là số nguyên."}), 400

    try:
        result = flashcard_audio_scan_service.scan_deck_audio(
            user_id=current_user.id,
            deck_id=deck_id,
            admin_mode=is_admin_user(current_user),
            upload_root=Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]),
        )
    except flashcard_audio_scan_service.AudioScanError as exc:
        return _error(exc)
    return jsonify(result)
