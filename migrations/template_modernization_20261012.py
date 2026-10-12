"""Frozen helpers for deployed revision 20261012_000057.

Exact transformations captured from release e077d275; no live app/model imports.
Historical version rows are rewritten by that deployed migration. This helper
preserves its behavior rather than introducing a new migration policy.
"""
from __future__ import annotations
import hashlib as _hashlib
import json as _json
import re as _re
import re
from typing import Any
_TAG_RE = _re.compile(r"\{\{\{(?P<triple>.*?)\}\}\}|\{\{(?P<body>.*?)\}\}", _re.DOTALL)
ARRAY_INPUT_TYPE = "array"
INPUT_TYPES = {"text", "richtext", "markdown", "image", "audio", "diagram", "array"}


class TemplateTokenError(ValueError):
    """Raised when an unsupported template token or construct is encountered."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

def _scan_tags(source: str):
    """Yield (name, start, end) for variable tokens in source.

    Raises TemplateTokenError on unsupported constructs (e.g. delimiter change).
    """
    for m in _TAG_RE.finditer(source):
        triple = m.group("triple")
        if triple is not None:
            name = triple.strip()
            if not name or name == ".":
                continue
            leading = len(triple) - len(triple.lstrip())
            start = m.start("triple") + leading
            end = start + len(name)
            yield name, start, end
            continue

        body = m.group("body")
        if body is not None:
            body_l = body.lstrip()
            if not body_l:
                continue
            sigil = body_l[0]
            if sigil in ("!", ">"):
                continue
            if sigil == "=":
                raise TemplateTokenError(
                    "DELIMITER_CHANGE_UNSUPPORTED",
                    "Delimiter change tags are not supported.",
                )
            if sigil in ("#", "^", "/", "&"):
                after_sigil = body_l[1:]
                name = after_sigil.strip()
                if not name or name == ".":
                    continue
                leading_in_after = len(after_sigil) - len(after_sigil.lstrip())
                leading_body = len(body) - len(body_l)
                start = m.start("body") + leading_body + 1 + leading_in_after
                end = start + len(name)
                yield name, start, end
            else:
                name = body.strip()
                if not name or name == ".":
                    continue
                leading_body = len(body) - len(body_l)
                start = m.start("body") + leading_body
                end = start + len(name)
                yield name, start, end

def extract_variable_names(source: str | None) -> list[str]:
    """Extract unique variable names in order of first appearance.

    Returns empty list if source is None or empty.
    Raises TemplateTokenError if delimiter change tags are present.
    """
    if not source:
        return []

    names: list[str] = []
    seen: set[str] = set()
    for name, _, _ in _scan_tags(source):
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names

def template_content_hash(
    front_html: str | None,
    back_html: str | None,
    shared_css: str | None,
) -> str:
    """Deterministic SHA-256 digest of normalized template content JSON."""
    payload = {
        "front_html": front_html or "",
        "back_html": back_html or "",
        "shared_css": shared_css or "",
    }
    encoded = _json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return _hashlib.sha256(encoded).hexdigest()

class TemplateLibraryError(ValueError):
    def __init__(self, code, message, *, status=400, field=None, details=None):
        super().__init__(message)
        self.code, self.status, self.field, self.details = code, status, field, details

def text(value, *, field, maximum=None, required=False):
    if not isinstance(value, str) or (required and not value.strip()) or (maximum and len(value) > maximum):
        raise TemplateLibraryError("VALIDATION_ERROR", f"Invalid {field}.", field=field)
    return value.strip() if required else value

def validate_input_schema(schema):
    if not isinstance(schema, list):
        raise TemplateLibraryError("VALIDATION_ERROR", "input_schema must be an array.", field="input_schema")
    result, keys = [], set()
    for item in schema:
        if not isinstance(item, dict) or set(item) - {"key", "label", "type", "required", "typing"}:
            raise TemplateLibraryError("VALIDATION_ERROR", "Invalid input definition.", field="input_schema")
        key = item.get("key")
        if not isinstance(key, str) or not key.strip() or key != key.strip() or any(c in key for c in "{}#^/!>&=\n\r") or key in {".", "FrontSide"} or key in keys:
            raise TemplateLibraryError("VALIDATION_ERROR", "Input keys must be unique valid template variables.", field="input_schema")
        kind = item.get("type", "text")
        if kind not in INPUT_TYPES or not isinstance(item.get("required", False), bool):
            raise TemplateLibraryError("VALIDATION_ERROR", "Invalid input type or recommendation.", field="input_schema")
        # Parked 2026-10-10 with the host typing mode (STUDY_TYPING_ANSWER_PLAN §12):
        # templates build and check their own answer boxes in HTML/JS, so any
        # number of array inputs is fine and typing options are not stored.
        # A "typing" key saved before is still accepted and dropped.
        # if kind == ARRAY_INPUT_TYPE and any(other["type"] == ARRAY_INPUT_TYPE for other in result):
        #     raise TemplateLibraryError("VALIDATION_ERROR", "A template can declare only one array input.", field="input_schema")
        label = text(item.get("label", key), field="input_schema.label", maximum=255)
        normalized = {"key": key, "label": label, "type": kind, "required": item.get("required", False)}
        # typing = _typing_options(item, kind)
        # if typing is not None:
        #     normalized["typing"] = typing
        result.append(normalized)
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
        field_type = getattr(field, "field_type", "text")
        # An inferred input for an array field stays text: only an explicitly
        # declared array input would drive the (parked) host typing mode.
        if field_type == ARRAY_INPUT_TYPE:
            field_type = "text"
        result.append({"key": key, "label": key, "type": field_type, "required": False})
    return validate_input_schema(result)

def _upgrade_html_field_double_brace_tokens(
    source_html: str,
    field_defs: list[Any],
) -> str:
    upgraded = source_html or ""
    for field_def in field_defs:
        if field_def.field_type not in {"image", "audio", "diagram", "richtext", "markdown"}:
            continue
        name = re.escape(field_def.name)
        # Upgrade HTML-producing fields from {{Field}} to {{{Field}}}.
        token_re = re.compile(rf"(?<!{{){{{{\s*{name}\s*}}}}(?!}})")
        upgraded = token_re.sub(f"{{{{{{{field_def.name}}}}}}}", upgraded)
    return upgraded

def _rewrite_media_url_attribute_tokens(source_html: str, field_defs: list[Any]) -> str:
    """Compile legacy ``src={{Media}}`` usage to the explicit URL helper."""
    rewritten = source_html or ""
    for field_def in field_defs:
        if str(getattr(field_def, "field_type", "") or "").lower() not in {"image", "audio", "diagram"}:
            continue
        field_name = str(getattr(field_def, "name", "") or "")
        if not field_name:
            continue
        token = re.compile(
            rf"(?P<prefix>\b(?:src|href|poster)\s*=\s*['\"]\s*)"
            rf"\{{\{{\{{?\s*{re.escape(field_name)}\s*\}}\}}\}}?"
            rf"(?P<suffix>\s*['\"])",
            flags=re.IGNORECASE,
        )
        rewritten = token.sub(
            lambda match: f"{match.group('prefix')}{{{{{field_name}_url}}}}{match.group('suffix')}",
            rewritten,
        )
    return rewritten
