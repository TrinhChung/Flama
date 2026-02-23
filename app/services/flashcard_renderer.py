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
]

_css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
_template_cache: OrderedDict[str, str] = OrderedDict()
_preview_cache: dict[str, tuple[datetime, dict[str, str]]] = {}
_cache_lock = threading.Lock()
_MAX_TEMPLATE_CACHE = 512
_PREVIEW_TTL = timedelta(seconds=30)
PREVIEW_MEDIA_IMAGE_TOKEN = "__fc_preview_image__"
PREVIEW_MEDIA_AUDIO_TOKEN = "__fc_preview_audio__"
PREVIEW_MEDIA_DIAGRAM_TOKEN = "__fc_preview_diagram__"


class TemplateCompileError(ValueError):
    """Mustache template compile/parse error."""


def _allowed_attr(tag: str, name: str, value: str) -> bool:
    lowered = name.lower()
    if lowered.startswith("on"):
        return False
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


def _render_media_html(field_type: str, value: Any, field_name: str, media_by_id: dict[str, Any]) -> str:
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

    asset = media_by_id.get(raw)
    media_url = None
    if asset is not None:
        media_url = f"/media/proxy/{asset.id}"
    elif raw.startswith("/media/proxy/"):
        media_url = raw

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
) -> dict[str, Any]:
    values = field_values or {}
    media_by_id = {str(asset.id): asset for asset in (media_assets or [])}
    context: dict[str, Any] = {}

    for field_def in field_defs:
        name = field_def.name
        value = values.get(name)
        if field_def.field_type == "richtext":
            context[name] = sanitize_richtext(str(value or ""))
            continue
        if field_def.field_type in {"image", "audio", "diagram"}:
            context[name] = _render_media_html(field_def.field_type, value, name, media_by_id)
            continue
        context[name] = "" if value is None else str(value)

    # Keep unknown keys for legacy compatibility.
    for key, value in values.items():
        if key not in context:
            context[key] = "" if value is None else str(value)

    return context


def render_template_pair(
    *,
    template: Any,
    field_defs: list[Any],
    field_values: dict[str, Any] | None,
    media_assets: list[Any] | None = None,
    preview_note_key: str | None = None,
) -> dict[str, str]:
    css = sanitize_css(getattr(template, "shared_css", ""))
    preview_key = None
    if preview_note_key:
        preview_hash = hashlib.sha256(
            (getattr(template, "front_html", "") + getattr(template, "back_html", "") + css + preview_note_key).encode("utf-8")
        ).hexdigest()
        preview_key = preview_hash
        cached = _preview_cache.get(preview_hash)
        if cached and datetime.utcnow() - cached[0] <= _PREVIEW_TTL:
            return cached[1]

    context = build_render_context(field_defs, field_values, media_assets)
    template_updated = str(getattr(template, "updated_at", ""))
    front_source_raw = getattr(template, "front_html", "")
    back_source_raw = getattr(template, "back_html", "")
    front_hash = hashlib.sha256(front_source_raw.encode("utf-8")).hexdigest()[:16]
    back_hash = hashlib.sha256(back_source_raw.encode("utf-8")).hexdigest()[:16]
    front_key = f"{template.id}:{template_updated}:front:{front_hash}"
    back_key = f"{template.id}:{template_updated}:back:{back_hash}"
    front_source = _cache_template(front_key, front_source_raw)
    back_source = _cache_template(back_key, back_source_raw)

    try:
        front_rendered = chevron.render(front_source, context)
        back_rendered = chevron.render(back_source, context)
    except Exception as exc:
        raise TemplateCompileError(str(exc)) from exc

    safe_front = sanitize_html_fragment(front_rendered)
    safe_back = sanitize_html_fragment(back_rendered)
    scoped_front = f"<style>{css}</style>{safe_front}" if css else safe_front
    scoped_back = f"<style>{css}</style>{safe_back}" if css else safe_back
    result = {"front_html": scoped_front, "back_html": scoped_back}

    if preview_key:
        _preview_cache[preview_key] = (datetime.utcnow(), result)
    return result
