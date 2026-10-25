"""Template rendering and security helpers for flashcard v2."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Any

from flask import current_app, has_app_context

import bleach
import chevron
from bleach.css_sanitizer import CSSSanitizer
from app.services.media_field_codec import is_canonical_media_url, split_media_field_value
from app.services.template_binding_service import prepare_bound_fields
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
    "svg",
    "g",
    "path",
    "line",
    "circle",
    "rect",
    "ellipse",
    "polyline",
    "polygon",
    "text",
    "tspan",
]
# Template markup may also carry its own answer box, checked by the template's
# script (a typed answer is plain HTML/JS in the card). Scripts can create the
# same elements anyway, and the sandboxed iframe blocks form submission
# (form-action 'none') and network access. Field content keeps the list above.
TEMPLATE_HTML_TAGS = [*ALLOWED_HTML_TAGS, "input", "label"]

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
_preview_cache: OrderedDict[str, tuple[datetime, dict[str, Any]]] = OrderedDict()
_cache_lock = threading.Lock()
_MAX_TEMPLATE_CACHE = 512
_PREVIEW_TTL = timedelta(seconds=30)
PREVIEW_MEDIA_IMAGE_TOKEN = "__fc_preview_image__"
PREVIEW_MEDIA_AUDIO_TOKEN = "__fc_preview_audio__"
PREVIEW_MEDIA_DIAGRAM_TOKEN = "__fc_preview_diagram__"
LINEBREAK_TOKEN = "__FC_LINEBREAK_TOKEN__"
_INLINE_SCRIPT_RE = re.compile(r"(?is)<script\b([^>]*)>(.*?)</script>")
_HTML_TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")
_SCRIPT_TYPE_RE = re.compile(
    r"""(?is)\btype\s*=\s*(['"])(.*?)\1"""
)
_SCRIPT_SRC_RE = re.compile(r"""(?is)\bsrc\s*=""")
_PROXY_MEDIA_URL_RE = re.compile(r"^/media/proxy/([A-Za-z0-9][A-Za-z0-9_-]{0,127})$")
_LIBRARY_MEDIA_URL_RE = re.compile(r"^/media/library/([A-Za-z0-9][A-Za-z0-9_.-]{0,127})$")
_STATIC_STROKE_URL_RE = re.compile(r"^/static/strokes/([a-zA-Z0-9_-]+)/([a-fA-F0-9]+)\.svg$")
_SCRIPT_TOKEN_PREFIX = "__FC_INLINE_SCRIPT_BLOCK_"
# {{FrontSide}} on the back shows the rendered front, as in Anki; on the front it
# is empty. The token becomes a tag-like marker before Mustache runs, so escaped
# field text can never produce it, and the marker is then swapped for the front
# markup (without the front's scripts) before the back is sanitized. Keep in
# sync with FRONT_SIDE_TOKEN_RE in frontend clientRenderer.ts; "&amp;" covers a
# client source that went through bleach.
FRONT_SIDE_TOKEN_RE = re.compile(r"\{\{\{\s*FrontSide\s*\}\}\}|\{\{\s*(?:&amp;|&)?\s*FrontSide\s*\}\}")
_FRONT_SIDE_MARKER = "<flama-front-side></flama-front-side>"
_ALLOWED_INLINE_SCRIPT_TYPES = {
    "",
    "text/javascript",
    "application/javascript",
    "application/ecmascript",
    "text/ecmascript",
    "module",
}
_SAFE_BUTTON_ONCLICK_RE = re.compile(
    r"""^\s*document\.getElementById\(\s*['"][A-Za-z0-9_-]+['"]\s*\)\.play\(\)\s*;?\s*$"""
)

# ---------------------------------------------------------------------------
# Safe onclick validation – whitelist of common DOM manipulation patterns
# that are safe inside the sandboxed iframe (allow-scripts, no allow-same-origin).
# Patterns MUST stay synchronised with frontend isSafeOnclickValue()
# in clientRenderer.ts.
# ---------------------------------------------------------------------------
_SAFE_ID = r"[A-Za-z0-9_-]+"
_TARGET = rf"(?:document\.getElementById\(\s*['\"]{ _SAFE_ID }['\"]\s*\)|this)"

_SAFE_ONCLICK_PATTERNS = [
    re.compile(rf"^{_TARGET}\.(?:play|pause|load|click|focus|blur|remove)\(\)$"),
    re.compile(rf"^{_TARGET}\.style\.[a-zA-Z]+\s*=\s*'[^']{{0,50}}'$"),
    re.compile(rf"^{_TARGET}\.classList\.(?:add|remove|toggle)\(\s*'[A-Za-z0-9_-]+'\s*\)$"),
    re.compile(rf"^{_TARGET}\.hidden\s*=\s*(?:true|false)$"),
    re.compile(rf"^{_TARGET}\.textContent\s*=\s*'[^']{{0,100}}'$"),
]


def _is_safe_button_onclick(value: str) -> bool:
    """Return True if *value* is a safe onclick attribute for a <button>."""
    statements = [s.strip() for s in value.split(";") if s.strip()]
    if not statements or len(statements) > 10:
        return False
    return all(
        any(pat.match(stmt) for pat in _SAFE_ONCLICK_PATTERNS)
        for stmt in statements
    )


class TemplateCompileError(ValueError):
    """Mustache template compile/parse error."""


_CAPABILITY_ATTRS = {
    "src", "href", "poster", "action", "formaction", "background",
    "cite", "codebase", "manifest", "srcdoc",
}
_SAFE_INERT_ATTR_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_:-]*$")


