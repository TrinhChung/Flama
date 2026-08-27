"""Release publishing, manifest hashing, checkpoints creation, and membership sync."""

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
    MAX_IDEMPOTENCY_KEY_LENGTH,
    MAX_VERSION_LABEL_LENGTH,
    DeckReleaseError,
    DeckReleaseState,
    PublishReleaseResult,
    _get_owned_item,
    _hash_value,
    _json_bytes,
    _utcnow,
)
from app.services.release.diff import (
    _build_release_diff_plan,
    _summary_for_changes,
)
from app.services.release.reconstruct import (
    _build_working_state,
    _chunks,
)


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
) -> PublishReleaseResult:
    """Build and stage an immutable release in the caller's transaction."""

    normalized_version = _normalize_version_label(version_label)
    normalized_key = _normalize_idempotency_key(idempotency_key)
    normalized_changelog = str(changelog).strip() if changelog is not None else None
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
    existing_idempotent = deck_release_repository.get_release_by_idempotency_key(
        deck_item_id=item.id,
        idempotency_key=normalized_key,
    )
    if existing_idempotent is not None:
        same_request = (
            existing_idempotent.version_label == normalized_version
            and existing_idempotent.parent_release_id == normalized_expected_head
            and (existing_idempotent.changelog or None) == (normalized_changelog or None)
            and (
                normalized_expected_revision is None
                or int(existing_idempotent.source_working_revision or 0)
                == normalized_expected_revision
            )
        )
        if not same_request:
            raise DeckReleaseError(
                "IDEMPOTENCY_KEY_REUSED",
                "Idempotency-Key was already used for another release request.",
                status=409,
                field="Idempotency-Key",
            )
        return PublishReleaseResult(existing_idempotent, replayed=True)

    current_head_id = str(item.current_release_id) if item.current_release_id else None
    if normalized_expected_head != current_head_id:
        raise DeckReleaseError(
            "RELEASE_HEAD_STALE",
            "The published release changed. Refresh the preview and retry.",
            status=409,
            field="expected_current_release_id",
        )
    if (
        normalized_expected_revision is not None
        and normalized_expected_revision != int(item.working_revision or 0)
    ):
        raise DeckReleaseError(
            "WORKING_REVISION_STALE",
            "The owner working revision changed. Refresh the preview and retry.",
            status=409,
            field="expected_working_revision",
        )
    if deck_release_repository.get_release_by_version_label(
        deck_item_id=item.id,
        version_label=normalized_version,
    ):
        raise DeckReleaseError(
            "VERSION_ALREADY_EXISTS",
            "version_label already exists for this deck.",
            status=409,
            field="version_label",
        )

    parent_release = item.current_release
    if parent_release is not None and parent_release.status != "published":
        raise DeckReleaseError(
            "RELEASE_HEAD_INVALID",
            "The current release is not published.",
            status=409,
        )
    diff_plan = _build_release_diff_plan(item=item)
    changes = diff_plan.changes
    if parent_release is not None and not changes:
        raise DeckReleaseError(
            "NO_RELEASE_CHANGES",
            "There are no unpublished source changes.",
            status=409,
        )

    sequence_no = deck_release_repository.next_release_sequence(item.id)
    summary = _summary_for_changes(changes)
    release = DeckRelease(
        deck_item_id=item.id,
        sequence_no=sequence_no,
        version_label=normalized_version,
        parent_release_id=current_head_id,
        status="building",
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
    return PublishReleaseResult(release, replayed=False)



