"""Serialization helpers for deck change requests."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.repositories import deck_change_request_repository
from app.services.change_request.helpers import (
    CHANGE_TYPE_FIELD_DEF_ADD,
    CHANGE_TYPE_FIELD_DEF_DISABLE,
    CHANGE_TYPE_FIELD_DEF_UPDATE,
    CHANGE_TYPE_FIELD_ORDER_UPDATE,
    CHANGE_TYPE_NOTE_FIELD_REMOVE,
    CHANGE_TYPE_NOTE_FIELD_SET,
    DEFAULT_ITEM_PAGE_LIMIT,
    MAX_ITEM_PAGE_LIMIT,
    OPEN_REQUEST_STATUSES,
    REQUEST_STATUS_DRAFT,
    REQUEST_STATUS_HAS_CONFLICT,
    REQUEST_STATUS_MERGED,
    REQUEST_STATUS_NEEDS_SYNC,
    REQUEST_STATUS_PENDING_REVIEW,
    REQUEST_STATUS_REJECTED,
    _coerce_page_limit,
    _decode_cursor,
    _effective_after_value,
    _encode_cursor,
    _get_request_install,
    _item_resolution_mode,
    _load_field_defs_by_ids,
    _load_notes_by_ids,
    _normalize_item_filters,
    _note_label,
    _primary_conflict,
    change_note_id,
)
from models.deck_change_request import DeckChangeRequest
from models.deck_change_request_conflict import DeckChangeRequestConflict
from models.deck_change_request_item import DeckChangeRequestItem
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.field_def import FieldDef
from models.note import Note


def _actor_payload(user: Any, fallback_id: int | None) -> dict[str, Any]:
    """Name the person, not the id: owners decide whom to trust by name."""
    if user is None:
        return {"id": fallback_id, "username": "Unknown", "display_name": None, "avatar_url": None}
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or None,
        "avatar_url": user.avatar_url or None,
    }


def _serialize_conflict(row: DeckChangeRequestConflict) -> dict[str, Any]:
    return {
        "id": row.id,
        "item_id": row.item_id,
        "conflict_type": row.conflict_type,
        "source_ref_id": row.source_ref_id,
        "upstream_value": row.upstream_value,
        "local_value": row.local_value,
        "base_value": row.base_value,
        "resolution_mode": row.resolution_mode,
        "resolved_value": row.resolved_value,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def _serialize_request_item(item: DeckChangeRequestItem) -> dict[str, Any]:
    metadata = dict(item.metadata_json or {})
    conflict = next((row for row in (item.conflicts or []) if row is not None), None)
    field_def_id = str(metadata.get("source_field_def_id") or "").strip() or None
    if field_def_id is None and item.change_type in {
        CHANGE_TYPE_FIELD_DEF_UPDATE,
        CHANGE_TYPE_FIELD_DEF_DISABLE,
    }:
        field_def_id = str(item.source_ref_id or "").strip() or None
    return {
        "id": item.id,
        "change_type": item.change_type,
        "source_ref_id": item.source_ref_id,
        "local_ref_id": item.local_ref_id,
        "source_note_id": metadata.get("source_note_id"),
        "field_def_id": field_def_id,
        "path_key": item.path_key,
        "path_label": item.path_label,
        "before_value": item.before_value,
        "after_value": item.after_value,
        "effective_after_value": _effective_after_value(item),
        "metadata": metadata,
        "is_conflict": bool(item.is_conflict),
        "conflict": _serialize_conflict(conflict) if conflict else None,
        "review_decision": metadata.get("review_decision"),
    }


def serialize_request_page(
    request_obj: DeckChangeRequest,
    *,
    viewer_user_id: int,
    item_rows: list[DeckChangeRequestItem],
    item_count: int,
    unresolved_conflict_count: int,
    change_counts: dict[str, int],
    page: dict[str, Any],
    note_count: int | None = None,
    note_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    serialized_items = [_serialize_request_item(item) for item in item_rows]
    page_conflicts = [
        _serialize_conflict(conflict)
        for item in item_rows
        for conflict in (item.conflicts or [])
        if conflict is not None
    ]
    return {
        "id": request_obj.id,
        "deck_install_id": request_obj.deck_install_id,
        "deck_item_id": request_obj.deck_item_id,
        "local_deck_id": request_obj.local_deck_id,
        "source_deck_id": request_obj.source_deck_id,
        "source_note_type_id": request_obj.source_note_type_id,
        "status": request_obj.status,
        "base_release_id": request_obj.base_release_id,
        "revision": int(request_obj.revision or 0),
        "title": request_obj.title,
        "description": request_obj.description,
        "overlay_fingerprint": request_obj.overlay_fingerprint,
        "last_sync_status": request_obj.last_sync_status,
        "last_synced_at": request_obj.last_synced_at.isoformat() if request_obj.last_synced_at else None,
        "submitted_at": request_obj.submitted_at.isoformat() if request_obj.submitted_at else None,
        "reviewed_at": request_obj.reviewed_at.isoformat() if request_obj.reviewed_at else None,
        "merged_at": request_obj.merged_at.isoformat() if request_obj.merged_at else None,
        "review_comment": request_obj.review_comment,
        "created_at": request_obj.created_at.isoformat() if request_obj.created_at else None,
        "updated_at": request_obj.updated_at.isoformat() if request_obj.updated_at else None,
        "requester": _actor_payload(request_obj.requester, request_obj.requester_user_id),
        "owner": _actor_payload(request_obj.owner, request_obj.owner_user_id),
        "reviewed_by": (
            _actor_payload(request_obj.reviewed_by, request_obj.reviewed_by_user_id)
            if request_obj.reviewed_by
            else None
        ),
        "deck_item": (
            {
                "id": request_obj.deck_item.id,
                "title": request_obj.deck_item.title,
            }
            if request_obj.deck_item
            else None
        ),
        "item_count": int(item_count),
        # Null on later pages: the total is counted once, with the first page.
        "note_count": int(note_count) if note_count is not None else None,
        "unresolved_conflict_count": int(unresolved_conflict_count),
        "change_counts": dict(change_counts),
        "can_submit": (
            int(request_obj.requester_user_id) == int(viewer_user_id)
            and request_obj.status == REQUEST_STATUS_DRAFT
            and int(unresolved_conflict_count) == 0
        ),
        "can_resolve": (
            int(request_obj.requester_user_id) == int(viewer_user_id)
            and request_obj.status == REQUEST_STATUS_HAS_CONFLICT
        ),
        "can_review": (
            int(request_obj.owner_user_id) == int(viewer_user_id)
            and request_obj.status == REQUEST_STATUS_PENDING_REVIEW
        ),
        "items": serialized_items,
        "conflicts": page_conflicts,
        "field_defs": list((note_context or {}).get("field_defs") or []),
        "notes": dict((note_context or {}).get("notes") or {}),
        "page": page,
    }


def serialize_request(request_obj: DeckChangeRequest, *, viewer_user_id: int) -> dict[str, Any]:
    """Serialize an already-loaded request graph (legacy/internal callers)."""

    item_rows = list(request_obj.items or [])
    unresolved_conflicts = [
        row for row in (request_obj.conflicts or []) if row.resolved_at is None
    ]
    return serialize_request_page(
        request_obj,
        viewer_user_id=viewer_user_id,
        item_rows=item_rows,
        item_count=len(item_rows),
        unresolved_conflict_count=len(unresolved_conflicts),
        change_counts=dict(Counter(item.change_type for item in item_rows)),
        note_count=len({note_id for item in item_rows if (note_id := change_note_id(item))}),
        page={
            "limit": len(item_rows),
            "has_more": False,
            "next_cursor": None,
            "filtered_item_count": len(item_rows),
            "revision": int(request_obj.revision or 0),
        },
    )


def serialize_request_summary(
    request_obj: DeckChangeRequest,
    *,
    item_count: int | None = None,
    unresolved_conflict_count: int | None = None,
    note_count: int | None = None,
) -> dict[str, Any]:
    if item_count is None:
        item_count = len(request_obj.items or [])
    if unresolved_conflict_count is None:
        unresolved_conflict_count = len(
            [row for row in (request_obj.conflicts or []) if row.resolved_at is None]
        )
    return {
        "id": request_obj.id,
        "deck_item_id": request_obj.deck_item_id,
        "title": request_obj.title,
        "status": request_obj.status,
        "base_release_id": request_obj.base_release_id,
        "revision": int(request_obj.revision or 0),
        "requester": _actor_payload(request_obj.requester, request_obj.requester_user_id),
        "deck_item": (
            {
                "id": request_obj.deck_item.id,
                "title": request_obj.deck_item.title,
            }
            if request_obj.deck_item
            else None
        ),
        "item_count": int(item_count),
        "note_count": (
            int(note_count)
            if note_count is not None
            else len({note_id for item in (request_obj.items or []) if (note_id := change_note_id(item))})
        ),
        "unresolved_conflict_count": int(unresolved_conflict_count),
        "submitted_at": request_obj.submitted_at.isoformat() if request_obj.submitted_at else None,
        "updated_at": request_obj.updated_at.isoformat() if request_obj.updated_at else None,
    }
