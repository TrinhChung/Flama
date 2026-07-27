"""Versioned REST resources for form-based admin screens."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.repositories import image_library_repository
from app.services import admin_rest_api_service, admin_service, tts_provider_service
from app.utils.permissions import is_admin_user
from models import db
from models.tts_provider_config import TtsProviderConfig

admin_rest_api_bp = Blueprint(
    "admin_rest_api",
    __name__,
    url_prefix="/api/v1/admin",
)

IMAGE_STATUS_FILTERS = {"", "enabled", "disabled", "missing_file"}


def _error(error: admin_rest_api_service.AdminRestApiError):
    payload = {"error": error.code, "message": str(error)}
    if error.field:
        payload["field"] = error.field
    return jsonify(payload), error.status


def _guard():
    if is_admin_user(current_user):
        return None
    return jsonify(
        {
            "error": "FORBIDDEN",
            "message": "Administrator access is required.",
        }
    ), 403


def _request_payload() -> dict:
    if request.is_json:
        payload = request.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}
    return request.form.to_dict(flat=True)


@admin_rest_api_bp.get("/tts-providers")
@login_required
def list_tts_providers():
    guard = _guard()
    if guard is not None:
        return guard
    search_term = tts_provider_service.normalize_search_query(request.args.get("q"))
    active_filter = tts_provider_service.normalize_active_filter(
        request.args.get("active")
    )
    provider_type_filter = tts_provider_service.normalize_provider_type_filter(
        request.args.get("provider_type")
    )
    return jsonify(
        admin_rest_api_service.list_tts_providers(
            search_term=search_term,
            active_filter=active_filter,
            provider_type_filter=provider_type_filter,
        )
    )


@admin_rest_api_bp.post("/tts-providers")
@login_required
def create_tts_provider():
    guard = _guard()
    if guard is not None:
        return guard
    try:
        row = admin_rest_api_service.save_tts_provider(
            actor_user_id=current_user.id,
            payload=_request_payload(),
            row=None,
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return _error(exc)
    return jsonify({"item": admin_rest_api_service.serialize_tts_provider(row)}), 201


@admin_rest_api_bp.put("/tts-providers/<int:provider_id>")
@login_required
def update_tts_provider(provider_id: int):
    guard = _guard()
    if guard is not None:
        return guard
    row = db.session.get(TtsProviderConfig, provider_id)
    if row is None:
        return jsonify({"error": "NOT_FOUND", "message": "Provider not found."}), 404
    try:
        row = admin_rest_api_service.save_tts_provider(
            actor_user_id=current_user.id,
            payload=_request_payload(),
            row=row,
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return _error(exc)
    return jsonify({"item": admin_rest_api_service.serialize_tts_provider(row)})


@admin_rest_api_bp.delete("/tts-providers/<int:provider_id>")
@login_required
def delete_tts_provider(provider_id: int):
    guard = _guard()
    if guard is not None:
        return guard
    row = db.session.get(TtsProviderConfig, provider_id)
    if row is None:
        return jsonify({"error": "NOT_FOUND", "message": "Provider not found."}), 404
    try:
        admin_rest_api_service.delete_tts_provider(row)
    except admin_rest_api_service.AdminRestApiError as exc:
        return _error(exc)
    return "", 204


@admin_rest_api_bp.get("/support-donation")
@login_required
def get_support_donation():
    guard = _guard()
    if guard is not None:
        return guard
    from app.services import support_donation_service

    return jsonify(
        {
            "item": admin_rest_api_service.serialize_support_donation_config(
                support_donation_service.get_latest_config()
            )
        }
    )


@admin_rest_api_bp.put("/support-donation")
@login_required
def update_support_donation():
    guard = _guard()
    if guard is not None:
        return guard
    try:
        row = admin_rest_api_service.save_support_donation_config(
            actor_user_id=current_user.id,
            payload=_request_payload(),
            uploaded_file=request.files.get("qr_image"),
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return _error(exc)
    return jsonify(
        {
            "item": admin_rest_api_service.serialize_support_donation_config(
                row
            )
        }
    )


@admin_rest_api_bp.get("/image-library")
@login_required
def list_image_assets():
    guard = _guard()
    if guard is not None:
        return guard
    search_term = str(request.args.get("q") or "").strip()
    if len(search_term) > 120:
        return (
            jsonify(
                {
                    "error": "VALIDATION_ERROR",
                    "message": "q must not exceed 120 characters.",
                    "field": "q",
                }
            ),
            400,
        )
    status = str(request.args.get("status") or "").strip().lower()
    if status not in IMAGE_STATUS_FILTERS:
        status = ""
    page = admin_service.coerce_int(
        request.args.get("page"),
        default=1,
        minimum=1,
    )
    per_page = admin_service.coerce_int(
        request.args.get("per_page"),
        default=24,
        minimum=1,
        maximum=60,
    )
    return jsonify(
        admin_rest_api_service.list_image_assets(
            search_term=search_term,
            status=status,
            page=page,
            per_page=per_page,
        )
    )


@admin_rest_api_bp.post("/image-library")
@login_required
def create_image_asset():
    guard = _guard()
    if guard is not None:
        return guard
    try:
        row = admin_rest_api_service.save_image_asset(
            actor_user_id=current_user.id,
            payload=_request_payload(),
            uploaded_file=request.files.get("image"),
            row=None,
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return _error(exc)
    return jsonify({"item": admin_rest_api_service.serialize_image_asset(row)}), 201


@admin_rest_api_bp.patch("/image-library/<asset_id>")
@login_required
def update_image_asset(asset_id: str):
    guard = _guard()
    if guard is not None:
        return guard
    row = image_library_repository.get_by_id(asset_id)
    if row is None:
        return jsonify({"error": "NOT_FOUND", "message": "Image asset not found."}), 404
    try:
        row = admin_rest_api_service.save_image_asset(
            actor_user_id=current_user.id,
            payload=_request_payload(),
            uploaded_file=request.files.get("image"),
            row=row,
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return _error(exc)
    return jsonify({"item": admin_rest_api_service.serialize_image_asset(row)})
