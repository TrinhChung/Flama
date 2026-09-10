"""Admin management endpoints for MCP tokens and user access permissions."""

from __future__ import annotations

from datetime import datetime, timedelta
import secrets
from typing import Any

from flask import Blueprint, jsonify, request
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.api.common import admin_required, error_response, json_object
from app.services import mcp_access_token_service, mcp_scope_service
from app.services.mcp_access_token_service import (
    DEFAULT_SCOPES,
    _dump_scopes,
    _hash_token,
    _normalize_scopes,
    _resolve_status,
)
from models import db
from models.mcp_access_token import McpAccessToken
from models.user import User
from models.user_permission_audit_log import UserPermissionAuditLog

admin_mcp_tokens_bp = Blueprint("api_v1_admin_mcp_tokens", __name__)


@admin_mcp_tokens_bp.before_request
@admin_required
def _ensure_admin_access():
    pass


@admin_mcp_tokens_bp.get("/summary")
def get_mcp_summary():
    """Return overview metrics for MCP tokens and user access."""
    now = datetime.utcnow()

    total_tokens = db.session.query(func.count(McpAccessToken.id)).scalar() or 0
    active_tokens = (
        db.session.query(func.count(McpAccessToken.id))
        .filter(
            McpAccessToken.revoked.is_(False),
            or_(
                McpAccessToken.expires_at.is_(None),
                McpAccessToken.expires_at > now,
            ),
        )
        .scalar()
        or 0
    )
    revoked_tokens = (
        db.session.query(func.count(McpAccessToken.id))
        .filter(McpAccessToken.revoked.is_(True))
        .scalar()
        or 0
    )
    expired_tokens = (
        db.session.query(func.count(McpAccessToken.id))
        .filter(
            McpAccessToken.revoked.is_(False),
            McpAccessToken.expires_at.isnot(None),
            McpAccessToken.expires_at <= now,
        )
        .scalar()
        or 0
    )
    total_requests = (
        db.session.query(func.coalesce(func.sum(McpAccessToken.used_requests), 0)).scalar() or 0
    )

    total_users = db.session.query(func.count(User.id)).scalar() or 0
    permitted_users = (
        db.session.query(func.count(User.id))
        .filter(
            or_(
                User.is_admin.is_(True),
                User.can_manage_mcp_tokens.is_(True),
                User.can_use_mcp.is_(True),
            )
        )
        .scalar()
        or 0
    )

    return jsonify(
        {
            "total_tokens": total_tokens,
            "active_tokens": active_tokens,
            "revoked_tokens": revoked_tokens,
            "expired_tokens": expired_tokens,
            "inactive_tokens": revoked_tokens + expired_tokens,
            "total_requests": int(total_requests),
            "total_users": total_users,
            "permitted_users": permitted_users,
        }
    )


@admin_mcp_tokens_bp.get("/users")
def list_users_mcp_status():
    """List users with their MCP permission status and token counts."""
    search_term = str(request.args.get("q") or "").strip()
    permission_filter = str(request.args.get("filter") or "all").strip().lower()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

    query = User.query.options(selectinload(User.role))

    if search_term:
        term = f"%{search_term}%"
        query = query.filter(
            or_(
                User.username.ilike(term),
                User.email.ilike(term),
                User.display_name.ilike(term),
            )
        )

    if permission_filter == "permitted":
        query = query.filter(
            or_(
                User.is_admin.is_(True),
                User.can_manage_mcp_tokens.is_(True),
                User.can_use_mcp.is_(True),
            )
        )
    elif permission_filter == "unpermitted":
        query = query.filter(
            User.is_admin.is_(False),
            or_(User.can_manage_mcp_tokens.is_(False), User.can_manage_mcp_tokens.is_(None)),
            or_(User.can_use_mcp.is_(False), User.can_use_mcp.is_(None)),
        )

    query = query.order_by(User.id.asc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    user_ids = [u.id for u in pagination.items]
    now = datetime.utcnow()

    # Query token counts per user
    token_counts: dict[int, dict[str, int]] = {uid: {"active": 0, "total": 0} for uid in user_ids}
    if user_ids:
        rows = (
            db.session.query(
                McpAccessToken.user_id,
                McpAccessToken.revoked,
                McpAccessToken.expires_at,
            )
            .filter(McpAccessToken.user_id.in_(user_ids))
            .all()
        )
        for uid, revoked, expires_at in rows:
            token_counts[uid]["total"] += 1
            if not revoked and (expires_at is None or expires_at > now):
                token_counts[uid]["active"] += 1

    items = []
    for user in pagination.items:
        can_manage = bool(
            user.is_admin
            or getattr(user, "can_manage_mcp_tokens", False)
            or getattr(user, "can_use_mcp", False)
        )
        raw_can_manage = bool(
            getattr(user, "can_manage_mcp_tokens", False)
            or getattr(user, "can_use_mcp", False)
        )
        items.append(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "display_name": getattr(user, "display_name", None) or user.username,
                "avatar_url": getattr(user, "avatar_url", None),
                "role_name": user.role.name if user.role else ("Admin" if user.is_admin else "User"),
                "is_admin": bool(user.is_admin),
                "is_disabled": bool(user.is_disabled),
                "can_manage_mcp_tokens": can_manage,
                "raw_can_manage_mcp_tokens": raw_can_manage,
                "can_use_mcp": True,
                "raw_can_use_mcp": raw_can_manage,
                "active_tokens_count": token_counts[user.id]["active"],
                "total_tokens_count": token_counts[user.id]["total"],
            }
        )

    return jsonify(
        {
            "items": items,
            "total": pagination.total,
            "page": pagination.page,
            "per_page": per_page,
            "pages": max(pagination.pages, 1),
        }
    )


