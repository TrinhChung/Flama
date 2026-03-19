"""Template rendering and security helpers for flashcard v2."""

from __future__ import annotations

import hashlib
import html
import logging
import re
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

import bleach
import chevron
from bleach.css_sanitizer import CSSSanitizer
try:
    from markdown_it import MarkdownIt
except Exception:  # pragma: no cover - optional dependency fallback
    MarkdownIt = None  # type: ignore[assignment]
try:
    import mistune
except Exception:  # pragma: no cover - optional dependency fallback
    mistune = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

ALLOWED_HTML_TAGS = [
    "div",
    "span",
    "p",
    "br",
    "hr",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "mark",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "img",
    "audio",
    "video",
    "source",
    "button",
    "ruby",
    "rt",
    "rp",
    "a",
    "style",
]

ALLOWED_CSS_PROPERTIES = [
    "color",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "text-align",
    "text-transform",
    "line-height",
    "margin",
    "margin-left",
    "margin-right",
    "margin-top",
    "margin-bottom",
    "padding",
    "padding-left",
    "padding-right",
    "padding-top",
    "padding-bottom",
    "background-color",
    "display",
    "flex-direction",
    "justify-content",
    "align-items",
    "flex-wrap",
    "flex",
    "gap",
    "height",
    "width",
    "max-width",
    "max-height",
    "min-height",
    "min-width",
    "border",
    "border-radius",
    "object-fit",
]

_css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
_markdown_parser = None
if MarkdownIt is not None:
    _markdown_parser = MarkdownIt(
        "commonmark",
        {
            "html": False,
            "linkify": False,
            "typographer": False,
        },
    )
elif mistune is not None:
    # Fallback renderer when markdown-it-py is missing in runtime env.
    _markdown_parser = mistune.create_markdown(escape=True)
_template_cache: OrderedDict[str, str] = OrderedDict()
_preview_cache: dict[str, tuple[datetime, dict[str, str]]] = {}
_cache_lock = threading.Lock()
_MAX_TEMPLATE_CACHE = 512
_PREVIEW_TTL = timedelta(seconds=30)
PREVIEW_MEDIA_IMAGE_TOKEN = "__fc_preview_image__"
PREVIEW_MEDIA_AUDIO_TOKEN = "__fc_preview_audio__"
PREVIEW_MEDIA_DIAGRAM_TOKEN = "__fc_preview_diagram__"
LINEBREAK_TOKEN = "__FC_LINEBREAK_TOKEN__"
_INLINE_SCRIPT_RE = re.compile(r"(?is)<script\b([^>]*)>(.*?)</script>")
_HTML_TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")
_SAFE_BUTTON_ONCLICK_RE = re.compile(
    r"""^\s*document\.getElementById\(\s*['"][A-Za-z0-9_-]+['"]\s*\)\.play\(\)\s*;?\s*$"""
)
_SCRIPT_TAG_RE = re.compile(r"(?is)^\s*<script\b([^>]*)>(.*?)</script>\s*$")
_SCRIPT_TYPE_ATTR_RE = re.compile(
    r"""\btype\s*=\s*("[^"]*"|'[^']*'|[^\s"'=<>`]+)""",
    flags=re.IGNORECASE,
)


class TemplateCompileError(ValueError):
    """Mustache template compile/parse error."""


def _allowed_attr(tag: str, name: str, value: str) -> bool:
    lowered = name.lower()
    if lowered.startswith("on"):
        if lowered == "onclick" and tag == "button":
            return bool(_SAFE_BUTTON_ONCLICK_RE.match((value or "").strip()))
        return False
    if lowered == "auto-split":
        return tag in {"div", "p", "span", "li", "td"}
    if lowered in {"class", "id", "style", "alt"}:
        return True
    if lowered == "controls":
        return tag in {"audio", "video"}
    if lowered == "autoplay":
        return tag == "audio"
    if lowered in {"src", "href"}:
        val = (value or "").strip()
        if val.startswith("/media/proxy/"):
            return True
        if lowered == "href" and val.startswith("https://"):
            return True
        return False
    return False


def _extract_inline_scripts(source_html: str) -> tuple[str, list[str]]:
    scripts: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        attrs = (match.group(1) or "").strip()
        body = match.group(2) or ""
        if re.search(r"\bsrc\s*=", attrs, flags=re.IGNORECASE):
            return ""
        # Keep only optional type attribute; strip everything else.
        type_match = _SCRIPT_TYPE_ATTR_RE.search(attrs)
        type_attr = f" type={type_match.group(1)}" if type_match else ""
        scripts.append(f"<script{type_attr}>{body}</script>")
        return ""

    cleaned = _INLINE_SCRIPT_RE.sub(_replace, source_html or "")
    return cleaned, scripts


