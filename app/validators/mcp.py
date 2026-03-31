"""Validation helpers for the minimal MCP JSON-RPC endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .flashcard_input import RequestValidationError


@dataclass(frozen=True)
class McpJsonRpcRequest:
    """Normalized JSON-RPC request envelope for the MCP route."""

    request_id: Any | None
    method: str
    params: dict[str, Any]


def validate_mcp_jsonrpc_request(payload: Any) -> McpJsonRpcRequest:
    """Validate and normalize the outer JSON-RPC request envelope."""
    if not isinstance(payload, dict):
        raise RequestValidationError(
            "Payload phải là JSON object.",
            status=400,
            code="INVALID_REQUEST",
        )

    if payload.get("jsonrpc") != "2.0":
        raise RequestValidationError(
            "jsonrpc phải là '2.0'.",
            field="jsonrpc",
            status=400,
            code="INVALID_REQUEST",
        )

    method = payload.get("method")
    if not isinstance(method, str) or not method.strip():
        raise RequestValidationError(
            "method là bắt buộc.",
            field="method",
            status=400,
            code="INVALID_REQUEST",
        )

    params = payload.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise RequestValidationError(
            "params phải là JSON object.",
            field="params",
            status=400,
            code="INVALID_PARAMS",
        )

    return McpJsonRpcRequest(
        request_id=payload.get("id"),
        method=method.strip(),
        params=params,
    )


def validate_list_my_decks_arguments(arguments: Any) -> dict[str, Any]:
    """Ensure the only MCP tool exposed by this route accepts no arguments."""
    if arguments is None:
        return {}
    if not isinstance(arguments, dict):
        raise RequestValidationError(
            "arguments phải là JSON object.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    if arguments:
        raise RequestValidationError(
            "Tool list_my_decks không nhận arguments.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    return {}


def validate_mcp_tool_call_params(params: Any) -> dict[str, Any]:
    """Restrict tools/call params to the minimal shape this endpoint supports."""
    if not isinstance(params, dict):
        raise RequestValidationError(
            "params phải là JSON object.",
            field="params",
            status=400,
            code="INVALID_PARAMS",
        )

    unknown_keys = sorted(str(key) for key in params.keys() if key not in {"name", "arguments"})
    if unknown_keys:
        raise RequestValidationError(
            "tools/call chỉ hỗ trợ name và arguments.",
            field="params",
            status=400,
            code="INVALID_PARAMS",
        )

    return params
