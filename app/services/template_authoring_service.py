"""Read-only candidate analysis and artifacts shared by web and MCP previews.

Compilation here is not a browser test. The artifacts are prepared by Study's
normal code and must still be rendered by its client and sandbox.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

from chevron.tokenizer import ChevronError, tokenize

from app.services.flashcard_renderer import (
    TemplateCompileError, prepare_client_template_source, render_template_pair,
)
from app.services.template_tokens import extract_variable_names, TemplateTokenError


def diagnostic(code, message, *, severity="warning", stage="template", source_part="front_html", hint=""):
    return dict(code=code, severity=severity, stage=stage, source_part=source_part,
                message=str(message)[:1000], hint=str(hint)[:1000])


def analyze_template_sources(*, template, field_defs) -> list[dict[str, Any]]:
    """Use existing token discovery and Chevron's parser, never a new compiler.

    Unknown variables and unsupported loop metadata are warnings for legacy
    compatibility. Broken sections and Handlebars helpers are definite errors.
    Script tokens are literal in Study, so their content is not parsed as HTML.
    """
    result = []
    known = {str(field.name) for field in field_defs}
    known |= {f"{name}{suffix}" for name in tuple(known) for suffix in ("_url", "_urls")}
    known.add("FrontSide")
    for part in ("front_html", "back_html"):
        source = str(getattr(template, part, "") or "")
        prepared = prepare_client_template_source(source, field_defs)
        try:
            names = extract_variable_names(prepared["source"])
            # Tokenization validates paired sections with the actual parser.
            list(tokenize(prepared["source"]))
        except (TemplateTokenError, ChevronError) as exc:
            result.append(diagnostic(getattr(exc, "code", "MUSTACHE_SYNTAX_ERROR"), str(exc),
                severity="error", source_part=part, hint="Use paired {{#name}}…{{/name}} sections."))
            continue
        for name in names:
            if (re.match(r"^(?:each|if|unless|with)\s", name)
                    or name.startswith("../") or (name == "else" and name not in known)):
                result.append(diagnostic("HANDLEBARS_UNSUPPORTED", f"Unsupported helper: {name}",
                    severity="error", source_part=part,
                    hint="Use Mustache {{#options}}{{.}}{{/options}}; compute positions in template JavaScript."))
            elif name.startswith("@"):
                result.append(diagnostic("LOOP_METADATA_UNSUPPORTED", f"{name} has no loop metadata value.",
                    source_part=part, hint="Iterate DOM options with index + 1; do not use @index."))
            elif name not in known and name.split(".", 1)[0] not in known:
                result.append(diagnostic("UNDECLARED_VARIABLE", f"No declared input named {name}.",
                    source_part=part, hint="Declare/map the input, or remove the token. Item methods such as index are not values."))
        if any("{{" in script for script in prepared["inline_scripts"]):
            result.append(diagnostic("SCRIPT_TOKENS_LITERAL", "Study does not interpolate Mustache inside template scripts.",
                source_part=part, hint="Read already-rendered DOM text or FlamaCard.getContext().fieldValues; never insert raw field data into JavaScript."))
        if "{{>" in prepared["source"] or "{{ >" in prepared["source"]:
            result.append(diagnostic("PARTIALS_UNSUPPORTED", "External Mustache partials are not available in Study.",
                severity="error", source_part=part, hint="Include the markup directly in front_html/back_html."))
    if "{{" in str(getattr(template, "shared_css", "") or ""):
        result.append(diagnostic("SHARED_CSS_NOT_INTERPOLATED", "shared_css is static and does not interpolate per-note Mustache values.",
            source_part="shared_css", hint="Use a template-authored inline <style> or classes derived from rendered DOM."))
    return sorted(result, key=lambda item: item["severity"] != "error")[:100]


def validate_quiz_samples(values):
    """Opt-in recipe contract; no special semantics imposed on generic arrays."""
    options, answers = values.get("options"), values.get("correct_answers")
    if not isinstance(options, list) or not options or any(not isinstance(v, str) or not v.strip() for v in options):
        return [diagnostic("QUIZ_OPTIONS_INVALID", "Quiz options must be a nonempty flat array of nonempty strings.",
            severity="error", stage="input", source_part="sample_values.options", hint="Supply an ordered list of option strings.")]
    if (not isinstance(answers, list) or not answers
            or any(not isinstance(v, str) or not re.fullmatch(r"[1-9][0-9]*", v) for v in answers)
            or len(set(answers)) != len(answers)
            or any(len(v) > len(str(len(options))) or int(v) > len(options) for v in answers)):
        return [diagnostic("QUIZ_ANSWERS_INVALID", "correct_answers must contain unique 1-based string positions within options.",
            severity="error", stage="input", source_part="sample_values.correct_answers", hint='For example ["1", "3"]. Reordering options requires updating these positions.')]
    return []


def sample_diagnostics(field_defs, values):
    result = []
    names = {field.name for field in field_defs}
    for name in set(values) - names:
        result.append(diagnostic("UNKNOWN_SAMPLE_INPUT", f"No declared field named {name}.",
            severity="error", stage="input", source_part="sample_values",
            hint="Key samples by raw input name or by the attached source field name."))
    for field in field_defs:
        if getattr(field, "required", False) and (field.name not in values or values[field.name] in ("", [])):
            result.append(diagnostic("REQUIRED_SAMPLE_MISSING", f"Required sample {field.name} is missing or empty.",
                severity="error", stage="input", source_part="sample_values",
                hint="Provide an explicit value for this required field."))
        if field.name in values and field.field_type != "array" and isinstance(values[field.name], list):
            result.append(diagnostic("SAMPLE_TYPE_MISMATCH", f"{field.name} is {field.field_type}, but received an array.",
                severity="error", stage="input", source_part="sample_values", hint="Use text for this field type."))
    return result


def preview_candidate(*, input_schema, front_html, back_html, sample_values, shared_css="", profile="generic"):
    """Pure raw-candidate entry point for MCP and the browser fixture generator."""
    from app.validators.mcp_template_preview import validate_template_preview_arguments
    args = validate_template_preview_arguments(dict(input_schema=input_schema, front_html=front_html,
        back_html=back_html, shared_css=shared_css, sample_values=sample_values, profile=profile))
    fields = [SimpleNamespace(id=f"preview-{index}", name=item["key"], field_type=item["type"],
        required=item.get("required", False), position=index) for index, item in enumerate(args["input_schema"])]
    template = SimpleNamespace(id="candidate", updated_at="candidate", front_html=args["front_html"],
        back_html=args["back_html"], shared_css=args["shared_css"], input_schema=args["input_schema"],
        input_bindings={field.name: field.id for field in fields})
    return build_candidate_preview(template=template, field_defs=fields, field_values=args["sample_values"],
        initial_diagnostics=sample_diagnostics(fields, args["sample_values"]), profile=profile)


def candidate_artifacts(*, template, field_defs, field_values, media_assets=None):
    """Prepare an ephemeral effective card through the same functions as Study."""
    from app.services.study_artifact_service import (
        EffectiveStudyCard, build_content_artifact, build_template_artifact,
    )
    note = SimpleNamespace(id="preview-sample", media_assets=media_assets or [])
    context = EffectiveStudyCard(card=None, note=note, template=template,
        field_defs=field_defs, field_values=field_values)
    return dict(template_artifact=build_template_artifact(context),
                content_artifact=build_content_artifact(context))


def build_candidate_preview(*, template, field_defs, field_values, media_assets=None,
                            initial_diagnostics=None, sample_source=None, profile=None):
    from app.services.study_artifact_service import RENDERER_ABI, canonical_digest, serialize_field_defs
    from app.services.template_binding_service import prepare_bound_fields
    field_defs, field_values = prepare_bound_fields(template, field_defs, field_values)
    diagnostics = list(initial_diagnostics or [])
    diagnostics.extend(analyze_template_sources(template=template, field_defs=field_defs))
    if profile == "quiz":
        diagnostics.extend(validate_quiz_samples(field_values))
    candidate_hash = canonical_digest(dict(
        front_html=template.front_html, back_html=template.back_html, shared_css=template.shared_css,
        fields=serialize_field_defs(field_defs), sample_values=field_values,
        input_schema=getattr(template, "input_schema", []),
        input_bindings=getattr(template, "input_bindings", {}), renderer_abi=RENDERER_ABI,
    ))
    checks = {stage: ("failed" if any(d["severity"] == "error" and d["stage"] == stage for d in diagnostics)
                       else "passed") for stage in ("input", "binding", "template")}
    checks.update(server_render="not_run", study_browser="not_run", interaction="not_run")
    preview = None
    server_render = None
    if "failed" not in checks.values():
        try:
            preview = candidate_artifacts(template=template, field_defs=field_defs,
                field_values=field_values, media_assets=media_assets)
            server_render = render_template_pair(template=template, field_defs=field_defs,
                field_values=field_values, media_assets=media_assets or [])
            checks["server_render"] = "passed"
        except (TemplateCompileError, ValueError) as exc:
            diagnostics.append(diagnostic("TEMPLATE_COMPILE_ERROR", str(exc), severity="error",
                stage="server_render", hint="Fix the reported Mustache source and preview again."))
            checks["server_render"] = "failed"
            preview = None
    return dict(schema_version="template-preview.v1", candidate_hash=candidate_hash,
        renderer_abi=RENDERER_ABI, checks=checks,
        diagnostics=sorted(diagnostics, key=lambda item: item["severity"] != "error")[:100],
        preview=preview, server_render=server_render,
        sample_source=sample_source or {"kind": "provided"},
        verification_note="Browser and interaction checks have not run. Server HTML is diagnostic evidence only.")