def _upgrade_html_field_double_brace_tokens(
    source_html: str,
    field_defs: list[Any],
) -> str:
    upgraded = source_html or ""
    for field_def in field_defs:
        if field_def.field_type not in {"image", "diagram", "richtext", "markdown"}:
            continue
        name = re.escape(field_def.name)
        # Upgrade HTML-producing fields from {{Field}} to {{{Field}}}.
        token_re = re.compile(rf"(?<!{{){{{{\s*{name}\s*}}}}(?!}})")
        upgraded = token_re.sub(f"{{{{{{{field_def.name}}}}}}}", upgraded)
    return upgraded


def _media_field_used_as_url(field_name: str, template_sources: tuple[str, str] | None) -> bool:
    if not template_sources:
        return False
    pattern = re.compile(
        r"""(?is)\b(?:src|href)\s*=\s*["']\s*\{\{\s*"""
        + re.escape(field_name)
        + r"""\s*\}\}\s*["']""",
        flags=re.IGNORECASE,
    )
    return bool(pattern.search(template_sources[0] or "") or pattern.search(template_sources[1] or ""))


def _resolve_media_url(value: Any, media_lookup: dict[str, Any]) -> str:
    if is_field_empty(value):
        return ""
    raw = str(value).strip()
    sound_match = re.match(r"^\[sound:([^\]]+)\]$", raw)
    if sound_match:
        raw = sound_match.group(1).strip()
    asset = media_lookup.get(raw)
    if asset is not None:
        return f"/media/proxy/{asset.id}"
    if raw.startswith("/media/proxy/"):
        return raw
    return ""


def _normalize_multiline_value(value: Any) -> str:
    text = "" if value is None else str(value)
    # Normalize Windows/Mac newlines and preserve explicit line breaks from editors.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\\n", LINEBREAK_TOKEN)
    return normalized.replace("\n", LINEBREAK_TOKEN)


def _normalize_markdown_value(value: Any) -> str:
    text = "" if value is None else str(value)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\\n", "\n")


def _replace_linebreak_token_in_html_text_nodes(rendered_html: str) -> str:
    if LINEBREAK_TOKEN not in rendered_html:
        return rendered_html

    # Split into tag/text chunks, then only convert tokens in text chunks.
    chunks = _HTML_TAG_SPLIT_RE.split(rendered_html)
    for index, chunk in enumerate(chunks):
        if LINEBREAK_TOKEN not in chunk:
            continue
        if index % 2 == 0:
            chunks[index] = chunk.replace(LINEBREAK_TOKEN, "<br>")
        else:
            chunks[index] = chunk.replace(LINEBREAK_TOKEN, "\\n")
    return "".join(chunks)


def _strip_wrapped_attr_value(raw_value: str) -> str:
    token = (raw_value or "").strip()
    if len(token) >= 2 and (
        (token.startswith('"') and token.endswith('"'))
        or (token.startswith("'") and token.endswith("'"))
    ):
        return token[1:-1]
    return token


def _defer_inline_script_block(script_block: str) -> str:
    match = _SCRIPT_TAG_RE.match(script_block or "")
    if not match:
        return (
            '<script type="application/x-flama-note-script" '
            f'data-flama-inline-script="1">{script_block or ""}</script>'
        )

    attrs = match.group(1) or ""
    body = match.group(2) or ""
    type_match = _SCRIPT_TYPE_ATTR_RE.search(attrs)
    declared_type = (
        _strip_wrapped_attr_value(type_match.group(1))
        if type_match is not None
        else ""
    )
    declared_attr = ""
    if declared_type:
        escaped_type = html.escape(declared_type, quote=True)
        declared_attr = f' data-flama-script-type="{escaped_type}"'

    return (
        '<script type="application/x-flama-note-script" '
        f'data-flama-inline-script="1"{declared_attr}>{body}</script>'
    )


def _restore_linebreak_token(raw_text: str) -> str:
    if LINEBREAK_TOKEN not in raw_text:
        return raw_text
    return raw_text.replace(LINEBREAK_TOKEN, "\\n")


