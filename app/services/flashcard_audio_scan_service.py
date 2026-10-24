"""Application service for scanning deck flashcard audio fields and media integrity."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import selectinload

from models import db
from models.deck import Deck
from models.field_types import field_value_text
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType

logger = logging.getLogger(__name__)

_AUDIO_SUFFIX_RE = re.compile(r"(_audio|audio|_sound|sound|audioreading|audioexpression|audioword)$", re.IGNORECASE)
_PRIORITY_SOURCE_FIELDS = [
    "Reading",
    "reading",
    "Word",
    "word",
    "Expression",
    "expression",
    "Front",
    "front",
    "Kanji",
    "kanji",
    "Vocabulary",
    "vocabulary",
    "Sentence",
    "sentence",
    "Meaning",
    "meaning",
    "Vietnamese",
    "vietnamese",
]


class AudioScanError(ValueError):
    """Domain error for deck audio scan requests."""

    def __init__(self, message: str, *, status: int = 400, code: str = "AUDIO_SCAN_ERROR") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def infer_auto_mappings(field_defs: list[FieldDef]) -> list[dict[str, Any]]:
    """Automatically detect source -> destination audio field mappings."""
    field_name_lookup = {f.name.lower(): f.name for f in field_defs if f.name}
    audio_fields: list[FieldDef] = []

    for f in field_defs:
        if not f.name:
            continue
        is_audio_type = f.field_type == "audio"
        name_lower = f.name.lower()
        has_audio_name = (
            "audio" in name_lower
            or "sound" in name_lower
            or name_lower.endswith("_au")
            or name_lower.endswith("_snd")
        )
        if is_audio_type or has_audio_name:
            audio_fields.append(f)

    mappings: list[dict[str, Any]] = []
    used_destinations: set[str] = set()

    for audio_field in audio_fields:
        dest_name = audio_field.name
        if dest_name in used_destinations:
            continue

        dest_lower = dest_name.lower()
        source_name: str | None = None
        confidence = "default"

        # 1. Try stripping suffixes like _audio, audio, _sound, sound
        match = _AUDIO_SUFFIX_RE.search(dest_name)
        if match:
            stripped = dest_name[: match.start()].strip(" _-")
            if stripped:
                stripped_lower = stripped.lower()
                if stripped_lower in field_name_lookup and field_name_lookup[stripped_lower] != dest_name:
                    source_name = field_name_lookup[stripped_lower]
                    confidence = "exact_suffix"
                else:
                    # Prefix matching on stripped root
                    for k_lower, k_orig in field_name_lookup.items():
                        if k_orig != dest_name and (k_lower.startswith(stripped_lower) or stripped_lower.startswith(k_lower)):
                            source_name = k_orig
                            confidence = "prefix_suffix"
                            break

        # 2. If not matched, try prefix pattern (e.g. AudioReading -> Reading, Audio_Front -> Front)
        if not source_name:
            if dest_lower.startswith("audio_") or dest_lower.startswith("sound_"):
                stripped = dest_name[6:].strip(" _-")
                if stripped.lower() in field_name_lookup and field_name_lookup[stripped.lower()] != dest_name:
                    source_name = field_name_lookup[stripped.lower()]
                    confidence = "exact_prefix"
            elif dest_lower.startswith("audio") and len(dest_name) > 5:
                stripped = dest_name[5:].strip(" _-")
                if stripped.lower() in field_name_lookup and field_name_lookup[stripped.lower()] != dest_name:
                    source_name = field_name_lookup[stripped.lower()]
                    confidence = "exact_prefix"

        # 3. If generic "Audio" or "Sound", pick highest priority text field
        if not source_name:
            for p in _PRIORITY_SOURCE_FIELDS:
                if p.lower() in field_name_lookup and field_name_lookup[p.lower()] != dest_name:
                    source_name = field_name_lookup[p.lower()]
                    confidence = "priority_fallback"
                    break

        # 4. Fallback to first non-audio field if available
        if not source_name:
            for f in field_defs:
                if f.name != dest_name and f.field_type != "audio":
                    source_name = f.name
                    confidence = "first_available"
                    break

        if source_name:
            mappings.append(
                {
                    "source_field": source_name,
                    "destination_field": dest_name,
                    "confidence": confidence,
                }
            )
            used_destinations.add(dest_name)

    # If no audio field exists at all in the note type, provide a sensible default mapping
    if not mappings and field_defs:
        source_name = None
        for p in _PRIORITY_SOURCE_FIELDS:
            if p.lower() in field_name_lookup:
                source_name = field_name_lookup[p.lower()]
                break
        if not source_name:
            source_name = field_defs[0].name

        if source_name:
            mappings.append(
                {
                    "source_field": source_name,
                    "destination_field": "Audio",
                    "confidence": "suggested_default",
                }
            )

    return mappings


def scan_deck_audio(
    *,
    user_id: int,
    deck_id: int,
    admin_mode: bool,
    upload_root: Path,
    note_only: bool = False,
) -> dict[str, Any]:
    """Scan a deck's notes, note types, and media assets for audio generation readiness."""
    from app.repositories.deck_tree_query import collect_subtree_ids

    deck = (
        Deck.query.filter_by(id=deck_id)
        .options(selectinload(Deck.note_type).selectinload(NoteType.field_defs))
        .first()
    )
    if deck is None:
        raise AudioScanError(f"Deck #{deck_id} không tồn tại.", status=404, code="DECK_NOT_FOUND")

    subtree_deck_ids = collect_subtree_ids(deck_id)
    if not subtree_deck_ids:
        subtree_deck_ids = [deck_id]

    notes_query = (
        Note.query.filter(Note.deck_id.in_(subtree_deck_ids))
        .options(
            selectinload(Note.note_type).selectinload(NoteType.field_defs),
            *([] if note_only else [selectinload(Note.cards)]),
            selectinload(Note.media_assets),
        )
        .order_by(Note.created_at.asc())
    )
    if not admin_mode:
        notes_query = notes_query.filter(Note.user_id == user_id)

    notes: list[Note] = notes_query.all()

    # Collect note types from deck and notes
    note_type_map: dict[str, NoteType] = {}
    if deck.note_type and deck.note_type.id:
        note_type_map[deck.note_type.id] = deck.note_type

    for note in notes:
        if note.note_type and note.note_type.id not in note_type_map:
            note_type_map[note.note_type.id] = note.note_type

    # Also query any note_type_ids that weren't loaded
    missing_nt_ids = {note.note_type_id for note in notes if note.note_type_id and note.note_type_id not in note_type_map}
    if missing_nt_ids:
        extra_nts = (
            NoteType.query.filter(NoteType.id.in_(missing_nt_ids))
            .options(selectinload(NoteType.field_defs))
            .all()
        )
        for nt in extra_nts:
            note_type_map[nt.id] = nt

    all_field_defs: list[FieldDef] = []
    seen_field_keys: set[str] = set()
    for nt in note_type_map.values():
        for fd in nt.field_defs or []:
            key = f"{nt.id}:{fd.name}"
            if key not in seen_field_keys:
                seen_field_keys.add(key)
                all_field_defs.append(fd)

    # Check note.field_values for any field names not in FieldDef
    existing_field_names_lower = {f.name.lower() for f in all_field_defs if f.name}
    for note in notes:
        for f_name in (note.field_values or {}).keys():
            if f_name and f_name.lower() not in existing_field_names_lower:
                existing_field_names_lower.add(f_name.lower())
                synthetic_fd = FieldDef(
                    name=f_name,
                    field_type="audio" if ("audio" in f_name.lower() or "sound" in f_name.lower()) else "text",
                    position=len(all_field_defs),
                    required=False,
                )
                all_field_defs.append(synthetic_fd)

    # Compute suggested auto-mappings across note types
    auto_mappings = infer_auto_mappings(all_field_defs)
    mapped_destinations = {m["destination_field"] for m in auto_mappings}

    all_available_field_names = [f.name for f in all_field_defs if f.name]
    if not all_available_field_names:
        all_available_field_names = ["Front", "Back", "Audio"]

    resolved_upload_root = upload_root.resolve()

    note_items: list[dict[str, Any]] = []
    needs_audio_note_ids: set[str] = set()
    missing_count = 0
    broken_count = 0
    valid_count = 0

    for note in notes:
        field_values = dict(note.field_values or {})
        card_id = "" if note_only else (note.cards[0].id if note.cards else "")

        # Determine primary word representation
        word = (
            field_values.get("Word")
            or field_values.get("Front")
            or field_values.get("Expression")
            or field_values.get("Kanji")
            or field_values.get("Reading")
            or field_values.get("Vocabulary")
            or (next(iter(field_values.values())) if field_values else "")
            or note.id
        )
        word = field_value_text(word)

        media_by_field: dict[str, list[MediaAsset]] = {}
        for asset in note.media_assets or []:
            media_by_field.setdefault(asset.field_name, []).append(asset)

        audio_status_map: dict[str, dict[str, Any]] = {}
        note_has_missing = False
        note_has_broken = False

        # Check all destination fields from auto mappings or fields with audio in name/type
        note_field_defs = note.note_type.field_defs if note.note_type else []
        note_field_names = {f.name for f in note_field_defs if f.name}
        if not note_field_names:
            note_field_names = set(field_values.keys())

        dest_fields_to_check = set(mapped_destinations)
        for f in note_field_defs:
            if f.name and (f.field_type == "audio" or "audio" in f.name.lower() or "sound" in f.name.lower()):
                dest_fields_to_check.add(f.name)
        for k in field_values.keys():
            if "audio" in k.lower() or "sound" in k.lower():
                dest_fields_to_check.add(k)

        for dest_field in dest_fields_to_check:
            if dest_field not in note_field_names and dest_field not in field_values:
                continue

            raw_val = str(field_values.get(dest_field) or "").strip()
            field_assets = media_by_field.get(dest_field, [])

            if not raw_val and not field_assets:
                audio_status_map[dest_field] = {
                    "status": "missing",
                    "value": "",
                    "asset_id": None,
                    "url": None,
                }
                note_has_missing = True
                missing_count += 1
            else:
                # Find matching media asset
                matched_asset: MediaAsset | None = None
                if field_assets:
                    for a in field_assets:
                        if a.id == raw_val or a.filename == raw_val:
                            matched_asset = a
                            break
                    if not matched_asset:
                        matched_asset = field_assets[0]

                if matched_asset is not None:
                    # Verify physical file existence
                    full_path = (resolved_upload_root / matched_asset.storage_path).resolve()
                    if full_path.is_file() and full_path.stat().st_size > 0:
                        audio_status_map[dest_field] = {
                            "status": "valid",
                            "value": raw_val or matched_asset.filename,
                            "asset_id": matched_asset.id,
                            "url": f"/media/proxy/{matched_asset.id}",
                            "filename": matched_asset.filename,
                        }
                        valid_count += 1
                    else:
                        audio_status_map[dest_field] = {
                            "status": "broken",
                            "value": raw_val or matched_asset.filename,
                            "asset_id": matched_asset.id,
                            "url": None,
                            "reason": "File âm thanh không tồn tại trên máy chủ",
                        }
                        note_has_broken = True
                        broken_count += 1
                else:
                    # Value is present but no MediaAsset record exists
                    audio_status_map[dest_field] = {
                        "status": "broken",
                        "value": raw_val,
                        "asset_id": None,
                        "url": None,
                        "reason": "Không tìm thấy MediaAsset liên kết với trường",
                    }
                    note_has_broken = True
                    broken_count += 1

        if note_has_missing or note_has_broken:
            needs_audio_note_ids.add(note.id)

        note_items.append(
            {
                "note_id": note.id,
                "card_id": card_id,
                "word": word,
                "note_type_id": note.note_type_id,
                "field_values": field_values,
                "audio_status": audio_status_map,
                "needs_audio": note_has_missing or note_has_broken,
            }
        )

    serialized_note_types = [
        {
            "id": nt.id,
            "name": nt.name,
            "fields": [
                {
                    "name": f.name,
                    "field_type": str(f.field_type or "text"),
                    "position": f.position,
                    "required": bool(f.required),
                }
                for f in (nt.field_defs or [])
            ],
        }
        for nt in note_type_map.values()
    ]

    return {
        "deck": {
            "id": deck.id,
            "name": deck.name,
        },
        "total_notes": len(notes),
        "available_fields": all_available_field_names,
        "summary": {
            "total_notes": len(notes),
            "needs_audio_count": len(needs_audio_note_ids),
            "missing_field_count": missing_count,
            "broken_field_count": broken_count,
            "valid_field_count": valid_count,
        },
        "note_types": serialized_note_types,
        "auto_mappings": auto_mappings,
        "notes": note_items,
    }
