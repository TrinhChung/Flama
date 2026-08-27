"""Administrative user resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.api.common import admin_required, error_response, json_object
from app.services import admin_service, admin_user_api_service


admin_users_bp = Blueprint("api_v1_admin_users", __name__)


def _service_error(error: admin_user_api_service.AdminUserApiError):
    if error.extras:
        payload = {
            "error": error.code,
            "message": str(error),
            **error.extras,
        }
        if error.field:
            payload["field"] = error.field
        return jsonify(payload), error.status
    return error_response(
        error.code,
        str(error),
        status=error.status,
        field=error.field,
    )


@admin_users_bp.get("")
@admin_required
def list_users():
    search_term = str(request.args.get("q") or "").strip()
    if len(search_term) > 120:
        return error_response(
            "VALIDATION_ERROR",
            "q must not exceed 120 characters.",
            status=400,
            field="q",
        )
    status_filter = admin_service.normalize_status_filter(
        request.args.get("status")
    )
    user_ids = admin_service.parse_user_ids(
        request.args.get("ids") or request.args.get("user_ids")
    )
    raw_role_id = request.args.get("role_id")
    role_id = (
        admin_service.coerce_int(raw_role_id, default=0, minimum=1)
        if raw_role_id
        else None
    )
    return jsonify(
        admin_user_api_service.list_users(
            search_term=search_term,
            status_filter=status_filter,
            user_ids=user_ids or None,
            role_id=role_id,
            page=admin_service.coerce_int(
                request.args.get("page"),
                default=1,
                minimum=1,
            ),
            per_page=admin_service.coerce_int(
                request.args.get("per_page"),
                default=10,
                minimum=1,
                maximum=100,
            ),
        )
    )


@admin_users_bp.patch("/<int:user_id>")
@admin_required
def update_user(user_id: int):
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    try:
        result = admin_user_api_service.update_user(
            actor_user_id=current_user.id,
            user_id=user_id,
            payload=payload,
        )
    except admin_user_api_service.AdminUserApiError as exc:
        return _service_error(exc)
    return jsonify(result)


@admin_users_bp.post("/roles/batch")
@admin_required
def batch_assign_roles():
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    user_ids = admin_service.parse_user_ids_payload(payload)
    role_id = admin_service.coerce_int(
        payload.get("target_role_id"),
        default=0,
        minimum=1,
    )
    mode = str(payload.get("mode") or "replace").strip().lower()
    if not user_ids:
        return error_response(
            "VALIDATION_ERROR",
            "user_ids must contain at least one valid user id.",
            status=400,
            field="user_ids",
        )
    if mode != "replace":
        return error_response(
            "VALIDATION_ERROR",
            "Only replace mode is supported.",
            status=400,
            field="mode",
        )
    try:
        success_count, fail_count, results = (
            admin_user_api_service.batch_assign_roles(
                actor_user_id=current_user.id,
                user_ids=user_ids,
                role_id=role_id,
            )
        )
    except admin_user_api_service.AdminUserApiError as exc:
        return _service_error(exc)
    return jsonify(
        {
            "message": "Batch role assignment completed.",
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results,
        }
    )


@admin_users_bp.post("/status/batch")
@admin_required
def batch_update_status():
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    user_ids = admin_service.parse_user_ids_payload(payload)
    action = str(payload.get("action") or "").strip().lower()
    if not user_ids:
        return error_response(
            "VALIDATION_ERROR",
            "user_ids must contain at least one valid user id.",
            status=400,
            field="user_ids",
        )
    if action not in {"activate", "disable"}:
        return error_response(
            "VALIDATION_ERROR",
            "action must be activate or disable.",
            status=400,
            field="action",
        )
    try:
        success_count, fail_count, results = (
            admin_user_api_service.batch_update_status(
                actor_user_id=current_user.id,
                user_ids=user_ids,
                action=action,
            )
        )
    except admin_user_api_service.AdminUserApiError as exc:
        return _service_error(exc)
    return jsonify(
        {
            "message": "Batch status update completed.",
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results,
        }
    )
