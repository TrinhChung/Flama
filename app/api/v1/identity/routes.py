"""Identity and session REST API V1 routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common import error_response, json_object
from app.services import (
    email_verification_service,
    identity_api_service,
    student_verification_service,
)


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


def _email_verification_error(error: email_verification_service.EmailVerificationError):
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


@identity_bp.get("/student-status")
def get_student_status():
    return jsonify(student_verification_service.serialize_student_profile(current_user))


@identity_bp.post("/email/request-verification")
@login_required
def request_email_verification():
    try:
        result = email_verification_service.request_email_verification(
            user=current_user,
            remote_addr=request.remote_addr,
        )
    except email_verification_service.EmailVerificationError as exc:
        return _email_verification_error(exc)
    return jsonify(result)


@identity_bp.post("/email/verify")
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
        return _email_verification_error(exc)
    return jsonify(result)


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


@identity_bp.post("/auth/forgot-password")
def forgot_password():
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        result = identity_api_service.request_password_reset(
            payload=payload,
            remote_addr=request.remote_addr,
        )
    except identity_api_service.IdentityApiError as exc:
        return _service_error(exc)
    return jsonify(result)


@identity_bp.post("/auth/reset-password")
def reset_password():
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        result = identity_api_service.reset_password_with_token(payload=payload)
    except identity_api_service.IdentityApiError as exc:
        return _service_error(exc)
    return jsonify(result)
