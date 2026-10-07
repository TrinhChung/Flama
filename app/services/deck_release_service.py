"""Immutable release orchestration for shared marketplace decks.

Release atoms cover source fields and immutable template presentation pins.
Source Note/Card identities stay untouched; templates inherit through their
separate per-user subscriptions.

The service never commits or rolls back.  HTTP/CLI adapters own transactions.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.repositories import deck_release_repository
from app.repositories.deck_tree_query import collect_subtree_ids
from app.services import release_core
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint


VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}
VISIBLE_ENTITY_KINDS = {"note_field", "field_def", "template"}
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


class DeckReleaseError(Exception):
    """Stable application error surfaced by the release HTTP adapter."""

    def __init__(
        self,
        error: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.status = status
        self.field = field


@dataclass
class NoteReleaseState:
    source_note_id: str
    source_deck_id: int | None
    note_type_id: str | None
    field_values_by_id: dict[str, Any] = field(default_factory=dict)
    raw_field_values: dict[str, Any] = field(default_factory=dict)
    tags: list[Any] = field(default_factory=list)
    checkpoint_sequence: int = 0


@dataclass
class DeckReleaseState:
    deck_item_id: str
    sequence_no: int
    field_defs: dict[str, dict[str, Any]] = field(default_factory=dict)
    notes: dict[str, NoteReleaseState] = field(default_factory=dict)


@dataclass(frozen=True)
class PublishReleaseResult:
    release: DeckRelease
    replayed: bool


@dataclass
class ReleaseDiffPlan:
    changes: list[dict[str, Any]]
    working_state: DeckReleaseState | None
    sparse_memberships: dict[tuple[str, str], dict[str, Any] | None] | None
    strategy: str
    initial_baseline_mode: str | None = None
    baseline_note_count: int | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _hash_value(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _hash_if_present(value: Any, *, exists: bool) -> str | None:
    if not exists:
        return None
    return _hash_value(value)


def _coerce_page_limit(raw_limit: Any) -> int:
    if raw_limit is None or str(raw_limit).strip() == "":
        return DEFAULT_PAGE_LIMIT
    try:
        parsed = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            "limit must be an integer.",
            field="limit",
        ) from exc
    if parsed < 1 or parsed > MAX_PAGE_LIMIT:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            f"limit must be between 1 and {MAX_PAGE_LIMIT}.",
            field="limit",
        )
    return parsed


def _coerce_optional_positive_int(raw_value: Any, *, field_name: str) -> int | None:
    if raw_value is None or str(raw_value).strip() == "":
        return None
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            f"{field_name} must be an integer.",
            field=field_name,
        ) from exc
    if parsed < 1:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            f"{field_name} must be a positive integer.",
            field=field_name,
        )
    return parsed


def _encode_preview_cursor(
    snapshot_revision: int,
    sort_key: str,
    change_key: str,
) -> str:
    encoded = base64.urlsafe_b64encode(
        _json_bytes([int(snapshot_revision), str(sort_key), str(change_key)])
    ).decode("ascii")
    return encoded.rstrip("=")


def _decode_preview_cursor(cursor: str | None) -> tuple[int, str, str] | None:
    normalized = (cursor or "").strip()
    if not normalized:
        return None
    try:
        padded = normalized + ("=" * (-len(normalized) % 4))
        decoded = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if not isinstance(decoded, list) or len(decoded) != 3:
            raise ValueError("invalid cursor payload")
        return int(decoded[0]), str(decoded[1]), str(decoded[2])
    except (ValueError, TypeError, UnicodeDecodeError, binascii.Error) as exc:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            "cursor is invalid.",
            field="cursor",
        ) from exc


def _get_owned_item(*, deck_item_id: str, user_id: int, lock: bool = False) -> DeckMarketplaceItem:
    item = deck_release_repository.get_deck_item(
        deck_item_id,
        for_update=lock,
    )
    if not item or int(item.owner_user_id) != int(user_id):
        raise DeckReleaseError(
            "DECK_NOT_FOUND",
            "Shared deck not found.",
            status=404,
        )
    return item


def _get_visible_item(*, deck_item_id: str, user_id: int) -> DeckMarketplaceItem:
    item = deck_release_repository.get_deck_item(deck_item_id)
    if not item:
        raise DeckReleaseError(
            "DECK_NOT_FOUND",
            "Shared deck not found.",
            status=404,
        )
    is_owner = int(item.owner_user_id) == int(user_id)
    if not is_owner and str(item.publish_status or "").lower() not in VISIBLE_PUBLISH_STATUSES:
        raise DeckReleaseError(
            "DECK_NOT_FOUND",
            "Shared deck not found.",
            status=404,
        )
    return item


def _get_visible_release(
    *,
    item: DeckMarketplaceItem,
    release_id: str,
    user_id: int,
) -> DeckRelease:
    release = deck_release_repository.get_release_for_item(
        deck_item_id=item.id,
        release_id=release_id,
    )
    is_owner = int(item.owner_user_id) == int(user_id)
    if not release or (release.status != "published" and not is_owner):
        raise DeckReleaseError(
            "RELEASE_NOT_FOUND",
            "Release not found.",
            status=404,
        )
    return release


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
    plan = _build_content_release_diff_plan(item=item, include_initial_checkpoint_state=include_initial_checkpoint_state)
    from models import db
    from app.services.template_release_service import deck_template_presentations
    before = deck_template_presentations(db.session, note_type_id=item.source_note_type_id, release_id=item.current_release_id) if item.current_release_id else {}
    after = deck_template_presentations(db.session, note_type_id=item.source_note_type_id)
    for template_id in sorted(set(before) | set(after)):
        if template_id in before and template_id in after and release_core.same(before[template_id], after[template_id]):
            continue
        plan.changes.append(_change_descriptor(
            change_key=f"template:{template_id}:presentation", entity_kind="template", entity_id=template_id,
            field_def_id=None, field_name=None, property_key="presentation",
            before_exists=template_id in before, after_exists=template_id in after,
            before_value=before.get(template_id), after_value=after.get(template_id),
            source_deck_id=item.source_deck_id, sort_key=f"template:{template_id}",
        ))
    plan.changes.sort(key=lambda row: (str(row["sort_key"]), str(row["change_key"])))
    return plan


def _build_content_release_diff_plan(
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
            "type must be note_field, field_def, or template.",
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


def _normalize_version_label(raw_value: Any) -> str:
    version_label = str(raw_value or "").strip()
    if not version_label:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            "version_label is required.",
            field="version_label",
        )
    if len(version_label) > MAX_VERSION_LABEL_LENGTH:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            f"version_label must be at most {MAX_VERSION_LABEL_LENGTH} characters.",
            field="version_label",
        )
    return version_label


def _normalize_idempotency_key(raw_value: Any) -> str:
    idempotency_key = str(raw_value or "").strip()
    if not idempotency_key:
        raise DeckReleaseError(
            "IDEMPOTENCY_KEY_REQUIRED",
            "Idempotency-Key header is required.",
            field="Idempotency-Key",
        )
    if len(idempotency_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            f"Idempotency-Key must be at most {MAX_IDEMPOTENCY_KEY_LENGTH} characters.",
            field="Idempotency-Key",
        )
    return idempotency_key


def _normalize_expected_working_revision(raw_value: Any) -> int | None:
    if raw_value is None:
        return None
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            "expected_working_revision must be an integer.",
            field="expected_working_revision",
        ) from exc
    if parsed < 0:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            "expected_working_revision must be zero or greater.",
            field="expected_working_revision",
        )
    return parsed


def _release_manifest_hash(changes: list[dict[str, Any]]) -> str:
    manifest = [
        {
            key: value
            for key, value in change.items()
            if key
            in {
                "change_key",
                "entity_kind",
                "entity_id",
                "field_def_id",
                "property_key",
                "operation",
                "before_hash",
                "after_hash",
                "source_deck_id",
            }
        }
        for change in changes
    ]
    return _hash_value(manifest)


def _checkpoint_hash(*, field_values: dict[str, Any], tags: list[Any]) -> str:
    return _hash_value({"field_values": field_values, "tags": tags})


def _initial_release_manifest_hash(
    *,
    changes: list[dict[str, Any]],
    checkpoints: list[DeckReleaseNoteCheckpoint],
) -> str:
    """Commit initial checkpoint content when note atoms are compacted away."""

    digest = hashlib.sha256()
    digest.update(b"deck-initial-release-v1\0")
    digest.update(_release_manifest_hash(changes).encode("ascii"))
    for checkpoint in sorted(
        checkpoints,
        key=lambda row: str(row.source_note_id),
    ):
        digest.update(b"\0")
        digest.update(
            _json_bytes(
                {
                    "source_note_id": str(checkpoint.source_note_id),
                    "source_deck_id": checkpoint.source_deck_id,
                    "note_type_id": str(checkpoint.note_type_id),
                    "content_hash": checkpoint.content_hash,
                }
            )
        )
    return digest.hexdigest()


def _build_release_change_rows(
    *,
    release: DeckRelease,
    changes: list[dict[str, Any]],
) -> list[DeckReleaseChange]:
    return [
        DeckReleaseChange(
            release_id=release.id,
            release_sequence_no=int(release.sequence_no),
            change_key=row["change_key"],
            entity_kind=row["entity_kind"],
            entity_id=row["entity_id"],
            field_def_id=row["field_def_id"],
            property_key=row["property_key"],
            operation=row["operation"],
            before_value=row["before_value"],
            after_value=row["after_value"],
            before_hash=row["before_hash"],
            after_hash=row["after_hash"],
            source_deck_id=row["source_deck_id"],
            sort_key=row["sort_key"],
        )
        for row in changes
    ]


def _create_initial_checkpoints(
    *,
    release: DeckRelease,
    working_state: DeckReleaseState,
) -> list[DeckReleaseNoteCheckpoint]:
    checkpoints: list[DeckReleaseNoteCheckpoint] = []
    for note in working_state.notes.values():
        raw_values = dict(note.raw_field_values or {})
        tags = list(note.tags or [])
        checkpoints.append(
            DeckReleaseNoteCheckpoint(
                release_id=release.id,
                release_sequence_no=int(release.sequence_no),
                source_note_id=note.source_note_id,
                source_deck_id=note.source_deck_id,
                note_type_id=str(note.note_type_id or ""),
                field_values=raw_values,
                tags=tags,
                content_hash=_checkpoint_hash(
                    field_values=raw_values,
                    tags=tags,
                ),
            )
        )
    return checkpoints


def _sync_memberships(
    *,
    item: DeckMarketplaceItem,
    sequence_no: int,
    working_state: DeckReleaseState,
) -> None:
    existing_rows = deck_release_repository.list_memberships(item.id)
    active_existing = {
        (row.entity_kind, str(row.entity_id)): row
        for row in existing_rows
        if row.removed_sequence is None
    }
    current: dict[tuple[str, str], dict[str, Any]] = {}
    for field_id, payload in working_state.field_defs.items():
        current[("field_def", field_id)] = {
            "source_deck_id": item.source_deck_id,
            "metadata_json": {"name": payload.get("name")},
        }
    for note_id, note in working_state.notes.items():
        current[("note", note_id)] = {
            "source_deck_id": note.source_deck_id,
            "metadata_json": {"note_type_id": note.note_type_id},
        }

    for key, payload in current.items():
        membership = active_existing.get(key)
        membership_changed = bool(
            membership is not None
            and (
                membership.source_deck_id != payload["source_deck_id"]
                or dict(membership.metadata_json or {}) != payload["metadata_json"]
            )
        )
        if membership_changed:
            membership.removed_sequence = sequence_no
            membership = None
        if membership is None:
            membership = DeckReleaseEntityMembership(
                deck_item_id=item.id,
                entity_kind=key[0],
                entity_id=key[1],
                source_deck_id=payload["source_deck_id"],
                introduced_sequence=sequence_no,
                removed_sequence=None,
                metadata_json=payload["metadata_json"],
            )
            deck_release_repository.add_membership(membership)

    for key, membership in active_existing.items():
        if key not in current and membership.removed_sequence is None:
            membership.removed_sequence = sequence_no


def _sync_sparse_memberships(
    *,
    item: DeckMarketplaceItem,
    sequence_no: int,
    current: dict[tuple[str, str], dict[str, Any] | None],
) -> None:
    """Update only membership intervals touched by a trusted sparse journal."""

    entity_ids_by_kind: dict[str, set[str]] = {}
    for entity_kind, entity_id in current:
        entity_ids_by_kind.setdefault(entity_kind, set()).add(entity_id)

    active_existing: dict[tuple[str, str], DeckReleaseEntityMembership] = {}
    for entity_kind, entity_ids in entity_ids_by_kind.items():
        for entity_id_chunk in _chunks(sorted(entity_ids)):
            rows = deck_release_repository.list_memberships_for_entities(
                deck_item_id=item.id,
                entity_kind=entity_kind,
                entity_ids=entity_id_chunk,
            )
            for row in rows:
                if row.removed_sequence is not None:
                    continue
                key = (str(row.entity_kind), str(row.entity_id))
                if key in active_existing:
                    raise DeckReleaseError(
                        "MEMBERSHIP_HISTORY_INVALID",
                        "The release membership history has overlapping active intervals.",
                        status=409,
                    )
                active_existing[key] = row

    for key, payload in current.items():
        membership = active_existing.get(key)
        unchanged = bool(
            membership is not None
            and payload is not None
            and membership.source_deck_id == payload.get("source_deck_id")
            and dict(membership.metadata_json or {})
            == dict(payload.get("metadata_json") or {})
        )
        if unchanged:
            continue
        if membership is not None:
            membership.removed_sequence = sequence_no
        if payload is None:
            continue
        deck_release_repository.add_membership(
            DeckReleaseEntityMembership(
                deck_item_id=item.id,
                entity_kind=key[0],
                entity_id=key[1],
                source_deck_id=payload.get("source_deck_id"),
                introduced_sequence=sequence_no,
                removed_sequence=None,
                metadata_json=dict(payload.get("metadata_json") or {}),
            )
        )


def publish_release(
    *,
    deck_item_id: str,
    user_id: int,
    version_label: Any,
    changelog: Any,
    expected_current_release_id: str | None,
    expected_working_revision: Any,
    idempotency_key: Any,
    publish_mode: str = "manual",
) -> PublishReleaseResult:
    """Build and stage an immutable release in the caller's transaction."""

    normalized_version = _normalize_version_label(version_label)
    normalized_key = _normalize_idempotency_key(idempotency_key)
    normalized_changelog = str(changelog).strip() if changelog is not None else None
    normalized_publish_mode = "automatic" if str(publish_mode).strip().lower() == "automatic" else "manual"
    normalized_expected_revision = _normalize_expected_working_revision(
        expected_working_revision
    )
    normalized_expected_head = (
        str(expected_current_release_id).strip()
        if expected_current_release_id is not None
        else None
    )

    item = _get_owned_item(
        deck_item_id=deck_item_id,
        user_id=user_id,
        lock=True,
    )
    request = release_core.PublishRequest(
        normalized_version, normalized_key, normalized_expected_head,
        normalized_expected_revision, normalized_changelog, normalized_publish_mode,
    )
    release, replayed = release_core.publish(_DeckPublishAdapter(item, user_id), request)
    return PublishReleaseResult(release, replayed=replayed)