def _strict_allowed_attr(tag: str, name: str, value: str) -> bool:
    lowered = name.lower()
    if lowered.startswith("on"):
        if lowered == "onclick" and tag == "button":
            return _is_safe_button_onclick((value or "").strip())
        return False
    if lowered in _CAPABILITY_ATTRS:
        if lowered in {"src", "href", "poster"}:
            val = (value or "").strip()
            if (
                _PROXY_MEDIA_URL_RE.match(val)
                or _LIBRARY_MEDIA_URL_RE.match(val)
                or _STATIC_STROKE_URL_RE.match(val)
            ):
                return True
            if lowered == "href" and val.startswith("https://"):
                return True
        return False
    if lowered == "controls":
        return tag in {"audio", "video"}
    if lowered == "autoplay":
        return tag == "audio"
    if lowered in {"width", "height"}:
        return tag in {"img", "video", "source", "audio", "table", "th", "td", "svg", "rect", "circle", "line"}
    if lowered in {"colspan", "rowspan"}:
        return tag in {"th", "td"}
    if _SAFE_INERT_ATTR_NAME_RE.match(lowered):
        return True
    return False


def _template_allowed_attr(tag: str, name: str, value: str) -> bool:
    lowered = name.lower()
    if lowered.startswith("on"):
        return True
    if lowered in _CAPABILITY_ATTRS:
        if lowered in {"src", "href", "poster"}:
            val = (value or "").strip()
            if is_canonical_media_url(val):
                return True
            if lowered == "href" and val.startswith("https://"):
                return True
            if lowered in {"src", "poster"} and is_canonical_media_url(val):
                return True
        return False
    if lowered in {"controls", "loop", "muted", "playsinline", "autoplay", "preload"}:
        return tag in {"audio", "video"}
    if lowered in {"width", "height"}:
        return tag in {"img", "video", "source", "audio", "table", "th", "td", "svg", "rect", "circle", "line"}
    if lowered in {"colspan", "rowspan"}:
        return tag in {"th", "td"}
    if _SAFE_INERT_ATTR_NAME_RE.match(lowered):
        return True
    return False


def _is_media_template_url_attr(
    tag: str,
    name: str,
    value: str,
    field_defs: list[Any],
    dot_media_field_types: set[str] | None = None,
) -> bool:
    """Allow whole-value Mustache URLs backed by declared media fields only.

    The placeholder is template-authored code, not a trusted URL. Its rendered
    value is validated again in the client against the note artifact media list.
    """
    lowered_name = str(name or "").lower()
    lowered_tag = str(tag or "").lower()
    if lowered_name not in {"src", "href"}:
        return False
    match = re.fullmatch(r"\s*\{\{\{?\s*([^{}]+?)\s*\}\}\}?\s*", str(value or ""))
    if not match:
        return False
    placeholder = match.group(1).strip()
    if placeholder == "." and dot_media_field_types:
        if lowered_name == "href":
            return lowered_tag == "a"
        if lowered_tag in {"audio", "source"} and "audio" in dot_media_field_types:
            return True
        if lowered_tag == "img" and dot_media_field_types.intersection({"image", "diagram"}):
            return True
    for field_def in field_defs:
        field_type = str(getattr(field_def, "field_type", "") or "").lower()
        if field_type not in {"audio", "image", "diagram"}:
            continue
        field_name = str(getattr(field_def, "name", "") or "")
        if placeholder not in {field_name, f"{field_name}_url"}:
            continue
        if lowered_name == "href":
            return lowered_tag == "a"
        if field_type == "audio":
            return lowered_tag in {"audio", "source"}
        return lowered_tag == "img"
    return False


