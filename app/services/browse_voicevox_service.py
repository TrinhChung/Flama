"""VoiceVox application service shared by Browse HTTP adapters."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from app.services import deck_working_tree_service, tts_provider_service
from app.services.media_field_codec import (
    is_canonical_media_url,
    join_media_field_urls,
    split_media_field_value,
)
from models import db
from models.field_types import field_value_text
from models.card import card_id_clause
from models.flashcard import Card, MediaAsset, Note, NoteType


_VOICEVOX_TEMPLATE_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_AUDIO_FILE_EXT_RE = re.compile(
    r"\.(mp3|wav|ogg|opus|flac|m4a|aac|webm)(?:\?.*)?$",
    re.IGNORECASE,
)
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_INLINE_STYLE_RE = re.compile(r"(\*\*|__|\*|_|~~|`)")
_MD_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s*")
_MD_LIST_MARKER_RE = re.compile(r"(?m)^\s{0,3}(?:[-+*]|\d+\.)\s+")


class BrowseVoiceVoxError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = code


@dataclass(frozen=True)
class PreviewAudio:
    content: bytes
    mime_type: str
    extension: str
    warnings: list[str]


def preview_voicevox(*, user_id: int, payload: object) -> PreviewAudio:
    provider = _active_voicevox_provider()
    if not isinstance(payload, dict):
        raise BrowseVoiceVoxError("Payload phải là JSON object.")
    settings_payload = payload.get("settings")
    if settings_payload is not None and not isinstance(settings_payload, dict):
        raise BrowseVoiceVoxError("settings phải là JSON object.")

    synth_result, errors, warnings = (
        tts_provider_service.synthesize_voicevox_audio_for_user(
            db.session,
            user_id=user_id,
            provider=provider,
            text=str(payload.get("text") or "").strip(),
            character_id=str(payload.get("character_id") or "").strip(),
            settings_payload=settings_payload,
            api_key_override=str(payload.get("api_key") or "").strip() or None,
            use_opus=_to_bool(payload.get("use_opus")),
        )
    )
    if errors or synth_result is None:
        raise BrowseVoiceVoxError(
            "; ".join(errors or ["Không tạo được preview audio."])
        )
    return PreviewAudio(
        content=synth_result.content,
        mime_type=synth_result.mime_type,
        extension=synth_result.extension,
        warnings=list(warnings or []),
    )


def precheck_voicevox(
    *,
    user_id: int,
    admin_mode: bool,
    payload: dict[str, Any],
) -> dict[str, Any]:
    raw_card_ids = payload.get("card_ids")
    if not isinstance(raw_card_ids, list):
        raise BrowseVoiceVoxError("card_ids phải là mảng.")
    destination_field = str(payload.get("destination_field") or "").strip()
    if not destination_field:
        raise BrowseVoiceVoxError("destination_field là bắt buộc.")

    card_ids = _unique_ids(raw_card_ids)
    empty_payload = {
        "warning": False,
        "count": 0,
        "items": [],
        "mixed_note_types": False,
        "note_type_count": 0,
    }
    if not card_ids:
        return empty_payload

    query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(card_id_clause(db.session, card_ids))
        .options(
            selectinload(Card.note)
            .selectinload(Note.note_type)
            .selectinload(NoteType.field_defs),
        )
    )
    if not admin_mode:
        query = query.filter(Note.user_id == user_id)
    cards = query.all()
    if not cards:
        return empty_payload

    card_order = {card_id: index for index, card_id in enumerate(card_ids)}
    ordered_cards = sorted(
        cards,
        key=lambda item: card_order.get(item.id, 1_000_000),
    )
    seen_note_ids: set[str] = set()
    note_type_ids: set[str] = set()
    warning_items: list[dict[str, Any]] = []
    for card_obj in ordered_cards:
        note_obj = card_obj.note
        if note_obj is None or note_obj.id in seen_note_ids:
            continue
        seen_note_ids.add(note_obj.id)
        note_type_ids.add(
            str(note_obj.note_type_id or "__missing__").strip() or "__missing__"
        )
        field_defs = {
            str(field_def.name or "").strip(): field_def
            for field_def in (
                note_obj.note_type.field_defs if note_obj.note_type else []
            )
            if str(field_def.name or "").strip()
        }
        destination_def = field_defs.get(destination_field)
        if destination_def is None:
            continue
        if str(destination_def.field_type or "").strip().lower() != "audio":
            raise BrowseVoiceVoxError(
                f"Trường đích '{destination_field}' phải có kiểu audio.",
                code="invalid_destination_field",
            )
        existing_value = str(
            dict(note_obj.field_values or {}).get(destination_field) or ""
        ).strip()
        if not existing_value or _is_audio_like_field_value(existing_value):
            continue
        warning_items.append(
            {
                "note_id": note_obj.id,
                "field_name": destination_field,
                "field_type": str(destination_def.field_type or "text"),
                "sample": existing_value[:120],
            }
        )
    return {
        "warning": bool(warning_items),
        "count": len(warning_items),
        "items": warning_items[:5],
        "mixed_note_types": len(note_type_ids) > 1,
        "note_type_count": len(note_type_ids),
    }


def generate_voicevox(
    *,
    user_id: int,
    admin_mode: bool,
    payload: object,
    upload_root: Path,
) -> dict[str, Any]:
    provider = _active_voicevox_provider()
    if not isinstance(payload, dict):
        raise BrowseVoiceVoxError("Payload phải là JSON object.")
    raw_card_ids = payload.get("card_ids")
    card_ids: list[str] = []
    if isinstance(raw_card_ids, list):
        card_ids = _unique_ids(raw_card_ids)

    deck_id = payload.get("deck_id")
    deck_id_int: int | None = None
    if deck_id is not None:
        try:
            deck_id_int = int(deck_id)
        except (TypeError, ValueError):
            deck_id_int = None

    if not card_ids and deck_id_int is not None:
        from app.repositories.deck_tree_query import collect_subtree_ids
        subtree_ids = collect_subtree_ids(deck_id_int) or [deck_id_int]
        deck_cards_query = (
            Card.query.join(Note, Card.note_id == Note.id)
            .filter(Note.deck_id.in_(subtree_ids))
        )
        if not admin_mode:
            deck_cards_query = deck_cards_query.filter(Note.user_id == user_id)
        card_ids = [c.id for c in deck_cards_query.all()]

    if not card_ids:
        if raw_card_ids is not None and not isinstance(raw_card_ids, list):
            raise BrowseVoiceVoxError("card_ids phải là mảng.")
        raise BrowseVoiceVoxError(
            "Không có card nào được chọn để tạo audio."
        )

    source_field = str(payload.get("source_field") or "").strip()
    destination_field = str(payload.get("destination_field") or "").strip()
    character_id = str(payload.get("character_id") or "").strip()
    if not source_field:
        raise BrowseVoiceVoxError("source_field là bắt buộc.")
    if not destination_field:
        raise BrowseVoiceVoxError("destination_field là bắt buộc.")
    if not character_id:
        raise BrowseVoiceVoxError("character_id là bắt buộc.")
    settings_payload = payload.get("settings")
    if settings_payload is not None and not isinstance(settings_payload, dict):
        raise BrowseVoiceVoxError("settings phải là JSON object.")

    append_audio = _to_bool(payload.get("append_audio"))
    use_opus = _to_bool(payload.get("use_opus"))
    filename_template = str(payload.get("filename_template") or "").strip()
    speaker_label = str(payload.get("speaker_label") or character_id).strip()
    style_label = str(payload.get("style_label") or "").strip()
    api_key_override = str(payload.get("api_key") or "").strip() or None

    query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(card_id_clause(db.session, card_ids))
        .options(
            selectinload(Card.note)
            .selectinload(Note.note_type)
            .selectinload(NoteType.field_defs),
            selectinload(Card.note).selectinload(Note.media_assets),
        )
    )
    if not admin_mode:
        query = query.filter(Note.user_id == user_id)
    cards = query.all()
    if not cards:
        raise BrowseVoiceVoxError(
            "Không tìm thấy card hợp lệ để tạo audio.",
            status=404,
        )

    card_order = {card_id: index for index, card_id in enumerate(card_ids)}
    ordered_cards = sorted(
        cards,
        key=lambda item: card_order.get(item.id, 1_000_000),
    )
    selected_notes: list[Note] = []
    seen_note_ids: set[str] = set()
    for card_obj in ordered_cards:
        note_obj = card_obj.note
        if note_obj is None or note_obj.id in seen_note_ids:
            continue
        seen_note_ids.add(note_obj.id)
        selected_notes.append(note_obj)
    if not selected_notes:
        raise BrowseVoiceVoxError("Không có note hợp lệ để tạo audio.")
    selected_note_type_ids = {
        str(note_obj.note_type_id or "__missing__").strip() or "__missing__"
        for note_obj in selected_notes
    }
    if len(selected_note_type_ids) > 1:
        raise BrowseVoiceVoxError(
            "Bộ deck đang chọn chứa nhiều note type nên không thể thực hiện thao tác tạo âm thanh đồng loạt.",
            code="mixed_note_types",
        )

    destination_defs = {
        str(field_def.name or "").strip(): field_def
        for field_def in (
            selected_notes[0].note_type.field_defs
            if selected_notes[0].note_type else []
        )
    }
    destination_def = destination_defs.get(destination_field)
    if destination_def is None or str(destination_def.field_type or "").strip().lower() != "audio":
        raise BrowseVoiceVoxError(
            f"Trường đích '{destination_field}' phải tồn tại và có kiểu audio.",
            code="invalid_destination_field",
        )

    resolved_upload_root = upload_root.resolve()
    generated_items: list[dict[str, Any]] = []
    skipped_items: list[dict[str, str]] = []
    warning_items: list[str] = []
    audio_cache: dict[
        str,
        tuple[tts_provider_service.SynthesizedAudioResult, list[str]],
    ] = {}
    dirty_mutations: list[dict[str, Any]] = []

    for sequence, note_obj in enumerate(selected_notes, start=1):
        field_defs = {
            str(field_def.name or "").strip(): field_def
            for field_def in (
                note_obj.note_type.field_defs if note_obj.note_type else []
            )
            if str(field_def.name or "").strip()
        }
        source_def = field_defs.get(source_field)
        destination_def = field_defs.get(destination_field)
        if source_def is None:
            skipped_items.append(
                {
                    "note_id": note_obj.id,
                    "reason": f"Note không có source field '{source_field}'.",
                }
            )
            continue
        if destination_def is None:
            skipped_items.append(
                {
                    "note_id": note_obj.id,
                    "reason": f"Note không có destination field '{destination_field}'.",
                }
            )
            continue

        note_values = dict(note_obj.field_values or {})
        source_text_raw = field_value_text(note_values.get(source_field)).strip()
        source_type = str(source_def.field_type or "").strip().lower()
        if source_type == "richtext":
            source_text = _strip_richtext_to_plain(source_text_raw)
        elif source_type == "markdown":
            source_text = _strip_markdown_to_plain(source_text_raw)
        elif source_type == "text":
            source_text = _strip_richtext_to_plain(source_text_raw)
        else:
            source_text = _strip_richtext_to_plain(source_text_raw)
        source_text = source_text.strip()
        if not source_text:
            skipped_items.append(
                {"note_id": note_obj.id, "reason": "Source field trống."}
            )
            continue

        cache_key = "|".join(
            [
                source_text,
                character_id,
                "opus" if use_opus else "default",
                str(settings_payload or {}),
            ]
        )
        cached = audio_cache.get(cache_key)
        if cached is None:
            synth_result, errors, warnings = (
                tts_provider_service.synthesize_voicevox_audio_for_user(
                    db.session,
                    user_id=user_id,
                    provider=provider,
                    text=source_text,
                    character_id=character_id,
                    settings_payload=settings_payload,
                    api_key_override=api_key_override,
                    use_opus=use_opus,
                )
            )
            if errors or synth_result is None:
                skipped_items.append(
                    {
                        "note_id": note_obj.id,
                        "reason": "; ".join(
                            errors or ["VoiceVox synthesis thất bại."]
                        ),
                    }
                )
                continue
            cached = (synth_result, list(warnings or []))
            audio_cache[cache_key] = cached
        synth_result, cached_warnings = cached
        warning_items.extend(cached_warnings)

        sha256 = hashlib.sha256(synth_result.content).hexdigest()
        existing_asset = MediaAsset.query.filter_by(
            note_id=note_obj.id,
            field_name=destination_field,
            sha256=sha256,
        ).first()
        if existing_asset is None:
            filename = _render_voicevox_filename(
                template=filename_template,
                extension=synth_result.extension or "wav",
                speaker_label=speaker_label,
                style_label=style_label,
                note_id=note_obj.id,
                sequence=sequence,
            )
            relative_dir = Path("voicevox") / str(user_id) / str(note_obj.id)
            relative_path = relative_dir / filename
            full_path = (resolved_upload_root / relative_path).resolve()
            counter = 2
            while full_path.exists():
                filename = f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
                relative_path = relative_dir / filename
                full_path = (resolved_upload_root / relative_path).resolve()
                counter += 1
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(synth_result.content)
            existing_asset = MediaAsset(
                note_id=note_obj.id,
                field_name=destination_field,
                filename=filename,
                mime_type=synth_result.mime_type,
                storage_path=str(relative_path).replace("\\", "/"),
                sha256=sha256,
                size_bytes=len(synth_result.content),
            )
            db.session.add(existing_asset)
            db.session.flush()

        filename = str(existing_asset.filename or "")
        asset_url = f"/media/proxy/{existing_asset.id}"
        existing_value = str(note_values.get(destination_field) or "").strip()
        if append_audio and existing_value:
            next_value = join_media_field_urls(
                [*split_media_field_value(existing_value), asset_url]
            )
        else:
            next_value = asset_url
        if note_values.get(destination_field) != next_value:
            note_values[destination_field] = next_value
            note_obj.field_values = note_values
            dirty_mutations.append(
                {
                    "note": note_obj,
                    "field_names": {destination_field},
                    "operation": "set",
                }
            )
        generated_items.append(
            {
                "note_id": note_obj.id,
                "asset_id": existing_asset.id,
                "filename": filename,
                "destination_field": destination_field,
                "value": next_value,
                "url": asset_url,
            }
        )

    try:
        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=dirty_mutations,
        )
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise BrowseVoiceVoxError(
            "Không thể lưu kết quả generate audio vào database.",
            status=500,
        ) from exc

    unique_warnings = list(
        dict.fromkeys(
            str(warning or "").strip()
            for warning in warning_items
            if str(warning or "").strip()
        )
    )
    return {
        "success": True,
        "generated_count": len(generated_items),
        "selected_note_count": len(selected_notes),
        "skipped_count": len(skipped_items),
        "items": generated_items,
        "skipped": skipped_items,
        "warnings": unique_warnings,
        "output_root": str(
            (resolved_upload_root / "voicevox" / str(user_id)).resolve()
        ),
    }


def _active_voicevox_provider():
    provider = tts_provider_service.find_provider_by_type(
        tts_provider_service.VOICEVOX_PROVIDER_TYPE,
        include_inactive=False,
    )
    if provider is None:
        raise BrowseVoiceVoxError(
            "Provider không tồn tại hoặc đang bị tắt.",
            status=404,
        )
    return provider


def _unique_ids(raw_ids: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for raw_id in raw_ids:
        item_id = str(raw_id or "").strip()
        if item_id and item_id not in seen:
            seen.add(item_id)
            output.append(item_id)
    return output


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _strip_richtext_to_plain(raw_value: object) -> str:
    text = str(raw_value or "")
    # Strip <rp> tags
    text = re.sub(r"(?is)<rp>[^<]*</rp>", "", text)

    # Extract <rt> text from <ruby> blocks
    def _replace_ruby(m: re.Match) -> str:
        inner = m.group(1)
        rt_matches = re.findall(r"(?is)<rt\b[^>]*>([^<]*)</rt>", inner)
        if rt_matches:
            return "".join(rt_matches)
        return re.sub(r"(?is)<[^>]+>", "", inner)

    text = re.sub(r"(?is)<ruby\b[^>]*>(.*?)</ruby>", _replace_ruby, text)
    text = re.sub(r"(?is)<rt\b[^>]*>.*?</rt>", "", text)
    no_tags = re.sub(r"(?is)<[^>]+>", " ", text)
    return " ".join(no_tags.replace("&nbsp;", " ").split()).strip()


def _strip_markdown_to_plain(raw_value: object) -> str:
    text = str(raw_value or "")
    text = _MD_IMAGE_RE.sub(r" \1 ", text)
    text = _MD_LINK_RE.sub(r" \1 ", text)
    text = _MD_HEADING_RE.sub("", text)
    text = _MD_LIST_MARKER_RE.sub("", text)
    text = _MD_INLINE_STYLE_RE.sub("", text)
    return " ".join(text.split()).strip()


def _slug_filename_component(
    raw_value: object,
    *,
    fallback: str,
    max_len: int = 80,
) -> str:
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return fallback
    safe = secure_filename(raw_text).strip("._-") or fallback
    return safe[:max_len] or fallback


def _render_voicevox_filename(
    *,
    template: str,
    extension: str,
    speaker_label: str,
    style_label: str,
    note_id: str,
    sequence: int,
) -> str:
    now = datetime.now(timezone.utc)
    token_values = {
        "speaker": _slug_filename_component(speaker_label, fallback="speaker"),
        "style": _slug_filename_component(style_label, fallback="style"),
        "uid": uuid4().hex[:12],
        "note_id": _slug_filename_component(
            note_id,
            fallback="note",
            max_len=36,
        ),
        "index": str(int(sequence)),
        "date": now.strftime("%Y%m%d"),
        "timestamp": now.strftime("%Y%m%d%H%M%S"),
    }
    raw_template = (
        str(template or "").strip()
        or "VOICEVOX-{{speaker}}_{{style}}_{{uid}}"
    )

    def _replace_token(match: re.Match[str]) -> str:
        return token_values.get(str(match.group(1) or "").strip().lower(), "")

    rendered = _VOICEVOX_TEMPLATE_TOKEN_RE.sub(
        _replace_token,
        raw_template,
    ).strip()
    base_name = secure_filename(rendered).strip("._-")
    if not base_name:
        base_name = f"voicevox_{token_values['uid']}"
    ext = _slug_filename_component(
        extension,
        fallback="wav",
        max_len=10,
    ).lstrip(".")
    return f"{base_name}.{ext}"


def _looks_like_audio_token(raw_value: object) -> bool:
    token = str(raw_value or "").strip()
    if not token:
        return False
    token_lower = token.lower()
    return (
        (token_lower.startswith("[sound:") and token.endswith("]"))
        or "<audio" in token_lower
        or is_canonical_media_url(token)
        or bool(_AUDIO_FILE_EXT_RE.search(token_lower))
    )


def _is_audio_like_field_value(raw_value: object) -> bool:
    text = str(raw_value or "").strip()
    if not text:
        return False
    chunks = [
        line.strip()
        for line in re.split(r"[\r\n]+", text)
        if line and line.strip()
    ]
    return bool(chunks) and all(_looks_like_audio_token(chunk) for chunk in chunks)
