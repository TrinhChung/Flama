"""Normalize safe text artifacts produced by Anki and Yomitan import sources."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

import bleach

from app.services import deck_working_tree_service
from app.services.flashcard_renderer import (
    ALLOWED_HTML_TAGS,
    _css_sanitizer,
    _strict_allowed_attr,
)
from models import db
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.field_def import FieldDef
from models.field_types import stored_field_value
from models.note import Note


_ANKI_APOSTROPHE_ENTITY_RE = re.compile(
    r"&(?:apos|#0*39|#x0*27);",
    flags=re.IGNORECASE,
)
_NORMALIZABLE_FIELD_TYPES = {"text", "richtext", "markdown"}

_HTML_TAG_RE = re.compile(r"(?is)<\s*/?\s*[a-z!][^>]*>")
_NON_CONTENT_BLOCKS_RE = re.compile(r"(?is)<(script|style|svg)\b[^>]*>.*?(?:</\1\s*>|$)")
_SELF_CLOSING_NON_CONTENT_RE = re.compile(r"(?is)<(script|style|svg)\b[^>]*/>")
_SCRIPT_STYLE_BLOCKS_RE = re.compile(r"(?is)<(script|style)\b[^>]*>.*?(?:</\1\s*>|$)")
_SELF_CLOSING_SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)\b[^>]*/>")
_RP_BLOCK_RE = re.compile(r"(?is)<rp\b[^>]*>.*?(?:</rp\s*>|$)")
_RUBY_BLOCK_RE = re.compile(r"(?is)<ruby\b[^>]*>(.*?)(?:</ruby\s*>|$)")
_INNERMOST_RUBY_RE = re.compile(
    r"(?is)<ruby\b[^>]*>((?:(?!<ruby\b).)*?)(?:</ruby\s*>|$)"
)

# Allowed HTML tags for richtext fields, augmented with <small> and SVG elements for pitch-accent graphs
RICHTEXT_ALLOWED_TAGS = list(
    set(ALLOWED_HTML_TAGS)
    | {
        "small",
        "svg",
        "path",
        "circle",
        "line",
        "polyline",
        "polygon",
        "rect",
        "g",
        "text",
    }
)


def normalize_anki_text_entities(value: str) -> str:
    """Decode only apostrophe entities known to leak from Anki field text.

    This intentionally does not use ``html.unescape``. Decoding arbitrary HTML
    entities could turn inert text into markup before the normal field
    sanitizer has validated it.
    """
    if not value or "&" not in value:
        return value
    return _ANKI_APOSTROPHE_ENTITY_RE.sub("'", value)


def detect_field_role(field_name: str, identity_role: str | None = None) -> str:
    """Detect the semantic role of a note field based on role metadata and name heuristics."""
    if identity_role == "primary":
        return "identity"

    clean_name = str(field_name or "").strip().lower()

    if any(
        kw in clean_name
        for kw in (
            "reading",
            "pronunciation",
            "furigana",
            "kana",
            "kunyomi",
            "onyomi",
            "cách đọc",
            "cach doc",
            "phát âm",
            "phat am",
        )
    ):
        return "reading"

    if clean_name in {
        "word",
        "expression",
        "headword",
        "term",
        "kanji",
        "character",
        "vocab",
        "vocabulary",
        "từ",
        "tu",
        "từ vựng",
        "tu vung",
    } or any(clean_name.startswith(p) for p in ("word", "expression", "headword", "term")):
        return "identity"

    if any(
        kw in clean_name
        for kw in (
            "sentence",
            "example",
            "context",
            "ví dụ",
            "vi du",
            "câu",
        )
    ):
        return "sentence"

    if any(
        kw in clean_name
        for kw in (
            "meaning",
            "glossary",
            "definition",
            "translation",
            "dịch",
            "dich",
            "nghĩa",
            "nghia",
            "ý nghĩa",
            "y nghia",
        )
    ):
        return "meaning"

    return "general"


class YomitanTextExtractor(HTMLParser):
    """Parse HTML layout structures into structured, human-readable plain text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.chunks: list[str] = []
        self.list_stack: list[dict[str, Any]] = []

    def _ensure_newline(self, count: int = 1) -> None:
        if not self.chunks:
            return
        trailing = 0
        for chunk in reversed(self.chunks):
            for ch in reversed(chunk):
                if ch == "\n":
                    trailing += 1
                else:
                    break
            if chunk:
                break
        if trailing < count:
            self.chunks.append("\n" * (count - trailing))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in ("ol", "ul"):
            self._ensure_newline(1)
            self.list_stack.append({"tag": t, "count": 0})
        elif t == "li":
            self._ensure_newline(1)
            depth = len(self.list_stack)
            if depth > 0:
                cur = self.list_stack[-1]
                cur["count"] += 1
                count = cur["count"]
                if depth == 1:
                    if cur["tag"] == "ol":
                        self.chunks.append(f"{count}. ")
                    else:
                        self.chunks.append("• ")
                else:
                    indent = "  " * (depth - 1)
                    if cur["tag"] == "ol":
                        self.chunks.append(f"{indent}{count}. ")
                    else:
                        self.chunks.append(f"{indent}• ")
            else:
                self.chunks.append("• ")
        elif t in (
            "p",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "blockquote",
            "tr",
            "header",
            "footer",
            "article",
            "section",
        ):
            self._ensure_newline(1)
        elif t == "br":
            self.chunks.append("\n")
        elif t in ("td", "th"):
            if self.chunks and not self.chunks[-1].endswith((" ", "\n")):
                self.chunks.append(" ")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("ol", "ul"):
            if self.list_stack:
                self.list_stack.pop()
            self._ensure_newline(1)
        elif t in (
            "li",
            "p",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "blockquote",
            "tr",
            "header",
            "footer",
            "article",
            "section",
        ):
            self._ensure_newline(1)

    def handle_data(self, data: str) -> None:
        if data:
            self.chunks.append(data)

    def handle_entityref(self, name: str) -> None:
        self.chunks.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.chunks.append(f"&#{name};")