class _DeckPublishAdapter:
    """Keep deck sparse journals/checkpoints behind the shared publisher policy."""

    def __init__(self, item, user_id):
        self.item = item
        self.user_id = user_id
        self.head_id = str(item.current_release_id) if item.current_release_id else None
        self.revision = int(item.working_revision or 0)

    def fail(self, code, message, *, field=None):
        raise DeckReleaseError(code, message, status=409, field=field)

    def find_replay(self, key):
        return deck_release_repository.get_release_by_idempotency_key(deck_item_id=self.item.id, idempotency_key=key)

    def matches_replay(self, existing, request):
        return (
            existing.version_label == request.version_label
            and existing.parent_release_id == request.expected_head_id
            and (existing.changelog or None) == (request.change_note or None)
            and (request.expected_revision is None or int(existing.source_working_revision or 0) == request.expected_revision)
        )

    def label_exists(self, label):
        return deck_release_repository.get_release_by_version_label(deck_item_id=self.item.id, version_label=label) is not None

    def plan(self):
        if self.item.current_release is not None and self.item.current_release.status != "published":
            self.fail("RELEASE_HEAD_INVALID", "The current release is not published.")
        return _build_release_diff_plan(item=self.item)

    def has_changes(self, plan):
        return bool(plan.changes)

    def persist(self, plan, request):
        return _stage_deck_release(item=self.item, user_id=self.user_id, diff_plan=plan, request=request)


