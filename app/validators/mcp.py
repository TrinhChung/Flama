"""Validation helpers for the minimal MCP JSON-RPC endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models.field_types import FIELD_TYPES, stored_field_value

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
    if set(arguments) - {"note_type_id", "name", "include_templates", "application_id"}:
        raise RequestValidationError("Unknown schema argument.", field="arguments", code="INVALID_PARAMS")
    include_templates = arguments.get("include_templates", False)
    if not isinstance(include_templates, bool):
        raise RequestValidationError("include_templates must be boolean.", field="include_templates", code="INVALID_PARAMS")
    application_id = arguments.get("application_id")
    if application_id is not None and (not include_templates or not isinstance(application_id, str)
            or not application_id.strip() or len(application_id) > 128):
        raise RequestValidationError("application_id requires include_templates=true and a nonempty occurrence ID.",
            field="application_id", code="INVALID_PARAMS")
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
        "include_templates": include_templates,
        "application_id": application_id.strip() if application_id is not None else None,
    }


VALID_FIELD_TYPES = frozenset(FIELD_TYPES)


def _extract_taxonomy_from_dict(arguments: dict[str, Any]) -> dict[str, Any]:
    tax_payload: dict[str, Any] = {}
    if isinstance(arguments.get("taxonomy_metadata"), dict):
        tax_payload.update(arguments["taxonomy_metadata"])

    taxonomy_field_names = (
        "taxonomy_domain", "domain",
        "taxonomy_subject", "subject",
        "taxonomy_difficulty_band", "difficulty_band", "level_band",
        "taxonomy_framework", "framework",
        "taxonomy_framework_level", "framework_level",
        "taxonomy_framework_track", "framework_track",
        "taxonomy_learning_goals", "learning_goals",
        "taxonomy_primary_topics", "primary_topics",
        "taxonomy_format_features", "format_features",
        "taxonomy_audience", "audience",
        "taxonomy_best_used_for", "best_used_for",
        "subcategory", "target_audience",
    )
    for key in taxonomy_field_names:
        if key in arguments and arguments[key] is not None:
            tax_payload[key] = arguments[key]

    return tax_payload


def validate_create_note_type_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")

    name = str(arguments.get("name") or "").strip()
    if not name:
        raise RequestValidationError("name là bắt buộc.", field="name", status=400, code="INVALID_PARAMS")
    if len(name) > 255:
        raise RequestValidationError("name không được vượt quá 255 ký tự.", field="name", status=400, code="INVALID_PARAMS")

    description = str(arguments.get("description")).strip() if arguments.get("description") is not None else None
    primary_category = str(arguments.get("primary_category") or arguments.get("category") or "").strip() or None

    raw_tags = arguments.get("tags")
    tags: list[str] = []
    if raw_tags is not None:
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        else:
            raise RequestValidationError("tags phải là danh sách chuỗi.", field="tags", status=400, code="INVALID_PARAMS")

    preview_text = str(arguments.get("preview_text")).strip() if arguments.get("preview_text") is not None else None
    preview_image_url = str(arguments.get("preview_image_url")).strip() if arguments.get("preview_image_url") is not None else None

    raw_tax = arguments.get("taxonomy_metadata")
    if raw_tax is not None and not isinstance(raw_tax, dict):
        raise RequestValidationError("taxonomy_metadata phải là JSON object.", field="taxonomy_metadata", status=400, code="INVALID_PARAMS")

    taxonomy_payload = _extract_taxonomy_from_dict(arguments)

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
        "primary_category": primary_category,
        "tags": tags,
        "preview_text": preview_text,
        "preview_image_url": preview_image_url,
        "taxonomy_metadata": taxonomy_payload if taxonomy_payload else (raw_tax if raw_tax is not None else None),
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
    primary_category = str(arguments.get("primary_category") or arguments.get("category")).strip() if (arguments.get("primary_category") or arguments.get("category")) is not None else None

    raw_tags = arguments.get("tags")
    tags: list[str] | None = None
    if raw_tags is not None:
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        else:
            raise RequestValidationError("tags phải là danh sách chuỗi.", field="tags", status=400, code="INVALID_PARAMS")

    preview_text = str(arguments["preview_text"]).strip() if arguments.get("preview_text") is not None else None
    preview_image_url = str(arguments["preview_image_url"]).strip() if arguments.get("preview_image_url") is not None else None

    pricing_mode = str(arguments["pricing_mode"]).strip().lower() if arguments.get("pricing_mode") is not None else None
    if pricing_mode is not None and pricing_mode not in ("free", "paid"):
        raise RequestValidationError("pricing_mode phải là 'free' hoặc 'paid'.", field="pricing_mode", status=400, code="INVALID_PARAMS")

    price_amount_minor = None
    if arguments.get("price_amount_minor") is not None:
        try:
            price_amount_minor = int(arguments.get("price_amount_minor"))
            if price_amount_minor < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise RequestValidationError("price_amount_minor phải là số nguyên không âm.", field="price_amount_minor", status=400, code="INVALID_PARAMS")

    publish_status = str(arguments["publish_status"]).strip().lower() if arguments.get("publish_status") is not None else None
    if publish_status is not None and publish_status not in ("published", "unlisted", "archived", "private"):
        raise RequestValidationError("publish_status không hợp lệ.", field="publish_status", status=400, code="INVALID_PARAMS")

    raw_tax = arguments.get("taxonomy_metadata")
    if raw_tax is not None and not isinstance(raw_tax, dict):
        raise RequestValidationError("taxonomy_metadata phải là JSON object.", field="taxonomy_metadata", status=400, code="INVALID_PARAMS")

    taxonomy_payload = _extract_taxonomy_from_dict(arguments)

    preview_id = str(arguments["preview_id"]).strip() if arguments.get("preview_id") else None
    confirm = bool(arguments.get("confirm", False))

    return {
        "note_type_id": str(note_type_id).strip(),
        "name": name,
        "description": description,
        "primary_category": primary_category,
        "tags": tags,
        "preview_text": preview_text,
        "preview_image_url": preview_image_url,
        "pricing_mode": pricing_mode,
        "price_amount_minor": price_amount_minor,
        "publish_status": publish_status,
        "taxonomy_metadata": taxonomy_payload if taxonomy_payload else (raw_tax if raw_tax is not None else None),
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
    revisions = {}
    for key in ("expected_content_revision", "expected_field_schema_revision"):
        if key not in arguments:
            continue
        value = arguments[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RequestValidationError("Revision must be a non-negative integer.", field=key, status=400, code="INVALID_PARAMS")
        revisions[key] = value

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
        "fields": {str(k).strip(): stored_field_value(v) for k, v in fields.items()} if fields is not None else None,
        "tags": [str(t).strip() for t in tags if str(t).strip()] if tags is not None else None,
        "deck_id": deck_id,
        **revisions,
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

    operation_key = arguments.get("operation_key")
    if operation_key is not None and (
        not isinstance(operation_key, str) or not operation_key
        or operation_key != operation_key.strip() or len(operation_key) > 36
    ):
        raise RequestValidationError(
            "operation_key must be a canonical non-empty string up to 36 characters (a UUID is recommended).",
            field="operation_key", status=400, code="INVALID_PARAMS",
        )

    return {
        "card_id": str(card_id).strip(),
        "rating": rating,
        "duration_ms": duration_ms,
        **({"operation_key": operation_key} if operation_key is not None else {}),
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
        "fields": {str(k).strip(): stored_field_value(v) for k, v in fields.items()},
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


def validate_crawl_note_media_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    if "user_id" in arguments or "userId" in arguments:
        raise RequestValidationError("user_id không được phép truyền trong arguments.", field="arguments", status=400, code="INVALID_PARAMS")

    note_id = str(arguments.get("note_id") or "").strip()
    if not note_id:
        raise RequestValidationError("note_id là bắt buộc.", field="note_id", status=400, code="INVALID_PARAMS")

    field_name = str(arguments.get("field_name") or "").strip()
    if not field_name:
        raise RequestValidationError("field_name là bắt buộc.", field="field_name", status=400, code="INVALID_PARAMS")

    url = str(arguments.get("url") or arguments.get("source_url") or "").strip()
    if not url:
        raise RequestValidationError("url là bắt buộc.", field="url", status=400, code="INVALID_PARAMS")

    markdown_inline = bool(arguments.get("markdown_inline", False))

    return {
        "note_id": note_id,
        "field_name": field_name,
        "url": url,
        "markdown_inline": markdown_inline,
    }


def validate_extract_page_images_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    if "user_id" in arguments or "userId" in arguments:
        raise RequestValidationError("user_id không được phép truyền trong arguments.", field="arguments", status=400, code="INVALID_PARAMS")

    page_url = str(arguments.get("page_url") or arguments.get("url") or "").strip()
    if not page_url:
        raise RequestValidationError("page_url là bắt buộc.", field="page_url", status=400, code="INVALID_PARAMS")

    max_images = arguments.get("max_images", 20)
    try:
        max_images_int = int(max_images)
    except (TypeError, ValueError):
        max_images_int = 20

    return {
        "page_url": page_url,
        "max_images": max(1, min(max_images_int, 50)),
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
        "status": str(status).strip().lower() if status else "enabled",
        "limit": limit,
        "offset": offset,
    }


def validate_get_image_arguments(arguments: Any) -> dict[str, Any]:
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

    raw_key = arguments.get("image_key") or arguments.get("name")
    raw_id = arguments.get("asset_id") or arguments.get("id")

    image_key = str(raw_key).strip() if raw_key is not None and str(raw_key).strip() else None
    asset_id = str(raw_id).strip() if raw_id is not None and str(raw_id).strip() else None

    if not image_key and not asset_id:
        raise RequestValidationError(
            "Cần cung cấp 'image_key' hoặc 'asset_id'.",
            field="image_key",
            status=400,
            code="INVALID_PARAMS",
        )

    return {
        "image_key": image_key,
        "asset_id": asset_id,
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


# ---------------------------------------------------------------------------
# Shared Decks & Releases Validators
# ---------------------------------------------------------------------------


def _validate_positive_int(
    val: Any,
    field_name: str,
    *,
    default: int = 20,
    max_val: int | None = None,
    allow_zero: bool = False,
) -> int:
    if val is None:
        return default
    try:
        parsed = int(val)
    except (ValueError, TypeError):
        raise RequestValidationError(
            f"'{field_name}' phải là số nguyên.",
            field=field_name,
            status=400,
            code="INVALID_PARAMS",
        )
    min_val = 0 if allow_zero else 1
    if parsed < min_val:
        return min_val
    if max_val is not None and parsed > max_val:
        return max_val
    return parsed


def validate_list_shared_decks_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for list_shared_decks tool."""
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")

    query = str(arguments.get("query") or arguments.get("q") or "").strip() or None
    category = str(arguments.get("category") or "").strip() or None
    
    raw_tags = arguments.get("tags")
    tags: list[str] = []
    if raw_tags is not None:
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        else:
            raise RequestValidationError("tags phải là danh sách chuỗi hoặc chuỗi phân tách bởi dấu phẩy.", field="tags", status=400, code="INVALID_PARAMS")

    pricing_mode = str(arguments.get("pricing_mode") or arguments.get("pricing") or "").strip().lower() or None
    if pricing_mode is not None and pricing_mode not in ("free", "paid", "all"):
        raise RequestValidationError("pricing_mode phải là 'free', 'paid' hoặc 'all'.", field="pricing_mode", status=400, code="INVALID_PARAMS")
    if pricing_mode == "all":
        pricing_mode = None

    sort_by = str(arguments.get("sort_by") or arguments.get("sort") or "popular").strip().lower()
    valid_sorts = {"popular", "recently_updated", "rating", "newest", "price_asc", "price_desc"}
    if sort_by not in valid_sorts:
        sort_by = "popular"

    only_mine = bool(arguments.get("only_mine", False))
    limit = _validate_positive_int(arguments.get("limit", 20), "limit", default=20, max_val=100)
    offset = _validate_positive_int(arguments.get("offset", 0), "offset", default=0, allow_zero=True)

    return {
        "query": query,
        "category": category,
        "tags": tags,
        "pricing_mode": pricing_mode,
        "sort_by": sort_by,
        "only_mine": only_mine,
        "limit": limit,
        "offset": offset,
    }


