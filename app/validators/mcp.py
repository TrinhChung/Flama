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
    """Ensure tools expecting no arguments receive empty object or null, ignoring extra metadata."""
    if arguments is None:
        return {}
    if not isinstance(arguments, dict):
        raise RequestValidationError(
            "arguments phải là JSON object.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    if "user_id" in arguments or "userId" in arguments:
        raise RequestValidationError(
            "user_id không được phép truyền trong arguments.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    non_meta_keys = [k for k in arguments.keys() if not k.startswith("_")]
    if non_meta_keys:
        raise RequestValidationError(
            f"Tool '{tool_name}' không nhận tham số: {', '.join(non_meta_keys)}.",
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


VALID_FIELD_TYPES = frozenset({"text", "richtext", "markdown", "image", "audio", "diagram"})


def validate_create_note_type_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")

    name = str(arguments.get("name") or "").strip()
    if not name:
        raise RequestValidationError("name là bắt buộc.", field="name", status=400, code="INVALID_PARAMS")
    if len(name) > 255:
        raise RequestValidationError("name không được vượt quá 255 ký tự.", field="name", status=400, code="INVALID_PARAMS")

    description = str(arguments.get("description")).strip() if arguments.get("description") is not None else None

    raw_fields = arguments.get("fields")
    fields: list[dict[str, Any]] = []
    if raw_fields is not None:
        if not isinstance(raw_fields, list):
            raise RequestValidationError("fields phải là một danh sách các field definitions.", field="fields", status=400, code="INVALID_PARAMS")
        seen_names: set[str] = set()
        primary_count = 0
        for idx, f in enumerate(raw_fields):
            if not isinstance(f, dict):
                raise RequestValidationError(f"Field ở vị trí {idx} phải là JSON object.", field=f"fields[{idx}]", status=400, code="INVALID_PARAMS")
            f_name = str(f.get("name") or "").strip()
            if not f_name:
                raise RequestValidationError(f"Tên field ở vị trí {idx} không được để trống.", field=f"fields[{idx}].name", status=400, code="INVALID_PARAMS")
            if len(f_name) > 255:
                raise RequestValidationError(f"Tên field '{f_name}' không được vượt quá 255 ký tự.", field=f"fields[{idx}].name", status=400, code="INVALID_PARAMS")
            if f_name.lower() in seen_names:
                raise RequestValidationError(f"Tên field trùng lặp: '{f_name}'.", field=f"fields[{idx}].name", status=400, code="DUPLICATE_FIELD_NAME")
            seen_names.add(f_name.lower())

            f_type = str(f.get("field_type") or "text").strip().lower()
            if f_type not in VALID_FIELD_TYPES:
                raise RequestValidationError(
                    f"field_type '{f_type}' không hợp lệ. Hỗ trợ: {', '.join(sorted(VALID_FIELD_TYPES))}",
                    field=f"fields[{idx}].field_type",
                    status=400,
                    code="INVALID_FIELD_TYPE",
                )

            identity_role = f.get("identity_role")
            if identity_role not in (None, "primary"):
                raise RequestValidationError("identity_role chỉ có thể là null hoặc 'primary'.", field=f"fields[{idx}].identity_role", status=400, code="INVALID_PARAMS")

            if identity_role == "primary":
                primary_count += 1
                if primary_count > 1:
                    raise RequestValidationError("Chỉ được phép có tối đa một primary identity field.", field=f"fields[{idx}].identity_role", status=400, code="MULTIPLE_PRIMARY_IDENTITY")
                if f_type != "text":
                    raise RequestValidationError("Primary identity field bắt buộc phải có field_type là 'text'.", field=f"fields[{idx}].field_type", status=400, code="INVALID_IDENTITY_TYPE")

            fields.append({
                "name": f_name,
                "field_type": f_type,
                "position": int(f.get("position", idx)),
                "required": True if identity_role == "primary" else bool(f.get("required", False)),
                "identity_role": identity_role,
            })

    raw_templates = arguments.get("templates")
    templates: list[dict[str, Any]] = []
    if raw_templates is not None:
        if isinstance(raw_templates, dict):
            raw_templates = [raw_templates]
        if not isinstance(raw_templates, list):
            raise RequestValidationError("templates phải là một danh sách hoặc object template.", field="templates", status=400, code="INVALID_PARAMS")

        seen_t_names: set[str] = set()
        for idx, t in enumerate(raw_templates):
            if not isinstance(t, dict):
                raise RequestValidationError(f"Template ở vị trí {idx} phải là JSON object.", field=f"templates[{idx}]", status=400, code="INVALID_PARAMS")
            t_name = str(t.get("name") or f"Card {idx + 1}").strip()
            if t_name.lower() in seen_t_names:
                raise RequestValidationError(f"Tên template trùng lặp: '{t_name}'.", field=f"templates[{idx}].name", status=400, code="DUPLICATE_TEMPLATE_NAME")
            seen_t_names.add(t_name.lower())

            templates.append({
                "name": t_name,
                "front_html": str(t.get("front_html") or "").strip(),
                "back_html": str(t.get("back_html") or "").strip(),
                "shared_css": str(t.get("shared_css") or "").strip(),
                "position": int(t.get("position", idx)),
            })

    return {
        "name": name,
        "description": description,
        "fields": fields if fields else None,
        "templates": templates if templates else None,
    }


def validate_preview_note_type_update_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")

    note_type_id = arguments.get("note_type_id")
    if not note_type_id or not str(note_type_id).strip():
        raise RequestValidationError("note_type_id là bắt buộc.", field="note_type_id", status=400, code="INVALID_PARAMS")

    name = str(arguments["name"]).strip() if arguments.get("name") is not None else None
    description = str(arguments["description"]).strip() if arguments.get("description") is not None else None

    return {
        "note_type_id": str(note_type_id).strip(),
        "name": name,
        "description": description,
        "fields": arguments.get("fields"),
        "templates": arguments.get("templates"),
    }


def validate_update_note_type_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")

    note_type_id = arguments.get("note_type_id")
    if not note_type_id or not str(note_type_id).strip():
        raise RequestValidationError("note_type_id là bắt buộc.", field="note_type_id", status=400, code="INVALID_PARAMS")

    name = str(arguments["name"]).strip() if arguments.get("name") is not None else None
    description = str(arguments["description"]).strip() if arguments.get("description") is not None else None
    preview_id = str(arguments["preview_id"]).strip() if arguments.get("preview_id") else None
    confirm = bool(arguments.get("confirm", False))

    return {
        "note_type_id": str(note_type_id).strip(),
        "name": name,
        "description": description,
        "fields": arguments.get("fields"),
        "templates": arguments.get("templates"),
        "preview_id": preview_id,
        "confirm": confirm,
    }


def validate_delete_note_type_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")

    note_type_id = arguments.get("note_type_id")
    if not note_type_id or not str(note_type_id).strip():
        raise RequestValidationError("note_type_id là bắt buộc.", field="note_type_id", status=400, code="INVALID_PARAMS")

    confirm = bool(arguments.get("confirm", False))
    preview_id = str(arguments["preview_id"]).strip() if arguments.get("preview_id") else None

    return {
        "note_type_id": str(note_type_id).strip(),
        "confirm": confirm,
        "preview_id": preview_id,
    }


def validate_get_deck_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    deck_id = arguments.get("deck_id")
    if deck_id is None:
        raise RequestValidationError("deck_id là bắt buộc.", field="deck_id", status=400, code="INVALID_PARAMS")
    try:
        deck_id_int = int(deck_id)
    except (TypeError, ValueError):
        raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")
    return {"deck_id": deck_id_int}


def validate_create_deck_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    name = str(arguments.get("name") or "").strip()
    if not name:
        raise RequestValidationError("name là bắt buộc.", field="name", status=400, code="INVALID_PARAMS")
    if len(name) > 255:
        raise RequestValidationError("name không được vượt quá 255 ký tự.", field="name", status=400, code="INVALID_PARAMS")
    parent_id = arguments.get("parent_id")
    if parent_id is not None:
        try:
            parent_id = int(parent_id)
        except (TypeError, ValueError):
            raise RequestValidationError("parent_id phải là số nguyên.", field="parent_id", status=400, code="INVALID_PARAMS")
    description = arguments.get("description")
    default_note_type_id = arguments.get("default_note_type_id") or arguments.get("note_type_id")
    return {
        "name": name,
        "parent_id": parent_id,
        "description": str(description).strip() if description is not None else None,
        "default_note_type_id": str(default_note_type_id).strip() if default_note_type_id else None,
    }


def validate_update_deck_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    deck_id = arguments.get("deck_id")
    if deck_id is None:
        raise RequestValidationError("deck_id là bắt buộc.", field="deck_id", status=400, code="INVALID_PARAMS")
    try:
        deck_id_int = int(deck_id)
    except (TypeError, ValueError):
        raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")

    name = arguments.get("name")
    description = arguments.get("description")
    parent_id = arguments.get("parent_id")
    has_parent_id = "parent_id" in arguments
    default_note_type_id = arguments.get("default_note_type_id") or arguments.get("note_type_id")
    has_default_note_type_id = ("default_note_type_id" in arguments) or ("note_type_id" in arguments)

    if name is None and description is None and not has_parent_id and not has_default_note_type_id:
        raise RequestValidationError("Cần cung cấp ít nhất một trường để cập nhật (name, description, parent_id, hoặc default_note_type_id).", field="name", status=400, code="INVALID_PARAMS")

    cleaned_name = str(name).strip() if name is not None else None
    if cleaned_name is not None and not cleaned_name:
        raise RequestValidationError("name không được để trống.", field="name", status=400, code="INVALID_PARAMS")
    if cleaned_name is not None and len(cleaned_name) > 255:
        raise RequestValidationError("name không được vượt quá 255 ký tự.", field="name", status=400, code="INVALID_PARAMS")

    cleaned_parent_id = None
    if has_parent_id and parent_id is not None:
        try:
            cleaned_parent_id = int(parent_id)
        except (TypeError, ValueError):
            raise RequestValidationError("parent_id phải là số nguyên hoặc null.", field="parent_id", status=400, code="INVALID_PARAMS")

    cleaned_default_note_type_id = None
    if has_default_note_type_id and default_note_type_id is not None:
        cleaned_default_note_type_id = str(default_note_type_id).strip() or None

    return {
        "deck_id": deck_id_int,
        "name": cleaned_name,
        "description": str(description).strip() if description is not None else None,
        "parent_id": cleaned_parent_id,
        "update_parent": has_parent_id,
        "default_note_type_id": cleaned_default_note_type_id,
        "update_default_note_type": has_default_note_type_id,
    }


def validate_delete_deck_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    deck_id = arguments.get("deck_id")
    if deck_id is None:
        raise RequestValidationError("deck_id là bắt buộc.", field="deck_id", status=400, code="INVALID_PARAMS")
    try:
        deck_id_int = int(deck_id)
    except (TypeError, ValueError):
        raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")
    confirm = bool(arguments.get("confirm", False))
    return {"deck_id": deck_id_int, "confirm": confirm}


def validate_list_notes_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    deck_id = arguments.get("deck_id")
    if deck_id is not None:
        try:
            deck_id = int(deck_id)
        except (TypeError, ValueError):
            raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")
    limit = arguments.get("limit", 20)
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 20
    offset = arguments.get("offset", 0)
    try:
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        offset = 0
    sort_by = str(arguments.get("sort_by") or "created_at").strip().lower()
    if sort_by not in {"created_at", "updated_at", "id"}:
        sort_by = "created_at"
    sort_dir = str(arguments.get("sort_dir") or "desc").strip().lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "desc"

    return {
        "deck_id": deck_id,
        "limit": limit,
        "offset": offset,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }


def validate_get_note_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    note_id = arguments.get("note_id")
    if not note_id or not str(note_id).strip():
        raise RequestValidationError("note_id là bắt buộc.", field="note_id", status=400, code="INVALID_PARAMS")
    return {"note_id": str(note_id).strip()}


def validate_find_notes_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError(
            "arguments phải là JSON object.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    query = arguments.get("query")
    deck_id = arguments.get("deck_id")
    tag = arguments.get("tag")

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
    offset = arguments.get("offset", 0)
    try:
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        offset = 0

    return {
        "query": str(query).strip() if query is not None else "",
        "deck_id": deck_id,
        "tag": str(tag).strip() if tag else None,
        "limit": limit,
        "offset": offset,
    }


def validate_update_note_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    note_id = arguments.get("note_id")
    if not note_id or not str(note_id).strip():
        raise RequestValidationError("note_id là bắt buộc.", field="note_id", status=400, code="INVALID_PARAMS")

    fields = arguments.get("fields")
    tags = arguments.get("tags")
    deck_id = arguments.get("deck_id")

    if fields is None and tags is None and deck_id is None:
        raise RequestValidationError("Cần cung cấp ít nhất một trường để cập nhật (fields, tags, hoặc deck_id).", field="fields", status=400, code="INVALID_PARAMS")

    if fields is not None and not isinstance(fields, dict):
        raise RequestValidationError("fields phải là JSON object.", field="fields", status=400, code="INVALID_PARAMS")
    if tags is not None and not isinstance(tags, list):
        raise RequestValidationError("tags phải là danh sách chuỗi.", field="tags", status=400, code="INVALID_PARAMS")
    if deck_id is not None:
        try:
            deck_id = int(deck_id)
        except (TypeError, ValueError):
            raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")

    return {
        "note_id": str(note_id).strip(),
        "fields": {str(k).strip(): str(v or "") for k, v in fields.items()} if fields is not None else None,
        "tags": [str(t).strip() for t in tags if str(t).strip()] if tags is not None else None,
        "deck_id": deck_id,
    }


def validate_delete_note_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    note_id = arguments.get("note_id")
    if not note_id or not str(note_id).strip():
        raise RequestValidationError("note_id là bắt buộc.", field="note_id", status=400, code="INVALID_PARAMS")
    confirm = bool(arguments.get("confirm", False))
    return {"note_id": str(note_id).strip(), "confirm": confirm}


def validate_move_note_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    note_id = arguments.get("note_id")
    if not note_id or not str(note_id).strip():
        raise RequestValidationError("note_id là bắt buộc.", field="note_id", status=400, code="INVALID_PARAMS")
    deck_id = arguments.get("deck_id")
    if deck_id is None:
        raise RequestValidationError("deck_id là bắt buộc.", field="deck_id", status=400, code="INVALID_PARAMS")
    try:
        deck_id_int = int(deck_id)
    except (TypeError, ValueError):
        raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")
    return {"note_id": str(note_id).strip(), "deck_id": deck_id_int}


def validate_add_tags_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    note_ids_raw = arguments.get("note_ids")
    if note_ids_raw is None and "note_id" in arguments:
        note_ids_raw = [arguments["note_id"]]
    if not isinstance(note_ids_raw, list) or not note_ids_raw:
        raise RequestValidationError("note_ids phải là danh sách ít nhất 1 note ID.", field="note_ids", status=400, code="INVALID_PARAMS")
    tags_raw = arguments.get("tags")
    if not isinstance(tags_raw, list) or not tags_raw:
        raise RequestValidationError("tags phải là danh sách ít nhất 1 tag.", field="tags", status=400, code="INVALID_PARAMS")

    cleaned_note_ids = [str(item).strip() for item in note_ids_raw if str(item).strip()]
    cleaned_tags = [str(item).strip() for item in tags_raw if str(item).strip()]
    if not cleaned_note_ids:
        raise RequestValidationError("note_ids không hợp lệ.", field="note_ids", status=400, code="INVALID_PARAMS")
    if not cleaned_tags:
        raise RequestValidationError("tags không hợp lệ.", field="tags", status=400, code="INVALID_PARAMS")

    return {"note_ids": cleaned_note_ids, "tags": cleaned_tags}


def validate_remove_tags_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    note_ids_raw = arguments.get("note_ids")
    if note_ids_raw is None and "note_id" in arguments:
        note_ids_raw = [arguments["note_id"]]
    if not isinstance(note_ids_raw, list) or not note_ids_raw:
        raise RequestValidationError("note_ids phải là danh sách ít nhất 1 note ID.", field="note_ids", status=400, code="INVALID_PARAMS")
    tags_raw = arguments.get("tags")
    if not isinstance(tags_raw, list) or not tags_raw:
        raise RequestValidationError("tags phải là danh sách ít nhất 1 tag.", field="tags", status=400, code="INVALID_PARAMS")

    cleaned_note_ids = [str(item).strip() for item in note_ids_raw if str(item).strip()]
    cleaned_tags = [str(item).strip() for item in tags_raw if str(item).strip()]
    if not cleaned_note_ids:
        raise RequestValidationError("note_ids không hợp lệ.", field="note_ids", status=400, code="INVALID_PARAMS")
    if not cleaned_tags:
        raise RequestValidationError("tags không hợp lệ.", field="tags", status=400, code="INVALID_PARAMS")

    return {"note_ids": cleaned_note_ids, "tags": cleaned_tags}


def validate_batch_update_notes_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    notes_raw = arguments.get("notes")
    if not isinstance(notes_raw, list) or not notes_raw:
        raise RequestValidationError("notes phải là danh sách ít nhất 1 note.", field="notes", status=400, code="INVALID_PARAMS")
    if len(notes_raw) > 50:
        raise RequestValidationError("Chỉ có thể cập nhật tối đa 50 notes trong một lần gọi.", field="notes", status=400, code="INVALID_PARAMS")

    validated_notes = [validate_update_note_arguments(item) for item in notes_raw]
    return {"notes": validated_notes}


def validate_batch_delete_notes_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    note_ids_raw = arguments.get("note_ids")
    if not isinstance(note_ids_raw, list) or not note_ids_raw:
        raise RequestValidationError("note_ids phải là danh sách ít nhất 1 note ID.", field="note_ids", status=400, code="INVALID_PARAMS")
    if len(note_ids_raw) > 50:
        raise RequestValidationError("Chỉ có thể xóa tối đa 50 notes trong một lần gọi.", field="note_ids", status=400, code="INVALID_PARAMS")

    cleaned_ids = [str(item).strip() for item in note_ids_raw if str(item).strip()]
    if not cleaned_ids:
        raise RequestValidationError("note_ids không hợp lệ.", field="note_ids", status=400, code="INVALID_PARAMS")
    confirm = bool(arguments.get("confirm", False))
    return {"note_ids": cleaned_ids, "confirm": confirm}


def validate_batch_move_notes_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    note_ids_raw = arguments.get("note_ids")
    if not isinstance(note_ids_raw, list) or not note_ids_raw:
        raise RequestValidationError("note_ids phải là danh sách ít nhất 1 note ID.", field="note_ids", status=400, code="INVALID_PARAMS")
    if len(note_ids_raw) > 50:
        raise RequestValidationError("Chỉ có thể di chuyển tối đa 50 notes trong một lần gọi.", field="note_ids", status=400, code="INVALID_PARAMS")
    deck_id = arguments.get("deck_id")
    if deck_id is None:
        raise RequestValidationError("deck_id là bắt buộc.", field="deck_id", status=400, code="INVALID_PARAMS")
    try:
        deck_id_int = int(deck_id)
    except (TypeError, ValueError):
        raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")

    cleaned_ids = [str(item).strip() for item in note_ids_raw if str(item).strip()]
    if not cleaned_ids:
        raise RequestValidationError("note_ids không hợp lệ.", field="note_ids", status=400, code="INVALID_PARAMS")
    return {"note_ids": cleaned_ids, "deck_id": deck_id_int}


def validate_get_study_queue_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    deck_id = arguments.get("deck_id")
    if deck_id is not None:
        try:
            deck_id = int(deck_id)
        except (TypeError, ValueError):
            raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")
    limit = arguments.get("limit", 10)
    try:
        limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit = 10
    return {"deck_id": deck_id, "limit": limit}


def validate_get_card_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    card_id = arguments.get("card_id")
    if not card_id or not str(card_id).strip():
        raise RequestValidationError("card_id là bắt buộc.", field="card_id", status=400, code="INVALID_PARAMS")
    return {"card_id": str(card_id).strip()}


def validate_submit_review_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    card_id = arguments.get("card_id")
    if not card_id or not str(card_id).strip():
        raise RequestValidationError("card_id là bắt buộc.", field="card_id", status=400, code="INVALID_PARAMS")
    rating = str(arguments.get("rating") or "").strip().lower()
    if rating not in {"again", "hard", "good", "easy"}:
        raise RequestValidationError("rating phải là một trong: 'again', 'hard', 'good', 'easy'.", field="rating", status=400, code="INVALID_PARAMS")
    duration_ms = arguments.get("duration_ms")
    if duration_ms is not None:
        try:
            duration_ms = max(0, min(3600000, int(duration_ms)))
        except (TypeError, ValueError):
            duration_ms = None

    return {
        "card_id": str(card_id).strip(),
        "rating": rating,
        "duration_ms": duration_ms,
    }


def validate_get_deck_stats_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    deck_id = arguments.get("deck_id")
    if deck_id is None:
        raise RequestValidationError("deck_id là bắt buộc.", field="deck_id", status=400, code="INVALID_PARAMS")
    try:
        deck_id_int = int(deck_id)
    except (TypeError, ValueError):
        raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")
    return {"deck_id": deck_id_int}


def validate_get_study_stats_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    year = arguments.get("year")
    if year is not None:
        try:
            year = int(year)
        except (TypeError, ValueError):
            raise RequestValidationError("year phải là số nguyên.", field="year", status=400, code="INVALID_PARAMS")
    return {"year": year}


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


def validate_resolve_deck_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    path = str(arguments.get("path") or "").strip()
    if not path:
        raise RequestValidationError("path là bắt buộc.", field="path", status=400, code="INVALID_PARAMS")
    if len(path) > 2048:
        raise RequestValidationError("path không được vượt quá 2048 ký tự.", field="path", status=400, code="INVALID_PARAMS")
    return {"path": path}


def validate_batch_ensure_decks_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    paths = arguments.get("paths")
    if not isinstance(paths, list) or not paths:
        raise RequestValidationError("paths phải là danh sách ít nhất 1 path.", field="paths", status=400, code="INVALID_PARAMS")
    if len(paths) > 200:
        raise RequestValidationError("paths không được vượt quá 200 items.", field="paths", status=400, code="INVALID_PARAMS")
    clean_paths: list[str] = []
    for p in paths:
        cleaned = str(p or "").strip()
        if not cleaned:
            continue
        if len(cleaned) > 2048:
            raise RequestValidationError("Mỗi path không được vượt quá 2048 ký tự.", field="paths", status=400, code="INVALID_PARAMS")
        clean_paths.append(cleaned)
    if not clean_paths:
        raise RequestValidationError("Cần ít nhất một path hợp lệ trong paths.", field="paths", status=400, code="INVALID_PARAMS")
    return {"paths": clean_paths}


def _validate_sync_notes_payload(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    notes = arguments.get("notes")
    if not isinstance(notes, list) or not notes:
        raise RequestValidationError("notes phải là danh sách ít nhất 1 note.", field="notes", status=400, code="INVALID_PARAMS")
    if len(notes) > 500:
        raise RequestValidationError("notes không được vượt quá 500 items trong một lần gọi.", field="notes", status=400, code="INVALID_PARAMS")

    source_key = str(arguments.get("source_key") or "").strip() or None
    deck_id = arguments.get("deck_id")
    deck_id_int: int | None = None
    if deck_id is not None:
        try:
            deck_id_int = int(deck_id)
        except (TypeError, ValueError):
            raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")

    deck_path = str(arguments.get("deck_path") or "").strip() or None
    note_type_id = str(arguments.get("note_type_id") or "").strip() or None
    note_type_name = str(arguments.get("note_type_name") or "").strip() or None

    validated_notes: list[dict[str, Any]] = []
    for idx, item in enumerate(notes):
        if not isinstance(item, dict):
            raise RequestValidationError(f"Item #{idx} trong notes phải là JSON object.", field="notes", status=400, code="INVALID_PARAMS")
        fields = item.get("fields")
        if not isinstance(fields, dict):
            raise RequestValidationError(f"Item #{idx} thiếu 'fields' dạng object.", field="notes", status=400, code="INVALID_PARAMS")
        tags = item.get("tags")
        if tags is not None and not isinstance(tags, list):
            tags = [str(tags)]

        item_deck_id = item.get("deck_id")
        item_deck_id_int: int | None = None
        if item_deck_id is not None:
            try:
                item_deck_id_int = int(item_deck_id)
            except (TypeError, ValueError):
                raise RequestValidationError(f"deck_id ở item #{idx} phải là số nguyên.", field="notes", status=400, code="INVALID_PARAMS")

        validated_notes.append({
            "external_id": str(item.get("external_id") or "").strip() or None,
            "fields": fields,
            "tags": [str(t).strip() for t in (tags or []) if str(t).strip()],
            "deck_id": item_deck_id_int,
            "deck_path": str(item.get("deck_path") or "").strip() or None,
        })

    return {
        "source_key": source_key,
        "deck_id": deck_id_int,
        "deck_path": deck_path,
        "note_type_id": note_type_id,
        "note_type_name": note_type_name,
        "notes": validated_notes,
    }


def validate_preview_note_sync_arguments(arguments: Any) -> dict[str, Any]:
    return _validate_sync_notes_payload(arguments)


def validate_sync_notes_arguments(arguments: Any) -> dict[str, Any]:
    payload = _validate_sync_notes_payload(arguments)
    payload["stop_on_error"] = bool(arguments.get("stop_on_error", False))
    payload["ensure_decks"] = bool(arguments.get("ensure_decks", True))
    return payload


def validate_import_image_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError(
            "arguments phải là JSON object.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    if "user_id" in arguments or "userId" in arguments:
        raise RequestValidationError(
            "user_id không được phép truyền trong arguments.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )

    url = arguments.get("url") or arguments.get("source_url")
    file_data = arguments.get("file_data") or arguments.get("file")
    filename = arguments.get("filename")
    image_key = arguments.get("image_key") or arguments.get("name")
    tags = arguments.get("tags")
    description = arguments.get("description")
    is_enabled = arguments.get("is_enabled")

    if not url and not file_data:
        raise RequestValidationError(
            "Cần cung cấp 'url' hoặc 'file_data' để import ảnh.",
            field="url",
            status=400,
            code="INVALID_PARAMS",
        )
    if url and file_data:
        raise RequestValidationError(
            "Chỉ chọn một nguồn ảnh: 'url' hoặc 'file_data'.",
            field="url",
            status=400,
            code="INVALID_PARAMS",
        )

    if url is not None:
        url_str = str(url).strip()
        if not url_str:
            raise RequestValidationError("url không được để trống.", field="url", status=400, code="INVALID_PARAMS")
        if len(url_str) > 2048:
            raise RequestValidationError("url quá dài (tối đa 2048 ký tự).", field="url", status=400, code="INVALID_PARAMS")
        url = url_str

    if tags is not None and not isinstance(tags, (list, tuple, set, str)):
        raise RequestValidationError("tags phải là danh sách chuỗi hoặc chuỗi phân cách dấu phẩy.", field="tags", status=400, code="INVALID_PARAMS")

    return {
        "url": url,
        "file_data": file_data,
        "filename": str(filename).strip() if filename else None,
        "image_key": str(image_key).strip() if image_key else None,
        "tags": tags,
        "description": str(description).strip() if description is not None else "",
        "is_enabled": is_enabled if isinstance(is_enabled, bool) else True,
    }


def validate_search_images_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise RequestValidationError(
            "arguments phải là JSON object.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    if "user_id" in arguments or "userId" in arguments:
        raise RequestValidationError(
            "user_id không được phép truyền trong arguments.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )

    query = arguments.get("query") or arguments.get("q")
    tag = arguments.get("tag")
    status = arguments.get("status")
    limit = arguments.get("limit", 20)
    offset = arguments.get("offset", 0)

    try:
        limit = max(1, min(int(limit), 60))
    except (TypeError, ValueError):
        limit = 20

    try:
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        offset = 0

    return {
        "query": str(query).strip() if query is not None else "",
        "tag": str(tag).strip() if tag is not None else None,
        "status": str(status).strip().lower() if status else "",
        "limit": limit,
        "offset": offset,
    }


def validate_get_image_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError(
            "arguments phải là JSON object.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )
    if "user_id" in arguments or "userId" in arguments:
        raise RequestValidationError(
            "user_id không được phép truyền trong arguments.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )

    image_key = arguments.get("image_key") or arguments.get("name")
    asset_id = arguments.get("asset_id") or arguments.get("id")

    if not image_key and not asset_id:
        raise RequestValidationError(
            "Cần cung cấp 'image_key' hoặc 'asset_id'.",
            field="image_key",
            status=400,
            code="INVALID_PARAMS",
        )

    return {
        "image_key": str(image_key).strip() if image_key else None,
        "asset_id": str(asset_id).strip() if asset_id else None,
    }


def validate_mcp_tool_call_params(params: Any) -> dict[str, Any]:
    """Validate and extract tools/call params supporting MCP metadata (_meta, context, etc.)."""
    if not isinstance(params, dict):
        raise RequestValidationError(
            "params phải là JSON object.",
            field="params",
            status=400,
            code="INVALID_PARAMS",
        )

    if "user_id" in params or "userId" in params:
        raise RequestValidationError(
            "user_id không được phép truyền trong params.",
            field="params",
            status=400,
            code="INVALID_PARAMS",
        )

    name = params.get("name")
    if not name or not isinstance(name, str) or not name.strip():
        raise RequestValidationError(
            "name là bắt buộc.",
            field="name",
            status=400,
            code="INVALID_PARAMS",
        )

    arguments = params.get("arguments")
    if arguments is not None and not isinstance(arguments, dict):
        raise RequestValidationError(
            "arguments phải là JSON object.",
            field="arguments",
            status=400,
            code="INVALID_PARAMS",
        )

    return {
        "name": name.strip(),
        "arguments": arguments if isinstance(arguments, dict) else {},
        "_meta": params.get("_meta"),
    }

