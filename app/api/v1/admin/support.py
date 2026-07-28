"""Administrative support-donation resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.api.common import admin_required
from app.services import admin_rest_api_service, support_donation_service

from .common import admin_service_error, request_payload


admin_support_bp = Blueprint("api_v1_admin_support", __name__)


@admin_support_bp.get("")
@admin_required
def get_support_donation():
    return jsonify(
        {
            "item": admin_rest_api_service.serialize_support_donation_config(
                support_donation_service.get_latest_config()
            )
        }
    )


@admin_support_bp.put("")
@admin_required
def update_support_donation():
    try:
        row = admin_rest_api_service.save_support_donation_config(
            actor_user_id=current_user.id,
            payload=request_payload(),
            uploaded_file=request.files.get("qr_image"),
        )
    except admin_rest_api_service.AdminRestApiError as exc:
        return admin_service_error(exc)
    return jsonify(
        {
            "item": admin_rest_api_service.serialize_support_donation_config(
                row
            )
        }
    )