def _extract_proxy_asset_id(media_url: str | None) -> str:
    if not media_url:
        return ""
    match = _PROXY_MEDIA_URL_RE.match(str(media_url).strip())
    return match.group(1) if match else ""


def _short_sha256(value: str | None) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]


def _renderer_shell_key(
    *,
    template: Any,
    side: str,
    side_source: str,
    css: str,
    field_defs: list[Any],
) -> str:
    field_defs_signature = "|".join(
        [
            ":".join(
                [
                    str(getattr(field_def, "name", "") or ""),
                    str(getattr(field_def, "field_type", "") or ""),
                    str(int(getattr(field_def, "position", 0) or 0)),
                    "1" if bool(getattr(field_def, "required", False)) else "0",
                ]
            )
            for field_def in field_defs
        ]
    )
    return ":".join(
        [
            "tpl",
            str(getattr(template, "id", "") or ""),
            str(getattr(template, "updated_at", "") or ""),
            str(side or ""),
            _short_sha256(css),
            _short_sha256(field_defs_signature),
            _short_sha256(side_source),
        ]
    )


def _sanitize_inline_script(attrs: str, body: str) -> str:
    raw_attrs = attrs or ""
    if _SCRIPT_SRC_RE.search(raw_attrs):
        return ""
    type_match = _SCRIPT_TYPE_RE.search(raw_attrs)
    script_type = ""
    if type_match:
        script_type = str(type_match.group(2) or "").strip().lower()
        if script_type not in _ALLOWED_INLINE_SCRIPT_TYPES:
            return ""
    if script_type:
        return f"<script type=\"{html.escape(script_type, quote=True)}\">{body or ''}</script>"
    return f"<script>{body or ''}</script>"


def _extract_inline_scripts(source_html: str) -> tuple[str, list[tuple[str, str]]]:
    scripts: list[tuple[str, str]] = []

    def _replace(match: re.Match[str]) -> str:
        safe_script = _sanitize_inline_script(match.group(1) or "", match.group(2) or "")
        if not safe_script:
            return ""
        token = f"{_SCRIPT_TOKEN_PREFIX}{len(scripts)}__"
        scripts.append((token, safe_script))
        return token

    cleaned = _INLINE_SCRIPT_RE.sub(_replace, source_html or "")
    return cleaned, scripts


def _restore_inline_scripts(source_html: str, scripts: list[tuple[str, str]]) -> str:
    restored = source_html or ""
    for token, script_html in scripts:
        restored = restored.replace(token, script_html)
    return restored


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


def rewrite_media_template_url_tokens(source_html: str, field_defs: list[Any]) -> str:
    """Public migration helper for deterministic ``Field_url`` placeholders."""
    return _rewrite_media_url_attribute_tokens(source_html, field_defs)


def _resolve_media_url(value: Any, media_lookup: dict[str, Any]) -> str:
    if is_field_empty(value):
        return ""
    raw = str(value).strip()
    if raw == PREVIEW_MEDIA_AUDIO_TOKEN:
        return "/media/proxy/sample-audio"
    if raw == PREVIEW_MEDIA_IMAGE_TOKEN:
        return "/media/proxy/sample-image"
    if raw == PREVIEW_MEDIA_DIAGRAM_TOKEN:
        return "/media/proxy/sample-diagram"
    sound_match = re.match(r"^\[sound:([^\]]+)\]$", raw)
    if sound_match:
        raw = sound_match.group(1).strip()
    asset = media_lookup.get(raw)
    if asset is not None:
        return f"/media/proxy/{asset.id}"
    if is_canonical_media_url(raw):
        return raw
    if raw.startswith("stroke_"):
        return f"/media/library/{raw}.svg"
    # External URLs — pass through directly for user-provided public media.
    return ""


def _normalize_multiline_value(value: Any) -> str:
    text = "" if value is None else str(value)
    # Normalize Windows/Mac newlines and preserve explicit line breaks from editors.
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\\n", LINEBREAK_TOKEN)
    return normalized.replace("\n", LINEBREAK_TOKEN)


