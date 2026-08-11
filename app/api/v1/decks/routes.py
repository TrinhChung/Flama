"""Deck REST API V1 routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common import admin_required, error_response, json_object
from app.api.v1.decks.presenters import serialize_deck
from app.services import deck_api_service
from app.utils.permissions import is_admin_user


decks_bp = Blueprint("api_v1_decks", __name__)


def _service_error(error: deck_api_service.DeckApiError):
    return error_response(
        error.code,
        str(error),
        status=error.status,
        field=error.field,
    )


@decks_bp.post("")
@login_required
def create_deck():
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        result = deck_api_service.create_deck(
            payload=payload,
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
        )
    except deck_api_service.DeckApiError as exc:
        return _service_error(exc)
    return jsonify(
        {
            "created_count": result.created_count,
            "created_names": result.created_names,
            "path": result.path_tokens,
            "item": (
                serialize_deck(result.final_deck)
                if result.final_deck is not None
                else None
            ),
        }
    ), 201 if result.created_count else 200


@decks_bp.patch("/<int:deck_id>")
@admin_required
def update_deck(deck_id: int):
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        result = deck_api_service.update_deck(
            deck_id=deck_id,
            payload=payload,
        )
    except deck_api_service.DeckApiError as exc:
        return _service_error(exc)
    return jsonify(
        {
            "changed": result.changed,
            "item": serialize_deck(result.deck),
        }
    )


@decks_bp.delete("/<int:deck_id>")
@login_required
def delete_deck(deck_id: int):
    purge = request.args.get("purge") == "true"
    if purge and not is_admin_user(current_user):
        return error_response(
            "FORBIDDEN",
            "Only administrators can purge decks.",
            status=403,
        )
    try:
        mode = deck_api_service.delete_deck(
            deck_id=deck_id,
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            purge=purge,
        )
    except deck_api_service.DeckApiError as exc:
        return _service_error(exc)
    return jsonify({"deleted": True, "mode": mode, "id": deck_id})


@decks_bp.post("/<int:deck_id>/progress-reset")
@login_required
def reset_deck_progress(deck_id: int):
    try:
        deleted_count = deck_api_service.reset_deck_progress(
            deck_id=deck_id,
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
        )
    except deck_api_service.DeckApiError as exc:
        return _service_error(exc)
    return jsonify(
        {
            "reset": True,
            "deck_id": deck_id,
            "deleted_progress_count": deleted_count,
        }
    )