def validate_get_shared_deck_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for get_shared_deck tool."""
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    raw_id = arguments.get("deck_item_id") or arguments.get("id")
    deck_item_id = str(raw_id).strip() if raw_id is not None else ""
    if not deck_item_id:
        raise RequestValidationError("deck_item_id là bắt buộc.", field="deck_item_id", status=400, code="INVALID_PARAMS")
    return {"deck_item_id": deck_item_id}


def validate_list_shared_deck_notes_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for list_shared_deck_notes tool."""
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    raw_id = arguments.get("deck_item_id") or arguments.get("id")
    deck_item_id = str(raw_id).strip() if raw_id is not None else ""
    if not deck_item_id:
        raise RequestValidationError("deck_item_id là bắt buộc.", field="deck_item_id", status=400, code="INVALID_PARAMS")
    query = str(arguments.get("query") or arguments.get("q") or "").strip() or None
    limit = _validate_positive_int(arguments.get("limit", 20), "limit", default=20, max_val=100)
    offset = _validate_positive_int(arguments.get("offset", 0), "offset", default=0, allow_zero=True)
    return {
        "deck_item_id": deck_item_id,
        "query": query,
        "limit": limit,
        "offset": offset,
    }


def validate_get_deck_publish_options_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for get_deck_publish_options tool."""
    if arguments is None:
        return {}
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    raw_deck_id = arguments.get("deck_id")
    deck_id = None
    if raw_deck_id is not None:
        try:
            deck_id = int(raw_deck_id)
        except (ValueError, TypeError):
            raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")
    return {"deck_id": deck_id}


def validate_share_deck_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for share_deck tool."""
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    raw_deck_id = arguments.get("deck_id")
    deck_path = str(arguments.get("deck_path") or "").strip() or None
    if raw_deck_id is None and not deck_path:
        raise RequestValidationError("Cần cung cấp ít nhất 'deck_id' hoặc 'deck_path'.", field="deck_id", status=400, code="INVALID_PARAMS")
    deck_id = None
    if raw_deck_id is not None:
        try:
            deck_id = int(raw_deck_id)
        except (ValueError, TypeError):
            raise RequestValidationError("deck_id phải là số nguyên.", field="deck_id", status=400, code="INVALID_PARAMS")

    title = str(arguments.get("title") or "").strip() or None
    description = str(arguments.get("description")).strip() if arguments.get("description") is not None else None
    primary_category = str(arguments.get("primary_category") or arguments.get("category") or "").strip() or None

    raw_tags = arguments.get("tags")
    tags: list[str] = []
    if raw_tags is not None:
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        else:
            raise RequestValidationError("tags phải là danh sách chuỗi.", field="tags", status=400, code="INVALID_PARAMS")

    pricing_mode = str(arguments.get("pricing_mode") or "free").strip().lower()
    if pricing_mode not in ("free", "paid"):
        raise RequestValidationError("pricing_mode phải là 'free' hoặc 'paid'.", field="pricing_mode", status=400, code="INVALID_PARAMS")

    price_amount_minor = None
    if arguments.get("price_amount_minor") is not None:
        try:
            price_amount_minor = int(arguments.get("price_amount_minor"))
            if price_amount_minor < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise RequestValidationError("price_amount_minor phải là số nguyên không âm.", field="price_amount_minor", status=400, code="INVALID_PARAMS")

    is_unlisted = bool(arguments.get("is_unlisted", False))
    preview_text = str(arguments.get("preview_text")).strip() if arguments.get("preview_text") is not None else None

    sample_cards_count = None
    if arguments.get("sample_cards_count") is not None:
        try:
            sample_cards_count = max(0, int(arguments.get("sample_cards_count")))
        except (ValueError, TypeError):
            raise RequestValidationError("sample_cards_count phải là số nguyên không âm.", field="sample_cards_count", status=400, code="INVALID_PARAMS")

    raw_tax = arguments.get("taxonomy_metadata")
    if raw_tax is not None and not isinstance(raw_tax, dict):
        raise RequestValidationError("taxonomy_metadata phải là JSON object.", field="taxonomy_metadata", status=400, code="INVALID_PARAMS")

    taxonomy_payload = _extract_taxonomy_from_dict(arguments)

    return {
        "deck_id": deck_id,
        "deck_path": deck_path,
        "title": title,
        "description": description,
        "primary_category": primary_category,
        "tags": tags,
        "pricing_mode": pricing_mode,
        "price_amount_minor": price_amount_minor,
        "is_unlisted": is_unlisted,
        "preview_text": preview_text,
        "sample_cards_count": sample_cards_count,
        "taxonomy_metadata": taxonomy_payload if taxonomy_payload else (raw_tax if raw_tax is not None else None),
    }