class _MustacheText(str):
    """Make Chevron's lookup data-only instead of exposing Python attributes.

    Chevron falls back to getattr after a string/list TypeError. A missing
    data property must raise KeyError instead; numeric access remains available
    just as in mustache.js. Normal string operations retain their behavior.
    """

    def __getitem__(self, key):
        if isinstance(key, str):
            if not key.isascii() or not key.isdecimal():
                raise KeyError(key)
            key = int(key)
        return super().__getitem__(key)


class _MustacheList(list):
    """A stored array, handed to Mustache unchanged so sections iterate it.

    Only ``{{field}}`` on the whole list needs help: chevron would print the
    Python repr. It prints what mustache.js prints (``String(array)``) instead,
    so server and browser agree. Templates format items themselves.
    """

    __slots__ = ()

    def __getitem__(self, key):
        if isinstance(key, str):
            if not key.isascii() or not key.isdecimal():
                raise KeyError(key)
            key = int(key)
        return super().__getitem__(key)

    def __str__(self) -> str:
        return ",".join("" if item is None else str(item) for item in self)


class _MustacheEmptyItem(_MustacheText):
    """An empty array item that still takes its place in a section loop.

    chevron skips a section body whose item is falsy; mustache.js renders it
    for every item. Keeping the empty position makes both print it, so paired
    columns stay aligned on the server too.
    """

    __slots__ = ()

    def __bool__(self) -> bool:
        return True


def _mustache_list(items: list[Any]) -> _MustacheList:
    return _MustacheList(
        _mustache_list(item) if isinstance(item, list)
        else _MustacheEmptyItem() if item is None or item == ""
        else _MustacheText(item) if isinstance(item, str) else item
        for item in items
    )


def _plain_context_value(value: Any) -> Any:
    if isinstance(value, list):
        return _mustache_list(value)
    return _normalize_multiline_value(value)


def _data_only_mustache_scope(value):
    if isinstance(value, dict):
        return {key: _data_only_mustache_scope(item) for key, item in value.items()}
    if isinstance(value, list):
        return _MustacheList(_data_only_mustache_scope(item) for item in value)
    if isinstance(value, _MustacheEmptyItem):
        return value
    if isinstance(value, str):
        return _MustacheText(value)
    return value


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
        attributes=_strict_allowed_attr,
        strip=True,
        css_sanitizer=_css_sanitizer,
    )


def sanitize_template_html_fragment(raw_html: str | None) -> str:
    cleaned_html, scripts = _extract_inline_scripts(raw_html or "")
    safe_html = bleach.clean(
        cleaned_html,
        tags=TEMPLATE_HTML_TAGS,
        attributes=_template_allowed_attr,
        strip=True,
        css_sanitizer=_css_sanitizer,
    )
    return _restore_inline_scripts(safe_html, scripts)


def prepare_client_template_source(
    raw_html: str | None,
    field_defs: list[Any],
) -> dict[str, Any]:
    """Prepare a template for Mustache rendering inside the React study client.

    Template-authored inline scripts are returned separately so untrusted field
    content can be sanitized after interpolation without granting it script
    provenance.
    """
    upgraded = _upgrade_html_field_double_brace_tokens(
        _rewrite_media_url_attribute_tokens(raw_html or "", field_defs),
        field_defs,
    )
    dot_media_field_types = {
        str(getattr(field_def, "field_type", "") or "").lower()
        for field_def in field_defs
        if re.search(
            rf"\{{\{{#\s*{re.escape(str(getattr(field_def, 'name', '') or ''))}_urls\s*\}}\}}",
            upgraded,
        )
    }
    script_free_html, scripts = _extract_inline_scripts(upgraded)
    for token, _ in scripts:
        script_free_html = script_free_html.replace(token, "")

    def _client_template_allowed_attr(tag: str, name: str, value: str) -> bool:
        return _is_media_template_url_attr(
            tag,
            name,
            value,
            field_defs,
            dot_media_field_types,
        ) or _template_allowed_attr(
            tag,
            name,
            value,
        )

    safe_source = bleach.clean(
        script_free_html,
        tags=TEMPLATE_HTML_TAGS,
        attributes=_client_template_allowed_attr,
        strip=True,
        css_sanitizer=_css_sanitizer,
    )
    return {
        "source": safe_source,
        "inline_scripts": [script_html for _, script_html in scripts],
    }


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
    if isinstance(value, (list, tuple, set)):
        return not any(not is_field_empty(item) for item in value)
    if isinstance(value, dict):
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
        chevron.render(source, {}, partials_path=None)
    except Exception as exc:  # pragma: no cover - defensive
        raise TemplateCompileError(str(exc)) from exc
    with _cache_lock:
        _template_cache[cache_key] = source
        _template_cache.move_to_end(cache_key)
        while len(_template_cache) > _MAX_TEMPLATE_CACHE:
            _template_cache.popitem(last=False)
    return source


