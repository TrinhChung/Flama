"""State reconstruction and historical note field resolution for releases."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import joinedload

from app.repositories import (
    deck_release_repository,
    flashcards_share_repository,
    vocabulary_repository,
)
from app.repositories.deck_tree_query import collect_subtree_ids
from models import db
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType

logger = logging.getLogger(__name__)

VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}
VISIBLE_ENTITY_KINDS = {"note_field", "field_def"}
FILTER_OPERATION_ALIASES = {
    "add": "add",
    "added": "add",
    "set": "set",
    "modified": "set",
    "remove": "remove",
    "removed": "remove",
    "conflict": "conflict",
}
FIELD_DEF_PROPERTIES = (
    "name",
    "field_type",
    "position",
    "required",
    "identity_role",
)
DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 200
MAX_IDEMPOTENCY_KEY_LENGTH = 64
MAX_VERSION_LABEL_LENGTH = 50
_MISSING = object()


from app.services.release.base import (
    FIELD_DEF_PROPERTIES,
    VISIBLE_ENTITY_KINDS,
    VISIBLE_PUBLISH_STATUSES,
    DeckReleaseError,
    DeckReleaseState,
    NoteReleaseState,
    _MISSING,
    _get_visible_item,
    _get_visible_release,
    _json_bytes,
)


def _field_def_payload(field_def: Any) -> dict[str, Any]:
    return {
        "name": field_def.name,
        "field_type": field_def.field_type,
        "position": int(field_def.position or 0),
        "required": bool(field_def.required),
        "identity_role": field_def.identity_role,
    }



def _build_working_state(
    item: DeckMarketplaceItem,
    *,
    include_notes: bool = True,
) -> DeckReleaseState:
    if item.source_deck_id is None:
        raise DeckReleaseError(
            "SOURCE_DECK_REQUIRED",
            "Shared deck no longer has a source deck.",
            status=409,
        )
    if not item.source_note_type_id:
        raise DeckReleaseError(
            "SOURCE_NOTE_TYPE_REQUIRED",
            "A source note type is required for release V1.",
            status=409,
        )

    field_rows = deck_release_repository.list_source_field_defs(item)
    field_defs = {str(row.id): _field_def_payload(row) for row in field_rows}
    notes: dict[str, NoteReleaseState] = {}
    if include_notes:
        field_id_by_name = {
            str(payload["name"]): field_id
            for field_id, payload in field_defs.items()
        }
        for note in deck_release_repository.list_source_notes(item):
            raw_values = dict(note.field_values or {})
            values_by_id = {
                field_id_by_name[field_name]: value
                for field_name, value in raw_values.items()
                if field_name in field_id_by_name
            }
            notes[str(note.id)] = NoteReleaseState(
                source_note_id=str(note.id),
                source_deck_id=int(note.deck_id) if note.deck_id is not None else None,
                note_type_id=str(note.note_type_id) if note.note_type_id else None,
                field_values_by_id=values_by_id,
                raw_field_values=raw_values,
                tags=list(note.tags or []),
            )

    return DeckReleaseState(
        deck_item_id=str(item.id),
        sequence_no=0,
        field_defs=field_defs,
        notes=notes,
    )



def _apply_field_change(
    field_defs: dict[str, dict[str, Any]],
    change: DeckReleaseChange,
) -> None:
    field_id = str(change.field_def_id or change.entity_id)
    if change.operation in {"add", "set"}:
        field_defs.setdefault(field_id, {})[str(change.property_key)] = change.after_value
        return
    if change.operation == "remove":
        payload = field_defs.get(field_id)
        if payload is not None:
            payload.pop(str(change.property_key), None)



def _field_defs_at_sequence(
    field_changes: list[DeckReleaseChange],
    sequence_no: int,
) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for change in field_changes:
        if int(change.release_sequence_no) > sequence_no:
            break
        _apply_field_change(state, change)
    return state



def reconstruct_release_state(release_or_id: DeckRelease | str) -> DeckReleaseState:
    """Reconstruct field-def and note-field state at a published release."""

    release = (
        release_or_id
        if isinstance(release_or_id, DeckRelease)
        else deck_release_repository.get_release(str(release_or_id))
    )
    if not release or release.status != "published":
        raise DeckReleaseError(
            "RELEASE_NOT_FOUND",
            "Release not found.",
            status=404,
        )

    target_sequence = int(release.sequence_no)
    history = deck_release_repository.list_release_history_changes(
        deck_item_id=release.deck_item_id,
        through_sequence=target_sequence,
        entity_kinds=VISIBLE_ENTITY_KINDS,
    )
    field_changes = [row for row in history if row.entity_kind == "field_def"]
    note_changes = [row for row in history if row.entity_kind == "note_field"]
    target_field_defs = _field_defs_at_sequence(field_changes, target_sequence)

    latest_checkpoints: dict[str, DeckReleaseNoteCheckpoint] = {}
    for checkpoint in deck_release_repository.list_note_checkpoints(
        deck_item_id=release.deck_item_id,
        through_sequence=target_sequence,
    ):
        latest_checkpoints[str(checkpoint.source_note_id)] = checkpoint

    notes: dict[str, NoteReleaseState] = {}
    field_state_cache: dict[int, dict[str, dict[str, Any]]] = {}
    for note_id, checkpoint in latest_checkpoints.items():
        checkpoint_sequence = int(checkpoint.release_sequence_no)
        checkpoint_field_defs = field_state_cache.get(checkpoint_sequence)
        if checkpoint_field_defs is None:
            checkpoint_field_defs = _field_defs_at_sequence(
                field_changes,
                checkpoint_sequence,
            )
            field_state_cache[checkpoint_sequence] = checkpoint_field_defs
        field_id_by_name = {
            str(payload.get("name")): field_id
            for field_id, payload in checkpoint_field_defs.items()
            if payload.get("name") is not None
        }
        raw_values = dict(checkpoint.field_values or {})
        values_by_id = {
            field_id_by_name[field_name]: value
            for field_name, value in raw_values.items()
            if field_name in field_id_by_name
        }
        notes[note_id] = NoteReleaseState(
            source_note_id=note_id,
            source_deck_id=(
                int(checkpoint.source_deck_id)
                if checkpoint.source_deck_id is not None
                else None
            ),
            note_type_id=str(checkpoint.note_type_id),
            field_values_by_id=values_by_id,
            raw_field_values=raw_values,
            tags=list(checkpoint.tags or []),
            checkpoint_sequence=checkpoint_sequence,
        )

    memberships = deck_release_repository.list_memberships(release.deck_item_id)
    active_note_ids: set[str] = set()
    active_field_ids: set[str] = set()
    membership_by_note: dict[str, DeckReleaseEntityMembership] = {}
    for membership in memberships:
        active = int(membership.introduced_sequence) <= target_sequence and (
            membership.removed_sequence is None
            or int(membership.removed_sequence) > target_sequence
        )
        if not active:
            continue
        if membership.entity_kind == "note":
            note_id = str(membership.entity_id)
            active_note_ids.add(note_id)
            membership_by_note[note_id] = membership
        elif membership.entity_kind == "field_def":
            active_field_ids.add(str(membership.entity_id))

    for change in note_changes:
        note_id = str(change.entity_id)
        note_state = notes.get(note_id)
        if (
            note_state is not None
            and int(change.release_sequence_no) <= note_state.checkpoint_sequence
        ):
            continue
        if note_state is None:
            membership = membership_by_note.get(note_id)
            metadata = (
                dict(membership.metadata_json or {})
                if membership is not None
                else {}
            )
            note_state = NoteReleaseState(
                source_note_id=note_id,
                source_deck_id=(
                    int(change.source_deck_id)
                    if change.source_deck_id is not None
                    else (
                        int(membership.source_deck_id)
                        if membership is not None and membership.source_deck_id is not None
                        else None
                    )
                ),
                note_type_id=(
                    str(metadata.get("note_type_id"))
                    if metadata.get("note_type_id")
                    else None
                ),
            )
            notes[note_id] = note_state
        field_id = str(change.field_def_id or "")
        if not field_id:
            continue
        if change.operation in {"add", "set"}:
            note_state.field_values_by_id[field_id] = change.after_value
        elif change.operation == "remove":
            note_state.field_values_by_id.pop(field_id, None)

    for note_id in active_note_ids:
        if note_id in notes:
            continue
        membership = membership_by_note[note_id]
        metadata = dict(membership.metadata_json or {})
        notes[note_id] = NoteReleaseState(
            source_note_id=note_id,
            source_deck_id=(
                int(membership.source_deck_id)
                if membership.source_deck_id is not None
                else None
            ),
            note_type_id=(
                str(metadata.get("note_type_id"))
                if metadata.get("note_type_id")
                else None
            ),
        )

    if memberships:
        notes = {
            note_id: note_state
            for note_id, note_state in notes.items()
            if note_id in active_note_ids
        }
        target_field_defs = {
            field_id: payload
            for field_id, payload in target_field_defs.items()
            if field_id in active_field_ids
        }

    return DeckReleaseState(
        deck_item_id=str(release.deck_item_id),
        sequence_no=target_sequence,
        field_defs=target_field_defs,
        notes=notes,
    )



def _resolve_published_release(release_or_id: DeckRelease | str) -> DeckRelease:
    release = (
        release_or_id
        if isinstance(release_or_id, DeckRelease)
        else deck_release_repository.get_release(str(release_or_id))
    )
    if not release or release.status != "published":
        raise DeckReleaseError(
            "RELEASE_NOT_FOUND",
            "Release not found.",
            status=404,
        )
    return release



def get_field_defs_at_release(
    release_or_id: DeckRelease | str,
) -> dict[str, dict[str, Any]]:
    """Return active field-definition properties keyed by stable FieldDef ID."""

    release = _resolve_published_release(release_or_id)
    target_sequence = int(release.sequence_no)
    field_changes = deck_release_repository.list_release_history_changes(
        deck_item_id=release.deck_item_id,
        through_sequence=target_sequence,
        entity_kinds=["field_def"],
    )
    field_defs = _field_defs_at_sequence(field_changes, target_sequence)
    memberships = deck_release_repository.list_memberships_for_entities(
        deck_item_id=release.deck_item_id,
        entity_kind="field_def",
    )
    if not memberships:
        return field_defs
    active_ids = {
        str(row.entity_id)
        for row in memberships
        if int(row.introduced_sequence) <= target_sequence
        and (
            row.removed_sequence is None
            or int(row.removed_sequence) > target_sequence
        )
    }
    return {
        field_id: payload
        for field_id, payload in field_defs.items()
        if field_id in active_ids
    }



def _chunks(values: list[str], size: int = 500):
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]



def _get_note_field_values_by_id_for_ids_at_release(
    release_or_id: DeckRelease | str,
    note_ids: list[str] | tuple[str, ...] | set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Batch reconstruct selected notes keyed by stable FieldDef identity.

    Missing keys mean the requested note is not a member of the target release.
    A field removed at the target release is omitted from that note's value map.
    """

    release = _resolve_published_release(release_or_id)
    requested_ids = sorted({str(note_id) for note_id in note_ids if note_id})
    if not requested_ids:
        return {}, get_field_defs_at_release(release)

    target_sequence = int(release.sequence_no)
    field_changes = deck_release_repository.list_release_history_changes(
        deck_item_id=release.deck_item_id,
        through_sequence=target_sequence,
        entity_kinds=["field_def"],
    )
    target_field_defs = _field_defs_at_sequence(field_changes, target_sequence)
    active_field_memberships = deck_release_repository.list_memberships_for_entities(
        deck_item_id=release.deck_item_id,
        entity_kind="field_def",
    )
    if active_field_memberships:
        active_field_ids = {
            str(row.entity_id)
            for row in active_field_memberships
            if int(row.introduced_sequence) <= target_sequence
            and (
                row.removed_sequence is None
                or int(row.removed_sequence) > target_sequence
            )
        }
        target_field_defs = {
            field_id: payload
            for field_id, payload in target_field_defs.items()
            if field_id in active_field_ids
        }

    checkpoints: list[DeckReleaseNoteCheckpoint] = []
    note_changes: list[DeckReleaseChange] = []
    note_memberships: list[DeckReleaseEntityMembership] = []
    for note_id_chunk in _chunks(requested_ids):
        checkpoints.extend(
            deck_release_repository.list_note_checkpoints_for_ids(
                deck_item_id=release.deck_item_id,
                through_sequence=target_sequence,
                note_ids=note_id_chunk,
            )
        )
        note_changes.extend(
            deck_release_repository.list_note_field_history_for_ids(
                deck_item_id=release.deck_item_id,
                through_sequence=target_sequence,
                note_ids=note_id_chunk,
            )
        )
        note_memberships.extend(
            deck_release_repository.list_memberships_for_entities(
                deck_item_id=release.deck_item_id,
                entity_kind="note",
                entity_ids=note_id_chunk,
            )
        )

    latest_checkpoints: dict[str, DeckReleaseNoteCheckpoint] = {}
    for checkpoint in checkpoints:
        latest_checkpoints[str(checkpoint.source_note_id)] = checkpoint

    membership_by_id = {
        str(row.entity_id): row
        for row in note_memberships
        if int(row.introduced_sequence) <= target_sequence
        and (
            row.removed_sequence is None
            or int(row.removed_sequence) > target_sequence
        )
    }
    active_note_ids = set(membership_by_id)
    field_state_cache: dict[int, dict[str, dict[str, Any]]] = {}
    values_by_note: dict[str, dict[str, Any]] = {}
    checkpoint_sequence_by_note: dict[str, int] = {}
    for note_id, checkpoint in latest_checkpoints.items():
        if note_memberships and note_id not in active_note_ids:
            continue
        checkpoint_sequence = int(checkpoint.release_sequence_no)
        checkpoint_sequence_by_note[note_id] = checkpoint_sequence
        checkpoint_field_defs = field_state_cache.get(checkpoint_sequence)
        if checkpoint_field_defs is None:
            checkpoint_field_defs = _field_defs_at_sequence(
                field_changes,
                checkpoint_sequence,
            )
            field_state_cache[checkpoint_sequence] = checkpoint_field_defs
        field_id_by_name = {
            str(payload.get("name")): field_id
            for field_id, payload in checkpoint_field_defs.items()
            if payload.get("name") is not None
        }
        values_by_note[note_id] = {
            field_id_by_name[field_name]: value
            for field_name, value in dict(checkpoint.field_values or {}).items()
            if field_name in field_id_by_name
        }

    for note_id in active_note_ids:
        values_by_note.setdefault(note_id, {})

    for change in note_changes:
        note_id = str(change.entity_id)
        if note_memberships and note_id not in active_note_ids:
            continue
        if int(change.release_sequence_no) <= checkpoint_sequence_by_note.get(
            note_id, 0
        ):
            continue
        field_id = str(change.field_def_id or "")
        if not field_id:
            continue
        note_values = values_by_note.setdefault(note_id, {})
        if change.operation in {"add", "set"}:
            note_values[field_id] = change.after_value
        elif change.operation == "remove":
            note_values.pop(field_id, None)

    if not note_memberships:
        # Compatibility for early/partial release rows created before membership
        # backfill: checkpoints/changes still establish note visibility.
        active_note_ids = set(values_by_note)

    result: dict[str, dict[str, Any]] = {}
    for note_id in active_note_ids:
        note_values = values_by_note.get(note_id, {})
        result[note_id] = {
            field_id: value
            for field_id, value in note_values.items()
            if field_id in target_field_defs
        }
    return result, target_field_defs



