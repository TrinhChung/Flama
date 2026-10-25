"""Administrative usage quota resources (API, MCP and media upload)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.api.common import admin_required, error_response, json_object
from app.services import admin_quota_service
from app.services.admin_quota_service import AdminQuotaServiceError

admin_quotas_bp = Blueprint("api_v1_admin_quotas", __name__)


def _service_error(error: AdminQuotaServiceError):
    return error_response(error.code, str(error), status=error.status, field=error.field)


def _payload():
    payload = json_object()
    if payload is None:
        return None, error_response("VALIDATION_ERROR", "Payload must be a JSON object.", status=400)
    return payload, None


@admin_quotas_bp.get("")
@admin_required
def get_quota_overview():
    """Policies, role defaults, current-period usage rankings and user overrides."""
    try:
        overview = admin_quota_service.get_overview(period=str(request.args.get("period") or "day"))
    except AdminQuotaServiceError as exc:
        return _service_error(exc)
    return jsonify(overview)


@admin_quotas_bp.put("/policies/<kind>")
@admin_required
def update_quota_policy(kind: str):
    payload, error = _payload()
    if error is not None:
        return error
    try:
        policy = admin_quota_service.update_policy(kind=kind, payload=payload, actor_user_id=int(current_user.id))
    except AdminQuotaServiceError as exc:
        return _service_error(exc)
    return jsonify({"policy": policy, "message": "Đã lưu chính sách quota."})


@admin_quotas_bp.get("/users/search")
@admin_required
def search_quota_users():
    q = str(request.args.get("q") or "").strip()
    if len(q) > 100:
        return error_response("VALIDATION_ERROR", "q must not exceed 100 characters.", status=400, field="q")
    return jsonify({"items": admin_quota_service.search_users(query_text=q)})


@admin_quotas_bp.get("/users/<int:user_id>")
@admin_required
def get_user_quota(user_id: int):
    try:
        return jsonify(admin_quota_service.get_user_detail(user_id))
    except AdminQuotaServiceError as exc:
        return _service_error(exc)


@admin_quotas_bp.put("/users/<int:user_id>/<kind>")
@admin_required
def upsert_user_quota(user_id: int, kind: str):
    payload, error = _payload()
    if error is not None:
        return error
    try:
        detail = admin_quota_service.upsert_override(
            user_id=user_id, kind=kind, payload=payload, actor_user_id=int(current_user.id)
        )
    except AdminQuotaServiceError as exc:
        return _service_error(exc)
    return jsonify({**detail, "message": "Đã lưu quota riêng cho người dùng."})


@admin_quotas_bp.delete("/users/<int:user_id>/<kind>")
@admin_required
def delete_user_quota(user_id: int, kind: str):
    try:
        detail = admin_quota_service.delete_override(user_id=user_id, kind=kind)
    except AdminQuotaServiceError as exc:
        return _service_error(exc)
    return jsonify({**detail, "message": "Đã xoá quota riêng, người dùng quay về mặc định theo vai trò."})
