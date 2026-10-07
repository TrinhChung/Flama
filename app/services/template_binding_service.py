"""Render-time projection of abstract template inputs onto stable FieldDef IDs.

Sources remain untouched. Projected fields feed the existing renderer so typed
media, rich text, Markdown, and sanitization retain their normal behavior.
"""

from __future__ import annotations

from dataclasses import replace
import json
from types import SimpleNamespace
from typing import Any, Mapping
from uuid import UUID, uuid5


_ALIAS_NAMESPACE = UUID("b46d9f8b-43d3-51a4-9787-d297c41bd2dc")
_FIELD_ATTRIBUTES = ("id", "name", "field_type", "required", "position")


class _ProjectedFields(list):
    def __init__(self, fields, *, key, source_fields):
        super().__init__(fields)
        self.projection_key = key
        self.source_fields = source_fields


class _ProjectedValues(dict):
    def __init__(self, values, *, key, source_values):
        super().__init__(values)
        self.projection_key = key
        self.source_values = source_values


def _copy_field(field):
    return SimpleNamespace(**{key: getattr(field, key, None) for key in _FIELD_ATTRIBUTES})


def _inputs(template, bindings):
    schema = getattr(template, "input_schema", None) or []
    inputs = []
    seen = set()
    for item in schema:
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("key") or "").strip()
        if key and key not in seen:
            inputs.append({"key": key, "type": str(item.get("type") or "text"),
                           "required": bool(item.get("required", False))})
            seen.add(key)
    if not inputs:
        inputs = [{"key": str(key), "type": "text", "required": False} for key in bindings]
    return inputs


def prepare_bound_fields(
    template: Any,
    field_defs: list[Any],
    field_values: dict[str, Any] | None,
    *,
    input_bindings: Mapping[str, str | None] | None = None,
) -> tuple[list[Any], dict[str, Any] | None]:
    """Project aliases without rewriting sources or mutating Note fields.

    Missing and stale targets produce empty inputs, including required inputs.
    An identity binding returns the original objects to preserve legacy hashes.
    Projection can be applied repeatedly; changing the binding of an already
    projected context reuses its detached original field/value snapshot.
    """
    raw_bindings = input_bindings if input_bindings is not None else getattr(template, "input_bindings", None)
    bindings = dict(raw_bindings) if isinstance(raw_bindings, Mapping) else {}
    inputs = _inputs(template, bindings)
    if not inputs:
        return field_defs, field_values
    projection_key = json.dumps(
        [str(getattr(template, "id", "")), inputs, bindings], sort_keys=True,
        separators=(",", ":"), ensure_ascii=False,
    )
    if (isinstance(field_defs, _ProjectedFields) and isinstance(field_values, _ProjectedValues)
            and field_defs.projection_key == field_values.projection_key == projection_key):
        return field_defs, field_values

    source_fields = field_defs.source_fields if isinstance(field_defs, _ProjectedFields) else field_defs
    source_values = field_values.source_values if isinstance(field_values, _ProjectedValues) else (field_values or {})
    by_id = {str(field.id): field for field in source_fields}
    targets = [(item, by_id.get(str(bindings.get(item["key"]) or ""))) for item in inputs]
    if all(target is not None and target.name == item["key"] for item, target in targets):
        if not isinstance(field_defs, _ProjectedFields):
            return field_defs, field_values
        return source_fields, source_values

    source_snapshot = [_copy_field(field) for field in source_fields]
    source_values_snapshot = dict(source_values)
    names = {item["key"] for item in inputs}
    projected = [_copy_field(field) for field in source_fields if field.name not in names]
    values = dict(source_values)
    next_position = max((int(getattr(field, "position", 0) or 0) for field in source_fields), default=-1) + 1
    for index, (item, target) in enumerate(targets):
        key = item["key"]
        target_id = str(target.id) if target is not None else str(bindings.get(key) or "")
        field_type = str(getattr(target, "field_type", None) or item["type"] or "text")
        alias_id = str(uuid5(_ALIAS_NAMESPACE, json.dumps(
            [str(getattr(template, "id", "")), key, target_id, field_type], ensure_ascii=False,
            separators=(",", ":"),
        )))
        projected.append(SimpleNamespace(
            id=alias_id, name=key, field_type=field_type,
            required=item["required"], position=next_position + index,
        ))
        values[key] = source_values.get(target.name, "") if target is not None else ""
        # A declared input owns its helper namespace too; unrelated note data
        # must not become a fallback URL when an input is unbound or retargeted.
        values.pop(f"{key}_url", None)
        values.pop(f"{key}_urls", None)
    return (
        _ProjectedFields(projected, key=projection_key, source_fields=source_snapshot),
        _ProjectedValues(values, key=projection_key, source_values=source_values_snapshot),
    )


def binding_warnings(template, field_defs, *, input_bindings=None):
    """Return advisory diagnostics; missing required inputs never block render."""
    raw = input_bindings if input_bindings is not None else getattr(template, "input_bindings", None)
    bindings = dict(raw) if isinstance(raw, Mapping) else {}
    ids = {str(field.id) for field in field_defs}
    warnings = []
    for item in _inputs(template, bindings):
        target = str(bindings.get(item["key"]) or "")
        if target and target not in ids:
            warnings.append({"code": "INPUT_FIELD_NOT_FOUND", "input_key": item["key"], "field_def_id": target})
        elif item["required"] and not target:
            warnings.append({"code": "REQUIRED_INPUT_UNBOUND", "input_key": item["key"], "field_def_id": None})
    return warnings


def apply_binding_projection(context):
    """Return an effective Card context with an idempotent field projection."""
    fields, values = prepare_bound_fields(context.template, context.field_defs, context.field_values)
    if fields is context.field_defs and values is context.field_values:
        return context
    return replace(context, field_defs=fields, field_values=values)