def _decode_safe_text_entities(text: str) -> str:
    """Safely decode text entities without unescaping tags or creating raw HTML."""
    if not text or "&" not in text:
        return text

    def _replace_numeric(match: re.Match[str]) -> str:
        raw = match.group(0)
        content = match.group(1)
        try:
            if content.lower().startswith("x"):
                codepoint = int(content[1:], 16)
            else:
                codepoint = int(content, 10)
            if 0xD800 <= codepoint <= 0xDFFF or codepoint == 0:
                return raw
            char = chr(codepoint)
            if char in {"<", ">"}:
                return raw
            return char
        except (ValueError, OverflowError):
            return raw

    # Decode decimal and hex numeric character entities (except < and >)
    text = re.sub(r"&#([0-9a-fA-F]+|x[0-9a-fA-F]+);", _replace_numeric, text)

    # Decode safe named text entities
    text = text.replace("&quot;", '"')
    text = text.replace("&apos;", "'")
    text = text.replace("&nbsp;", " ")
    text = text.replace("\u00a0", " ")
    text = _ANKI_APOSTROPHE_ENTITY_RE.sub("'", text)

    # Decode &amp; safely
    text = re.sub(r"&amp;(?!lt;|gt;)", "&", text)
    text = text.replace("&amp;", "&")
    return text


