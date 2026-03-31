"""Minimal MCP JSON-RPC endpoint exposing list_my_decks."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, make_response, request
from flask_login import current_user

from app.services import mcp_tool_service
from app.validators import (
    RequestValidationError,
    validate_list_my_decks_arguments,
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

    if not current_user.is_authenticated:
        logger.info("MCP rejected unauthenticated request for method=%s", rpc_request.method)
        return _jsonrpc_error(
            request_id,
            code=-32001,
            message="Authentication required.",
            status=401,
            data={"code": "AUTH_REQUIRED"},
        )
    if not getattr(current_user, "is_active", True):
        logger.warning("MCP rejected disabled user request for user_id=%s", getattr(current_user, "id", None))
        return _jsonrpc_error(
            request_id,
            code=-32003,
            message="User account is disabled.",
            status=403,
            data={"code": "USER_DISABLED"},
        )

    logger.info(
        "MCP request method=%s user_id=%s",
        rpc_request.method,
        getattr(current_user, "id", None),
    )

    try:
        if rpc_request.method == "initialize":
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
                        "Call tools/list, then tools/call with name='list_my_decks'. "
                        "Do not send user_id; the server uses the current authenticated session."
                    ),
                },
            )

        if rpc_request.method == "notifications/initialized":
            response = make_response("", 204)
            response.headers["MCP-Protocol-Version"] = mcp_tool_service.MCP_PROTOCOL_VERSION
            return response

        if rpc_request.method == "tools/list":
            return _jsonrpc_result(
                request_id,
                {
                    "tools": mcp_tool_service.list_mcp_tools(),
                },
            )

        if rpc_request.method == "tools/call":
            validate_mcp_tool_call_params(rpc_request.params)
            tool_name = str(rpc_request.params.get("name") or "").strip()
            if not tool_name:
                raise RequestValidationError(
                    "name là bắt buộc.",
                    field="name",
                    status=400,
                    code="INVALID_PARAMS",
                )
            if tool_name != mcp_tool_service.LIST_MY_DECKS_TOOL_NAME:
                return _jsonrpc_error(
                    request_id,
                    code=-32602,
                    message=f"Unknown tool: {tool_name}",
                    status=400,
                    data={"field": "name", "code": "UNKNOWN_TOOL"},
                )

            validate_list_my_decks_arguments(rpc_request.params.get("arguments"))
            result = mcp_tool_service.build_list_my_decks_tool_result(user_id=current_user.id)
            logger.info(
                "MCP tool=%s user_id=%s deck_count=%s",
                tool_name,
                current_user.id,
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
    except Exception:
        logger.exception(
            "Unhandled MCP error for method=%s user_id=%s",
            rpc_request.method,
            getattr(current_user, "id", None),
        )
        return _jsonrpc_error(
            request_id,
            code=-32603,
            message="Internal MCP server error.",
            status=500,
            data={"code": "INTERNAL_ERROR"},
        )