def _stage_deck_release(*, item, user_id, diff_plan, request):
    normalized_version = request.version_label
    normalized_key = request.idempotency_key
    normalized_changelog = request.change_note
    normalized_publish_mode = request.mode
    current_head_id = request.expected_head_id
    parent_release = item.current_release
    changes = diff_plan.changes

    sequence_no = deck_release_repository.next_release_sequence(item.id)
    summary = _summary_for_changes(changes)
    release = DeckRelease(
        deck_item_id=item.id,
        sequence_no=sequence_no,
        version_label=normalized_version,
        parent_release_id=current_head_id,
        status="building",
        publish_mode=normalized_publish_mode,
        source_working_revision=int(item.working_revision or 0),
        manifest_hash=_release_manifest_hash(changes),
        changelog=normalized_changelog,
        idempotency_key=normalized_key,
        created_by_user_id=user_id,
        **summary,
    )
    deck_release_repository.add_release(release)
    deck_release_repository.flush()

    deck_release_repository.add_release_changes(
        _build_release_change_rows(release=release, changes=changes)
    )
    if parent_release is None:
        working_state = diff_plan.working_state
        if working_state is None:
            raise DeckReleaseError(
                "RELEASE_BUILD_INVALID",
                "Initial release state could not be built.",
                status=409,
            )
        initial_checkpoints = _create_initial_checkpoints(
            release=release,
            working_state=working_state,
        )
        deck_release_repository.add_note_checkpoints(initial_checkpoints)
        release.manifest_hash = _initial_release_manifest_hash(
            changes=changes,
            checkpoints=initial_checkpoints,
        )
    if diff_plan.sparse_memberships is not None:
        _sync_sparse_memberships(
            item=item,
            sequence_no=sequence_no,
            current=diff_plan.sparse_memberships,
        )
    else:
        working_state = diff_plan.working_state
        if working_state is None:
            raise DeckReleaseError(
                "RELEASE_BUILD_INVALID",
                "Release working state could not be built.",
                status=409,
            )
        _sync_memberships(
            item=item,
            sequence_no=sequence_no,
            working_state=working_state,
        )

    published_at = _utcnow()
    release.status = "published"
    release.published_at = published_at
    item.current_release = release
    item.current_release_id = release.id
    from app.services import marketplace_query_service

    item.preview_samples_release_id = release.id
    item.preview_samples_schema_version = 1
    item.preview_samples_json = marketplace_query_service.build_release_sample_cache_from_release(
        item,
        release,
        limit=5,
    )
    item.version = normalized_version
    item.changelog = normalized_changelog
    item.published_at = published_at
    from app.services import deck_working_tree_service

    deck_working_tree_service.clear_dirty_entities(deck_item_id=item.id)
    item.dirty_tracking_revision = int(item.working_revision or 0)
    deck_release_repository.flush()
    from models import db
    from app.services.template_release_service import capture_deck_release_template_pins
    capture_deck_release_template_pins(db.session, release, actor_user_id=user_id)
    return release


