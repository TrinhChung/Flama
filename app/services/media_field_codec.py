"""Canonical URL-list contract shared by flashcard media field flows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlsplit


MEDIA_FIELD_TYPES = frozenset({"image", "audio", "diagram"})
_IMAGE_EXTENSIONS = frozenset({"avif", "bmp", "gif", "jpeg", "jpg", "png", "svg", "webp"})
_AUDIO_EXTENSIONS = frozenset({"aac", "flac", "m4a", "mp3", "oga", "ogg", "opus", "wav", "webm"})
_PROXY_RE = re.compile(r"^/media/proxy/([A-Za-z0-9][A-Za-z0-9_-]{0,127})$")
_STAGED_RE = re.compile(r"^/media/staged/([A-Za-z0-9_-]{8,64})$")
_ASSET_RE = re.compile(r"^/media/asset/([A-Za-z0-9][A-Za-z0-9_-]{0,127})$")
_LIBRARY_RE = re.compile(r"^/media/library/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_STATIC_STROKE_RE = re.compile(r"^/static/strokes/[A-Za-z0-9_-]+/[A-Fa-f0-9]+\.svg$")
_SOUND_RE = re.compile(r"^\[sound:(.+)\]$", re.IGNORECASE)
_SAFE_LEGACY_RE = re.compile(r"^[\w][\w .@()+,\-]{0,254}$", re.UNICODE)
_STROKE_KEY_RE = re.compile(r"^stroke_[a-z0-9_]+_[a-f0-9]{4,6}$", re.IGNORECASE)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class _MediaHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[tuple[str, str, str]] = []
        self.text_pieces: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered_tag = str(tag or "").lower()
        attr_map = {str(name or "").lower(): str(value or "") for name, value in attrs}
        src = attr_map.get("src", "").strip()
        if not src and lowered_tag == "a":
            src = attr_map.get("href", "").strip()
            if src:
                fam = media_reference_family_from_url(src)
                if fam is None and not any(src.lower().endswith(f".{ext}") for ext in _IMAGE_EXTENSIONS | _AUDIO_EXTENSIONS):
                    src = ""
        if src and lowered_tag in {"img", "audio", "video", "source", "a"}:
            self.sources.append((lowered_tag, src, attr_map.get("type", "").strip().lower()))

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self.text_pieces.append(cleaned)


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
    if _LIBRARY_RE.fullmatch(candidate) or _STAGED_RE.fullmatch(candidate) or _ASSET_RE.fullmatch(candidate):
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
    if candidate.startswith(("/media/library/", "/static/strokes/", "/media/staged/", "/media/asset/")) and expected == "audio":
        raise MediaFieldValueError(
            "Image-library URLs cannot be stored in an audio field.",
            reason="wrong_media_kind",
        )


def resolve_media_file_target(
    candidate: str,
    *,
    field_type: str,
    user_id: int | None = None,
) -> MediaReferenceTarget | None:
    """Attempts to resolve a candidate filename or stroke key to an existing system asset."""
    cleaned = str(candidate or "").strip()
    if not cleaned:
        return None

    expected_family = media_family(field_type)

    if _STROKE_KEY_RE.fullmatch(cleaned) and expected_family == "image":
        return MediaReferenceTarget(f"/media/library/{cleaned}.svg", "image")

    if cleaned.startswith("static/strokes/") or cleaned.startswith("/static/strokes/"):
        canonical_stroke = cleaned if cleaned.startswith("/") else f"/{cleaned}"
        if _STATIC_STROKE_RE.fullmatch(canonical_stroke):
            return MediaReferenceTarget(canonical_stroke, "image")

    basename = PurePosixPath(cleaned.replace("\\", "/")).name or cleaned

    # Check SharedImageAsset (image library) for image/diagram fields
    if expected_family == "image":
        try:
            from flask import has_app_context
            if has_app_context():
                from models.shared_image_asset import SharedImageAsset
                from sqlalchemy import func, or_
                stem = PurePosixPath(cleaned).stem
                base_stem = PurePosixPath(basename).stem
                shared = SharedImageAsset.query.filter(
                    or_(
                        func.lower(SharedImageAsset.image_key) == cleaned.lower(),
                        func.lower(SharedImageAsset.image_key) == basename.lower(),
                        func.lower(SharedImageAsset.image_key) == stem.lower(),
                        func.lower(SharedImageAsset.image_key) == base_stem.lower(),
                        func.lower(SharedImageAsset.filename) == cleaned.lower(),
                        func.lower(SharedImageAsset.filename) == basename.lower(),
                    ),
                    SharedImageAsset.is_enabled.is_(True),
                ).first()
                if shared:
                    return MediaReferenceTarget(f"/media/library/{shared.image_key}", "image")
        except Exception:
            pass

    # Check MediaAsset (by UUID or filename)
    try:
        from flask import has_app_context
        if has_app_context():
            from models import db
            from models.media_asset import MediaAsset
            if _UUID_RE.fullmatch(cleaned):
                asset = db.session.get(MediaAsset, cleaned)
                if asset:
                    family = "audio" if (asset.mime_type or "").startswith("audio/") else "image"
                    return MediaReferenceTarget(f"/media/proxy/{asset.id}", family)

            from models.note import Note
            from sqlalchemy import func, or_
            query = MediaAsset.query.filter(
                or_(
                    func.lower(MediaAsset.filename) == cleaned.lower(),
                    func.lower(MediaAsset.filename) == basename.lower(),
                )
            )
            if user_id is not None:
                user_asset = query.join(Note, MediaAsset.note_id == Note.id).filter(Note.user_id == user_id).first()
                if user_asset:
                    family = "audio" if (user_asset.mime_type or "").startswith("audio/") else "image"
                    return MediaReferenceTarget(f"/media/proxy/{user_asset.id}", family)

            asset = query.first()
            if asset:
                family = "audio" if (asset.mime_type or "").startswith("audio/") else "image"
                return MediaReferenceTarget(f"/media/proxy/{asset.id}", family)
    except Exception:
        pass

    return None


def normalize_media_reference_for_write(
    raw_reference: Any,
    *,
    field_type: str,
    reference_lookup: Mapping[str, Any] | set[str] | None = None,
    user_id: int | None = None,
) -> str:
    original = "" if raw_reference is None else str(raw_reference).strip()
    if not original:
        return ""
    candidate = original

    # Extract sources from HTML if tag/markup is present
    if "<" in candidate and ">" in candidate:
        parser = _MediaHtmlParser()
        try:
            parser.feed(candidate)
        except Exception:
            parser.sources = []
            parser.text_pieces = []

        expected = media_family(field_type)
        extracted_urls: list[str] = []

        if parser.sources:
            for tag, src, type_attr in parser.sources:
                if expected == "audio" and (tag == "img" or type_attr.startswith("image/")):
                    raise MediaFieldValueError(
                        "Image tags cannot be stored in an audio field.",
                        reason="wrong_media_kind",
                    )
                if expected == "image" and (tag in {"audio", "video"} or type_attr.startswith(("audio/", "video/"))):
                    raise MediaFieldValueError(
                        "Audio tags cannot be stored in an image field.",
                        reason="wrong_media_kind",
                    )
                try:
                    normalized_src = normalize_media_reference_for_write(
                        src,
                        field_type=field_type,
                        reference_lookup=reference_lookup,
                        user_id=user_id,
                    )
                    if normalized_src:
                        extracted_urls.append(normalized_src)
                except MediaFieldValueError as exc:
                    raise MediaFieldValueError(
                        f"Media reference in HTML <{tag}> tag could not be resolved: {exc}",
                        reason=getattr(exc, "reason", None) or "unresolved_legacy_reference",
                    ) from exc

            for piece in parser.text_pieces:
                for token in piece.split():
                    if is_canonical_media_url(token) or token.lower().startswith("[sound:"):
                        try:
                            norm = normalize_media_reference_for_write(
                                token,
                                field_type=field_type,
                                reference_lookup=reference_lookup,
                                user_id=user_id,
                            )
                            if norm:
                                extracted_urls.append(norm)
                        except Exception:
                            pass
        else:
            inner_text = " ".join(parser.text_pieces).strip() if getattr(parser, "text_pieces", None) else ""
            if not inner_text:
                inner_text = re.sub(r"<[^>]+>", "", candidate).strip()

            if inner_text:
                if "[sound:" in inner_text.lower():
                    if expected != "audio":
                        raise MediaFieldValueError(
                            "Anki sound syntax is only valid in audio fields.",
                            reason="wrong_media_kind",
                        )
                    sound_matches = re.findall(r"\[sound:([^\]]+)\]", inner_text, flags=re.IGNORECASE)
                    for sm in sound_matches:
                        norm = normalize_media_reference_for_write(
                            sm.strip(),
                            field_type=field_type,
                            reference_lookup=reference_lookup,
                            user_id=user_id,
                        )
                        if norm:
                            extracted_urls.append(norm)
                else:
                    try:
                        normalized_inner = normalize_media_reference_for_write(
                            inner_text,
                            field_type=field_type,
                            reference_lookup=reference_lookup,
                            user_id=user_id,
                        )
                        if normalized_inner:
                            extracted_urls.append(normalized_inner)
                    except MediaFieldValueError:
                        pass

        if extracted_urls:
            return join_media_field_urls(extracted_urls)
        raise MediaFieldValueError(
            "Media fields accept one HTTPS or managed-media URL per line.",
            reason="legacy_html",
        )

    if "[sound:" in candidate.lower():
        if media_family(field_type) != "audio":
            raise MediaFieldValueError(
                "Anki sound syntax is only valid in audio fields.",
                reason="wrong_media_kind",
            )
        sound_matches = re.findall(r"\[sound:([^\]]+)\]", candidate, flags=re.IGNORECASE)
        if sound_matches:
            extracted_sounds: list[str] = []
            for sm in sound_matches:
                norm_sound = normalize_media_reference_for_write(
                    sm.strip(),
                    field_type=field_type,
                    reference_lookup=reference_lookup,
                    user_id=user_id,
                )
                if norm_sound:
                    extracted_sounds.append(norm_sound)
            if extracted_sounds:
                return join_media_field_urls(extracted_sounds)

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

    # Check if candidate resolves to a local system file (SharedImageAsset, MediaAsset, stroke)
    file_target = resolve_media_file_target(candidate, field_type=field_type, user_id=user_id)
    if file_target is None and candidate != original:
        file_target = resolve_media_file_target(original, field_type=field_type, user_id=user_id)
    if file_target is not None and is_canonical_media_url(file_target.url):
        _assert_family(file_target.url, field_type=field_type, resolved_family=file_target.family)
        return file_target.url

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
    user_id: int | None = None,
) -> str:
    raw_str = "" if raw_value is None else str(raw_value).strip()
    if not raw_str:
        return ""

    if "<" in raw_str and ">" in raw_str:
        return normalize_media_reference_for_write(
            raw_str,
            field_type=field_type,
            reference_lookup=reference_lookup,
            user_id=user_id,
        )

    normalized = [
        normalize_media_reference_for_write(
            item,
            field_type=field_type,
            reference_lookup=reference_lookup,
            user_id=user_id,
        )
        for item in split_media_field_value(raw_str)
    ]
    return join_media_field_urls(normalized)