def _render_single_media_html(
    field_type: str,
    raw: str,
    field_name: str,
    media_lookup: dict[str, Any],
) -> str:
    """Render one canonical or resolvable legacy reference to safe HTML."""
    media_url = _resolve_media_url(raw, media_lookup)

    if not media_url:
        return ""

    escaped_alt = html.escape(field_name, quote=True)
    escaped_field = html.escape(field_name, quote=True)
    asset_id = _extract_proxy_asset_id(media_url)
    asset = media_lookup.get(raw) or media_lookup.get(media_url)
    asset_mime = str(getattr(asset, "mime_type", "") or "").strip().lower()
    is_svg = (
        raw.lower().endswith(".svg")
        or media_url.lower().endswith(".svg")
        or "image/svg+xml" in raw.lower()
        or "image/svg+xml" in media_url.lower()
        or asset_mime.startswith("image/svg+xml")
    )
    media_attrs = [
        f'data-flama-media-field="{escaped_field}"',
        f'data-flama-media-kind="{html.escape("svg" if is_svg else field_type, quote=True)}"',
    ]
    if field_type == "audio":
        media_attrs.append('class="flama-media-audio"')
    elif is_svg:
        media_attrs.append('data-flama-is-svg="true"')
        media_attrs.append('class="flama-media-image flama-svg-image"')
    else:
        media_attrs.append('class="flama-media-image"')

    if asset_id:
        media_attrs.append(f'data-flama-media-asset-id="{html.escape(asset_id, quote=True)}"')
    joined_attrs = " ".join(media_attrs)
    escaped_url = html.escape(media_url, quote=True)
    if field_type == "audio":
        return f'<audio controls {joined_attrs} src="{escaped_url}"></audio>'
    return f'<img {joined_attrs} src="{escaped_url}" alt="{escaped_alt}">'


def _render_media_html(field_type: str, value: Any, field_name: str, media_lookup: dict[str, Any]) -> str:
    if is_field_empty(value):
        return ""
    raw = str(value).strip()

    if raw == PREVIEW_MEDIA_IMAGE_TOKEN:
        return (
            f'<div class="fc-preview-media-box" style="background-color:#f3f4f6;padding:12px;text-align:center;">'
            f"[Image: {html.escape(field_name)}]"
            "</div>"
        )
    if raw == PREVIEW_MEDIA_AUDIO_TOKEN:
        return (
            f'<div class="fc-preview-media-box" style="background-color:#f3f4f6;padding:12px;text-align:center;">'
            f"[Audio: {html.escape(field_name)}]"
            "</div>"
        )
    if raw == PREVIEW_MEDIA_DIAGRAM_TOKEN:
        return (
            f'<div class="fc-preview-media-box" style="background-color:#f3f4f6;padding:12px;text-align:center;">'
            f"[Diagram: {html.escape(field_name)}]"
            "</div>"
        )

    # Split on newlines for multi-value support (e.g. 3 image URLs).
    lines = split_media_field_value(raw)

    if len(lines) <= 1:
        # Single value — render without wrapping div.
        return _render_single_media_html(field_type, raw, field_name, media_lookup)

    # Multi-value — render each line and wrap in a gallery div.
    fragments: list[str] = []
    for line in lines:
        rendered = _render_single_media_html(field_type, line, field_name, media_lookup)
        if rendered:
            fragments.append(rendered)
    if not fragments:
        return ""
    if len(fragments) == 1:
        return fragments[0]
    return f'<div class="flama-media-gallery">{"".join(fragments)}</div>'


