"""Minimal MCP JSON-RPC endpoint exposing list_my_decks."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, make_response, request
from flask_login import current_user

from app.services import mcp_auth_service, mcp_tool_registry, mcp_tool_service
from app.services.mcp_access_token_service import McpAccessTokenError
from app.utils.permissions import is_admin_user
from app.validators import (
    RequestValidationError,
    validate_mcp_jsonrpc_request,
    validate_mcp_tool_call_params,
)

mcp_bp = Blueprint("mcp", __name__)

logger = logging.getLogger(__name__)


def _jsonrpc_error(
    request_id,
    *,
    code: int,
    message: str,
    status: int,
    data: dict | None = None,
):
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": int(code),
            "message": message,
        },
    }
    if data:
        payload["error"]["data"] = data
    response = jsonify(payload)
    response.status_code = status
    response.headers["MCP-Protocol-Version"] = mcp_tool_service.MCP_PROTOCOL_VERSION
    return response


def _jsonrpc_result(request_id, result: dict, *, status: int = 200):
    response = jsonify(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }
    )
    response.status_code = status
    response.headers["MCP-Protocol-Version"] = mcp_tool_service.MCP_PROTOCOL_VERSION
    return response


def _auth_error_code(status: int) -> int:
    if status == 401:
        return -32001
    if status == 403:
        return -32003
    if status == 429:
        return -32029
    return -32603


def _ensure_mcp_admin_access(auth_context):
    if is_admin_user(getattr(auth_context, "user", None)):
        return auth_context
    raise McpAccessTokenError(
        "Admin access required.",
        status=403,
        code="ADMIN_REQUIRED",
    )


@mcp_bp.route("/api/mcp", methods=["POST"])
def mcp_api():
    try:
        rpc_request = validate_mcp_jsonrpc_request(request.get_json(silent=True))
    except RequestValidationError as exc:
        return _jsonrpc_error(
            None,
            code=-32600 if exc.code == "INVALID_REQUEST" else -32602,
            message=str(exc),
            status=exc.status,
            data={"field": exc.field, "code": exc.code},
        )

    request_id = rpc_request.request_id

    auth_context = None
    try:
        if rpc_request.method == "initialize":
            auth_context = _ensure_mcp_admin_access(
                mcp_auth_service.authenticate_mcp_request(
                    request=request,
                    session_user=current_user,
                )
            )
            return _jsonrpc_result(
                request_id,
                {
                    "protocolVersion": mcp_tool_service.MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {
                            "listChanged": False,
                        }
                    },
                    "serverInfo": {
                        "name": "flama-mcp",
                        "title": "Flama MCP",
                        "version": "1.0.0",
                        "description": "Minimal MCP endpoint for the authenticated user's decks.",
                    },
                    "instructions": (
                        "Call tools/list to discover tools. "
                        "Use tools/call with name='list_my_decks' after authenticating via session or Bearer token. "
                        "Do not send user_id; the server derives the user from auth context."
                    ),
                },
            )

        if rpc_request.method == "notifications/initialized":
            auth_context = _ensure_mcp_admin_access(
                mcp_auth_service.authenticate_mcp_request(
                    request=request,
                    session_user=current_user,
                )
            )
            response = make_response("", 204)
            response.headers["MCP-Protocol-Version"] = mcp_tool_service.MCP_PROTOCOL_VERSION
            return response

        if rpc_request.method == "tools/list":
            auth_context = _ensure_mcp_admin_access(
                mcp_auth_service.authenticate_mcp_request(
                    request=request,
                    session_user=current_user,
                )
            )
            return _jsonrpc_result(
                request_id,
                {
                    "tools": mcp_tool_registry.list_mcp_tools(),
                },
            )

        if rpc_request.method == "tools/call":
            params = validate_mcp_tool_call_params(rpc_request.params)
            tool_name = str(params.get("name") or "").strip()
            if not tool_name:
                raise RequestValidationError(
                    "name là bắt buộc.",
                    field="name",
                    status=400,
                    code="INVALID_PARAMS",
                )
            tool_definition = mcp_tool_registry.get_mcp_tool(tool_name)
            if tool_definition is None:
                return _jsonrpc_error(
                    request_id,
                    code=-32602,
                    message=f"Unknown tool: {tool_name}",
                    status=400,
                    data={"field": "name", "code": "UNKNOWN_TOOL"},
                )

            auth_context = _ensure_mcp_admin_access(
                mcp_auth_service.authenticate_mcp_request(
                    request=request,
                    session_user=current_user,
                    required_scope=tool_definition.required_scope,
                )
            )
            result = mcp_tool_registry.call_mcp_tool(
                tool_name=tool_name,
                user_id=auth_context.user.id,
                arguments=params.get("arguments"),
            )
            logger.info(
                "MCP tool=%s user_id=%s auth_type=%s deck_count=%s",
                tool_name,
                auth_context.user.id,
                auth_context.auth_type,
                len(result.get("structuredContent", {}).get("decks", [])),
            )
            return _jsonrpc_result(request_id, result)

        return _jsonrpc_error(
            request_id,
            code=-32601,
            message=f"Unsupported MCP method: {rpc_request.method}",
            status=404,
            data={"code": "METHOD_NOT_FOUND"},
        )
    except RequestValidationError as exc:
        return _jsonrpc_error(
            request_id,
            code=-32602,
            message=str(exc),
            status=exc.status,
            data={"field": exc.field, "code": exc.code},
        )
    except McpAccessTokenError as exc:
        logger.info(
            "MCP auth failure method=%s code=%s status=%s",
            rpc_request.method,
            exc.code,
            exc.status,
        )
        return _jsonrpc_error(
            request_id,
            code=_auth_error_code(exc.status),
            message=str(exc),
            status=exc.status,
            data={"code": exc.code},
        )
    except Exception:
        logger.exception(
            "Unhandled MCP error for method=%s user_id=%s",
            rpc_request.method,
            getattr(getattr(auth_context, "user", None), "id", None),
        )
        return _jsonrpc_error(
            request_id,
            code=-32603,
            message="Internal MCP server error.",
            status=500,
            data={"code": "INTERNAL_ERROR"},
        )
