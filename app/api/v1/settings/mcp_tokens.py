"""Administrative MCP access-token lifecycle."""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_login import current_user

from app.api.common import admin_required, error_response
from app.services import mcp_access_token_service


mcp_tokens_bp = Blueprint("api_v1_mcp_tokens", __name__)


@mcp_tokens_bp.get("")
@admin_required
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
@admin_required
def create_token():
    try:
        issued_token = mcp_access_token_service.issue_token_and_commit(
            user_id=current_user.id
        )
    except mcp_access_token_service.McpAccessTokenPersistenceError as exc:
        return error_response(
            "DB_ERROR",
            str(exc),
            status=500,
        )
    return jsonify({"item": issued_token.to_display_payload()}), 201


@mcp_tokens_bp.delete("/<int:token_id>")
@admin_required
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
