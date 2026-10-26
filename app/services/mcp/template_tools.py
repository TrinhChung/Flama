"""MCP adapters for the canonical personal template library and applications."""

from types import SimpleNamespace

from app.services import flashcard_content_service, template_library_service as library
from app.services.flashcard_content_service import ContentApiError
from app.services.common.mcp_response import wrap_tool_result
from app.services.mcp.authoring_responses import wrap_authoring_error
from app.services.template_authoring_service import analyze_template_sources
from app.services.template_version_service import TemplateVersionError
from app.validators import RequestValidationError
from app.validators.mcp_authoring import NAME, INPUT_SCHEMA, validate_object, validate_template_inputs
from app.validators.template_authoring import TemplateAuthoringValidationError
from app.validators.template_library import TemplateLibraryError


CONTENT = {"name": NAME, "description": {"type": "string"},
    "primary_category": {"type": ["string", "null"], "maxLength": 120},
    **{key: {"type": "string", "maxLength": 100000} for key in ("front_html", "back_html", "shared_css")},
    "input_schema": INPUT_SCHEMA, "change_note": {"type": "string", "maxLength": 1000}}
APPLICATION = {
    "input_bindings": {"type": "object", "additionalProperties": {"type": ["string", "null"]},
        "description": "Map input keys to FieldDef IDs from this NoteType's schema. Null unbinds an input. Replaces the binding map."},
    "display_name": {"type": ["string", "null"], "maxLength": 255},
    "position": {"type": "integer", "minimum": 0}, "is_default": {"type": "boolean"}}


def _compact(result):
    return {key: value for key, value in result.items() if key not in {
        "front_html", "back_html", "shared_css", "template"}}


def _analyze(payload, current=None):
    if current is not None and not set(payload) & {"front_html", "back_html", "shared_css", "input_schema"}:
        return
    candidate = {**(current or {}), **payload}
    fields = [SimpleNamespace(name=item["key"], field_type=item.get("type", "text"))
        for item in candidate.get("input_schema", [])]
    template = SimpleNamespace(**{key: candidate.get(key, "") for key in ("front_html", "back_html", "shared_css")})
    errors = [item for item in analyze_template_sources(template=template, field_defs=fields) if item["severity"] == "error"]
    if errors:
        raise TemplateAuthoringValidationError("Template source is invalid.", diagnostics=errors,
            field="template", status=400, code="TEMPLATE_SYNTAX_ERROR")


def _guard_note_type(user_id, note_type_id):
    # Match the existing MCP NoteType path: the new template tools must not
    # provide a second way around its published shared-schema guard.
    note_type = library._note_type(user_id, note_type_id)
    flashcard_content_service._ensure_version_safe_template_mutation(
        note_type=note_type, owner_user_id=user_id)


def _call(operation, user_id, arguments):
    args = dict(arguments)
    try:
        if operation == "list":
            args.setdefault("page", 1)
            return wrap_tool_result(library.list_templates(user_id=user_id, compact=True, **args))
        if operation == "get":
            include_source = args.pop("include_source", False)
            result = library.get_template(user_id=user_id, **args)
            return wrap_tool_result(result if include_source else _compact(result))
        if operation == "create":
            _analyze(args)
            result = library.create_template(user_id=user_id, payload=args)
        elif operation == "update":
            template_id = args.pop("template_id")
            current = library.get_template(user_id=user_id, template_id=template_id)
            for note_type_id in sorted({item["note_type_id"] for item in current.get("applications", [])}):
                _guard_note_type(user_id, note_type_id)
            _analyze(args, current)
            result = library.update_template(user_id=user_id, template_id=template_id, payload=args)
        elif operation == "attach":
            note_type_id = args.pop("note_type_id")
            _guard_note_type(user_id, note_type_id)
            result = library.attach_template(user_id=user_id, note_type_id=note_type_id, payload=args)
        elif operation == "application":
            note_type_id, application_id = args.pop("note_type_id"), args.pop("application_id")
            _guard_note_type(user_id, note_type_id)
            result = library.update_application(user_id=user_id, note_type_id=note_type_id,
                application_id=application_id, payload=args)
        return wrap_tool_result(_compact(result))
    except (TemplateLibraryError, TemplateVersionError, ContentApiError) as exc:
        code = exc.error if isinstance(exc, ContentApiError) else exc.code
        raise RequestValidationError(str(exc), field=exc.field, status=exc.status, code=code) from exc


def build_template_tools(definition):
    def tool(name, title, description, operation, properties, required=(), write=False):
        schema = {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}
        def validate(arguments):
            return validate_template_inputs(validate_object(arguments, schema))
        def handle(*, user_id, arguments):
            return _call(operation, user_id, arguments)
        return definition(name=name, title=title, description=description, input_schema=schema,
            handler=handle, arguments_validator=validate, required_scope="note-type:write" if write else "note-type:read",
            annotations={"readOnlyHint": not write, "destructiveHint": False}, error_handler=wrap_authoring_error)
    return (
        tool("list_card_templates", "List Card Templates",
            "List your reusable card templates with input schemas, usage and pagination, without HTML/CSS. Use get_card_template(include_source=true) to edit source.",
            "list", {"search": {"type": "string"}, "group": {"enum": ["all", "mine", "market", "standalone", "in_use"]},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "page_size": {"type": "integer", "minimum": 1, "default": 24}}),
        tool("get_card_template", "Get Card Template",
            "Read an owned reusable template, its declared inputs, current_version_id and applications. Source is opt-in. IDs do not grant access.",
            "get", {"template_id": NAME, "include_source": {"type": "boolean", "default": False}}, ("template_id",)),
        tool("create_card_template", "Create Card Template",
            "Create a personal reusable card template with typed input_schema and HTML/CSS. Preview the raw candidate first. Attach it with attach_card_template to generate study presentations.",
            "create", CONTENT, ("name",), True),
        tool("update_card_template", "Update Card Template",
            "Rename or edit an owned reusable template and its typed inputs through the versioned library. Pass expected_current_version_id from get_card_template to reject stale edits. Content edits affect active applications; preview first.",
            "update", {**CONTENT, "template_id": NAME, "expected_current_version_id": {"type": ["string", "null"]}}, ("template_id",), True),
        tool("attach_card_template", "Attach Card Template",
            "Attach an owned reusable template to an owned NoteType. Supply input_bindings from input keys to that NoteType's field IDs, optional display_name, position and is_default. Returns application_id for preview and later binding edits.",
            "attach", {**APPLICATION, "note_type_id": NAME, "template_id": NAME}, ("note_type_id", "template_id", "input_bindings"), True),
        tool("update_template_application", "Update Template Application",
            "Edit one owned template occurrence's input_bindings, display_name, position or default status without changing its reusable definition. Preview using note_type_id + application_id afterwards.",
            "application", {**APPLICATION, "note_type_id": NAME, "application_id": NAME}, ("note_type_id", "application_id"), True),
    )
