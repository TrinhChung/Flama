"""Small, repairable results for the template authoring workflow only."""

from app.services.common.mcp_response import wrap_tool_result
from app.services.template_authoring_service import diagnostic


def wrap_authoring_error(exc, *, preview=False):
    """Transport/authentication failures remain protocol errors, not validation."""
    if exc.status in (401, 403, 429, 503):
        raise exc
    diagnostics = getattr(exc, "diagnostics", None) or [diagnostic(
        exc.code or "INVALID_PARAMS", str(exc), severity="error", stage="input",
        source_part=exc.field or "arguments", hint="Correct the indicated input and call the tool again.")]
    checks = {key: "not_run" for key in (
        "input", "binding", "template", "javascript_syntax", "server_render", "study_browser", "interaction")}
    checks["input"] = "passed" if getattr(exc, "diagnostics", None) else "failed"
    for item in diagnostics:
        if item["severity"] == "error" and item["stage"] in checks:
            checks[item["stage"]] = "failed"
    if checks["javascript_syntax"] == "failed":
        checks["template"] = "failed"
    result = {"schema_version": "template-authoring-validation.v1", "checks": checks,
        "diagnostics": diagnostics[:100],
        "error": {"code": exc.code, "field": exc.field, "message": str(exc)}}
    if preview:
        from app.services.study_artifact_service import RENDERER_ABI
        from app.services.mcp_resource_registry import template_preview_ui_available
        result.update(schema_version="template-preview.v1", candidate_hash=None, renderer_abi=RENDERER_ABI,
            preview=None, preview_available=False, sample_source={"kind": "provided"}, media_base_url="",
            ui_available=template_preview_ui_available(), verification_note="Invalid input was not rendered or tested in a browser.")
    return wrap_tool_result(result, is_error=True)


def wrap_preview_error(exc):
    return wrap_authoring_error(exc, preview=True)


def wrap_schema_result(schema):
    # Full JSON used to appear twice in the same result (text and structured data).
    return {"structuredContent": schema, "content": [{"type": "text", "text": (
        f"{schema['name']}: {len(schema['fields'])} fields, {len(schema['templates'])} templates. "
        "Source is included only when include_templates=true is requested.")}]}


def wrap_impact_result(result):
    """Impact previews describe changes, without re-sending submitted source."""
    changes = dict(result["changes"])
    for key in ("added_templates", "updated_templates"):
        changes[key] = [{name: value for name, value in template.items()
            if name not in {"front_html", "back_html", "shared_css"}} for template in changes[key]]
    result = dict(result, changes=changes)
    wrapped = wrap_tool_result(result, is_error=bool(result.get("validation_errors")))
    wrapped["content"] = [{"type": "text", "text": (
        f"{result['note_type_name']}: {result['affected_notes']} notes, {result['affected_cards']} cards affected. "
        + ", ".join(f"{key}={value}" for key, value in result["checks"].items()))}]
    return wrapped
