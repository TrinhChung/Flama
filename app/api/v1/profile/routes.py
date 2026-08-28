"""User Profile and Creator Portfolio REST API routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common import error_response, json_object
from app.services import email_verification_service, profile_service
from app.services.admin_service import coerce_int

profile_bp = Blueprint("api_v1_profile", __name__)


def _service_error(error: profile_service.ProfileServiceError):
    return error_response(
        error.code,
        error.message,
        status=error.status,
        field=error.field,
    )


def _email_verification_error(error: email_verification_service.EmailVerificationError):
    payload = {
        "error": error.code,
        "message": str(error),
        **error.extras,
    }
    if error.field:
        payload["field"] = error.field
    return jsonify(payload), error.status


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
        result = profile_service.update_profile(
            current_user,
            payload,
            remote_addr=request.remote_addr,
        )
    except profile_service.ProfileServiceError as exc:
        return _service_error(exc)
    return jsonify(result)


@profile_bp.post("/avatar")
@login_required
def upload_avatar():
    file_storage = request.files.get("file") or request.files.get("avatar")
    try:
        result = profile_service.upload_avatar(current_user, file_storage)
    except profile_service.ProfileServiceError as exc:
        return _service_error(exc)
    return jsonify(result)


@profile_bp.delete("/avatar")
@login_required
def delete_avatar():
    try:
        result = profile_service.delete_avatar(current_user)
    except profile_service.ProfileServiceError as exc:
        return _service_error(exc)
    return jsonify(result)


@profile_bp.get("/u/<username>")
def get_public_profile(username: str):
    current_uid = current_user.id if getattr(current_user, "is_authenticated", False) else None
    try:
        result = profile_service.get_public_profile(username, current_user_id=current_uid)
    except profile_service.ProfileServiceError as exc:
        return _service_error(exc)
    return jsonify(result)


@profile_bp.get("/transactions")
@login_required
def list_transactions():
    """Backward-compatible endpoint delegating to wallet transaction query."""
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


@profile_bp.post("/verify-email/request")
@login_required
def request_email_verification():
    try:
        result = email_verification_service.request_email_verification(
            user=current_user,
            remote_addr=request.remote_addr,
        )
    except email_verification_service.EmailVerificationError as exc:
        return error_response(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
            **exc.extras,
        )
    return jsonify(result)


@profile_bp.post("/verify-email/confirm")
@login_required
def verify_email():
    payload = json_object() or {}
    code = payload.get("code") or payload.get("token") or ""
    try:
        result = email_verification_service.verify_email_with_code(
            user=current_user,
            code_or_token=str(code),
        )
    except email_verification_service.EmailVerificationError as exc:
        return error_response(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
            **exc.extras,
        )
    return jsonify(result)
