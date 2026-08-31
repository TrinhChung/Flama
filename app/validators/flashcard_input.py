"""Validation helpers for flashcard-related request payloads and uploads."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.services.flashcard_renderer import is_field_empty, sanitize_richtext
from app.services.media_field_codec import (
    MediaFieldValueError,
    normalize_media_field_for_write,
)

MAX_TEXT_FIELD_LENGTH = 5_000
MAX_RICHTEXT_LENGTH = 20_000
MAX_MARKDOWN_LENGTH = 20_000
MAX_TAG_LENGTH = 64
MAX_TAG_COUNT = 50
MAX_FILENAME_LENGTH = 255
MAX_FIELD_NAME_LENGTH = 255
MAX_QUERY_TEXT_LENGTH = 200

_HTML_TAG_RE = re.compile(r"(?is)<\s*/?\s*[a-z!][^>]*>")
_SCRIPT_TAG_RE = re.compile(r"(?is)<\s*script\b")
_DANGEROUS_ELEMENT_RE = re.compile(r"(?is)<\s*(?:iframe|object|embed|foreignobject|script)\b")
_EVENT_HANDLER_RE = re.compile(r"(?i)\bon[a-z0-9_-]+\s*=")
_JS_URL_RE = re.compile(r"(?i)javascript\s*:")
_SVG_DOCTYPE_RE = re.compile(r"(?is)<!DOCTYPE|<!ENTITY")
_SVG_DANGEROUS_STYLE_RE = re.compile(r"(?i)(?:expression\s*\(|url\s*\(\s*['\"]?\s*javascript\s*:)")
_SVG_URL_FUNCTION_RE = re.compile(r"(?is)url\s*\(\s*(['\"]?)(.*?)\1\s*\)")
_SVG_IMPORT_RE = re.compile(r"(?i)@import\b")
_SAFE_TIMEZONE_RE = re.compile(r"^[A-Za-z0-9_+/\-]{1,64}$")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_DANGEROUS_SVG_ELEMENTS = {"script", "iframe", "object", "embed", "foreignobject", "link", "meta"}
_SQLI_PROBE_RE = re.compile(
    r"(?i)(?:"
    r"--|/\*|\*/|"
    r"\bunion\s+select\b|"
    r"\bor\s+1\s*=\s*1\b|"
    r"\bdrop\s+table\b|"
    r"\binsert\s+into\b|"
    r"\bdelete\s+from\b|"
    r"\bupdate\s+\w+\s+set\b"
    r")"
)


class RequestValidationError(ValueError):
    """Error used by validation layer for request-level failures."""

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        status: int = 400,
        code: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(message)
        self.field = field
        self.status = int(status)
        self.code = str(code)


@dataclass(frozen=True)
class NoteMutationInput:
    """Normalized note mutation payload for create/patch/update routes."""

    field_values: dict[str, str]
    field_updates: dict[str, str]
    tags: list[str] | None
    deck_id: int | None
    update_tags: bool
    update_deck: bool


@dataclass(frozen=True)
class StudyNextInput:
    """Normalized query payload for /api/study/next."""

    scope: str
    scope_id_raw: str
    scope_id_int: int | None


@dataclass(frozen=True)
class StudyAnswerInput:
    """Normalized request payload for /api/study/<card_id>/answer."""

    rating: str
    scope: str
    requested_scope_id: int | None
    timezone: str | None
    duration_ms: int | None


@dataclass(frozen=True)
class MediaUploadValidationResult:
    """Validated upload payload before media persistence."""

    field_name: str
    safe_original_filename: str
    storage_filename: str
    content: bytes
    mime_type: str
    size_bytes: int
    sha256: str


MEDIA_KIND_SPECS: dict[str, dict[str, Any]] = {
    "jpeg": {
        "family": "image",
        "primary_ext": "jpg",
        "extensions": {"jpg", "jpeg"},
        "mimes": {"image/jpeg"},
    },
    "png": {
        "family": "image",
        "primary_ext": "png",
        "extensions": {"png"},
        "mimes": {"image/png"},
    },
    "gif": {
        "family": "image",
        "primary_ext": "gif",
        "extensions": {"gif"},
        "mimes": {"image/gif"},
    },
    "webp": {
        "family": "image",
        "primary_ext": "webp",
        "extensions": {"webp"},
        "mimes": {"image/webp"},
    },
    "svg": {
        "family": "image",
        "primary_ext": "svg",
        "extensions": {"svg"},
        "mimes": {"image/svg+xml"},
    },
    "mp3": {
        "family": "audio",
        "primary_ext": "mp3",
        "extensions": {"mp3"},
        "mimes": {"audio/mpeg"},
    },
    "ogg": {
        "family": "audio",
        "primary_ext": "ogg",
        "extensions": {"ogg"},
        "mimes": {"audio/ogg"},
    },
    "wav": {
        "family": "audio",
        "primary_ext": "wav",
        "extensions": {"wav"},
        "mimes": {"audio/wav", "audio/x-wav"},
    },
    "webm": {
        "family": "audio",
        "primary_ext": "webm",
        "extensions": {"webm"},
        "mimes": {"audio/webm"},
    },
}

FIELD_TYPE_TO_MEDIA_FAMILY = {
    "image": "image",
    "diagram": "image",
    "audio": "audio",
}

ALLOWED_MEDIA_MIME_TYPES = {
    mime
    for spec in MEDIA_KIND_SPECS.values()
    for mime in spec["mimes"]
}

ALLOWED_MEDIA_EXTENSIONS_BY_FAMILY = {
    "image": {
        ext
        for spec in MEDIA_KIND_SPECS.values()
        if spec["family"] == "image"
        for ext in spec["extensions"]
    },
    "audio": {
        ext
        for spec in MEDIA_KIND_SPECS.values()
        if spec["family"] == "audio"
        for ext in spec["extensions"]
    },
}


def _payload_dict(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise RequestValidationError("Payload must be an object.", field="body")
    return payload


def _reject_forbidden_keys(payload: dict[str, Any], forbidden_keys: set[str]) -> None:
    for key in forbidden_keys:
        if key in payload:
            raise RequestValidationError(f"Field '{key}' is not allowed.", field=key)


def _validate_allowed_keys(payload: dict[str, Any], allowed_keys: set[str]) -> None:
    unknown_keys = sorted(key for key in payload if key not in allowed_keys)
    if unknown_keys:
        raise RequestValidationError(
            f"Unknown fields: {', '.join(unknown_keys)}",
            field=unknown_keys[0],
        )


def _normalize_text_input(raw_value: Any) -> str:
    text = "" if raw_value is None else str(raw_value)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def sanitize_query_text(
    raw_value: Any,
    *,
    field_name: str,
    max_length: int = MAX_QUERY_TEXT_LENGTH,
) -> str:
    text = _normalize_text_input(raw_value)
    if not text:
        return ""

    if len(text) > max_length:
        raise RequestValidationError(
            f"{field_name} exceeds max length {max_length}.",
            field=field_name,
        )
    if _CONTROL_CHAR_RE.search(text):
        raise RequestValidationError(
            f"{field_name} contains control characters.",
            field=field_name,
        )
    if _SQLI_PROBE_RE.search(text):
        raise RequestValidationError(
            f"{field_name} contains potentially malicious SQL injection payload.",
            field=field_name,
        )
    return text


def escape_like_pattern(value: str) -> str:
    """Escape SQL LIKE wildcard tokens so search behaves as literal contains."""
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def sanitize_plain_text(raw_value: Any, *, field_name: str, max_length: int = MAX_TEXT_FIELD_LENGTH) -> str:
    text = _normalize_text_input(raw_value)
    if len(text) > max_length:
        raise RequestValidationError(
            f"Field '{field_name}' exceeds max length {max_length}.",
            field=field_name,
        )

    if not text:
        return ""

    if _SCRIPT_TAG_RE.search(text) or _DANGEROUS_ELEMENT_RE.search(text):
        raise RequestValidationError(
            f"Field '{field_name}' contains unsafe HTML content.",
            field=field_name,
        )
    if _EVENT_HANDLER_RE.search(text):
        raise RequestValidationError(
            f"Field '{field_name}' contains disallowed event handler content.",
            field=field_name,
        )
    if _JS_URL_RE.search(text):
        raise RequestValidationError(
            f"Field '{field_name}' contains disallowed javascript URL content.",
            field=field_name,
        )
    if _HTML_TAG_RE.search(text):
        raise RequestValidationError(
            f"Field '{field_name}' must be plain text (HTML is not allowed).",
            field=field_name,
        )

    return text


def sanitize_rich_text(raw_value: Any, *, field_name: str, max_length: int = MAX_RICHTEXT_LENGTH) -> str:
    raw_text = "" if raw_value is None else str(raw_value)
    if len(raw_text) > max_length:
        raise RequestValidationError(
            f"Field '{field_name}' exceeds max length {max_length}.",
            field=field_name,
        )
    return sanitize_richtext(raw_text).strip()


def sanitize_markdown_text(
    raw_value: Any,
    *,
    field_name: str,
    max_length: int = MAX_MARKDOWN_LENGTH,
) -> str:
    text = "" if raw_value is None else str(raw_value)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) > max_length:
        raise RequestValidationError(
            f"Field '{field_name}' exceeds max length {max_length}.",
            field=field_name,
        )
    if _CONTROL_CHAR_RE.search(normalized):
        raise RequestValidationError(
            f"Field '{field_name}' contains control characters.",
            field=field_name,
        )
    return normalized


def normalize_tags(raw_tags: Any) -> list[str]:
    if raw_tags is None:
        return []

    candidates: list[Any]
    if isinstance(raw_tags, str):
        candidates = raw_tags.split(",")
    elif isinstance(raw_tags, list):
        candidates = raw_tags
    else:
        raise RequestValidationError("tags must be a string or list.", field="tags")

    normalized: list[str] = []
    seen: set[str] = set()

    for raw_item in candidates:
        tag = sanitize_plain_text(raw_item, field_name="tags", max_length=MAX_TAG_LENGTH)
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(tag)
        if len(normalized) > MAX_TAG_COUNT:
            raise RequestValidationError(
                f"tags cannot contain more than {MAX_TAG_COUNT} items.",
                field="tags",
            )

    return normalized


def parse_nullable_int(raw_value: Any, *, field_name: str) -> int | None:
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise RequestValidationError(f"{field_name} must be an integer.", field=field_name) from exc


def _clean_media_reference(
    raw_value: Any,
    *,
    field_name: str,
    note_media_ids: Any,
    field_type: str = "audio",
) -> str:
    candidate = _normalize_text_input(raw_value)
    try:
        return normalize_media_field_for_write(
            candidate,
            field_type=field_type,
            reference_lookup=note_media_ids,
        )
    except MediaFieldValueError as exc:
        raise RequestValidationError(
            str(exc),
            field=field_name,
            code="INVALID_MEDIA_REFERENCE",
        ) from exc


def _assert_required_fields(
    note_type: Any,
    field_values: dict[str, str],
    *,
    allow_missing_media: bool = False,
) -> None:
    for field_def in note_type.field_defs:
        field_type = str(field_def.field_type or "text").strip().lower()
        if allow_missing_media and field_type in FIELD_TYPE_TO_MEDIA_FAMILY:
            continue
        if field_def.required and is_field_empty(field_values.get(field_def.name)):
            raise RequestValidationError(
                f"Field '{field_def.name}' is required.",
                field=field_def.name,
            )


def clean_note_field_values(
    *,
    note_type: Any,
    raw_field_values: Any,
    partial: bool,
    current_values: dict[str, Any] | None = None,
    note_media_ids: Any = None,
    allow_missing_media: bool = False,
) -> tuple[dict[str, str], dict[str, str]]:
    if raw_field_values is None:
        if partial:
            merged = {
                str(key).strip(): "" if value is None else str(value)
                for key, value in dict(current_values or {}).items()
                if str(key).strip()
            }
            _assert_required_fields(
                note_type,
                merged,
                allow_missing_media=allow_missing_media,
            )
            return merged, {}
        raw_field_values = {}

    if not isinstance(raw_field_values, dict):
        raise RequestValidationError("field_values must be an object.", field="field_values")

    field_map = {field_def.name: field_def for field_def in note_type.field_defs}
    unknown = sorted(str(key) for key in raw_field_values.keys() if key not in field_map)
    if unknown:
        raise RequestValidationError(
            f"Unknown fields: {', '.join(unknown)}",
            field="field_values",
        )

    merged: dict[str, str] = {}
    if current_values:
        merged.update(
            {
                str(key).strip(): "" if value is None else str(value)
                for key, value in dict(current_values).items()
                if str(key).strip()
            }
        )

    updates: dict[str, str] = {}
    for field_name, raw_value in raw_field_values.items():
        field_def = field_map[field_name]
        field_type = str(field_def.field_type or "text").strip().lower()
        if field_type == "richtext":
            cleaned_value = sanitize_rich_text(raw_value, field_name=field_name)
        elif field_type == "markdown":
            cleaned_value = sanitize_markdown_text(raw_value, field_name=field_name)
        elif field_type in {"image", "audio", "diagram"}:
            cleaned_value = _clean_media_reference(
                raw_value,
                field_name=field_name,
                note_media_ids=note_media_ids,
                field_type=field_type,
            )
        else:
            cleaned_value = sanitize_plain_text(raw_value, field_name=field_name)

        updates[field_name] = cleaned_value
        merged[field_name] = cleaned_value

    if not partial:
        for field_name in field_map:
            if field_name not in merged:
                merged[field_name] = ""

    _assert_required_fields(
        note_type,
        merged,
        allow_missing_media=allow_missing_media,
    )
    return merged, updates


def validate_note_create_request(
    *,
    note_type: Any,
    payload: dict[str, Any] | None,
    note_media_ids: Any = None,
    allow_missing_media: bool = False,
) -> NoteMutationInput:
    body = _payload_dict(payload)
    _reject_forbidden_keys(body, {"id", "user_id", "created_at", "updated_at"})
    _validate_allowed_keys(body, {"note_type_id", "deck_id", "field_values", "tags"})

    field_values, field_updates = clean_note_field_values(
        note_type=note_type,
        raw_field_values=body.get("field_values"),
        partial=False,
        current_values=None,
        note_media_ids=set() if note_media_ids is None else note_media_ids,
        allow_missing_media=allow_missing_media,
    )

    return NoteMutationInput(
        field_values=field_values,
        field_updates=field_updates,
        tags=normalize_tags(body.get("tags")),
        deck_id=parse_nullable_int(body.get("deck_id"), field_name="deck_id"),
        update_tags=True,
        update_deck=True,
    )


def validate_note_patch_request(
    *,
    note_type: Any,
    payload: dict[str, Any] | None,
    current_values: dict[str, Any] | None,
    note_media_ids: Any,
) -> NoteMutationInput:
    body = _payload_dict(payload)
    _reject_forbidden_keys(body, {"id", "user_id", "created_at", "updated_at", "note_type_id"})
    _validate_allowed_keys(body, {"field_values", "deck_id", "tags"})

    if "field_values" in body:
        merged_values, field_updates = clean_note_field_values(
            note_type=note_type,
            raw_field_values=body.get("field_values"),
            partial=True,
            current_values=current_values,
            note_media_ids=note_media_ids,
        )
    else:
        merged_values, field_updates = clean_note_field_values(
            note_type=note_type,
            raw_field_values=None,
            partial=True,
            current_values=current_values,
            note_media_ids=note_media_ids,
        )

    return NoteMutationInput(
        field_values=merged_values,
        field_updates=field_updates,
        tags=normalize_tags(body.get("tags")) if "tags" in body else None,
        deck_id=(
            parse_nullable_int(body.get("deck_id"), field_name="deck_id")
            if "deck_id" in body
            else None
        ),
        update_tags=("tags" in body),
        update_deck=("deck_id" in body),
    )


def validate_study_card_edit_request(
    *,
    note_type: Any,
    payload: dict[str, Any] | None,
    current_values: dict[str, Any] | None,
    note_media_ids: Any,
) -> NoteMutationInput:
    body = _payload_dict(payload)
    _validate_allowed_keys(body, {"field_values", "deck_id", "tags", "render_contract"})

    if "field_values" in body:
        merged_values, field_updates = clean_note_field_values(
            note_type=note_type,
            raw_field_values=body.get("field_values"),
            partial=True,
            current_values=current_values,
            note_media_ids=note_media_ids,
        )
    else:
        merged_values, field_updates = clean_note_field_values(
            note_type=note_type,
            raw_field_values=None,
            partial=True,
            current_values=current_values,
            note_media_ids=note_media_ids,
        )

    return NoteMutationInput(
        field_values=merged_values,
        field_updates=field_updates,
        tags=normalize_tags(body.get("tags")) if "tags" in body else None,
        deck_id=(
            parse_nullable_int(body.get("deck_id"), field_name="deck_id")
            if "deck_id" in body
            else None
        ),
        update_tags=("tags" in body),
        update_deck=("deck_id" in body),
    )


def validate_browse_card_update_request(
    *,
    note_type: Any,
    payload: dict[str, Any] | None,
    current_values: dict[str, Any] | None,
    note_media_ids: Any,
) -> NoteMutationInput:
    body = _payload_dict(payload)
    _validate_allowed_keys(body, {"field_values", "fields", "deck_id", "tags"})

    raw_updates = body.get("field_values")
    if raw_updates is None and "fields" in body:
        raw_updates = body.get("fields")

    if raw_updates is None:
        merged_values, field_updates = clean_note_field_values(
            note_type=note_type,
            raw_field_values=None,
            partial=True,
            current_values=current_values,
            note_media_ids=note_media_ids,
        )
    else:
        merged_values, field_updates = clean_note_field_values(
            note_type=note_type,
            raw_field_values=raw_updates,
            partial=True,
            current_values=current_values,
            note_media_ids=note_media_ids,
        )

    return NoteMutationInput(
        field_values=merged_values,
        field_updates=field_updates,
        tags=normalize_tags(body.get("tags")) if "tags" in body else None,
        deck_id=(
            parse_nullable_int(body.get("deck_id"), field_name="deck_id")
            if "deck_id" in body
            else None
        ),
        update_tags=("tags" in body),
        update_deck=("deck_id" in body),
    )


def validate_legacy_browse_note_update_request(
    *,
    note_type: Any,
    payload: dict[str, Any] | None,
    current_values: dict[str, Any] | None,
    note_media_ids: Any,
) -> dict[str, str]:
    body = _payload_dict(payload)
    _validate_allowed_keys(body, {"fields"})
    if "fields" not in body:
        raise RequestValidationError("Missing fields payload.", field="fields")

    merged_values, _ = clean_note_field_values(
        note_type=note_type,
        raw_field_values=body.get("fields"),
        partial=True,
        current_values=current_values,
        note_media_ids=note_media_ids,
    )
    return merged_values


def validate_study_next_query(args: Any) -> StudyNextInput:
    scope = (args.get("scope") or "deck").strip().lower()
    if scope not in {"deck", "note_type"}:
        raise RequestValidationError(
            f"Unsupported scope: {scope}",
            field="scope",
        )

    scope_id_raw = (args.get("scope_id") or "").strip()
    if not scope_id_raw:
        raise RequestValidationError(
            f"scope_id is required for {scope} scope.",
            field="scope_id",
        )

    scope_id_int: int | None = None
    if scope == "deck":
        scope_id_int = parse_nullable_int(scope_id_raw, field_name="scope_id")
        if scope_id_int is None:
            raise RequestValidationError("scope_id is required for deck scope.", field="scope_id")

    return StudyNextInput(
        scope=scope,
        scope_id_raw=scope_id_raw,
        scope_id_int=scope_id_int,
    )


def _normalize_timezone(raw_timezone: Any) -> str | None:
    if raw_timezone in (None, ""):
        return None
    candidate = str(raw_timezone).strip()
    if not _SAFE_TIMEZONE_RE.match(candidate):
        raise RequestValidationError("timezone has invalid format.", field="timezone")
    return candidate


def _normalize_duration_ms(raw_duration: Any) -> int | None:
    if raw_duration in (None, ""):
        return None
    try:
        duration = int(raw_duration)
    except (TypeError, ValueError) as exc:
        raise RequestValidationError("duration_ms must be an integer.", field="duration_ms") from exc
    if duration < 0 or duration > 3_600_000:
        raise RequestValidationError(
            "duration_ms must be between 0 and 3600000.",
            field="duration_ms",
        )
    return duration


def validate_study_answer_request(payload: dict[str, Any] | None) -> StudyAnswerInput:
    body = _payload_dict(payload)

    rating = (body.get("rating") or "").strip().lower()
    if rating not in {"again", "hard", "good", "easy"}:
        raise RequestValidationError(
            "rating must be one of: again, hard, good, easy.",
            field="rating",
        )

    scope = (body.get("scope") or "").strip().lower()
    requested_scope_id: int | None = None
    if scope == "deck":
        requested_scope_id = parse_nullable_int(body.get("scope_id"), field_name="scope_id")

    return StudyAnswerInput(
        rating=rating,
        scope=scope,
        requested_scope_id=requested_scope_id,
        timezone=_normalize_timezone(body.get("timezone")),
        duration_ms=_normalize_duration_ms(body.get("duration_ms")),
    )


def _normalize_mime(raw_mime: str | None) -> str:
    return (raw_mime or "application/octet-stream").split(";", 1)[0].strip().lower()


def _detect_media_kind(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "wav"
    if content.startswith(b"OggS"):
        return "ogg"
    if content.startswith(b"\x1aE\xdf\xa3"):
        return "webm"
    if content.startswith(b"ID3"):
        return "mp3"
    if len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0:
        return "mp3"
    if _looks_like_safe_svg(content):
        return "svg"
    return None


def _looks_like_safe_svg(content: bytes) -> bool:
    try:
        raw_text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False

    stripped = raw_text.lstrip("\ufeff\t\r\n ")
    lowered = stripped.lower()

    if not stripped.startswith("<") or "<svg" not in lowered:
        return False
    if _SVG_DOCTYPE_RE.search(raw_text):
        return False
    if _SCRIPT_TAG_RE.search(raw_text) or _DANGEROUS_ELEMENT_RE.search(raw_text):
        return False
    if _EVENT_HANDLER_RE.search(raw_text):
        return False
    if _JS_URL_RE.search(raw_text):
        return False
    if _SVG_DANGEROUS_STYLE_RE.search(raw_text) or _SVG_IMPORT_RE.search(raw_text):
        return False
    if _contains_external_svg_url(raw_text):
        return False

    try:
        root = ET.fromstring(raw_text)
    except ET.ParseError:
        return False

    if _xml_local_name(root.tag) != "svg":
        return False

    for element in root.iter():
        tag_name = _xml_local_name(element.tag)
        if tag_name in _DANGEROUS_SVG_ELEMENTS:
            return False

        if tag_name == "style":
            style_text = "".join(str(part or "") for part in element.itertext())
            if (
                _SVG_DANGEROUS_STYLE_RE.search(style_text)
                or _JS_URL_RE.search(style_text)
                or _SVG_IMPORT_RE.search(style_text)
                or _contains_external_svg_url(style_text)
            ):
                return False

        for attr_name, attr_value in element.attrib.items():
            normalized_attr = _xml_local_name(attr_name)
            normalized_value = str(attr_value or "").strip()
            lowered_value = normalized_value.lower()

            if normalized_attr.startswith("on"):
                return False
            if _JS_URL_RE.search(normalized_value):
                return False
            if normalized_attr == "style":
                if (
                    _SVG_DANGEROUS_STYLE_RE.search(normalized_value)
                    or _SVG_IMPORT_RE.search(normalized_value)
                    or _contains_external_svg_url(normalized_value)
                ):
                    return False
            if normalized_attr == "href" and normalized_value and not lowered_value.startswith("#"):
                return False
    return True


def _contains_external_svg_url(value: str) -> bool:
    for match in _SVG_URL_FUNCTION_RE.finditer(str(value or "")):
        target = str(match.group(2) or "").strip()
        if not target.startswith("#"):
            return True
    return False


def _xml_local_name(value: Any) -> str:
    token = str(value or "")
    if "}" in token:
        token = token.rsplit("}", 1)[1]
    if ":" in token:
        token = token.rsplit(":", 1)[1]
    return token.lower()


def _scan_media_content(
    *,
    content: bytes,
    scanner: Callable[[bytes], Any] | None,
    scan_enabled: bool,
) -> None:
    if not scan_enabled:
        return
    if scanner is None:
        return

    try:
        result = scanner(content)
    except Exception as exc:  # pragma: no cover - defensive hook
        raise RequestValidationError(
            "Media scanner failed.",
            field="file",
            status=503,
            code="MEDIA_SCAN_ERROR",
        ) from exc

    is_clean = True
    reason = "Malware signature detected."

    if isinstance(result, tuple) and result:
        is_clean = bool(result[0])
        if len(result) > 1 and result[1]:
            reason = str(result[1])
    elif isinstance(result, dict):
        is_clean = bool(result.get("clean", True))
        if result.get("reason"):
            reason = str(result.get("reason"))
    elif isinstance(result, bool):
        is_clean = result

    if not is_clean:
        raise RequestValidationError(
            reason,
            field="file",
            status=422,
            code="MEDIA_MALICIOUS",
        )


def validate_media_upload_request(
    *,
    field_name_raw: Any,
    field_type: str,
    uploaded: FileStorage | None,
    max_bytes: int,
    scanner: Callable[[bytes], Any] | None = None,
    scan_enabled: bool = False,
) -> MediaUploadValidationResult:
    field_name = sanitize_plain_text(
        field_name_raw,
        field_name="field_name",
        max_length=MAX_FIELD_NAME_LENGTH,
    )
    if not field_name:
        raise RequestValidationError("field_name is required.", field="field_name")

    media_family = FIELD_TYPE_TO_MEDIA_FAMILY.get(str(field_type or "").strip().lower())
    if media_family is None:
        raise RequestValidationError(
            "Field does not accept media.",
            field="field_name",
        )

    if uploaded is None or not uploaded.filename:
        raise RequestValidationError("Missing uploaded file.", field="file")

    original_name = Path(str(uploaded.filename or "")).name
    extension = Path(original_name).suffix.lower().lstrip(".")
    allowed_extensions = ALLOWED_MEDIA_EXTENSIONS_BY_FAMILY[media_family]
    if extension not in allowed_extensions:
        raise RequestValidationError(
            f"Unsupported file extension: {extension or '<none>'}",
            field="file",
            status=415,
            code="MEDIA_TYPE_NOT_ALLOWED",
        )

    content = uploaded.read()
    if not content:
        raise RequestValidationError("Uploaded file is empty.", field="file")

    if len(content) > int(max_bytes):
        raise RequestValidationError(
            f"File exceeds {int(max_bytes)} bytes.",
            field="file",
            status=413,
            code="MEDIA_TOO_LARGE",
        )

    client_mime = _normalize_mime(uploaded.mimetype)
    allowed_mimes = {
        mime
        for spec in MEDIA_KIND_SPECS.values()
        if spec["family"] == media_family
        for mime in spec["mimes"]
    }
    if client_mime not in allowed_mimes:
        raise RequestValidationError(
            f"Unsupported media type: {client_mime}",
            field="file",
            status=415,
            code="MEDIA_TYPE_NOT_ALLOWED",
        )

    detected_kind = _detect_media_kind(content)
    if detected_kind is None:
        raise RequestValidationError(
            "Could not verify file signature.",
            field="file",
            status=415,
            code="MEDIA_SIGNATURE_INVALID",
        )

    kind_spec = MEDIA_KIND_SPECS[detected_kind]
    if kind_spec["family"] != media_family:
        raise RequestValidationError(
            "Uploaded file content does not match the target media field type.",
            field="file",
            status=415,
            code="MEDIA_SIGNATURE_INVALID",
        )

    if extension not in kind_spec["extensions"]:
        raise RequestValidationError(
            "Uploaded file extension does not match actual file content.",
            field="file",
            status=415,
            code="MEDIA_SIGNATURE_INVALID",
        )

    if client_mime not in kind_spec["mimes"]:
        raise RequestValidationError(
            "Uploaded MIME type does not match actual file content.",
            field="file",
            status=415,
            code="MEDIA_SIGNATURE_INVALID",
        )

    _scan_media_content(content=content, scanner=scanner, scan_enabled=scan_enabled)

    digest = hashlib.sha256(content).hexdigest()
    primary_ext = str(kind_spec["primary_ext"])

    safe_original_filename = secure_filename(original_name)[:MAX_FILENAME_LENGTH]
    if not safe_original_filename:
        safe_original_filename = f"upload.{primary_ext}"

    storage_filename = f"{uuid4().hex}_{digest[:12]}.{primary_ext}"

    return MediaUploadValidationResult(
        field_name=field_name,
        safe_original_filename=safe_original_filename,
        storage_filename=storage_filename,
        content=content,
        mime_type=next(iter(kind_spec["mimes"])),
        size_bytes=len(content),
        sha256=digest,
    )


def resolve_safe_storage_path(*, upload_root: Path, relative_path: Path) -> Path:
    root = upload_root.resolve()
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise RequestValidationError(
            "Unsafe storage path detected.",
            field="file",
            status=400,
            code="MEDIA_PATH_INVALID",
        ) from exc
    return target


def build_safe_download_filename(filename: str | None, *, fallback_ext: str = "bin") -> str:
    safe_name = secure_filename(filename or "")[:MAX_FILENAME_LENGTH]
    if safe_name:
        return safe_name
    return f"media.{fallback_ext}"