def normalize_yomitan_html_to_plain(html_text: str, role: str = "general") -> str:
    """Convert Yomitan HTML markup to clean, human-readable plain text based on field role."""
    if not html_text:
        return ""

    if not html_text.strip():
        return ""

    text = str(html_text)

    # 1. Strip non-content blocks (<script>, <style>, <svg>) completely
    text = _SELF_CLOSING_NON_CONTENT_RE.sub("", text)
    text = _NON_CONTENT_BLOCKS_RE.sub("", text)

    # 2. Strip <rp> tags and their contents
    text = _RP_BLOCK_RE.sub("", text)

    # 3. Handle <ruby> structures based on field role
    def _replace_ruby(m: re.Match[str]) -> str:
        ruby_inner = m.group(1)
        if role == "reading":
            rts = re.findall(
                r"(?is)<rt\b[^>]*>(.*?)(?:</rt\s*>|(?=<rt\b)|(?=</ruby)|$)",
                ruby_inner,
            )
            if rts:
                cleaned = [re.sub(r"(?is)<[^>]+>", "", rt).strip() for rt in rts]
                return "".join(cleaned)
            return re.sub(r"(?is)<[^>]+>", "", ruby_inner).strip()
        else:
            without_rt = re.sub(
                r"(?is)<rt\b[^>]*>.*?(?:</rt\s*>|(?=<rt\b)|(?=</ruby)|$)",
                "",
                ruby_inner,
            )
            return re.sub(r"(?is)<[^>]+>", "", without_rt)

    prev = None
    while "<ruby" in text.lower() and text != prev:
        prev = text
        text = _INNERMOST_RUBY_RE.sub(_replace_ruby, text)
    text = re.sub(r"(?is)</?(?:ruby|rt|rp)\b[^>]*>", "", text)

    # 4. Extract structured text from HTML tags (lists, breaks, paragraphs)
    if "<" in text:
        extractor = YomitanTextExtractor()
        try:
            extractor.feed(text)
            extractor.close()
            text = "".join(extractor.chunks)
        except Exception:
            text = _HTML_TAG_RE.sub("", text)

    # 5. Remove any residual tags that may have bypassed the extractor
    if "<" in text:
        text = _HTML_TAG_RE.sub("", text)

    # 6. Decode safe text entities
    text = _decode_safe_text_entities(text)

    # 7. Normalize whitespace and newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def semantic_trim_plain_text(text: str, max_length: int = 5000) -> str:
    """Gracefully trim plain text exceeding max_length at natural boundary with an ellipsis."""
    if len(text) <= max_length:
        return text

    ellipsis = "..."
    # Reserve space for ellipsis and potential newline
    cut_limit = max_length - len(ellipsis) - 1
    window_start = max(0, cut_limit - 800)
    sub = text[window_start:cut_limit]

    # Priority 1: List item / numbered sense boundary (\n before \d+[.)] or circled numbers or paragraph break)
    p1 = list(re.finditer(r"(?:\n(?=\d+[\.\)])|\n(?=[①-⑳])|\n\n)", sub))
    if p1:
        cut_pos = window_start + p1[-1].start()
        return text[:cut_pos].rstrip() + "\n..."

    # Priority 2: Sentence terminal punctuation (Japanese 。！？ or Western . ! ?)
    p2 = list(re.finditer(r"(?:[。！？]|[\.!\?](?:\s|$))", sub))
    if p2:
        cut_pos = window_start + p2[-1].end()
        return text[:cut_pos].rstrip() + "..."

    # Priority 3: Clause delimiter / semicolon / newline
    p3 = list(re.finditer(r"(?:;(?:\s|$|\n)|\n)", sub))
    if p3:
        cut_pos = window_start + p3[-1].end()
        return text[:cut_pos].rstrip() + "..."

    # Priority 4: Word boundary (whitespace)
    p4 = list(re.finditer(r"\s+", sub))
    if p4:
        cut_pos = window_start + p4[-1].start()
        return text[:cut_pos].rstrip() + "..."

    # Priority 5: Hard slice fallback
    return text[:cut_limit].rstrip() + "..."