def validate_update_shared_deck_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for update_shared_deck tool."""
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    raw_id = arguments.get("deck_item_id") or arguments.get("id")
    deck_item_id = str(raw_id).strip() if raw_id is not None else ""
    if not deck_item_id:
        raise RequestValidationError("deck_item_id là bắt buộc.", field="deck_item_id", status=400, code="INVALID_PARAMS")

    title = str(arguments.get("title")).strip() if arguments.get("title") is not None else None
    description = str(arguments.get("description")).strip() if arguments.get("description") is not None else None
    primary_category = str(arguments.get("primary_category") or arguments.get("category")).strip() if (arguments.get("primary_category") or arguments.get("category")) is not None else None

    raw_tags = arguments.get("tags")
    tags: list[str] | None = None
    if raw_tags is not None:
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        else:
            raise RequestValidationError("tags phải là danh sách chuỗi.", field="tags", status=400, code="INVALID_PARAMS")

    pricing_mode = str(arguments.get("pricing_mode")).strip().lower() if arguments.get("pricing_mode") is not None else None
    if pricing_mode is not None and pricing_mode not in ("free", "paid"):
        raise RequestValidationError("pricing_mode phải là 'free' hoặc 'paid'.", field="pricing_mode", status=400, code="INVALID_PARAMS")

    price_amount_minor = None
    if arguments.get("price_amount_minor") is not None:
        try:
            price_amount_minor = int(arguments.get("price_amount_minor"))
            if price_amount_minor < 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise RequestValidationError("price_amount_minor phải là số nguyên không âm.", field="price_amount_minor", status=400, code="INVALID_PARAMS")

    publish_status = str(arguments.get("publish_status")).strip().lower() if arguments.get("publish_status") is not None else None
    if publish_status is not None and publish_status not in ("published", "unlisted", "archived", "draft", "private"):
        raise RequestValidationError("publish_status không hợp lệ.", field="publish_status", status=400, code="INVALID_PARAMS")

    preview_text = str(arguments.get("preview_text")).strip() if arguments.get("preview_text") is not None else None

    sample_cards_count = None
    if arguments.get("sample_cards_count") is not None:
        try:
            sample_cards_count = max(0, int(arguments.get("sample_cards_count")))
        except (ValueError, TypeError):
            raise RequestValidationError("sample_cards_count phải là số nguyên không âm.", field="sample_cards_count", status=400, code="INVALID_PARAMS")

    raw_tax = arguments.get("taxonomy_metadata")
    if raw_tax is not None and not isinstance(raw_tax, dict):
        raise RequestValidationError("taxonomy_metadata phải là JSON object.", field="taxonomy_metadata", status=400, code="INVALID_PARAMS")

    taxonomy_payload = _extract_taxonomy_from_dict(arguments)

    return {
        "deck_item_id": deck_item_id,
        "title": title,
        "description": description,
        "primary_category": primary_category,
        "tags": tags,
        "pricing_mode": pricing_mode,
        "price_amount_minor": price_amount_minor,
        "publish_status": publish_status,
        "preview_text": preview_text,
        "sample_cards_count": sample_cards_count,
        "taxonomy_metadata": taxonomy_payload if taxonomy_payload else (raw_tax if raw_tax is not None else None),
    }


def validate_get_taxonomy_schema_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for get_taxonomy_schema tool."""
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    content_type = str(arguments.get("content_type") or "deck_marketplace_item").strip().lower()
    if content_type not in ("deck_marketplace_item", "note_type"):
        raise RequestValidationError(
            "content_type phải là 'deck_marketplace_item' hoặc 'note_type'.",
            field="content_type",
            status=400,
            code="INVALID_PARAMS",
        )
    return {"content_type": content_type}