def serialize_release(release: DeckRelease | None) -> dict[str, Any] | None:
    if release is None:
        return None
    return {
        "id": str(release.id),
        "deck_item_id": str(release.deck_item_id),
        "sequence_no": int(release.sequence_no),
        "version_label": release.version_label,
        "parent_release_id": release.parent_release_id,
        "status": release.status,
        "publish_mode": getattr(release, "publish_mode", "manual") or "manual",
        "source_working_revision": int(release.source_working_revision or 0),
        "manifest_hash": release.manifest_hash,
        "change_count": int(release.change_count or 0),
        "entity_count": int(release.entity_count or 0),
        "added_count": int(release.added_count or 0),
        "modified_count": int(release.modified_count or 0),
        "removed_count": int(release.removed_count or 0),
        "changelog": release.changelog,
        "created_by_user_id": release.created_by_user_id,
        "created_at": release.created_at.isoformat() if release.created_at else None,
        "published_at": (
            release.published_at.isoformat() if release.published_at else None
        ),
    }


def serialize_release_change(
    change: DeckReleaseChange,
    *,
    field_names_by_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "id": int(change.id),
        "change_key": change.change_key,
        "entity_kind": change.entity_kind,
        "entity_id": change.entity_id,
        "field_def_id": change.field_def_id,
        "field_name": (
            (field_names_by_id or {}).get(str(change.field_def_id))
            if change.field_def_id
            else None
        ),
        "property_key": change.property_key,
        "operation": change.operation,
        "before_value": change.before_value,
        "after_value": change.after_value,
        "before_hash": change.before_hash,
        "after_hash": change.after_hash,
        "source_deck_id": change.source_deck_id,
        "sort_key": change.sort_key,
    }


