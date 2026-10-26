"""Discoverable schemas and strict payload validation for MCP authoring."""

from copy import deepcopy

from app.validators import RequestValidationError
from app.validators.template_library import TemplateLibraryError, validate_input_schema
from models.field_types import FIELD_TYPES


NAME = {"type": "string", "minLength": 1, "maxLength": 255}
FIELD_PROPERTIES = {
    "name": NAME, "field_type": {"type": "string", "enum": list(FIELD_TYPES)},
    "required": {"type": "boolean"}, "position": {"type": "integer", "minimum": 0},
    "identity_role": {"enum": [None, "primary"]},
}
FIELD_SCHEMA = {"type": "object", "properties": FIELD_PROPERTIES,
    "required": ["name"], "additionalProperties": False}
INPUT_SCHEMA = {"type": "array", "maxItems": 100, "items": {
    "type": "object", "properties": {"key": NAME, "label": {"type": "string", "maxLength": 255},
        "type": {"type": "string", "enum": list(FIELD_TYPES)}, "required": {"type": "boolean"}},
    "required": ["key", "type"], "additionalProperties": False}}
TEMPLATE_PROPERTIES = {"name": NAME,
    **{key: {"type": "string", "maxLength": 100000} for key in ("front_html", "back_html", "shared_css")},
    "position": {"type": "integer", "minimum": 0}, "is_default": {"type": "boolean"}}
TEMPLATE_SCHEMA = {"type": "object", "properties": TEMPLATE_PROPERTIES,
    "required": ["name"], "additionalProperties": False}
FIELD_UPDATE_SCHEMA = {"anyOf": [
    {"type": "array", "minItems": 1, "items": {**FIELD_SCHEMA, "properties": {
        **FIELD_PROPERTIES, "id": NAME, "old_name": NAME}}},
    {"type": "object", "properties": {
        "added": {"type": "array", "items": FIELD_SCHEMA},
        "renamed": {"type": "array", "items": {"type": "object", "properties": {
            "old_name": NAME, "new_name": NAME}, "required": ["old_name", "new_name"], "additionalProperties": False}},
        "removed": {"type": "array", "items": NAME},
        "modified": {"type": "array", "items": FIELD_SCHEMA}}, "additionalProperties": False}],
    "description": "Prefer deltas: added, renamed [{old_name,new_name}], removed [name], modified [{name,field_type,required,position,identity_role}]. A full list replaces the fields; retain id or old_name to rename safely."}
TEMPLATE_UPDATE_ITEM = {**TEMPLATE_SCHEMA, "properties": {
    **TEMPLATE_PROPERTIES, "id": NAME, "application_id": NAME}, "required": []}
TEMPLATE_UPDATE_SCHEMA = {"anyOf": [
    {"type": "array", "minItems": 1, "items": TEMPLATE_UPDATE_ITEM},
    {"type": "object", "properties": {
        "added": {"type": "array", "items": TEMPLATE_SCHEMA},
        "updated": {"type": "array", "items": TEMPLATE_UPDATE_ITEM},
        "removed": {"type": "array", "items": {"anyOf": [NAME, TEMPLATE_UPDATE_ITEM]}}}, "additionalProperties": False}],
    "description": "Prefer added/updated/removed deltas. Select existing occurrences with application_id, especially when renaming. A full list retires omitted occurrences. For reusable inputs/bindings use the card-template tools."}


def invalid(message, field, code="INVALID_PARAMS"):
    raise RequestValidationError(message, field=field, status=400, code=code)


def validate_object(arguments, schema):
    """Validate the small JSON-schema subset used by authoring tool arguments.

    Service validation remains authoritative for ownership, references and state.
    No coercion of booleans, positions or source text is allowed.
    """
    def check(value, rule, path):
        if "anyOf" in rule:
            for option in rule["anyOf"]:
                try:
                    check(value, option, path)
                    return
                except RequestValidationError:
                    pass
            invalid("Value does not match an accepted authoring shape. See the tool input schema.", path)
        kind = rule.get("type")
        matches = {"object": isinstance(value, dict), "array": isinstance(value, list),
            "string": isinstance(value, str), "boolean": isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool), "null": value is None}
        if kind and not any(matches.get(item, False) for item in (kind if isinstance(kind, list) else [kind])):
            invalid(f"Expected {kind}.", path)
        if "enum" in rule and value not in rule["enum"]:
            invalid(f"Expected one of {rule['enum']}.", path)
        if isinstance(value, dict):
            props = rule.get("properties", {})
            if rule.get("additionalProperties") is False and set(value) - set(props):
                invalid("Unsupported properties: " + ", ".join(sorted(set(value) - set(props))), path)
            for key in rule.get("required", []):
                if key not in value:
                    invalid("Required value is missing.", f"{path}.{key}")
            for key, item in value.items():
                child_rule = props.get(key, rule.get("additionalProperties"))
                if isinstance(child_rule, dict):
                    check(item, child_rule, f"{path}.{key}")
        elif isinstance(value, list):
            if not rule.get("minItems", 0) <= len(value) <= rule.get("maxItems", 1000):
                invalid("Invalid list length.", path)
            for index, item in enumerate(value):
                check(item, rule.get("items", {}), f"{path}[{index}]")
        elif isinstance(value, str):
            if len(value) < rule.get("minLength", 0) or len(value) > rule.get("maxLength", 100000):
                invalid("Invalid text length.", path)
            if rule.get("minLength") and not value.strip():
                invalid("Name or ID cannot be blank.", path)
            if rule.get("minLength") and value != value.strip():
                invalid("Name or ID cannot contain surrounding whitespace.", path)
        elif isinstance(value, int) and not isinstance(value, bool) and value < rule.get("minimum", value):
            invalid("Number is below its minimum.", path)
    check(arguments, schema, "arguments")
    return deepcopy(arguments)