class _RenderedMediaMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.allowed_media_urls: set[str] = set()
        self.allowed_audio_urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {str(name or "").lower(): str(value or "") for name, value in attrs}
        src = attr_map.get("src", "").strip()
        href = attr_map.get("href", "").strip()
        media_url = src if src else href

        def _is_known_media_url(url: str) -> bool:
            return bool(
                _PROXY_MEDIA_URL_RE.match(url)
                or _LIBRARY_MEDIA_URL_RE.match(url)
                or _STATIC_STROKE_URL_RE.match(url)
                or is_canonical_media_url(url)
            )

        if _is_known_media_url(media_url):
            self.allowed_media_urls.add(media_url)
        if tag.lower() == "audio" and _is_known_media_url(src):
            self.allowed_audio_urls.add(src)
        if tag.lower() == "source" and _is_known_media_url(src):
            type_value = str(attr_map.get("type", "") or "").strip().lower()
            if type_value.startswith("audio/"):
                self.allowed_audio_urls.add(src)


def build_renderer_side_payload(
    rendered_html: str | None,
    *,
    template_key: str | None = None,
    shell_key: str | None = None,
    supports_live_patch: bool | None = None,
) -> dict[str, Any]:
    normalized_html = str(rendered_html or "")
    parser = _RenderedMediaMetadataParser()
    try:
        parser.feed(normalized_html)
        parser.close()
    except Exception:
        logger.exception("Failed to derive renderer media metadata from rendered HTML.")
    allowed_audio_urls = sorted(parser.allowed_audio_urls)
    normalized_template_key = str(template_key or "").strip()
    normalized_shell_key = str(shell_key or normalized_template_key).strip()
    has_inline_script = "<script" in normalized_html.lower()
    resolved_live_patch = (
        bool(supports_live_patch)
        if supports_live_patch is not None
        else bool(normalized_template_key and normalized_shell_key and not has_inline_script)
    )
    if has_inline_script:
        resolved_live_patch = False
    return {
        "html": normalized_html,
        "allowed_media_urls": sorted(parser.allowed_media_urls),
        "allowed_audio_urls": allowed_audio_urls,
        "allowed_audio_asset_ids": [
            asset_id
            for asset_id in (_extract_proxy_asset_id(url) for url in allowed_audio_urls)
            if asset_id
        ],
        "template_key": normalized_template_key,
        "shell_key": normalized_shell_key,
        "has_inline_script": has_inline_script,
        "supports_live_patch": bool(
            resolved_live_patch and normalized_template_key and normalized_shell_key
        ),
    }