def list_deck_releases(
    *,
    deck_item_id: str,
    user_id: int,
    cursor: Any = None,
    limit: Any = None,
) -> dict[str, Any]:
    item = _get_visible_item(deck_item_id=deck_item_id, user_id=user_id)
    page_limit = _coerce_page_limit(limit)
    before_sequence = _coerce_optional_positive_int(cursor, field_name="cursor")
    is_owner = int(item.owner_user_id) == int(user_id)
    rows, has_more = deck_release_repository.list_releases(
        deck_item_id=item.id,
        before_sequence=before_sequence,
        limit=page_limit,
        published_only=not is_owner,
    )
    return {
        "deck_item_id": str(item.id),
        "current_release_id": item.current_release_id,
        "working_revision": int(item.working_revision or 0),
        "items": [serialize_release(row) for row in rows],
        "next_cursor": str(rows[-1].sequence_no) if has_more and rows else None,
    }


def get_deck_release_detail(
    *,
    deck_item_id: str,
    release_id: str,
    user_id: int,
) -> dict[str, Any]:
    item = _get_visible_item(deck_item_id=deck_item_id, user_id=user_id)
    release = _get_visible_release(
        item=item,
        release_id=release_id,
        user_id=user_id,
    )
    return {"release": serialize_release(release)}


