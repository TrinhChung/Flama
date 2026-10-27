"""Read-only preview adapter. It never constructs persistent model instances."""

from types import SimpleNamespace

from app.repositories import template_library_repository
from app.services.common.mcp_response import wrap_tool_result
from app.services.mcp.base import _owned_note_type_for_mutation
from app.services.template_authoring_service import build_candidate_preview, diagnostic, sample_diagnostics
from app.services.template_binding_service import binding_warnings
from app.validators import RequestValidationError
from models import db


def preview_note_type_template(*, user_id, arguments):
    values = arguments["sample_values"]
    diagnostics = []
    source = {"kind": "provided"}
    with db.session.no_autoflush:
        if arguments.get("note_type_id"):
            # Only direct owned applications are supported by this v1 target.
            # A marketplace install must not silently resolve the author's draft.
            nt = _owned_note_type_for_mutation(user_id=user_id, note_type_id=arguments["note_type_id"])
            application = next((row for row in template_library_repository.applications(db.session, nt.id)
                if str(row.id) == arguments["application_id"]), None)
            if application is None:
                raise RequestValidationError("Application does not belong to this owned NoteType.",
                    field="application_id", status=404, code="APPLICATION_NOT_FOUND")
            current = application.template
            fields = list(nt.field_defs)
            template = SimpleNamespace(id=str(current.id), updated_at="candidate",
                front_html=arguments.get("front_html", current.front_html or ""),
                back_html=arguments.get("back_html", current.back_html or ""),
                shared_css=arguments.get("shared_css", current.shared_css or ""),
                input_schema=current.input_schema or [], input_bindings=application.input_bindings)
            for warning in binding_warnings(template, fields):
                diagnostics.append(diagnostic(warning["code"], f"Input {warning['input_key']} has no valid source field.",
                    stage="binding", source_part="input_bindings",
                    severity="error",
                    hint="Map this occurrence's input to an existing FieldDef ID before previewing."))
            fields_by_id = {str(field.id): field for field in fields}
            for item in template.input_schema:
                target = fields_by_id.get(str((template.input_bindings or {}).get(item["key"]) or ""))
                if target is not None and target.field_type != item.get("type", "text"):
                    diagnostics.append(diagnostic("INPUT_TYPE_ADVISORY_MISMATCH",
                        f"{item['key']} requests {item.get('type', 'text')}; its source field is {target.field_type}.",
                        stage="binding", source_part="input_bindings",
                        hint="Study uses the source field type; template input types are advisory."))
            # The caller already supplied the target; don't echo internal references.
            source["kind"] = "provided_for_application"
        else:
            fields = [SimpleNamespace(id=f"preview-{index}", name=item["key"], field_type=item["type"],
                required=item.get("required", False), position=index) for index, item in enumerate(arguments["input_schema"])]
            template = SimpleNamespace(id="candidate", updated_at="candidate",
                front_html=arguments["front_html"], back_html=arguments["back_html"],
                shared_css=arguments.get("shared_css", ""), input_schema=arguments["input_schema"],
                input_bindings={field.name: field.id for field in fields})
        diagnostics.extend(sample_diagnostics(fields, values))
        result = build_candidate_preview(template=template, field_defs=fields, field_values=values,
            initial_diagnostics=diagnostics, sample_source=source, profile=arguments.get("profile"))
    from app.services.mcp_resource_registry import media_base_url, template_preview_ui_available
    result["media_base_url"] = media_base_url()
    result["ui_available"] = template_preview_ui_available()
    result["preview_available"] = result["preview"] is not None
    artifacts = result["preview"]
    if not arguments.get("include_preview", False):
        result["preview"] = None
    if not arguments.get("include_server_render", False):
        result.pop("server_render", None)
    # A completed read-only evaluation can report invalid source as data.
    # isError makes some MCP connectors replace structuredContent with an exception.
    result["valid"] = not any(d["severity"] == "error" for d in result["diagnostics"])
    wrapped = wrap_tool_result(result)
    if artifacts is not None and result["ui_available"]:
        wrapped["_meta"] = {"flama/template-preview": {"candidate_hash": result["candidate_hash"], "preview": artifacts}}
    wrapped["content"] = [{"type": "text", "text": (
        f"Candidate {result['candidate_hash']}: "
        + ", ".join(f"{key}={value}" for key, value in result["checks"].items())
        + ". Appearance and behavior are for user review. "
        + " ".join(f"{d['severity']} {d['code']}: {d['message']} {d['hint']}" for d in result["diagnostics"])
    )}]
    return wrapped
