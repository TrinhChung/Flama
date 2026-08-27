"""User Profile and Balance REST API routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common import error_response, json_object
from app.services import profile_service
from app.services.admin_service import coerce_int

profile_bp = Blueprint("api_v1_profile", __name__)


def _service_error(error: profile_service.ProfileServiceError):
    return error_response(
        error.code,
        error.message,
        status=error.status,
        field=error.field,
    )


@profile_bp.get("")
@login_required
def get_profile():
    return jsonify(profile_service.get_profile_payload(current_user))


@profile_bp.patch("")
@login_required
def update_profile():
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        result = profile_service.update_profile(current_user, payload)
    except profile_service.ProfileServiceError as exc:
        return _service_error(exc)
    return jsonify(result)


@profile_bp.get("/transactions")
@login_required
def list_transactions():
    page = coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = coerce_int(request.args.get("per_page"), default=10, minimum=1, maximum=100)
    tx_type = str(request.args.get("type") or "").strip() or None

    result = profile_service.list_profile_transactions(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
        transaction_type=tx_type,
    )
    return jsonify(result)