def list_deck_release_changes(
    *,
    deck_item_id: str,
    release_id: str,
    user_id: int,
    cursor: Any = None,
    limit: Any = None,
    entity_kind: str | None = None,
    operation: str | None = None,
    source_deck_id: Any = None,
    query_text: str | None = None,
) -> dict[str, Any]:
    item = _get_visible_item(deck_item_id=deck_item_id, user_id=user_id)
    release = _get_visible_release(
        item=item,
        release_id=release_id,
        user_id=user_id,
    )
    normalized_kind = (entity_kind or "").strip() or None
    if normalized_kind and normalized_kind not in VISIBLE_ENTITY_KINDS:
        raise DeckReleaseError(
            "VALIDATION_ERROR",
            "type must be note_field, field_def, or template.",
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
    after_id = _coerce_optional_positive_int(cursor, field_name="cursor")
    normalized_deck_id = _coerce_optional_positive_int(
        source_deck_id,
        field_name="deck_id",
    )
    page_limit = _coerce_page_limit(limit)
    rows, has_more = deck_release_repository.list_release_changes_page(
        release_id=release.id,
        after_id=after_id,
        limit=page_limit,
        entity_kind=normalized_kind,
        operation=normalized_operation,
        source_deck_id=normalized_deck_id,
        query_text=query_text,
    )
    field_defs = get_field_defs_at_release(release)
    if release.parent_release is not None:
        parent_field_defs = get_field_defs_at_release(release.parent_release)
        parent_field_defs.update(field_defs)
        field_defs = parent_field_defs
    field_names_by_id = {
        field_id: str(payload.get("name"))
        for field_id, payload in field_defs.items()
        if payload.get("name") is not None
    }
    release_payload = serialize_release(release)
    return {
        "release": release_payload,
        "snapshot_revision": str(release.id),
        "summary": {
            "change_count": int(release.change_count or 0),
            "entity_count": int(release.entity_count or 0),
            "added_count": int(release.added_count or 0),
            "modified_count": int(release.modified_count or 0),
            "removed_count": int(release.removed_count or 0),
        },
        "items": [
            serialize_release_change(row, field_names_by_id=field_names_by_id)
            for row in rows
        ],
        "next_cursor": str(rows[-1].id) if has_more and rows else None,
    }


def get_atomic_changes_between_releases(
    *,
    from_release_or_id: DeckRelease | str | None,
    to_release_or_id: DeckRelease | str,
) -> list[dict[str, Any]]:
    """Collapse atomic changes between two published releases by change key."""

    to_release = (
        to_release_or_id
        if isinstance(to_release_or_id, DeckRelease)
        else deck_release_repository.get_release(str(to_release_or_id))
    )
    from_release = (
        from_release_or_id
        if isinstance(from_release_or_id, DeckRelease)
        else (
            deck_release_repository.get_release(str(from_release_or_id))
            if from_release_or_id is not None
            else None
        )
    )
    if not to_release or to_release.status != "published":
        raise DeckReleaseError(
            "RELEASE_NOT_FOUND",
            "Target release not found.",
            status=404,
        )
    if from_release is not None:
        if from_release.status != "published":
            raise DeckReleaseError(
                "RELEASE_NOT_FOUND",
                "Base release not found.",
                status=404,
            )
        if from_release.deck_item_id != to_release.deck_item_id:
            raise DeckReleaseError(
                "RELEASE_DECK_MISMATCH",
                "Base and target releases belong to different decks.",
                status=409,
            )
        if int(from_release.sequence_no) > int(to_release.sequence_no):
            raise DeckReleaseError(
                "RELEASE_ORDER_INVALID",
                "Base release must not be newer than target release.",
                status=409,
            )

    rows = deck_release_repository.list_release_changes_between(
        deck_item_id=to_release.deck_item_id,
        after_sequence=int(from_release.sequence_no) if from_release else 0,
        through_sequence=int(to_release.sequence_no),
    )
    collapsed: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = collapsed.get(row.change_key)
        if current is None:
            current = {
                "change_key": row.change_key,
                "entity_kind": row.entity_kind,
                "entity_id": row.entity_id,
                "field_def_id": row.field_def_id,
                "property_key": row.property_key,
                "before_value": row.before_value,
                "before_hash": row.before_hash,
                "source_deck_id": row.source_deck_id,
                "sort_key": row.sort_key,
                "_before_exists": row.operation != "add",
            }
            collapsed[row.change_key] = current
        current.update(
            {
                "entity_kind": row.entity_kind,
                "entity_id": row.entity_id,
                "field_def_id": row.field_def_id,
                "property_key": row.property_key,
                "after_value": row.after_value,
                "after_hash": row.after_hash,
                "source_deck_id": row.source_deck_id,
                "sort_key": row.sort_key,
                "_after_exists": row.operation != "remove",
            }
        )

    result: list[dict[str, Any]] = []
    for row in collapsed.values():
        before_exists = bool(row.pop("_before_exists"))
        after_exists = bool(row.pop("_after_exists"))
        if before_exists == after_exists and (
            not before_exists or row.get("before_value") == row.get("after_value")
        ):
            continue
        if not before_exists and after_exists:
            row["operation"] = "add"
        elif before_exists and not after_exists:
            row["operation"] = "remove"
        else:
            row["operation"] = "set"
        result.append(row)
    return sorted(result, key=lambda row: (row["sort_key"], row["change_key"]))
