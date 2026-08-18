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


def validate_empty_arguments(arguments: Any, *, tool_name: str) -> dict[str, Any]:
    """Ensure tools expecting no arguments receive empty object or null."""
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
            f"Tool {tool_name} không nhận arguments.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    return {}


def validate_list_my_decks_arguments(arguments: Any) -> dict[str, Any]:
    return validate_empty_arguments(arguments, tool_name="list_my_decks")


def validate_get_deck_tree_arguments(arguments: Any) -> dict[str, Any]:
    return validate_empty_arguments(arguments, tool_name="get_deck_tree")


def validate_list_note_types_arguments(arguments: Any) -> dict[str, Any]:
    return validate_empty_arguments(arguments, tool_name="list_note_types")


def validate_get_note_type_schema_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError(
            "arguments phải là JSON object.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    note_type_id = arguments.get("note_type_id")
    name = arguments.get("name")
    if not note_type_id and not name:
        raise RequestValidationError(
            "Cần cung cấp ít nhất 'note_type_id' hoặc 'name'.",
            field="note_type_id",
            status=400,
            code="INVALID_PARAMS",
        )
    return {
        "note_type_id": str(note_type_id).strip() if note_type_id else None,
        "name": str(name).strip() if name else None,
    }


def validate_find_notes_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError(
            "arguments phải là JSON object.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    query = arguments.get("query")
    if query is None or not str(query).strip():
        raise RequestValidationError(
            "query là bắt buộc.",
            field="query",
            status=400,
            code="INVALID_PARAMS",
        )
    deck_id = arguments.get("deck_id")
    if deck_id is not None:
        try:
            deck_id = int(deck_id)
        except (TypeError, ValueError):
            raise RequestValidationError(
                "deck_id phải là số nguyên.",
                field="deck_id",
                status=400,
                code="INVALID_PARAMS",
            )
    limit = arguments.get("limit", 20)
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 20

    return {
        "query": str(query).strip(),
        "deck_id": deck_id,
        "limit": limit,
    }


def validate_single_note_payload(raw_note: Any) -> dict[str, Any]:
    if not isinstance(raw_note, dict):
        raise RequestValidationError(
            "Mỗi note phải là JSON object.",
            field="note",
            status=400,
            code="INVALID_PARAMS",
        )
    deck_id = raw_note.get("deck_id")
    deck_name = raw_note.get("deck_name") or raw_note.get("deckName")
    if deck_id is not None:
        try:
            deck_id = int(deck_id)
        except (TypeError, ValueError):
            raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")
    elif not deck_name or not str(deck_name).strip():
        raise RequestValidationError("Cần cung cấp deck_id hoặc deck_name.", field="deck_id", status=400, code="INVALID_PARAMS")

    note_type_id = raw_note.get("note_type_id")
    note_type_name = raw_note.get("note_type_name") or raw_note.get("modelName") or raw_note.get("model_name")
    if not note_type_id and not note_type_name:
        raise RequestValidationError("Cần cung cấp note_type_id hoặc note_type_name.", field="note_type_id", status=400, code="INVALID_PARAMS")

    fields = raw_note.get("fields") or raw_note.get("field_values")
    if not isinstance(fields, dict) or not fields:
        raise RequestValidationError("fields là bắt buộc và phải là object chứa các trường.", field="fields", status=400, code="INVALID_PARAMS")

    tags = raw_note.get("tags")
    if tags is not None and not isinstance(tags, list):
        raise RequestValidationError("tags phải là danh sách chuỗi.", field="tags", status=400, code="INVALID_PARAMS")

    allow_duplicate = bool(raw_note.get("allow_duplicate", raw_note.get("allowDuplicate", False)))

    return {
        "deck_id": deck_id,
        "deck_name": str(deck_name).strip() if deck_name else None,
        "note_type_id": str(note_type_id).strip() if note_type_id else None,
        "note_type_name": str(note_type_name).strip() if note_type_name else None,
        "fields": {str(k).strip(): str(v or "") for k, v in fields.items()},
        "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
        "allow_duplicate": allow_duplicate,
    }


def validate_create_note_arguments(arguments: Any) -> dict[str, Any]:
    return validate_single_note_payload(arguments)


def validate_batch_create_notes_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    notes_raw = arguments.get("notes")
    if not isinstance(notes_raw, list) or not notes_raw:
        raise RequestValidationError("notes phải là danh sách ít nhất 1 note.", field="notes", status=400, code="INVALID_PARAMS")
    if len(notes_raw) > 50:
        raise RequestValidationError("Chỉ có thể tạo tối đa 50 notes trong một lần gọi.", field="notes", status=400, code="INVALID_PARAMS")

    validated_notes = [validate_single_note_payload(item) for item in notes_raw]
    return {"notes": validated_notes}


def validate_get_due_card_counts_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    deck_id = arguments.get("deck_id")
    if deck_id is not None:
        try:
            deck_id = int(deck_id)
        except (TypeError, ValueError):
            raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")
    return {"deck_id": deck_id}


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
