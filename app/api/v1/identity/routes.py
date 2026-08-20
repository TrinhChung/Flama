"""Identity and session REST API V1 routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common import error_response, json_object
from app.services import identity_api_service


identity_bp = Blueprint("api_v1_identity", __name__)


def _service_error(error: identity_api_service.IdentityApiError):
    payload = {
        "error": error.code,
        "message": str(error),
        **error.extras,
    }
    if error.field:
        payload["field"] = error.field
    return jsonify(payload), error.status


@identity_bp.get("/session")
def get_session():
    return jsonify(identity_api_service.session_payload())


@identity_bp.delete("/session")
@login_required
def delete_session():
    return jsonify(identity_api_service.logout_session())


@identity_bp.post("/auth/register")
def register():
    payload = {} if current_user.is_authenticated else json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        result, status = identity_api_service.register_account(
            payload=payload,
            authenticated=bool(current_user.is_authenticated),
        )
    except identity_api_service.IdentityApiError as exc:
        return _service_error(exc)
    return jsonify(result), status


@identity_bp.post("/auth/login")
def login():
    payload = {} if current_user.is_authenticated else json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        result = identity_api_service.login_account(
            payload=payload,
            authenticated=bool(current_user.is_authenticated),
            remote_addr=request.remote_addr,
        )
    except identity_api_service.IdentityApiError as exc:
        return _service_error(exc)
    return jsonify(result)