def validate_preview_deck_release_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for preview_deck_release tool."""
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    raw_id = arguments.get("deck_item_id") or arguments.get("id")
    deck_item_id = str(raw_id).strip() if raw_id is not None else ""
    if not deck_item_id:
        raise RequestValidationError("deck_item_id là bắt buộc.", field="deck_item_id", status=400, code="INVALID_PARAMS")
    limit = _validate_positive_int(arguments.get("limit", 50), "limit", default=50, max_val=200)
    cursor = str(arguments.get("cursor")).strip() if arguments.get("cursor") is not None else None
    return {
        "deck_item_id": deck_item_id,
        "limit": limit,
        "cursor": cursor,
    }


def validate_publish_deck_release_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for publish_deck_release tool."""
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    raw_id = arguments.get("deck_item_id") or arguments.get("id")
    deck_item_id = str(raw_id).strip() if raw_id is not None else ""
    if not deck_item_id:
        raise RequestValidationError("deck_item_id là bắt buộc.", field="deck_item_id", status=400, code="INVALID_PARAMS")

    version_label = str(arguments.get("version_label") or arguments.get("version") or "").strip()
    if not version_label:
        raise RequestValidationError("version_label là bắt buộc.", field="version_label", status=400, code="INVALID_PARAMS")

    changelog = str(arguments.get("changelog")).strip() if arguments.get("changelog") is not None else None
    raw_expected_release_id = arguments.get("expected_current_release_id")
    expected_current_release_id = str(raw_expected_release_id).strip() if raw_expected_release_id is not None and str(raw_expected_release_id).strip() else None

    raw_revision = arguments.get("expected_working_revision")
    expected_working_revision = None
    if raw_revision is not None:
        try:
            expected_working_revision = int(raw_revision)
        except (ValueError, TypeError):
            raise RequestValidationError("expected_working_revision phải là số nguyên.", field="expected_working_revision", status=400, code="INVALID_PARAMS")

    return {
        "deck_item_id": deck_item_id,
        "version_label": version_label,
        "changelog": changelog,
        "expected_current_release_id": expected_current_release_id,
        "expected_working_revision": expected_working_revision,
    }


def validate_list_deck_releases_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for list_deck_releases tool."""
    if not isinstance(arguments, dict):
        raise RequestValidationError("arguments phải là JSON object.", field="arguments", status=400, code="INVALID_PARAMS")
    raw_id = arguments.get("deck_item_id") or arguments.get("id")
    deck_item_id = str(raw_id).strip() if raw_id is not None else ""
    if not deck_item_id:
        raise RequestValidationError("deck_item_id là bắt buộc.", field="deck_item_id", status=400, code="INVALID_PARAMS")
    limit = _validate_positive_int(arguments.get("limit", 20), "limit", default=20, max_val=100)
    cursor = str(arguments.get("cursor")).strip() if arguments.get("cursor") is not None else None
    return {
        "deck_item_id": deck_item_id,
        "limit": limit,
        "cursor": cursor,
    }


def validate_list_installed_decks_arguments(arguments: Any) -> dict[str, Any]:
    """Validate arguments for list_installed_decks tool."""
    return validate_empty_arguments(arguments, tool_name="list_installed_decks")


