"""Bounded, explicit input contract for the read-only candidate preview tool."""

from app.validators.flashcard_input import RequestValidationError
from app.validators.template_preview import preview_field_value
from models.field_types import FIELD_TYPES


TEMPLATE_PREVIEW_INPUT_SCHEMA = {
    "type": "object",
    "$defs": {"sampleValue": {"anyOf": [{"type": "string", "maxLength": 100000},
        {"type": "array", "items": {"$ref": "#/$defs/sampleValue"}}]}},
    "properties": {
        "note_type_id": {"type": "string"},
        "application_id": {"type": "string", "description": "Explicit attached occurrence; required with note_type_id."},
        "front_html": {"type": "string", "maxLength": 100000},
        "back_html": {"type": "string", "maxLength": 100000},
        "shared_css": {"type": "string", "maxLength": 100000},
        "input_schema": {"type": "array", "maxItems": 100, "items": {
            "type": "object", "properties": {"key": {"type": "string", "minLength": 1, "maxLength": 255},
                "label": {"type": "string", "maxLength": 255},
                "type": {"type": "string", "enum": list(FIELD_TYPES)}, "required": {"type": "boolean"}},
            "required": ["key", "type"], "additionalProperties": False}},
        "sample_values": {"type": "object", "maxProperties": 100,
            "additionalProperties": {"$ref": "#/$defs/sampleValue"},
            "description": "Explicit text or native string-list values keyed by input name (raw) or source field name (attached). Never persisted. No numeric/object/null values."},
        "profile": {"type": "string", "enum": ["generic", "quiz"], "default": "generic"},
        "include_preview": {"type": "boolean", "default": False,
            "description": "Include full Study artifacts in model-visible output. Normally artifacts are delivered only to the preview UI."},
        "include_server_render": {"type": "boolean", "default": False,
            "description": "Include legacy server-rendered HTML only for explicit render debugging."},
    },
    "required": ["sample_values"], "additionalProperties": False,
}

TEMPLATE_PREVIEW_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "schema_version": {"const": "template-preview.v1"},
        "valid": {"type": "boolean", "description": "False means the evaluation found validation errors. Inspect checks and diagnostics; no browser verification is implied."},
        "candidate_hash": {"type": ["string", "null"], "pattern": "^sha256-[a-f0-9]{64}$"},
        "renderer_abi": {"type": "string"},
        "checks": {"type": "object", "properties": {
            stage: {"type": "string", "enum": ["passed", "failed", "not_run", "unsupported"]}
            for stage in ("input", "binding", "template", "javascript_syntax", "server_render", "study_browser", "interaction")},
            "required": ["input", "binding", "template", "javascript_syntax", "server_render", "study_browser", "interaction"]},
        "diagnostics": {"type": "array", "maxItems": 100, "items": {"type": "object",
            "properties": {"code": {"type": "string"}, "severity": {"enum": ["warning", "error"]},
                "stage": {"type": "string"}, "source_part": {"type": "string"},
                "line": {"type": ["integer", "null"], "minimum": 1},
                "column": {"type": ["integer", "null"], "minimum": 1},
                "suggestions": {"type": "array", "maxItems": 5, "items": {"type": "string"}},
                "message": {"type": "string", "maxLength": 1000}, "hint": {"type": "string", "maxLength": 1000}},
            "required": ["code", "severity", "stage", "source_part", "message", "hint", "line", "column", "suggestions"]}},
        "preview_available": {"type": "boolean"},
        "preview": {"type": ["object", "null"], "properties": {
            "template_artifact": {"type": "object"}, "content_artifact": {"type": "object"}},
            "required": ["template_artifact", "content_artifact"]},
        "server_render": {"type": ["object", "null"]},
        "sample_source": {"type": "object", "properties": {"kind": {"type": "string"}}, "required": ["kind"]},
        "media_base_url": {"type": "string"}, "ui_available": {"type": "boolean"},
        "verification_note": {"type": "string"},
    },
    "required": ["schema_version", "valid", "candidate_hash", "renderer_abi", "checks", "diagnostics", "preview",
                 "preview_available", "sample_source", "media_base_url", "ui_available", "verification_note"],
}


def validate_template_preview_arguments(arguments):
    def invalid(message, field=None):
        raise RequestValidationError(message, field=field, code="INVALID_PARAMS")
    if not isinstance(arguments, dict):
        invalid("Preview arguments must be an object.")
    allowed = set(TEMPLATE_PREVIEW_INPUT_SCHEMA["properties"])
    if set(arguments) - allowed:
        invalid("Unknown preview argument. Select an occurrence with application_id, not template_id.")
    result = dict(arguments)
    for key in ("include_preview", "include_server_render"):
        if key in result and not isinstance(result[key], bool):
            invalid(f"{key} must be boolean.", key)
    for key in ("note_type_id", "application_id"):
        if key in result and (not isinstance(result[key], str) or not 1 <= len(result[key]) <= 128):
            invalid(f"{key} must be a nonempty ID.", key)
    attached = "note_type_id" in result
    if attached != ("application_id" in result):
        invalid("note_type_id and application_id must be supplied together.", "application_id")
    if attached and "input_schema" in result:
        invalid("Attached previews use the occurrence's input schema and field bindings.", "input_schema")
    if not attached and ("input_schema" not in result or "front_html" not in result or "back_html" not in result):
        invalid("Raw candidates require input_schema, front_html and back_html.", "input_schema")
    for key in ("front_html", "back_html", "shared_css"):
        if key in result and (not isinstance(result[key], str) or len(result[key]) > 100000):
            invalid(f"{key} must be text of at most 100000 characters.", key)
    if result.get("profile", "generic") not in ("generic", "quiz"):
        invalid("profile must be generic or quiz.", "profile")
    if "input_schema" in result:
        schema = result["input_schema"]
        if not isinstance(schema, list) or len(schema) > 100:
            invalid("input_schema must be a list of at most 100 inputs.", "input_schema")
        seen = set()
        for item in schema:
            if not isinstance(item, dict) or set(item) - {"key", "label", "type", "required"}:
                invalid("Each input must contain key, type and optional required.", "input_schema")
            if "label" in item and (not isinstance(item["label"], str) or len(item["label"]) > 255):
                invalid("Input label must be text of at most 255 characters.", "input_schema")
            key = item.get("key")
            if (not isinstance(key, str) or not key.strip() or key != key.strip()
                    or len(key) > 255 or "{" in key or "}" in key or key in seen):
                invalid("Input keys must be unique nonempty names without braces.", "input_schema")
            if item.get("type") not in FIELD_TYPES or ("required" in item and not isinstance(item["required"], bool)):
                invalid("Invalid input type or required flag.", "input_schema")
            seen.add(key)
    values = result.get("sample_values")
    if not isinstance(values, dict) or len(values) > 100:
        invalid("sample_values must explicitly supply an object of at most 100 text/list values.", "sample_values")
    cleaned, total = {}, 0
    for key, value in values.items():
        if not isinstance(key, str) or len(key) > 255:
            invalid("Sample keys must be input/field names.", "sample_values")
        cleaned[key], count = preview_field_value(value, field_name=key)
        total += count
        if total > 250000:
            invalid("sample_values exceeds the 250000 character limit.", "sample_values")
    result["sample_values"] = cleaned
    return result
