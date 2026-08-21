"""MCP (Model Context Protocol) JSON-RPC 2.0 endpoints for Flama Connect."""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, make_response, request

from app.services import mcp_auth_service, mcp_tool_registry, mcp_tool_service, oauth_service
from app.services.mcp_access_token_service import McpAccessTokenError
from app.validators import (
    RequestValidationError,
    validate_mcp_jsonrpc_request,
    validate_mcp_tool_call_params,
)
from models import db

logger = logging.getLogger(__name__)

mcp_connect_bp = Blueprint("flama_connect_mcp", __name__)


@mcp_connect_bp.get("/.well-known/oauth-protected-resource")
def connect_oauth_protected_resource():
    """RFC 9728 Protected Resource Metadata for Flama Connect."""
    data = oauth_service.get_protected_resource_metadata(request)
    base_url = oauth_service.get_base_url(request)
    data["resource"] = f"{base_url}/v1/mcp"
    return jsonify(data)



def _jsonrpc_error(
    request_id: Any,
    *,
    code: int,
    message: str,
    status: int,
    data: dict | None = None,
):
    payload: dict[str, Any] = {
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
    response.headers["Cache-Control"] = "no-store"
    if status == 401:
        base_url = oauth_service.get_base_url(request)
        response.headers["WWW-Authenticate"] = (
            f'Bearer error="unauthorized", resource_metadata="{base_url}/.well-known/oauth-protected-resource"'
        )
    return response



def _jsonrpc_result(request_id: Any, result: dict, *, status: int = 200):
    response = jsonify(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }
    )
    response.status_code = status
    response.headers["MCP-Protocol-Version"] = mcp_tool_service.MCP_PROTOCOL_VERSION
    response.headers["Cache-Control"] = "no-store"
    return response


def _auth_error_code(status: int) -> int:
    if status == 401:
        return -32001
    if status == 403:
        return -32003
    if status == 429:
        return -32029
    return -32603


def handle_mcp_request(url_token: str | None = None, session_user: Any = None):
    if request.method == "OPTIONS":
        return "", 204

    try:
        raw_json = request.get_json(silent=True)
        if raw_json is None:
            raw_data = request.get_data(as_text=True)
            if not raw_data:
                return _jsonrpc_error(
                    None,
                    code=-32700,
                    message="Empty request body. JSON payload is required.",
                    status=400,
                )
        rpc_request = validate_mcp_jsonrpc_request(raw_json)
    except RequestValidationError as exc:
        return _jsonrpc_error(
            None,
            code=-32600 if exc.code == "INVALID_REQUEST" else -32602,
            message=str(exc),
            status=exc.status,
            data={"field": exc.field, "code": exc.code},
        )

    request_id = rpc_request.request_id

    try:
        # Method: initialize
        if rpc_request.method == "initialize":
            auth_context = mcp_auth_service.authenticate_mcp_request_if_present(
                request=request,
                url_token=url_token,
                session_user=session_user,
            )
            user_info_msg = (
                f" Authenticated as user_id={auth_context.user.id} ({auth_context.user.username})."
                if auth_context
                else ""
            )
            return _jsonrpc_result(
                request_id,
                {
                    "protocolVersion": mcp_tool_service.MCP_PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {
                            "listChanged": False,
                        },
                        "resources": {
                            "subscribe": False,
                            "listChanged": False,
                        },
                        "prompts": {
                            "listChanged": False,
                        },
                    },
                    "serverInfo": {
                        "name": "flama-mcp-connect",
                        "title": "Flama MCP Service",
                        "version": "1.0.0",
                        "description": "Flama Model Context Protocol integration on Flama Connect." + user_info_msg,
                    },
                    "instructions": (
                        "Call tools/list to discover available flashcard tools. "
                        "Authenticate using Bearer token, X-Flama-Connect-Key, or URL token. "
                        "The server derives the user from the authentication context."
                    ),
                },
            )

        # Method: notifications/initialized
        if rpc_request.method == "notifications/initialized":
            response = make_response("", 204)
            response.headers["MCP-Protocol-Version"] = mcp_tool_service.MCP_PROTOCOL_VERSION
            return response

        # Method: tools/list
        if rpc_request.method == "tools/list":
            auth_context = mcp_auth_service.authenticate_mcp_request_if_present(
                request=request,
                url_token=url_token,
                session_user=session_user,
            )
            return _jsonrpc_result(
                request_id,
                {
                    "tools": mcp_tool_registry.list_mcp_tools(),
                },
            )

        # Method: resources/list
        if rpc_request.method == "resources/list":
            return _jsonrpc_result(
                request_id,
                {
                    "resources": [],
                },
            )

        # Method: prompts/list
        if rpc_request.method == "prompts/list":
            return _jsonrpc_result(
                request_id,
                {
                    "prompts": [],
                },
            )

        # Method: tools/call
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

            auth_context = mcp_auth_service.authenticate_mcp_request(
                request=request,
                url_token=url_token,
                session_user=session_user,
                required_scope=tool_definition.required_scope,
            )

            result = mcp_tool_registry.call_mcp_tool(
                tool_name=tool_name,
                user_id=auth_context.user.id,
                arguments=params.get("arguments"),
            )
            db.session.commit()
            logger.info(
                "MCP Connect tool=%s user_id=%s auth_type=%s success=True",
                tool_name,
                auth_context.user.id,
                auth_context.auth_type,
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
        db.session.rollback()
        # For JSON-RPC over HTTP, domain validation / resource errors (like 404 NOT_FOUND) must
        # return HTTP 400 so client transports do not mistake it for a missing URL endpoint
        # and terminate the MCP session.
        http_status = 400 if exc.status in (404, 400) else exc.status
        return _jsonrpc_error(
            request_id,
            code=-32602,
            message=str(exc),
            status=http_status,
            data={"field": exc.field, "code": exc.code},
        )
    except McpAccessTokenError as exc:
        db.session.rollback()
        logger.info("MCP Connect auth failure method=%s code=%s status=%s", rpc_request.method, exc.code, exc.status)
        return _jsonrpc_error(
            request_id,
            code=_auth_error_code(exc.status),
            message=str(exc),
            status=exc.status,
            data={"code": exc.code},
        )
    except Exception:
        db.session.rollback()
        logger.exception("Unhandled MCP Connect error for method=%s", rpc_request.method)
        return _jsonrpc_error(
            request_id,
            code=-32603,
            message="Internal MCP server error.",
            status=500,
            data={"code": "INTERNAL_ERROR"},
        )


@mcp_connect_bp.route("/v1/mcp", methods=["POST", "OPTIONS"])
@mcp_connect_bp.route("/v1/mcp/<url_token>", methods=["POST", "OPTIONS"])
def flama_mcp_endpoint(url_token: str | None = None):
    return handle_mcp_request(url_token=url_token)