def sanitize_css(css: str | None) -> str:
    if not css:
        return ""
    # Remove CSS imports/functions that can trigger external fetches.
    cleaned = re.sub(r"@import[^;]+;?", "", css, flags=re.IGNORECASE)
    cleaned = re.sub(r"url\s*\(", "blocked-url(", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"expression\s*\(", "blocked-expression(", cleaned, flags=re.IGNORECASE)
    return cleaned


def sanitize_html_fragment(raw_html: str | None) -> str:
    return bleach.clean(
        raw_html or "",
        tags=ALLOWED_HTML_TAGS,
        attributes=_allowed_attr,
        strip=True,
        css_sanitizer=_css_sanitizer,
    )


def sanitize_richtext(raw_html: str | None) -> str:
    return sanitize_html_fragment(raw_html)


def _fallback_markdown_inline_to_html(text: str) -> str:
    placeholders: list[str] = []
    html_text = html.escape(text or "")

    def _store(fragment: str) -> str:
        token = f"%%FCMD{len(placeholders)}%%"
        placeholders.append(fragment)
        return token

    html_text = re.sub(
        r"`([^`\n]+)`",
        lambda match: _store(f"<code>{html.escape(match.group(1))}</code>"),
        html_text,
    )
    html_text = re.sub(
        r"!\[([^\]]*)\]\(([^)\s]+)\)",
        lambda match: _store(
            f'<img src="{html.escape(match.group(2), quote=True)}" '
            f'alt="{html.escape((match.group(1) or "image").strip() or "image", quote=True)}">'
        ),
        html_text,
    )
    html_text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda match: _store(
            f'<a href="{html.escape(match.group(2), quote=True)}" target="_blank" rel="noopener noreferrer">'
            f"{html.escape(match.group(1))}</a>"
        ),
        html_text,
    )
    html_text = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", html_text)
    html_text = re.sub(r"__([^_\n]+)__", r"<strong>\1</strong>", html_text)
    html_text = re.sub(r"~~([^~\n]+)~~", r"<s>\1</s>", html_text)
    html_text = re.sub(r"(^|[^\*])\*([^*\n]+)\*(?!\*)", r"\1<em>\2</em>", html_text)
    html_text = re.sub(r"(^|[^_])_([^_\n]+)_(?!_)", r"\1<em>\2</em>", html_text)

    for index, fragment in enumerate(placeholders):
        html_text = html_text.replace(f"%%FCMD{index}%%", fragment)
    return html_text


def _fallback_render_markdown_to_html(source: str) -> str:
    lines = source.split("\n")
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            blocks.append(f"<h{level}>{_fallback_markdown_inline_to_html(heading_match.group(2))}</h{level}>")
            index += 1
            continue

        if re.match(r"^>\s?", line):
            quote_lines: list[str] = []
            while index < len(lines) and re.match(r"^>\s?", lines[index]):
                quote_lines.append(re.sub(r"^>\s?", "", lines[index]))
                index += 1
            quote_html = "<br>".join(_fallback_markdown_inline_to_html(item) for item in quote_lines)
            blocks.append(f"<blockquote><p>{quote_html}</p></blockquote>")
            continue

        if re.match(r"^[-*+]\s+", line):
            items: list[str] = []
            while index < len(lines):
                item_match = re.match(r"^[-*+]\s+(.*)$", lines[index])
                if not item_match:
                    break
                items.append(f"<li>{_fallback_markdown_inline_to_html(item_match.group(1))}</li>")
                index += 1
            blocks.append(f"<ul>{''.join(items)}</ul>")
            continue

        if re.match(r"^\d+\.\s+", line):
            items = []
            while index < len(lines):
                item_match = re.match(r"^\d+\.\s+(.*)$", lines[index])
                if not item_match:
                    break
                items.append(f"<li>{_fallback_markdown_inline_to_html(item_match.group(1))}</li>")
                index += 1
            blocks.append(f"<ol>{''.join(items)}</ol>")
            continue

        paragraph_lines = [line]
        index += 1
        while index < len(lines):
            current = lines[index]
            if not current.strip():
                index += 1
                break
            if re.match(r"^(#{1,3})\s+", current) or re.match(r"^>\s?", current) or re.match(r"^[-*+]\s+", current) or re.match(r"^\d+\.\s+", current) or current.strip().startswith("```"):
                break
            paragraph_lines.append(current)
            index += 1
        paragraph_html = "<br>".join(_fallback_markdown_inline_to_html(item) for item in paragraph_lines)
        blocks.append(f"<p>{paragraph_html}</p>")

    return "".join(blocks)


