"""Diff calculation, sparse diff generation, and preview generation for deck releases."""

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
    FILTER_OPERATION_ALIASES,
    VISIBLE_ENTITY_KINDS,
    VISIBLE_PUBLISH_STATUSES,
    DeckReleaseError,
    DeckReleaseState,
    NoteReleaseState,
    PublishReleaseResult,
    ReleaseDiffPlan,
    _MISSING,
    _coerce_optional_positive_int,
    _coerce_page_limit,
    _decode_preview_cursor,
    _encode_preview_cursor,
    _get_owned_item,
    _hash_if_present,
    _hash_value,
    _json_bytes,
)
from app.services.release.reconstruct import (
    _build_working_state,
    _chunks,
    _field_def_payload,
    get_field_defs_at_release,
    get_note_field_values_by_id_for_ids_at_release,
    reconstruct_release_state,
)


def _empty_release_state(deck_item_id: str) -> DeckReleaseState:
    return DeckReleaseState(deck_item_id=deck_item_id, sequence_no=0)



def _change_descriptor(
    *,
    change_key: str,
    entity_kind: str,
    entity_id: str,
    field_def_id: str | None,
    field_name: str | None,
    property_key: str,
    before_value: Any,
    after_value: Any,
    before_exists: bool,
    after_exists: bool,
    source_deck_id: int | None,
    sort_key: str,
) -> dict[str, Any]:
    if not before_exists and after_exists:
        operation = "add"
    elif before_exists and not after_exists:
        operation = "remove"
    else:
        operation = "set"
    return {
        "change_key": change_key,
        "entity_kind": entity_kind,
        "entity_id": entity_id,
        "field_def_id": field_def_id,
        "field_name": field_name,
        "property_key": property_key,
        "operation": operation,
        "before_value": None if not before_exists else before_value,
        "after_value": None if not after_exists else after_value,
        "before_hash": _hash_if_present(before_value, exists=before_exists),
        "after_hash": _hash_if_present(after_value, exists=after_exists),
        "source_deck_id": source_deck_id,
        "sort_key": sort_key,
        "_before_exists": before_exists,
        "_after_exists": after_exists,
    }