def sanitize_yomitan_richtext(raw_html: str | None, max_length: int = 20_000) -> str:
    """Sanitize rich text with Bleach and enforce length limit with balanced tag closure."""
    if not raw_html:
        return ""

    text = str(raw_html).strip()
    if not text:
        return ""

    # Strip script and style blocks completely (tag + content) before bleach
    text = _SCRIPT_STYLE_BLOCKS_RE.sub("", text)
    text = _SELF_CLOSING_SCRIPT_STYLE_RE.sub("", text)

    # 1. Clean with bleach first to reduce bloat
    cleaned = bleach.clean(
        text,
        tags=RICHTEXT_ALLOWED_TAGS,
        attributes=_strict_allowed_attr,
        strip=True,
        css_sanitizer=_css_sanitizer,
    ).strip()

    if len(cleaned) <= max_length:
        return cleaned

    # 2. Balanced tag closure trimming when exceeding max_length
    target_limit = max_length - 500
    while target_limit > 1000:
        slice_str = cleaned[:target_limit]
        last_close = -1
        for m in re.finditer(r"(?is)</(?:li|p|div|tr|td|th|ol|ul|table|blockquote|h[1-6])\s*>", slice_str):
            last_close = m.end()
        if last_close != -1:
            slice_str = slice_str[:last_close]
        else:
            last_gt = slice_str.rfind(">")
            last_lt = slice_str.rfind("<")
            if last_lt > last_gt:
                slice_str = slice_str[:last_lt]

        balanced = bleach.clean(
            slice_str,
            tags=RICHTEXT_ALLOWED_TAGS,
            attributes=_strict_allowed_attr,
            strip=True,
            css_sanitizer=_css_sanitizer,
        ).strip()

        if len(balanced) <= max_length:
            return balanced
        target_limit -= 1000

    # Fallback to safe slice
    return bleach.clean(
        cleaned[: max_length // 2],
        tags=RICHTEXT_ALLOWED_TAGS,
        attributes=_strict_allowed_attr,
        strip=True,
        css_sanitizer=_css_sanitizer,
    ).strip()


def normalize_anki_field_values(
    raw_values: dict[str, Any],
    field_defs: list[FieldDef] | tuple[FieldDef, ...],
) -> dict[str, Any]:
    """Normalize imported text and richtext fields with field-type awareness and semantic bounds."""
    from app.validators.field_value_identity import validate_incoming_field_labels
    validate_incoming_field_labels(raw_values, field_defs)
    field_defs_map: dict[str, Any] = {}
    for field_def in field_defs:
        name = getattr(field_def, "name", None)
        if not name and isinstance(field_def, dict):
            name = field_def.get("name")
        if name:
            field_defs_map[str(name)] = field_def

    normalized_result: dict[str, Any] = {}
    for name, value in raw_values.items():
        if value is None:
            normalized_result[name] = ""
            continue
        if isinstance(value, list):
            # Array items are already plain text; Anki entities never reach them.
            normalized_result[name] = value
            continue

        value_str = str(value)
        field_def = field_defs_map.get(name)
        field_type = "text"
        identity_role = None

        if field_def is not None:
            raw_type = getattr(field_def, "field_type", None)
            if not raw_type and isinstance(field_def, dict):
                raw_type = field_def.get("field_type")
            field_type = str(raw_type or "text").strip().lower()

            identity_role = getattr(field_def, "identity_role", None)
            if not identity_role and isinstance(field_def, dict):
                identity_role = field_def.get("identity_role")

        if field_type in {"audio", "image", "diagram"}:
            normalized_result[name] = value_str
        elif field_type == "markdown":
            normalized_result[name] = normalize_anki_text_entities(value_str)
        elif field_type == "richtext":
            normalized_result[name] = sanitize_yomitan_richtext(value_str, max_length=20_000)
        else:
            # text field or unrecognized type fallback
            role = detect_field_role(name, identity_role=identity_role)
            plain = normalize_yomitan_html_to_plain(value_str, role=role)
            normalized_result[name] = semantic_trim_plain_text(plain, max_length=5_000)

    return normalized_result


@dataclass(frozen=True)
class AnkiEntityBackfillResult:
    scanned: int
    changed: int


def backfill_anki_note_entities(
    *,
    user_id: int | None = None,
    deck_id: int | None = None,
) -> AnkiEntityBackfillResult:
    """Normalize existing notes that are known to originate from Anki sync.

    The caller owns the transaction so this can be used for a dry run via
    rollback or committed explicitly by the maintenance CLI.
    """
    tracked_note_exists = ConnectSourceNoteRef.query.filter(
        ConnectSourceNoteRef.note_id == Note.id
    ).exists()
    query = (
        Note.query.filter(tracked_note_exists)
        .filter(Note.field_values_by_id.isnot(None))
        .order_by(Note.id.asc())
    )
    if user_id is not None:
        query = query.filter(Note.user_id == user_id)
    if deck_id is not None:
        query = query.filter(Note.deck_id == deck_id)

    field_type_cache: dict[str, tuple[FieldDef, ...]] = {}
    dirty_mutations: list[dict[str, object]] = []
    scanned = 0
    changed = 0
    for note in query.yield_per(250):
        scanned += 1
        field_defs = field_type_cache.get(note.note_type_id)
        if field_defs is None:
            field_defs = tuple(
                FieldDef.query.filter_by(note_type_id=note.note_type_id)
                .order_by(FieldDef.position.asc(), FieldDef.id.asc())
                .all()
            )
            field_type_cache[note.note_type_id] = field_defs
        current = {
            str(name): stored_field_value(value)
            for name, value in dict(note.field_values or {}).items()
        }
        normalized = normalize_anki_field_values(current, field_defs)
        if normalized != current:
            note.field_values = normalized
            dirty_mutations.append(
                {
                    "note": note,
                    "field_names": {
                        field_name
                        for field_name in set(current) | set(normalized)
                        if current.get(field_name) != normalized.get(field_name)
                    },
                    "operation": "set",
                }
            )
            changed += 1
            if len(dirty_mutations) >= 250:
                deck_working_tree_service.mark_note_field_batches_changed(
                    mutations=dirty_mutations,
                )
                dirty_mutations.clear()

    deck_working_tree_service.mark_note_field_batches_changed(
        mutations=dirty_mutations,
    )
    db.session.flush()
    return AnkiEntityBackfillResult(scanned=scanned, changed=changed)