def render_markdown_to_safe_html(raw_markdown: str | None) -> str:
    source = _normalize_markdown_value(raw_markdown)
    if not source.strip():
        return ""
    if _markdown_parser is None:
        return sanitize_html_fragment(_fallback_render_markdown_to_html(source))
    try:
        if hasattr(_markdown_parser, "render"):
            rendered = _markdown_parser.render(source)
        else:
            rendered = _markdown_parser(source)
    except Exception:
        logger.exception("Failed to render markdown; falling back to plain text.")
        return sanitize_html_fragment(_fallback_render_markdown_to_html(source))
    return sanitize_html_fragment(rendered)


def is_field_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _cache_template(cache_key: str, source: str) -> str:
    with _cache_lock:
        existing = _template_cache.get(cache_key)
        if existing is not None:
            _template_cache.move_to_end(cache_key)
            return existing
    try:
        # Render once with empty data to validate Mustache syntax.
        chevron.render(source, {})
    except Exception as exc:  # pragma: no cover - defensive
        raise TemplateCompileError(str(exc)) from exc
    with _cache_lock:
        _template_cache[cache_key] = source
        _template_cache.move_to_end(cache_key)
        while len(_template_cache) > _MAX_TEMPLATE_CACHE:
            _template_cache.popitem(last=False)
    return source


def _render_media_html(field_type: str, value: Any, field_name: str, media_lookup: dict[str, Any]) -> str:
    if is_field_empty(value):
        return ""
    raw = str(value).strip()

    if raw == PREVIEW_MEDIA_IMAGE_TOKEN:
        return (
            f"<div class=\"fc-preview-media-box\" style=\"background-color:#f3f4f6;padding:12px;text-align:center;\">"
            f"[Image: {html.escape(field_name)}]"
            "</div>"
        )
    if raw == PREVIEW_MEDIA_AUDIO_TOKEN:
        return (
            f"<div class=\"fc-preview-media-box\" style=\"background-color:#f3f4f6;padding:12px;text-align:center;\">"
            f"[Audio: {html.escape(field_name)}]"
            "</div>"
        )
    if raw == PREVIEW_MEDIA_DIAGRAM_TOKEN:
        return (
            f"<div class=\"fc-preview-media-box\" style=\"background-color:#f3f4f6;padding:12px;text-align:center;\">"
            f"[Diagram: {html.escape(field_name)}]"
            "</div>"
        )

    # Backward compatibility for legacy HTML snippets in diagram/image fields.
    if field_type in {"image", "diagram"} and raw.startswith("<"):
        return sanitize_html_fragment(raw)

    media_url = _resolve_media_url(raw, media_lookup)

    if not media_url:
        return ""

    escaped_alt = html.escape(field_name, quote=True)
    if field_type == "audio":
        return f"<audio controls src=\"{media_url}\"></audio>"
    return f"<img src=\"{media_url}\" alt=\"{escaped_alt}\">"


def build_render_context(
    field_defs: list[Any],
    field_values: dict[str, Any] | None,
    media_assets: list[Any] | None,
    *,
    template_sources: tuple[str, str] | None = None,
) -> dict[str, Any]:
    values = field_values or {}
    media_lookup: dict[str, Any] = {}
    for asset in media_assets or []:
        asset_id = str(getattr(asset, "id", "") or "").strip()
        if asset_id:
            media_lookup[asset_id] = asset
            media_lookup[f"/media/proxy/{asset_id}"] = asset
        filename = str(getattr(asset, "filename", "") or "").strip()
        if filename:
            media_lookup.setdefault(filename, asset)
            media_lookup.setdefault(f"[sound:{filename}]", asset)
    context: dict[str, Any] = {}

    for field_def in field_defs:
        name = field_def.name
        value = values.get(name)
        if field_def.field_type == "richtext":
            context[name] = sanitize_richtext(_normalize_multiline_value(value))
            continue
        if field_def.field_type == "markdown":
            context[name] = render_markdown_to_safe_html(value)
            continue
        if field_def.field_type in {"image", "audio", "diagram"}:
            media_html = _render_media_html(field_def.field_type, value, name, media_lookup)
            media_url = _resolve_media_url(value, media_lookup)
            if field_def.field_type == "audio" and _media_field_used_as_url(name, template_sources):
                context[name] = media_url
            else:
                context[name] = media_html
            context[f"{name}_url"] = media_url
            continue
        context[name] = _normalize_multiline_value(value)

    # Keep unknown keys for legacy compatibility.
    for key, value in values.items():
        if key not in context:
            context[key] = _normalize_multiline_value(value)

    # Common alias for compatibility with older templates.
    if "hanviet" in context and "han_viet" not in context:
        context["han_viet"] = context["hanviet"]

    return context