@admin_mcp_tokens_bp.post("/users/<int:user_id>/permission")
def set_user_mcp_permission(user_id: int):
    """Grant or revoke MCP token management permission for a user."""
    user = db.session.get(User, user_id)
    if user is None:
        return error_response("NOT_FOUND", "User not found.", status=404)

    payload = json_object() or {}
    if "can_manage_mcp_tokens" in payload:
        new_val = bool(payload["can_manage_mcp_tokens"])
    elif "can_use_mcp" in payload:
        new_val = bool(payload["can_use_mcp"])
    else:
        return error_response("VALIDATION_ERROR", "can_manage_mcp_tokens or can_use_mcp is required.", status=400)

    old_val = bool(getattr(user, "can_manage_mcp_tokens", False) or getattr(user, "can_use_mcp", False))

    user.can_manage_mcp_tokens = new_val
    user.can_use_mcp = new_val
    db.session.add(user)

    # Record in audit log
    db.session.add(
        UserPermissionAuditLog(
            actor_user_id=current_user.id,
            target_user_id=user.id,
            action="update_mcp_token_management_permission",
            from_role_id=user.role_id,
            to_role_id=user.role_id,
            from_is_admin=bool(user.is_admin),
            to_is_admin=bool(user.is_admin),
            from_is_disabled=bool(user.is_disabled),
            to_is_disabled=bool(user.is_disabled),
            message=f"{'Cấp' if new_val else 'Thu hồi'} quyền Quản lý Token MCP (trước: {old_val}, sau: {new_val})",
        )
    )

    db.session.commit()

    can_manage_now = bool(user.is_admin or user.can_manage_mcp_tokens)
    return jsonify(
        {
            "success": True,
            "user_id": user.id,
            "can_manage_mcp_tokens": can_manage_now,
            "raw_can_manage_mcp_tokens": bool(user.can_manage_mcp_tokens),
            "can_use_mcp": True,
            "raw_can_use_mcp": bool(user.can_manage_mcp_tokens),
            "message": f"Đã {'cấp' if new_val else 'thu hồi'} quyền Quản lý Token MCP cho {user.username}.",
        }
    )