def get_note_field_values_by_id_for_ids_at_release(
    release_or_id: DeckRelease | str,
    note_ids: list[str] | tuple[str, ...] | set[str],
) -> dict[str, dict[str, Any]]:
    """Return selected release note values keyed by stable FieldDef ID."""

    values_by_note, _ = _get_note_field_values_by_id_for_ids_at_release(
        release_or_id,
        note_ids,
    )
    return values_by_note



def get_note_values_for_ids_at_release(
    release_or_id: DeckRelease | str,
    note_ids: list[str] | tuple[str, ...] | set[str],
) -> dict[str, dict[str, Any]]:
    """Return selected visible notes keyed by their names at the release."""

    values_by_note, target_field_defs = (
        _get_note_field_values_by_id_for_ids_at_release(
            release_or_id,
            note_ids,
        )
    )
    return {
        note_id: {
            str(target_field_defs[field_id]["name"]): value
            for field_id, value in note_values.items()
            if field_id in target_field_defs
            and target_field_defs[field_id].get("name") is not None
        }
        for note_id, note_values in values_by_note.items()
    }



def get_note_values_at_release(
    release_or_id: DeckRelease | str,
    note_id: str,
) -> dict[str, Any] | None:
    """Return a note's name-keyed values at a release, or ``None`` if hidden."""

    values_by_note = get_note_values_for_ids_at_release(
        release_or_id,
        [str(note_id)],
    )
    return values_by_note.get(str(note_id))