def validate_note_type_changes(arguments):
    for key, schema in (("fields", FIELD_UPDATE_SCHEMA), ("templates", TEMPLATE_UPDATE_SCHEMA)):
        if arguments.get(key) is not None:
            validate_object({key: arguments[key]}, {"type": "object", "properties": {key: schema}})
    if "confirm" in arguments and not isinstance(arguments["confirm"], bool):
        invalid("confirm must be boolean.", "confirm")
    if arguments.get("name") is not None:
        validate_object({"name": arguments["name"]}, {"type": "object", "properties": {"name": NAME}})


def planned_fields(current_fields, changes):
    """Validate references and final field invariants before preview or mutation."""
    rows = [{key: getattr(field, key) for key in ("id", "name", "field_type", "position", "required", "identity_role")}
        for field in current_fields]
    if changes is None:
        return rows
    by_id = {row["id"]: row for row in rows}
    by_name = {row["name"]: row for row in rows}
    if isinstance(changes, list):
        result = []
        retained = set()
        for index, item in enumerate(changes):
            reference = item.get("id") or item.get("old_name")
            old = by_id.get(item.get("id")) if item.get("id") else by_name.get(item.get("old_name") or item["name"])
            if reference and old is None:
                invalid("Field reference does not belong to this NoteType.", "fields", "FIELD_NOT_FOUND")
            if old and old["id"] in retained:
                invalid("A field may appear only once.", "fields", "DUPLICATE_FIELD_NAME")
            if old:
                retained.add(old["id"])
            result.append({"field_type": "text", "required": False, "identity_role": None,
                **(old or {}), **item, "position": item.get("position", index)})
    else:
        result = rows
        for rename in changes.get("renamed", []):
            row = by_name.pop(rename["old_name"], None)
            if row is None:
                invalid("Renamed field does not exist.", "fields.renamed", "FIELD_NOT_FOUND")
            if rename["new_name"] in by_name:
                invalid("New field name already exists.", "fields.renamed", "DUPLICATE_FIELD_NAME")
            row["name"] = rename["new_name"]
            by_name[row["name"]] = row
        for name in changes.get("removed", []):
            row = by_name.pop(name, None)
            if row is None:
                invalid("Removed field does not exist.", "fields.removed", "FIELD_NOT_FOUND")
            result.remove(row)
        for item in changes.get("added", []):
            if item["name"] in by_name:
                invalid("Added field already exists.", "fields.added", "DUPLICATE_FIELD_NAME")
            row = {"field_type": "text", "position": max((row["position"] for row in result), default=-1) + 1,
                "required": False, "identity_role": None, **item}
            result.append(row)
            by_name[row["name"]] = row
        for item in changes.get("modified", []):
            if item["name"] not in by_name:
                invalid("Modified field does not exist.", "fields.modified", "FIELD_NOT_FOUND")
            by_name[item["name"]].update(item)
    if not result:
        invalid("A NoteType requires at least one field.", "fields", "NOTE_TYPE_MUST_HAVE_FIELDS")
    names = [row["name"].casefold() for row in result]
    if len(set(names)) != len(names):
        invalid("Field names must be unique (case-insensitive).", "fields", "DUPLICATE_FIELD_NAME")
    primary = [row for row in result if row.get("identity_role") == "primary"]
    if len(primary) > 1:
        invalid("Only one primary identity field is allowed.", "fields", "MULTIPLE_PRIMARY_IDENTITY")
    if primary and primary[0]["field_type"] != "text":
        invalid("Primary identity fields must use text.", "fields", "INVALID_IDENTITY_TYPE")
    return result


def validate_template_inputs(arguments):
    if "input_schema" in arguments:
        try:
            arguments["input_schema"] = validate_input_schema(arguments["input_schema"])
        except TemplateLibraryError as exc:
            invalid(str(exc), exc.field or "input_schema", exc.code)
    return arguments
