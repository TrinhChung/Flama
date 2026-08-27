"""Administrative platform fee and commission resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.common import admin_required, error_response, json_object
from app.services import admin_fee_service
from app.services.admin_fee_service import AdminFeeServiceError

admin_fees_bp = Blueprint("api_v1_admin_fees", __name__)


def _fee_service_error(error: AdminFeeServiceError):
    return error_response(
        error.code,
        str(error),
        status=error.status,
        field=error.field,
    )


@admin_fees_bp.get("")
@admin_required
def get_fee_overview():
    """Return overview metrics, role fee rates, creator monetization policies, and custom fee users."""
    try:
        overview = admin_fee_service.get_fee_overview()
    except AdminFeeServiceError as exc:
        return _fee_service_error(exc)
    return jsonify(overview)


@admin_fees_bp.patch("/roles/<int:role_id>")
@admin_required
def update_role_fee(role_id: int):
    """Update default platform fee percentage for a specific role."""
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )

    if "default_platform_fee_percent" not in payload:
        return error_response(
            "VALIDATION_ERROR",
            "default_platform_fee_percent is required.",
            status=400,
            field="default_platform_fee_percent",
        )

    try:
        fee_percent = float(payload.get("default_platform_fee_percent"))
    except (TypeError, ValueError):
        return error_response(
            "VALIDATION_ERROR",
            "default_platform_fee_percent must be a valid number.",
            status=400,
            field="default_platform_fee_percent",
        )

    try:
        role_data = admin_fee_service.update_role_default_fee(
            role_id=role_id,
            fee_percent=fee_percent,
        )
    except AdminFeeServiceError as exc:
        return _fee_service_error(exc)

    return jsonify({"role": role_data, "message": "Đã cập nhật tỷ lệ phí cho vai trò thành công."})


@admin_fees_bp.put("/creator-policy")
@admin_required
def update_creator_policy():
    """Update monetization and quota policy for creator features (deck access keys)."""
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )

    feature_code = str(payload.get("feature_code") or "deck_access_keys").strip()
    is_monetized = payload.get("is_monetized")
    free_quota = payload.get("free_quota_per_creator")
    price_minor = payload.get("price_per_key_minor")
    requires_pro = payload.get("requires_pro_role")

    try:
        policy_data = admin_fee_service.update_creator_feature_policy(
            feature_code=feature_code,
            is_monetized=bool(is_monetized) if is_monetized is not None else None,
            free_quota_per_creator=int(free_quota) if free_quota is not None else None,
            price_per_key_minor=int(price_minor) if price_minor is not None else None,
            requires_pro_role=bool(requires_pro) if requires_pro is not None else None,
        )
    except (TypeError, ValueError) as exc:
        return error_response(
            "VALIDATION_ERROR",
            "Giá trị số không hợp lệ.",
            status=400,
        )
    except AdminFeeServiceError as exc:
        return _fee_service_error(exc)

    return jsonify({"creator_policy": policy_data, "message": "Đã lưu chính sách tính năng Creator thành công."})


@admin_fees_bp.patch("/users/<int:user_id>")
@admin_required
def update_user_custom_fee(user_id: int):
    """Set or reset custom platform fee override for an individual user."""
    payload = json_object()
    if payload is None:
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )

    if "custom_platform_fee_percent" not in payload:
        return error_response(
            "VALIDATION_ERROR",
            "custom_platform_fee_percent is required (provide a number or null to reset).",
            status=400,
            field="custom_platform_fee_percent",
        )

    raw_val = payload.get("custom_platform_fee_percent")
    custom_fee = None
    if raw_val is not None and raw_val != "":
        try:
            custom_fee = float(raw_val)
        except (TypeError, ValueError):
            return error_response(
                "VALIDATION_ERROR",
                "custom_platform_fee_percent must be a number between 0 and 100, or null.",
                status=400,
                field="custom_platform_fee_percent",
            )

    try:
        user_data = admin_fee_service.update_user_custom_fee(
            user_id=user_id,
            custom_fee_percent=custom_fee,
        )
    except AdminFeeServiceError as exc:
        return _fee_service_error(exc)

    msg = (
        f"Đã thiết lập phí tùy chỉnh thành {custom_fee}% cho người dùng."
        if custom_fee is not None
        else "Đã xóa ngoại lệ phí, đưa về mức phí mặc định theo vai trò."
    )
    return jsonify({"user": user_data, "message": msg})


@admin_fees_bp.get("/search-users")
@admin_required
def search_users():
    """Search users to configure custom fee override."""
    q = str(request.args.get("q") or "").strip()
    if len(q) > 100:
        return error_response("VALIDATION_ERROR", "q must not exceed 100 characters.", status=400, field="q")

    limit = 10
    raw_limit = request.args.get("limit")
    if raw_limit and raw_limit.isdigit():
        limit = min(max(1, int(raw_limit)), 30)

    results = admin_fee_service.search_users_for_fee_override(
        query_text=q,
        limit=limit,
    )
    return jsonify({"items": results})