@admin_mcp_tokens_bp.get("/tokens")
def list_system_tokens():
    """List all tokens across users with status, owner, and scope info."""
    user_id = request.args.get("user_id", type=int)
    status_filter = str(request.args.get("status") or "all").strip().lower()
    search_term = str(request.args.get("q") or "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 50, type=int), 1), 200)

    now = datetime.utcnow()

    query = (
        McpAccessToken.query.join(User, McpAccessToken.user_id == User.id)
        .options(selectinload(McpAccessToken.user), selectinload(McpAccessToken.client))
    )

    if user_id:
        query = query.filter(McpAccessToken.user_id == user_id)

    if search_term:
        term = f"%{search_term}%"
        query = query.filter(
            or_(
                McpAccessToken.name.ilike(term),
                User.username.ilike(term),
                User.email.ilike(term),
            )
        )

    if status_filter == "active":
        query = query.filter(
            McpAccessToken.revoked.is_(False),
            or_(McpAccessToken.expires_at.is_(None), McpAccessToken.expires_at > now),
        )
    elif status_filter == "revoked":
        query = query.filter(McpAccessToken.revoked.is_(True))
    elif status_filter == "expired":
        query = query.filter(
            McpAccessToken.revoked.is_(False),
            McpAccessToken.expires_at.isnot(None),
            McpAccessToken.expires_at <= now,
        )

    query = query.order_by(McpAccessToken.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for token in pagination.items:
        owner = token.user
        max_requests = int(token.max_requests or 0)
        used_requests = int(token.used_requests or 0)
        items.append(
            {
                "id": token.id,
                "user_id": token.user_id,
                "username": owner.username if owner else "Unknown",
                "email": owner.email if owner else "",
                "client_id": token.client_id,
                "client_name": token.client.client_name if token.client else None,
                "name": token.name or "MCP Token",
                "status": _resolve_status(row=token, now=now),
                "scopes": list(_normalize_scopes(token.scopes)),
                "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                "max_requests": max_requests,
                "used_requests": used_requests,
                "remaining_requests": max(max_requests - used_requests, 0),
                "created_at": token.created_at.isoformat() if token.created_at else None,
                "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
                "revoked": bool(token.revoked),
            }
        )

    return jsonify(
        {
            "items": items,
            "total": pagination.total,
            "page": pagination.page,
            "per_page": per_page,
            "pages": max(pagination.pages, 1),
        }
    )


@admin_mcp_tokens_bp.post("/tokens")
def create_system_token():
    """Admin issues a new token on behalf of a user."""
    payload = json_object() or {}
    user_id = payload.get("user_id")
    if not user_id:
        return error_response("VALIDATION_ERROR", "user_id is required.", status=400)

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return error_response("VALIDATION_ERROR", "user_id must be an integer.", status=400)

    target_user = db.session.get(User, user_id)
    if target_user is None:
        return error_response("NOT_FOUND", "User not found.", status=404)

    name = payload.get("name")
    expires_in_days = payload.get("expires_in_days", 180)
    scopes = payload.get("scopes")
    custom_token = payload.get("custom_token") or payload.get("token")
    if custom_token:
        custom_token = str(custom_token).strip()
        if len(custom_token) < 16:
            return error_response("VALIDATION_ERROR", "custom_token must be at least 16 characters.", status=400)

    try:
        issued_token = mcp_access_token_service.issue_token_and_commit(
            user_id=target_user.id,
            name=name,
            expires_in_days=expires_in_days,
            scopes=scopes,
            custom_token=custom_token,
        )
    except Exception as exc:
        return error_response("DB_ERROR", str(exc), status=500)

    return jsonify({"item": issued_token.to_display_payload(), "user_id": target_user.id}), 201


@admin_mcp_tokens_bp.patch("/tokens/<int:token_id>")
def update_system_token(token_id: int):
    """Admin updates token name, scopes, or expiry."""
    token_row = db.session.get(McpAccessToken, token_id)
    if token_row is None:
        return error_response("NOT_FOUND", "Token not found.", status=404)

    payload = json_object() or {}
    name = payload.get("name")
    expires_in_days = payload.get("expires_in_days", ...)
    scopes = payload.get("scopes")

    try:
        updated = mcp_access_token_service.update_token_and_commit(
            user_id=token_row.user_id,
            token_id=token_id,
            name=name,
            expires_in_days=expires_in_days,
            scopes=scopes,
        )
    except Exception as exc:
        return error_response("DB_ERROR", str(exc), status=500)

    if updated is None:
        return error_response("NOT_FOUND", "Token not found.", status=404)

    return jsonify({"item": updated}), 200


@admin_mcp_tokens_bp.post("/tokens/<int:token_id>/rotate")
def rotate_system_token(token_id: int):
    """Admin rotates a token secret."""
    token_row = db.session.get(McpAccessToken, token_id)
    if token_row is None:
        return error_response("NOT_FOUND", "Token not found.", status=404)

    payload = json_object() or {}
    expires_in_days = payload.get("expires_in_days", ...)
    scopes = payload.get("scopes")

    try:
        issued_token = mcp_access_token_service.rotate_token_and_commit(
            user_id=token_row.user_id,
            token_id=token_id,
            expires_in_days=expires_in_days,
            scopes=scopes,
        )
    except Exception as exc:
        return error_response("DB_ERROR", str(exc), status=500)

    if issued_token is None:
        return error_response("NOT_FOUND", "Token not found.", status=404)

    return jsonify({"item": issued_token.to_display_payload()}), 200


@admin_mcp_tokens_bp.delete("/tokens/<int:token_id>")
def revoke_system_token(token_id: int):
    """Admin revokes a token."""
    token_row = db.session.get(McpAccessToken, token_id)
    if token_row is None:
        return error_response("NOT_FOUND", "Token not found.", status=404)

    try:
        revoked = mcp_access_token_service.revoke_token_and_commit(
            user_id=token_row.user_id,
            token_id=token_id,
        )
    except Exception as exc:
        return error_response("DB_ERROR", str(exc), status=500)

    if not revoked:
        return error_response("NOT_FOUND", "Token not found or already revoked.", status=404)

    return "", 204


@admin_mcp_tokens_bp.delete("/tokens/<int:token_id>/purge")
def purge_system_token(token_id: int):
    """Admin permanently deletes a token."""
    token_row = db.session.get(McpAccessToken, token_id)
    if token_row is None:
        return error_response("NOT_FOUND", "Token not found.", status=404)

    try:
        purged = mcp_access_token_service.purge_token_and_commit(
            user_id=token_row.user_id,
            token_id=token_id,
        )
    except Exception as exc:
        return error_response("DB_ERROR", str(exc), status=500)

    if not purged:
        return error_response("NOT_FOUND", "Token not found.", status=404)

    return "", 204


@admin_mcp_tokens_bp.post("/cleanup")
def cleanup_system_tokens():
    """Admin cleans up all expired and revoked tokens system-wide."""
    now = datetime.utcnow()
    query = McpAccessToken.query.filter(
        or_(
            McpAccessToken.revoked.is_(True),
            McpAccessToken.expires_at <= now,
        )
    )
    count = query.delete(synchronize_session=False)
    db.session.commit()
    return jsonify({"success": True, "purged_count": count}), 200