def _build_atomic_diff(
    *,
    item: DeckMarketplaceItem,
    base_state: DeckReleaseState,
    working_state: DeckReleaseState,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    source_root = int(item.source_deck_id or 0)

    for field_id in sorted(set(base_state.field_defs) | set(working_state.field_defs)):
        before_payload = base_state.field_defs.get(field_id)
        after_payload = working_state.field_defs.get(field_id)
        position = int(
            (after_payload or before_payload or {}).get("position") or 0
        )
        for property_key in FIELD_DEF_PROPERTIES:
            before_exists = before_payload is not None and property_key in before_payload
            after_exists = after_payload is not None and property_key in after_payload
            before_value = (
                before_payload[property_key] if before_exists else _MISSING
            )
            after_value = after_payload[property_key] if after_exists else _MISSING
            if before_exists == after_exists and (
                not before_exists or before_value == after_value
            ):
                continue
            changes.append(
                _change_descriptor(
                    change_key=f"field_def:{field_id}:{property_key}",
                    entity_kind="field_def",
                    entity_id=field_id,
                    field_def_id=field_id,
                    field_name=str(
                        (after_payload or before_payload or {}).get("name") or ""
                    )
                    or None,
                    property_key=property_key,
                    before_value=before_value,
                    after_value=after_value,
                    before_exists=before_exists,
                    after_exists=after_exists,
                    source_deck_id=item.source_deck_id,
                    sort_key=(
                        f"0:{source_root:020d}:{position:010d}:"
                        f"{field_id}:{property_key}"
                    ),
                )
            )

    base_name_to_id = {
        str(payload.get("name")): field_id
        for field_id, payload in base_state.field_defs.items()
        if payload.get("name") is not None
    }
    for note_id in sorted(set(base_state.notes) | set(working_state.notes)):
        before_note = base_state.notes.get(note_id)
        after_note = working_state.notes.get(note_id)
        before_values = dict(before_note.field_values_by_id) if before_note else {}
        after_values = dict(after_note.field_values_by_id) if after_note else {}
        if after_note is not None:
            for field_name, value in after_note.raw_field_values.items():
                fallback_field_id = base_name_to_id.get(str(field_name))
                if fallback_field_id and fallback_field_id not in after_values:
                    after_values[fallback_field_id] = value

        source_deck_id = (
            after_note.source_deck_id
            if after_note is not None
            else before_note.source_deck_id if before_note is not None else None
        )
        for field_id in sorted(set(before_values) | set(after_values)):
            before_exists = field_id in before_values
            after_exists = field_id in after_values
            before_value = before_values.get(field_id, _MISSING)
            after_value = after_values.get(field_id, _MISSING)
            if before_exists == after_exists and (
                not before_exists or before_value == after_value
            ):
                continue
            field_payload = (
                working_state.field_defs.get(field_id)
                or base_state.field_defs.get(field_id)
                or {}
            )
            position = int(field_payload.get("position") or 0)
            property_key = f"field:{field_id}"
            changes.append(
                _change_descriptor(
                    change_key=f"note_field:{note_id}:{field_id}",
                    entity_kind="note_field",
                    entity_id=note_id,
                    field_def_id=field_id,
                    field_name=(
                        str(field_payload.get("name"))
                        if field_payload.get("name") is not None
                        else None
                    ),
                    property_key=property_key,
                    before_value=before_value,
                    after_value=after_value,
                    before_exists=before_exists,
                    after_exists=after_exists,
                    source_deck_id=source_deck_id,
                    sort_key=(
                        f"1:{int(source_deck_id or 0):020d}:{note_id}:"
                        f"{position:010d}:{field_id}"
                    ),
                )
            )

    return sorted(changes, key=lambda row: (row["sort_key"], row["change_key"]))



def _membership_is_active_at(
    membership: DeckReleaseEntityMembership,
    sequence_no: int,
) -> bool:
    return int(membership.introduced_sequence) <= int(sequence_no) and (
        membership.removed_sequence is None
        or int(membership.removed_sequence) > int(sequence_no)
    )



def _membership_payload(
    membership: DeckReleaseEntityMembership,
) -> dict[str, Any]:
    return {
        "source_deck_id": membership.source_deck_id,
        "metadata_json": dict(membership.metadata_json or {}),
    }



def _load_rows_in_chunks(loader, entity_ids: set[str]) -> list[Any]:
    rows: list[Any] = []
    normalized_ids = sorted(entity_ids)
    for entity_id_chunk in _chunks(normalized_ids):
        rows.extend(loader(entity_id_chunk))
    return rows



def _active_memberships_for_keys(
    *,
    deck_item_id: str,
    sequence_no: int,
    entity_ids_by_kind: dict[str, set[str]],
) -> dict[tuple[str, str], DeckReleaseEntityMembership] | None:
    """Load only touched membership intervals; ``None`` means corrupt history."""

    active: dict[tuple[str, str], DeckReleaseEntityMembership] = {}
    for entity_kind, entity_ids in entity_ids_by_kind.items():
        for entity_id_chunk in _chunks(sorted(entity_ids)):
            rows = deck_release_repository.list_memberships_for_entities(
                deck_item_id=deck_item_id,
                entity_kind=entity_kind,
                entity_ids=entity_id_chunk,
            )
            for row in rows:
                if not _membership_is_active_at(row, sequence_no):
                    continue
                key = (str(row.entity_kind), str(row.entity_id))
                if key in active:
                    return None
                active[key] = row
    return active



def _try_build_sparse_diff(
    *,
    item: DeckMarketplaceItem,
    base_release: DeckRelease,
) -> ReleaseDiffPlan | None:
    """Build a subsequent release from the sparse owner working-tree journal.

    The optimization is fail-closed.  Any tracking-revision mismatch, legacy
    name-only dirty row, impossible hash, or overlapping membership interval
    returns ``None`` so callers use the established full-deck comparison.
    """

    working_revision = int(item.working_revision or 0)
    tracked_revision = int(item.dirty_tracking_revision or 0)
    base_working_revision = int(base_release.source_working_revision or 0)
    if tracked_revision != working_revision or working_revision < base_working_revision:
        return None

    dirty_rows = deck_release_repository.list_working_dirty_entities(item.id)
    if working_revision == base_working_revision:
        if dirty_rows:
            return None
        return ReleaseDiffPlan(
            changes=[],
            working_state=None,
            sparse_memberships={},
            strategy="sparse",
        )
    if not dirty_rows:
        return None

    allowed_operations = {"add", "set", "remove", "retire"}
    for row in dirty_rows:
        if (
            str(row.entity_kind) not in VISIBLE_ENTITY_KINDS
            or str(row.operation) not in allowed_operations
            or not row.field_def_id
            or int(row.working_revision or 0) <= base_working_revision
            or int(row.working_revision or 0) > working_revision
        ):
            return None

    note_ids = {
        str(row.entity_id)
        for row in dirty_rows
        if row.entity_kind == "note_field"
    }
    field_ids = {
        str(row.field_def_id or row.entity_id)
        for row in dirty_rows
        if row.entity_kind == "field_def"
    } | {
        str(row.field_def_id)
        for row in dirty_rows
        if row.entity_kind == "note_field" and row.field_def_id
    }
    entity_ids_by_kind = {
        "note": note_ids,
        "field_def": field_ids,
    }
    base_memberships = _active_memberships_for_keys(
        deck_item_id=item.id,
        sequence_no=int(base_release.sequence_no),
        entity_ids_by_kind=entity_ids_by_kind,
    )
    if base_memberships is None:
        return None

    base_field_defs = get_field_defs_at_release(base_release)
    base_note_values = (
        get_note_field_values_by_id_for_ids_at_release(base_release, note_ids)
        if note_ids
        else {}
    )

    current_field_rows = _load_rows_in_chunks(
        deck_release_repository.list_field_defs_by_ids,
        field_ids,
    )
    current_fields = {
        str(row.id): row
        for row in current_field_rows
        if str(row.note_type_id) == str(item.source_note_type_id)
    }
    current_field_defs = {
        field_id: _field_def_payload(row)
        for field_id, row in current_fields.items()
    }
    current_field_id_by_name = {
        str(payload["name"]): field_id
        for field_id, payload in current_field_defs.items()
    }

    source_deck_ids = set(collect_subtree_ids(item.source_deck_id))
    current_note_rows = _load_rows_in_chunks(
        deck_release_repository.list_notes_by_ids,
        note_ids,
    )
    current_notes = {
        str(row.id): row
        for row in current_note_rows
        if int(row.user_id) == int(item.owner_user_id)
        and str(row.note_type_id) == str(item.source_note_type_id)
        and row.deck_id in source_deck_ids
    }
    current_note_values: dict[str, dict[str, Any]] = {}
    for note_id, note in current_notes.items():
        current_note_values[note_id] = {
            current_field_id_by_name[field_name]: value
            for field_name, value in dict(note.field_values or {}).items()
            if field_name in current_field_id_by_name
        }

    sparse_memberships: dict[
        tuple[str, str], dict[str, Any] | None
    ] = {}
    for field_id in field_ids:
        payload = current_field_defs.get(field_id)
        sparse_memberships[("field_def", field_id)] = (
            {
                "source_deck_id": item.source_deck_id,
                "metadata_json": {"name": payload.get("name")},
            }
            if payload is not None
            else None
        )
    for note_id in note_ids:
        note = current_notes.get(note_id)
        sparse_memberships[("note", note_id)] = (
            {
                "source_deck_id": note.deck_id,
                "metadata_json": {"note_type_id": str(note.note_type_id)},
            }
            if note is not None
            else None
        )

    changes: list[dict[str, Any]] = []
    source_root = int(item.source_deck_id or 0)
    for dirty in dirty_rows:
        field_id = str(dirty.field_def_id or "")
        if dirty.entity_kind == "field_def":
            if str(dirty.entity_id) != field_id:
                return None
            property_key = str(dirty.property_key or "")
            if property_key not in FIELD_DEF_PROPERTIES:
                return None
            before_payload = base_field_defs.get(field_id)
            after_payload = current_field_defs.get(field_id)
            before_exists = before_payload is not None and property_key in before_payload
            after_exists = after_payload is not None and property_key in after_payload
            before_value = before_payload[property_key] if before_exists else _MISSING
            after_value = after_payload[property_key] if after_exists else _MISSING
            if after_exists:
                if dirty.current_hash != _hash_value(after_value):
                    return None
            elif dirty.current_hash is not None:
                return None
            if before_exists == after_exists and (
                not before_exists or before_value == after_value
            ):
                continue
            position = int((after_payload or before_payload or {}).get("position") or 0)
            changes.append(
                _change_descriptor(
                    change_key=f"field_def:{field_id}:{property_key}",
                    entity_kind="field_def",
                    entity_id=field_id,
                    field_def_id=field_id,
                    field_name=str(
                        (after_payload or before_payload or {}).get("name") or ""
                    )
                    or None,
                    property_key=property_key,
                    before_value=before_value,
                    after_value=after_value,
                    before_exists=before_exists,
                    after_exists=after_exists,
                    source_deck_id=item.source_deck_id,
                    sort_key=(
                        f"0:{source_root:020d}:{position:010d}:"
                        f"{field_id}:{property_key}"
                    ),
                )
            )
            continue

        note_id = str(dirty.entity_id)
        expected_property_key = f"field:{field_id}"
        if str(dirty.property_key) != expected_property_key:
            return None
        before_values = base_note_values.get(note_id, {})
        after_values = current_note_values.get(note_id, {})
        before_exists = note_id in base_note_values and field_id in before_values
        after_exists = note_id in current_note_values and field_id in after_values
        before_value = before_values[field_id] if before_exists else _MISSING
        after_value = after_values[field_id] if after_exists else _MISSING
        if after_exists:
            if dirty.current_hash != _hash_value(after_value):
                return None
            current_note = current_notes[note_id]
            if (
                dirty.source_deck_id is not None
                and int(dirty.source_deck_id) != int(current_note.deck_id)
            ):
                return None
        elif dirty.current_hash is not None:
            return None
        if before_exists == after_exists and (
            not before_exists or before_value == after_value
        ):
            continue
        field_payload = current_field_defs.get(field_id) or base_field_defs.get(field_id) or {}
        position = int(field_payload.get("position") or 0)
        current_membership = sparse_memberships.get(("note", note_id))
        base_membership = base_memberships.get(("note", note_id))
        source_deck_id = (
            current_membership.get("source_deck_id")
            if current_membership is not None
            else (
                base_membership.source_deck_id
                if base_membership is not None
                else dirty.source_deck_id
            )
        )
        changes.append(
            _change_descriptor(
                change_key=f"note_field:{note_id}:{field_id}",
                entity_kind="note_field",
                entity_id=note_id,
                field_def_id=field_id,
                field_name=(
                    str(field_payload.get("name"))
                    if field_payload.get("name") is not None
                    else None
                ),
                property_key=expected_property_key,
                before_value=before_value,
                after_value=after_value,
                before_exists=before_exists,
                after_exists=after_exists,
                source_deck_id=source_deck_id,
                sort_key=(
                    f"1:{int(source_deck_id or 0):020d}:{note_id}:"
                    f"{position:010d}:{field_id}"
                ),
            )
        )

    return ReleaseDiffPlan(
        changes=sorted(
            changes,
            key=lambda row: (row["sort_key"], row["change_key"]),
        ),
        working_state=None,
        sparse_memberships=sparse_memberships,
        strategy="sparse",
    )



def _build_release_diff_plan(
    *,
    item: DeckMarketplaceItem,
    include_initial_checkpoint_state: bool = True,
) -> ReleaseDiffPlan:
    base_release = item.current_release
    if base_release is not None:
        sparse_plan = _try_build_sparse_diff(
            item=item,
            base_release=base_release,
        )
        if sparse_plan is not None:
            return sparse_plan
        base_state = reconstruct_release_state(base_release)
        working_state = _build_working_state(item)
        return ReleaseDiffPlan(
            changes=_build_atomic_diff(
                item=item,
                base_state=base_state,
                working_state=working_state,
            ),
            working_state=working_state,
            sparse_memberships=None,
            strategy="full",
        )

    base_state = _empty_release_state(str(item.id))
    preserve_legacy_diff = (
        deck_release_repository.has_legacy_install_without_release(str(item.id))
    )
    working_state = _build_working_state(
        item,
        include_notes=(preserve_legacy_diff or include_initial_checkpoint_state),
    )
    baseline_note_count = (
        len(working_state.notes)
        if working_state.notes
        else deck_release_repository.count_source_notes(item)
    )
    diff_working_state = working_state
    baseline_mode = "atomic" if preserve_legacy_diff else "checkpoint"
    if not preserve_legacy_diff:
        diff_working_state = DeckReleaseState(
            deck_item_id=working_state.deck_item_id,
            sequence_no=working_state.sequence_no,
            field_defs=working_state.field_defs,
            notes={},
        )
    return ReleaseDiffPlan(
        changes=_build_atomic_diff(
            item=item,
            base_state=base_state,
            working_state=diff_working_state,
        ),
        working_state=working_state,
        sparse_memberships=None,
        strategy="full",
        initial_baseline_mode=baseline_mode,
        baseline_note_count=baseline_note_count,
    )



def _summary_for_changes(changes: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "change_count": len(changes),
        "entity_count": len(
            {(row["entity_kind"], row["entity_id"]) for row in changes}
        ),
        "added_count": sum(row["operation"] == "add" for row in changes),
        "modified_count": sum(row["operation"] == "set" for row in changes),
        "removed_count": sum(row["operation"] == "remove" for row in changes),
    }



def _serialize_change_dict(change: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in change.items()
        if not str(key).startswith("_")
    }



def _matches_preview_filters(
    change: dict[str, Any],
    *,
    entity_kind: str | None,
    operation: str | None,
    source_deck_id: int | None,
    query_text: str | None,
) -> bool:
    if entity_kind and change["entity_kind"] != entity_kind:
        return False
    if operation and change["operation"] != operation:
        return False
    if source_deck_id is not None and change["source_deck_id"] != source_deck_id:
        return False
    normalized_query = (query_text or "").strip().lower()
    if not normalized_query:
        return True
    haystack = " ".join(
        [
            str(change.get("change_key") or ""),
            str(change.get("entity_id") or ""),
            str(change.get("property_key") or ""),
            json.dumps(change.get("before_value"), ensure_ascii=False, default=str),
            json.dumps(change.get("after_value"), ensure_ascii=False, default=str),
        ]
    ).lower()
    return normalized_query in haystack



def preview_release(
    *,
    deck_item_id: str,
    user_id: int,
    cursor: str | None = None,
    limit: Any = None,
    entity_kind: str | None = None,
    operation: str | None = None,
    source_deck_id: Any = None,
    query_text: str | None = None,
) -> dict[str, Any]:
    item = _get_owned_item(deck_item_id=deck_item_id, user_id=user_id)
    normalized_kind = (entity_kind or "").strip() or None
    if normalized_kind and normalized_kind not in VISIBLE_ENTITY_KINDS:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            "type must be note_field or field_def.",
            field="type",
        )
    normalized_operation = (operation or "").strip().lower() or None
    if normalized_operation:
        normalized_operation = FILTER_OPERATION_ALIASES.get(normalized_operation)
        if not normalized_operation:
            raise DeckReleaseError(
                "VALIDATION_ERROR",
                "operation must be added, modified, removed, add, set, remove, or conflict.",
                field="operation",
            )
    normalized_deck_id = _coerce_optional_positive_int(
        source_deck_id,
        field_name="deck_id",
    )
    page_limit = _coerce_page_limit(limit)
    decoded_cursor = _decode_preview_cursor(cursor)
    working_revision = int(item.working_revision or 0)
    if decoded_cursor is not None and decoded_cursor[0] != working_revision:
        raise DeckReleaseError(
            "WORKING_REVISION_STALE",
            "The owner working revision changed. Refresh the preview.",
            status=409,
            field="cursor",
        )

    base_release = item.current_release
    diff_plan = _build_release_diff_plan(
        item=item,
        include_initial_checkpoint_state=False,
    )
    all_changes = diff_plan.changes
    filtered = [
        row
        for row in all_changes
        if _matches_preview_filters(
            row,
            entity_kind=normalized_kind,
            operation=normalized_operation,
            source_deck_id=normalized_deck_id,
            query_text=query_text,
        )
    ]
    if decoded_cursor is not None:
        cursor_position = (decoded_cursor[1], decoded_cursor[2])
        filtered = [
            row
            for row in filtered
            if (str(row["sort_key"]), str(row["change_key"])) > cursor_position
        ]
    page = filtered[: page_limit + 1]
    has_more = len(page) > page_limit
    page = page[:page_limit]
    next_cursor = (
        _encode_preview_cursor(
            working_revision,
            page[-1]["sort_key"],
            page[-1]["change_key"],
        )
        if has_more and page
        else None
    )
    summary = _summary_for_changes(all_changes)
    if diff_plan.baseline_note_count is not None:
        summary["baseline_note_count"] = int(diff_plan.baseline_note_count)
    from app.services.release.query import serialize_release
    return {
        "deck_item_id": str(item.id),
        "deck_title": item.title,
        "base_release": serialize_release(base_release) if base_release else None,
        "working_revision": working_revision,
        "snapshot_revision": str(working_revision),
        "summary": summary,
        "initial_baseline_mode": diff_plan.initial_baseline_mode,
        "items": [_serialize_change_dict(row) for row in page],
        "next_cursor": next_cursor,
    }



