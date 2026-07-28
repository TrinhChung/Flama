"""Administrative TTS-provider resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.api.common import admin_required, error_response
from app.services import admin_rest_api_service, tts_provider_service

from .common import admin_service_error, request_payload


admin_tts_bp = Blueprint("api_v1_admin_tts", __name__)


@admin_tts_bp.get("")
@admin_required
def list_tts_providers():
    return jsonify(
        admin_rest_api_service.list_tts_providers(
            search_term=tts_provider_service.normalize_search_query(
                request.args.get("q")
            ),
            active_filter=tts_provider_service.normalize_active_filter(
                request.args.get("active")
            ),
            provider_type_filter=tts_provider_service.normalize_provider_type_filter(
                request.args.get("provider_type")
            ),
        )
    )


@admin_tts_bp.post("")
@admin_required
def create_tts_provider():
    try:
        row = admin_rest_api_service.save_tts_provider(
            actor_user_id=current_user.id,
            payload=request_payload(),
            row=None,
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return admin_service_error(exc)
    return jsonify(
        {"item": admin_rest_api_service.serialize_tts_provider(row)}
    ), 201


@admin_tts_bp.put("/<int:provider_id>")
@admin_required
def update_tts_provider(provider_id: int):
    row = admin_rest_api_service.get_tts_provider(provider_id)
    if row is None:
        return error_response(
            "NOT_FOUND",
            "Provider not found.",
            status=404,
        )
    try:
        row = admin_rest_api_service.save_tts_provider(
            actor_user_id=current_user.id,
            payload=request_payload(),
            row=row,
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return admin_service_error(exc)
    return jsonify(
        {"item": admin_rest_api_service.serialize_tts_provider(row)}
    )


@admin_tts_bp.delete("/<int:provider_id>")
@admin_required
def delete_tts_provider(provider_id: int):
    row = admin_rest_api_service.get_tts_provider(provider_id)
    if row is None:
        return error_response(
            "NOT_FOUND",
            "Provider not found.",
            status=404,
        )
    try:
        admin_rest_api_service.delete_tts_provider(row)
    except admin_rest_api_service.AdminRestApiError as exc:
        return admin_service_error(exc)
    return "", 204
