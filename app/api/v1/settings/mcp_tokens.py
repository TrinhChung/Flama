"""User-managed MCP access-token lifecycle."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.api.common import error_response
from app.services import mcp_access_token_service


mcp_tokens_bp = Blueprint("api_v1_mcp_tokens", __name__)


@mcp_tokens_bp.get("")
@login_required
def list_tokens():
    return jsonify(
        {
            "items": mcp_access_token_service.list_token_summaries(
                user_id=current_user.id
            ),
            "policy": mcp_access_token_service.get_token_policy(),
        }
    )


@mcp_tokens_bp.post("")
@login_required
def create_token():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name") if isinstance(payload, dict) else None
    expires_in_days = payload.get("expires_in_days", 180) if isinstance(payload, dict) else 180
    scopes = payload.get("scopes") if isinstance(payload, dict) else None

    try:
        issued_token = mcp_access_token_service.issue_token_and_commit(
            user_id=current_user.id,
            name=name,
            expires_in_days=expires_in_days,
            scopes=scopes,
        )
    except mcp_access_token_service.McpAccessTokenPersistenceError as exc:
        return error_response(
            "DB_ERROR",
            str(exc),
            status=500,
        )
    return jsonify({"item": issued_token.to_display_payload()}), 201


@mcp_tokens_bp.patch("/<int:token_id>")
@login_required
def update_token(token_id: int):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "A JSON object is required.", status=400)

    name = payload.get("name")
    expires_in_days = payload.get("expires_in_days", ...)
    scopes = payload.get("scopes")

    try:
        updated = mcp_access_token_service.update_token_and_commit(
            user_id=current_user.id,
            token_id=token_id,
            name=name,
            expires_in_days=expires_in_days,
            scopes=scopes,
        )
    except mcp_access_token_service.McpAccessTokenPersistenceError as exc:
        return error_response("DB_ERROR", str(exc), status=500)

    if updated is None:
        return error_response("NOT_FOUND", "MCP token not found.", status=404)

    return jsonify({"item": updated}), 200


@mcp_tokens_bp.post("/<int:token_id>/rotate")
@login_required
def rotate_token(token_id: int):
    payload = request.get_json(silent=True) or {}
    expires_in_days = payload.get("expires_in_days", ...) if isinstance(payload, dict) else ...
    scopes = payload.get("scopes") if isinstance(payload, dict) else None

    try:
        issued_token = mcp_access_token_service.rotate_token_and_commit(
            user_id=current_user.id,
            token_id=token_id,
            expires_in_days=expires_in_days,
            scopes=scopes,
        )
    except mcp_access_token_service.McpAccessTokenPersistenceError as exc:
        return error_response("DB_ERROR", str(exc), status=500)

    if issued_token is None:
        return error_response("NOT_FOUND", "MCP token not found.", status=404)

    return jsonify({"item": issued_token.to_display_payload()}), 200


@mcp_tokens_bp.delete("/<int:token_id>")
@login_required
def delete_token(token_id: int):
    try:
        revoked = mcp_access_token_service.revoke_token_and_commit(
            user_id=current_user.id,
            token_id=token_id,
        )
    except mcp_access_token_service.McpAccessTokenPersistenceError as exc:
        return error_response(
            "DB_ERROR",
            str(exc),
            status=500,
        )
    if not revoked:
        return error_response(
            "NOT_FOUND",
            "MCP token not found.",
            status=404,
        )
    return "", 204


@mcp_tokens_bp.delete("/<int:token_id>/purge")
@login_required
def purge_token(token_id: int):
    try:
        purged = mcp_access_token_service.purge_token_and_commit(
            user_id=current_user.id,
            token_id=token_id,
        )
    except mcp_access_token_service.McpAccessTokenPersistenceError as exc:
        return error_response("DB_ERROR", str(exc), status=500)

    if not purged:
        return error_response("NOT_FOUND", "MCP token not found.", status=404)

    return "", 204


@mcp_tokens_bp.post("/cleanup")
@login_required
def cleanup_tokens():
    try:
        count = mcp_access_token_service.cleanup_tokens_and_commit(
            user_id=current_user.id,
        )
    except mcp_access_token_service.McpAccessTokenPersistenceError as exc:
        return error_response("DB_ERROR", str(exc), status=500)

    return jsonify({"success": True, "purged_count": count}), 200