def _inject_dotted_field_nested_keys(context: dict[str, Any]) -> None:
    """Mirror flat dotted keys (e.g. ``a.b``) into nested dicts.

    Anki treats ``a.b`` as a literal field name.  Mustache (chevron /
    mustache.js) interprets ``{{a.b}}`` as ``context["a"]["b"]``.  This
    helper bridges the gap by ensuring both representations exist so
    that templates imported from Anki render correctly under Mustache.

    Safety: if the dot-prefix already exists as a non-dict value (i.e.
    there is a real field with the same name as the prefix), the dotted
    key is skipped to avoid overwriting unrelated data.
    """
    dotted_keys = [k for k in context if "." in k]
    if not dotted_keys:
        return
    for key in dotted_keys:
        parts = key.split(".")
        target: dict[str, Any] | None = context
        for part in parts[:-1]:
            assert target is not None  # for type narrowing
            existing = target.get(part)
            if existing is None:
                nested: dict[str, Any] = {}
                target[part] = nested
                target = nested
            elif isinstance(existing, dict):
                target = existing
            else:
                # Prefix collides with a non-dict value (a real field
                # with the same name).  Skip to avoid data corruption.
                target = None
                break
        if target is not None:
            target.setdefault(parts[-1], context[key])


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
            media_urls = [
                resolved
                for item in split_media_field_value(value)
                if (resolved := _resolve_media_url(item, media_lookup))
            ]
            context[name] = media_html
            context[f"{name}_url"] = media_urls[0] if media_urls else ""
            context[f"{name}_urls"] = media_urls
            continue
        context[name] = _plain_context_value(value)

    # Keep unknown keys for legacy compatibility.
    for key, value in values.items():
        if key not in context:
            context[key] = _plain_context_value(value)

    # Anki allows dots in field names (literal strings), but Mustache
    # treats dots as nested property access.  Mirror flat dotted keys
    # into nested dicts so both semantics work.
    _inject_dotted_field_nested_keys(context)

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
) -> dict[str, Any]:
    field_defs, field_values = prepare_bound_fields(template, field_defs, field_values)
    css = sanitize_css(getattr(template, "shared_css", ""))
    preview_key = None
    if preview_note_key:
        preview_hash = hashlib.sha256(
            (
                getattr(template, "front_html", "")
                + getattr(template, "back_html", "")
                + css
                + preview_note_key
                + json.dumps({
                    "fields": [{"id": str(getattr(field, "id", "")), "name": field.name,
                                "type": field.field_type, "required": bool(getattr(field, "required", False))}
                               for field in field_defs],
                    "values": field_values or {},
                    "media": [{"id": str(getattr(asset, "id", "")),
                               "filename": str(getattr(asset, "filename", "")),
                               "sha256": str(getattr(asset, "sha256", ""))}
                              for asset in media_assets or []],
                }, sort_keys=True, ensure_ascii=False, default=str)
            ).encode("utf-8")
        ).hexdigest()
        preview_key = preview_hash
        with _cache_lock:
            cached = _preview_cache.get(preview_hash)
            if cached and datetime.utcnow() - cached[0] <= _PREVIEW_TTL:
                _preview_cache.move_to_end(preview_hash)
                return cached[1]
            if cached:
                _preview_cache.pop(preview_hash, None)

    template_updated = str(getattr(template, "updated_at", ""))
    front_source_raw = getattr(template, "front_html", "")
    back_source_raw = getattr(template, "back_html", "")
    front_source_prepared = _upgrade_html_field_double_brace_tokens(
        _rewrite_media_url_attribute_tokens(front_source_raw, field_defs),
        field_defs,
    )
    back_source_prepared = _upgrade_html_field_double_brace_tokens(
        _rewrite_media_url_attribute_tokens(back_source_raw, field_defs),
        field_defs,
    )
    front_source_prepared = FRONT_SIDE_TOKEN_RE.sub("", front_source_prepared)
    back_source_prepared = FRONT_SIDE_TOKEN_RE.sub(_FRONT_SIDE_MARKER, back_source_prepared)
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
    front_template_key = _renderer_shell_key(
        template=template,
        side="front",
        side_source=front_source_prepared,
        css=css,
        field_defs=field_defs,
    )
    back_template_key = _renderer_shell_key(
        template=template,
        side="back",
        side_source=back_source_prepared,
        css=css,
        field_defs=field_defs,
    )
    front_source = _cache_template(front_key, front_source_prepared)
    back_source = _cache_template(back_key, back_source_prepared)

    try:
        safe_scope = _data_only_mustache_scope(context)
        front_rendered = chevron.render(front_source, safe_scope, partials_path=None)
        back_rendered = chevron.render(back_source, safe_scope, partials_path=None)
    except Exception as exc:
        raise TemplateCompileError(str(exc)) from exc
    if _FRONT_SIDE_MARKER in back_rendered:
        back_rendered = back_rendered.replace(_FRONT_SIDE_MARKER, _INLINE_SCRIPT_RE.sub("", front_rendered))

    front_rendered = _replace_linebreak_token_in_html_text_nodes(front_rendered)
    back_rendered = _replace_linebreak_token_in_html_text_nodes(back_rendered)
    safe_front = sanitize_template_html_fragment(front_rendered)
    safe_back = sanitize_template_html_fragment(back_rendered)
    scoped_front = f"<style>{css}</style>{safe_front}" if css else safe_front
    scoped_back = f"<style>{css}</style>{safe_back}" if css else safe_back
    result = {
        "front_html": scoped_front,
        "back_html": scoped_back,
        "front_renderer_payload": build_renderer_side_payload(
            scoped_front,
            template_key=front_template_key,
            shell_key=front_template_key,
        ),
        "back_renderer_payload": build_renderer_side_payload(
            scoped_back,
            template_key=back_template_key,
            shell_key=back_template_key,
        ),
    }

    if preview_key:
        max_entries = 512
        if has_app_context():
            max_entries = max(
                int(current_app.config.get("FLASHCARD_RENDER_PREVIEW_CACHE_MAX_ENTRIES", 512)),
                1,
            )
        with _cache_lock:
            _preview_cache[preview_key] = (datetime.utcnow(), result)
            _preview_cache.move_to_end(preview_key)
            while len(_preview_cache) > max_entries:
                _preview_cache.popitem(last=False)
    return result
