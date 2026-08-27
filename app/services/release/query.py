"""Deck release queries, change list inspection, and serialization."""

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
    FILTER_OPERATION_ALIASES,
    VISIBLE_ENTITY_KINDS,
    DeckReleaseError,
    _coerce_optional_positive_int,
    _coerce_page_limit,
    _get_visible_item,
    _get_visible_release,
)
from app.services.release.diff import _build_atomic_diff
from app.services.release.reconstruct import (
    get_field_defs_at_release,
    reconstruct_release_state,
)


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

