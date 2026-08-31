"""Canonical URL-list contract shared by flashcard media field flows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlsplit


MEDIA_FIELD_TYPES = frozenset({"image", "audio", "diagram"})
_IMAGE_EXTENSIONS = frozenset({"avif", "bmp", "gif", "jpeg", "jpg", "png", "svg", "webp"})
_AUDIO_EXTENSIONS = frozenset({"aac", "flac", "m4a", "mp3", "oga", "ogg", "opus", "wav", "webm"})
_PROXY_RE = re.compile(r"^/media/proxy/([A-Za-z0-9][A-Za-z0-9_-]{0,127})$")
_LIBRARY_RE = re.compile(r"^/media/library/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_STATIC_STROKE_RE = re.compile(r"^/static/strokes/[A-Za-z0-9_-]+/[A-Fa-f0-9]+\.svg$")
_SOUND_RE = re.compile(r"^\[sound:(.+)\]$", re.IGNORECASE)
_SAFE_LEGACY_RE = re.compile(r"^[\w][\w .@()+,\-]{0,254}$", re.UNICODE)


class MediaFieldValueError(ValueError):
    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class MediaReferenceTarget:
    url: str
    family: str | None = None


def media_family(field_type: str | None) -> str | None:
    normalized = str(field_type or "").strip().lower()
    if normalized == "audio":
        return "audio"
    if normalized in {"image", "diagram"}:
        return "image"
    return None


def split_media_field_value(raw_value: Any) -> list[str]:
    text = "" if raw_value is None else str(raw_value)
    return [
        line.strip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]


def join_media_field_urls(urls: list[str] | tuple[str, ...]) -> str:
    output: list[str] = []
    seen: set[str] = set()
    for raw_url in urls:
        url = str(raw_url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        output.append(url)
    return "\n".join(output)


def media_reference_family_from_url(raw_url: str) -> str | None:
    try:
        path = urlsplit(str(raw_url or "").strip()).path
    except ValueError:
        return None
    suffix = PurePosixPath(path).suffix.lower().lstrip(".")
    if suffix in _IMAGE_EXTENSIONS:
        return "image"
    if suffix in _AUDIO_EXTENSIONS:
        return "audio"
    return None


def is_canonical_media_url(raw_url: str, *, allow_local_http: bool = True) -> bool:
    candidate = str(raw_url or "").strip()
    if not candidate or any(char.isspace() or char in ('"', "'", "<", ">", "\x00") for char in candidate):
        return False
    if _PROXY_RE.fullmatch(candidate) or _STATIC_STROKE_RE.fullmatch(candidate):
        return True
    if _LIBRARY_RE.fullmatch(candidate):
        return True
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return False
    if parsed.scheme == "https" and bool(parsed.netloc):
        return True
    if parsed.scheme == "http" and bool(parsed.netloc) and allow_local_http:
        return (parsed.hostname or "").lower() in {"127.0.0.1", "localhost", "::1"}
    return False


def _lookup_target(
    candidate: str,
    reference_lookup: Mapping[str, Any] | set[str] | None,
) -> MediaReferenceTarget | None:
    if reference_lookup is None:
        return None
    if isinstance(reference_lookup, set):
        return MediaReferenceTarget(candidate) if candidate in reference_lookup else None
    entry = reference_lookup.get(candidate)
    if entry is None:
        return None
    if isinstance(entry, MediaReferenceTarget):
        return entry
    if isinstance(entry, str):
        return MediaReferenceTarget(entry)
    if isinstance(entry, tuple) and entry:
        family = str(entry[1]) if len(entry) > 1 and entry[1] else None
        return MediaReferenceTarget(str(entry[0]), family)
    asset_id = str(getattr(entry, "id", "") or "").strip()
    mime_type = str(getattr(entry, "mime_type", "") or "").strip().lower()
    family = "audio" if mime_type.startswith("audio/") else "image" if mime_type.startswith("image/") else None
    return MediaReferenceTarget(f"/media/proxy/{asset_id}", family) if asset_id else None


def build_media_reference_lookup(assets: Any) -> dict[str, MediaReferenceTarget]:
    """Index managed assets by canonical and legacy reference spellings."""
    lookup: dict[str, MediaReferenceTarget] = {}
    for asset in assets or []:
        asset_id = str(getattr(asset, "id", "") or "").strip()
        if not asset_id:
            continue
        mime_type = str(getattr(asset, "mime_type", "") or "").strip().lower()
        family = "audio" if mime_type.startswith("audio/") else "image" if mime_type.startswith("image/") else None
        url = f"/media/proxy/{asset_id}"
        target = MediaReferenceTarget(url, family)
        lookup[asset_id] = target
        lookup[url] = target
        filename = str(getattr(asset, "filename", "") or "").strip()
        if filename:
            lookup[filename] = target
            lookup[f"[sound:{filename}]"] = target
    return lookup


def _assert_family(candidate: str, *, field_type: str, resolved_family: str | None = None) -> None:
    expected = media_family(field_type)
    actual = resolved_family or media_reference_family_from_url(candidate)
    if expected and actual and expected != actual:
        raise MediaFieldValueError(
            f"Media URL does not match the '{field_type}' field type.",
            reason="wrong_media_kind",
        )
    if candidate.startswith(("/media/library/", "/static/strokes/")) and expected == "audio":
        raise MediaFieldValueError(
            "Image-library URLs cannot be stored in an audio field.",
            reason="wrong_media_kind",
        )


def normalize_media_reference_for_write(
    raw_reference: Any,
    *,
    field_type: str,
    reference_lookup: Mapping[str, Any] | set[str] | None = None,
) -> str:
    original = "" if raw_reference is None else str(raw_reference).strip()
    if not original:
        return ""
    candidate = original

    sound_match = _SOUND_RE.fullmatch(candidate)
    if sound_match:
        if media_family(field_type) != "audio":
            raise MediaFieldValueError(
                "Anki sound syntax is only valid in audio fields.",
                reason="wrong_media_kind",
            )
        candidate = sound_match.group(1).strip()

    if is_canonical_media_url(candidate):
        target = _lookup_target(candidate, reference_lookup)
        if candidate.startswith("/media/proxy/") and reference_lookup is not None and target is None:
            raise MediaFieldValueError(
                "The media asset does not belong to this note.",
                reason="unknown_media_asset",
            )
        _assert_family(candidate, field_type=field_type, resolved_family=target.family if target else None)
        return candidate

    target = _lookup_target(candidate, reference_lookup)
    if target is None:
        target = _lookup_target(original, reference_lookup)
    if target is not None and is_canonical_media_url(target.url):
        _assert_family(target.url, field_type=field_type, resolved_family=target.family)
        return target.url

    # A Connect import may temporarily reference a filename that was resolved
    # and explicitly allowlisted by the staging service. Never use this escape
    # hatch for an arbitrary filename merely because the caller is importing.
    if target is not None and _SAFE_LEGACY_RE.fullmatch(candidate):
        _assert_family(candidate, field_type=field_type, resolved_family=target.family)
        return original

    reason = "legacy_html" if "<" in candidate or ">" in candidate else (
        "unresolved_legacy_reference" if _SAFE_LEGACY_RE.fullmatch(candidate) else "invalid_media_reference"
    )
    raise MediaFieldValueError(
        "Media fields accept one HTTPS or managed-media URL per line.",
        reason=reason,
    )


def normalize_media_field_for_write(
    raw_value: Any,
    *,
    field_type: str,
    reference_lookup: Mapping[str, Any] | set[str] | None = None,
) -> str:
    normalized = [
        normalize_media_reference_for_write(
            item,
            field_type=field_type,
            reference_lookup=reference_lookup,
        )
        for item in split_media_field_value(raw_value)
    ]
    return join_media_field_urls(normalized)
