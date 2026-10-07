"""Validation for reusable template definitions and FieldDef-ID bindings."""

from copy import deepcopy
from app.services.template_tokens import TemplateTokenError, extract_variable_names

FIELD_TYPES = {"text", "richtext", "markdown", "image", "audio", "diagram"}


class TemplateLibraryError(ValueError):
    def __init__(self, code, message, *, status=400, field=None, details=None):
        super().__init__(message)
        self.code, self.status, self.field, self.details = code, status, field, details


def body(payload, allowed):
    if not isinstance(payload, dict) or set(payload) - set(allowed):
        raise TemplateLibraryError("VALIDATION_ERROR", "Request body contains unsupported properties.")
    return payload


def text(value, *, field, maximum=None, required=False):
    if not isinstance(value, str) or (required and not value.strip()) or (maximum and len(value) > maximum):
        raise TemplateLibraryError("VALIDATION_ERROR", f"Invalid {field}.", field=field)
    return value.strip() if required else value


def validate_input_schema(schema):
    if not isinstance(schema, list):
        raise TemplateLibraryError("VALIDATION_ERROR", "input_schema must be an array.", field="input_schema")
    result, keys = [], set()
    for item in schema:
        if not isinstance(item, dict) or set(item) - {"key", "label", "type", "required"}:
            raise TemplateLibraryError("VALIDATION_ERROR", "Invalid input definition.", field="input_schema")
        key = item.get("key")
        if not isinstance(key, str) or not key.strip() or key != key.strip() or any(c in key for c in "{}#^/!>&=\n\r") or key in {".", "FrontSide"} or key in keys:
            raise TemplateLibraryError("VALIDATION_ERROR", "Input keys must be unique valid template variables.", field="input_schema")
        kind = item.get("type", "text")
        if kind not in FIELD_TYPES or not isinstance(item.get("required", False), bool):
            raise TemplateLibraryError("VALIDATION_ERROR", "Invalid input type or recommendation.", field="input_schema")
        label = text(item.get("label", key), field="input_schema.label", maximum=255)
        result.append({"key": key, "label": label, "type": kind, "required": item.get("required", False)})
        keys.add(key)
    return result


def infer_input_schema(front, back, field_defs=()):
    names = {field.name: field for field in field_defs}
    try:
        keys = list(dict.fromkeys(extract_variable_names(front) + extract_variable_names(back)))
    except TemplateTokenError as exc:
        raise TemplateLibraryError("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html") from exc
    result = []
    for key in keys:
        if key in {"FrontSide", "."}:
            continue
        for suffix in ("_urls", "_url"):
            if key.endswith(suffix) and key[:-len(suffix)] in names:
                key = key[:-len(suffix)]
                break
        if any(item["key"] == key for item in result):
            continue
        field = names.get(key)
        result.append({"key": key, "label": key, "type": getattr(field, "field_type", "text"), "required": False})
    return validate_input_schema(result)


def validate_bindings(schema, bindings, field_defs):
    if not isinstance(bindings, dict):
        raise TemplateLibraryError("VALIDATION_ERROR", "input_bindings must be an object.", field="input_bindings")
    inputs = {item["key"]: item for item in schema}
    fields = {str(field.id): field for field in field_defs}
    result = {}
    for key, field_id in bindings.items():
        if key not in inputs:
            raise TemplateLibraryError("INPUT_NOT_FOUND", "Unknown template input.", field=key)
        if field_id is None or field_id == "":
            result[key] = None
            continue
        if not isinstance(field_id, str) or field_id not in fields:
            raise TemplateLibraryError("FIELD_OUT_OF_SCOPE", "Binding must reference a field of this NoteType.", field=key)
        if fields[field_id].field_type != inputs[key]["type"]:
            raise TemplateLibraryError("INPUT_TYPE_MISMATCH", "Input and field types must match.", field=key)
        result[key] = field_id
    return deepcopy(result)


def binding_warnings(schema, bindings, field_defs):
    fields = {str(field.id): field for field in field_defs}
    warnings = []
    for item in schema:
        field = fields.get((bindings or {}).get(item["key"]))
        if field is None or field.field_type != item["type"]:
            warnings.append({"input_key": item["key"], "code": "INPUT_UNBOUND" if field is None else "INPUT_TYPE_MISMATCH", "required": item["required"]})
    return warnings