def render_template_pair(
    *,
    template: Any,
    field_defs: list[Any],
    field_values: dict[str, Any] | None,
    media_assets: list[Any] | None = None,
    preview_note_key: str | None = None,
    allow_inline_script: bool = False,
    defer_inline_script: bool = False,
) -> dict[str, str]:
    css = sanitize_css(getattr(template, "shared_css", ""))
    if allow_inline_script and defer_inline_script:
        inline_script_mode = "inline-on-deferred"
    else:
        inline_script_mode = "inline-on" if allow_inline_script else "inline-off"
    preview_key = None
    if preview_note_key:
        preview_hash = hashlib.sha256(
            (
                getattr(template, "front_html", "")
                + getattr(template, "back_html", "")
                + css
                + preview_note_key
                + inline_script_mode
            ).encode("utf-8")
        ).hexdigest()
        preview_key = preview_hash
        cached = _preview_cache.get(preview_hash)
        if cached and datetime.utcnow() - cached[0] <= _PREVIEW_TTL:
            return cached[1]

    template_updated = str(getattr(template, "updated_at", ""))
    front_source_raw = getattr(template, "front_html", "")
    back_source_raw = getattr(template, "back_html", "")
    front_source_prepared = _upgrade_html_field_double_brace_tokens(front_source_raw, field_defs)
    back_source_prepared = _upgrade_html_field_double_brace_tokens(back_source_raw, field_defs)
    # Always strip inline <script> blocks before bleach cleaning.
    # When allow_inline_script=True we re-attach sanitized script blocks after rendering.
    front_source_prepared, front_script_sources = _extract_inline_scripts(front_source_prepared)
    back_source_prepared, back_script_sources = _extract_inline_scripts(back_source_prepared)
    if not allow_inline_script:
        front_script_sources = []
        back_script_sources = []

    context = build_render_context(
        field_defs,
        field_values,
        media_assets,
        template_sources=(front_source_raw, back_source_raw),
    )
    front_hash = hashlib.sha256(front_source_prepared.encode("utf-8")).hexdigest()[:16]
    back_hash = hashlib.sha256(back_source_prepared.encode("utf-8")).hexdigest()[:16]
    front_key = f"{template.id}:{template_updated}:front:{front_hash}"
    back_key = f"{template.id}:{template_updated}:back:{back_hash}"
    front_source = _cache_template(front_key, front_source_prepared)
    back_source = _cache_template(back_key, back_source_prepared)

    try:
        front_rendered = chevron.render(front_source, context)
        back_rendered = chevron.render(back_source, context)
        front_scripts = [_restore_linebreak_token(chevron.render(script_source, context)) for script_source in front_script_sources]
        back_scripts = [_restore_linebreak_token(chevron.render(script_source, context)) for script_source in back_script_sources]
    except Exception as exc:
        raise TemplateCompileError(str(exc)) from exc

    front_rendered = _replace_linebreak_token_in_html_text_nodes(front_rendered)
    back_rendered = _replace_linebreak_token_in_html_text_nodes(back_rendered)
    safe_front = sanitize_html_fragment(front_rendered)
    safe_back = sanitize_html_fragment(back_rendered)
    if allow_inline_script:
        if defer_inline_script:
            safe_front = f"{safe_front}{''.join(_defer_inline_script_block(item) for item in front_scripts)}"
            safe_back = f"{safe_back}{''.join(_defer_inline_script_block(item) for item in back_scripts)}"
        else:
            safe_front = f"{safe_front}{''.join(front_scripts)}"
            safe_back = f"{safe_back}{''.join(back_scripts)}"
    scoped_front = f"<style>{css}</style>{safe_front}" if css else safe_front
    scoped_back = f"<style>{css}</style>{safe_back}" if css else safe_back
    result = {"front_html": scoped_front, "back_html": scoped_back}

    if preview_key:
        _preview_cache[preview_key] = (datetime.utcnow(), result)
    return result
