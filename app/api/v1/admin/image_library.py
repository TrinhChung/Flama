"""Administrative shared-image library resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.api.common import admin_required, error_response
from app.services import admin_rest_api_service, admin_service

from .common import admin_service_error, request_payload


admin_image_library_bp = Blueprint("api_v1_admin_image_library", __name__)

IMAGE_STATUS_FILTERS = {"", "enabled", "disabled", "missing_file"}


@admin_image_library_bp.get("")
@admin_required
def list_image_assets():
    search_term = str(request.args.get("q") or "").strip()
    if len(search_term) > 120:
        return error_response(
            "VALIDATION_ERROR",
            "q must not exceed 120 characters.",
            status=400,
            field="q",
        )
    status = str(request.args.get("status") or "").strip().lower()
    if status not in IMAGE_STATUS_FILTERS:
        status = ""
    return jsonify(
        admin_rest_api_service.list_image_assets(
            search_term=search_term,
            status=status,
            page=admin_service.coerce_int(
                request.args.get("page"),
                default=1,
                minimum=1,
            ),
            per_page=admin_service.coerce_int(
                request.args.get("per_page"),
                default=24,
                minimum=1,
                maximum=60,
            ),
        )
    )


@admin_image_library_bp.post("")
@admin_required
def create_image_asset():
    try:
        row = admin_rest_api_service.save_image_asset(
            actor_user_id=current_user.id,
            payload=request_payload(),
            uploaded_file=request.files.get("image"),
            row=None,
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return admin_service_error(exc)
    return jsonify(
        {"item": admin_rest_api_service.serialize_image_asset(row)}
    ), 201


@admin_image_library_bp.patch("/<asset_id>")
@admin_required
def update_image_asset(asset_id: str):
    row = admin_rest_api_service.get_image_asset(asset_id)
    if row is None:
        return error_response(
            "NOT_FOUND",
            "Image asset not found.",
            status=404,
        )
    try:
        row = admin_rest_api_service.save_image_asset(
            actor_user_id=current_user.id,
            payload=request_payload(),
            uploaded_file=request.files.get("image"),
            row=row,
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return admin_service_error(exc)
    return jsonify(
        {"item": admin_rest_api_service.serialize_image_asset(row)}
    )
