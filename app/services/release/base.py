"""Data structures, errors, constants, and basic helpers for deck releases."""

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



