"""Constants, errors, utility helpers, and access control for change requests."""

from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from types import SimpleNamespace
from typing import Any

from app.repositories import deck_change_request_repository, flashcards_share_repository
from app.services import deck_working_tree_service, flashcards_share
from app.services.common.datetime_utils import (
    utcnow as _utcnow,
    stable_json as _stable_json,
)
from app.services.common.pagination import (
    encode_cursor as _encode_cursor_common,
    decode_cursor as _decode_cursor_common,
    coerce_page_limit as _coerce_page_limit_common,
)
from models import db
from models.audit_log import AuditLog
from models.deck_change_request import DeckChangeRequest
from models.deck_change_request_conflict import DeckChangeRequestConflict
from models.deck_change_request_item import DeckChangeRequestItem
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_field_order_override import DeckCloneFieldOrderOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.field_def import FieldDef
from models.field_types import field_value_text
from models.note import Note

REQUEST_STATUS_NEEDS_SYNC = "needs_sync"
REQUEST_STATUS_DRAFT = "draft"
REQUEST_STATUS_HAS_CONFLICT = "has_conflict"
REQUEST_STATUS_PENDING_REVIEW = "pending_review"
REQUEST_STATUS_REJECTED = "rejected"
REQUEST_STATUS_MERGED = "merged"

OPEN_EDITABLE_REQUEST_STATUSES = {
    REQUEST_STATUS_NEEDS_SYNC,
    REQUEST_STATUS_DRAFT,
    REQUEST_STATUS_HAS_CONFLICT,
}
OPEN_REQUEST_STATUSES = OPEN_EDITABLE_REQUEST_STATUSES | {REQUEST_STATUS_PENDING_REVIEW}
RESOLUTION_MODES = {"keep_mine", "keep_upstream", "manual"}
CHANGE_TYPE_NOTE_FIELD_SET = "note_field_set"
CHANGE_TYPE_NOTE_FIELD_REMOVE = "note_field_remove"
CHANGE_TYPE_FIELD_DEF_UPDATE = "field_def_update"
CHANGE_TYPE_FIELD_DEF_DISABLE = "field_def_disable"
CHANGE_TYPE_FIELD_DEF_ADD = "field_def_add"
CHANGE_TYPE_FIELD_ORDER_UPDATE = "field_order_update"

CHANGE_REQUEST_CHANGE_TYPES = {
    CHANGE_TYPE_NOTE_FIELD_SET,
    CHANGE_TYPE_NOTE_FIELD_REMOVE,
    CHANGE_TYPE_FIELD_DEF_UPDATE,
    CHANGE_TYPE_FIELD_DEF_DISABLE,
    CHANGE_TYPE_FIELD_DEF_ADD,
    CHANGE_TYPE_FIELD_ORDER_UPDATE,
}
CHANGE_REQUEST_DIFF_FILTERS = {
    "added": {CHANGE_TYPE_FIELD_DEF_ADD},
    "modified": {
        CHANGE_TYPE_NOTE_FIELD_SET,
        CHANGE_TYPE_FIELD_DEF_UPDATE,
        CHANGE_TYPE_FIELD_ORDER_UPDATE,
    },
    "removed": {CHANGE_TYPE_NOTE_FIELD_REMOVE, CHANGE_TYPE_FIELD_DEF_DISABLE},
}
DEFAULT_INBOX_PAGE_LIMIT = 30
MAX_INBOX_PAGE_LIMIT = 100
DEFAULT_ITEM_PAGE_LIMIT = 100
MAX_ITEM_PAGE_LIMIT = 250

MISSING_MARKER = {"__missing__": True}
NOTE_CHANGE_TYPES = {CHANGE_TYPE_NOTE_FIELD_SET, CHANGE_TYPE_NOTE_FIELD_REMOVE}
# The owner's per-item verdict lives in item metadata, so partial approval
# needs no extra columns.
REVIEW_DECISION_ACCEPTED = "accepted"
REVIEW_DECISION_DECLINED = "declined"
SELECTION_MODE_ALL_EXCEPT = "all_except"
SELECTION_MODE_ONLY = "only"


class ChangeRequestError(Exception):
    """Domain error for deck change request flows."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        error: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field
        self.error = error


def _utcnow() -> datetime:
    return datetime.utcnow()


def _audit(user_id: int | None, action: str, payload: dict[str, Any] | None = None) -> None:
    db.session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            payload=payload or {},
        )
    )


def _install_snapshot_at(install: DeckInstall) -> datetime | None:
    return install.base_snapshot_at or install.installed_at


def _is_missing(value: Any) -> bool:
    return isinstance(value, dict) and value.get("__missing__") is True


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _encode_cursor(payload: dict[str, Any]) -> str:
    raw = _stable_json(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(raw_cursor: str | None, *, expected_kind: str) -> dict[str, Any] | None:
    normalized = str(raw_cursor or "").strip()
    if not normalized:
        return None
    try:
        padded = normalized + "=" * (-len(normalized) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("kind") != expected_kind:
            raise ValueError("cursor kind mismatch")
        return payload
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ChangeRequestError(
            "cursor is invalid.",
            status=400,
            field="cursor",
        ) from exc


def _coerce_page_limit(
    raw_limit: Any,
    *,
    default: int,
    maximum: int,
) -> int:
    if raw_limit is None or str(raw_limit).strip() == "":
        return default
    try:
        value = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ChangeRequestError(
            "limit must be an integer.",
            status=400,
            field="limit",
        ) from exc
    if value < 1 or value > maximum:
        raise ChangeRequestError(
            f"limit must be between 1 and {maximum}.",
            status=400,
            field="limit",
        )
    return value


def _normalize_item_filters(
    *,
    raw_change_type: str | None,
    query_text: str | None,
    conflicts_only: bool,
) -> tuple[set[str] | None, str | None, bool, str]:
    normalized_type = str(raw_change_type or "").strip().lower()
    normalized_query = str(query_text or "").strip()
    if len(normalized_query) > 200:
        raise ChangeRequestError(
            "q must be at most 200 characters.",
            status=400,
            field="q",
        )
    change_types: set[str] | None = None
    if normalized_type and normalized_type != "all":
        if normalized_type == "conflict":
            conflicts_only = True
        elif normalized_type in CHANGE_REQUEST_DIFF_FILTERS:
            change_types = set(CHANGE_REQUEST_DIFF_FILTERS[normalized_type])
        elif normalized_type in CHANGE_REQUEST_CHANGE_TYPES:
            change_types = {normalized_type}
        else:
            raise ChangeRequestError(
                "type is invalid.",
                status=400,
                field="type",
            )
    filter_key = hashlib.sha256(
        _stable_json(
            {
                "change_types": sorted(change_types or []),
                "q": normalized_query,
                "conflicts_only": bool(conflicts_only),
            }
        ).encode("utf-8")
    ).hexdigest()[:16]
    return change_types, normalized_query or None, bool(conflicts_only), filter_key


def _load_notes_by_ids(note_ids: set[str], *, chunk_size: int = 500) -> dict[str, Note]:
    rows_by_id: dict[str, Note] = {}
    normalized = sorted({str(note_id) for note_id in note_ids if note_id})
    for offset in range(0, len(normalized), chunk_size):
        rows = Note.query.filter(Note.id.in_(normalized[offset:offset + chunk_size])).all()
        rows_by_id.update({str(row.id): row for row in rows})
    return rows_by_id


def _note_deck_ids(note_ids: set[str], *, chunk_size: int = 500) -> dict[str, int | None]:
    """Deck of each Note that still exists, with the same visibility rules but no content."""
    normalized = sorted({str(note_id) for note_id in note_ids if note_id})
    found: dict[str, int | None] = {}
    for offset in range(0, len(normalized), chunk_size):
        rows = (
            db.session.query(Note.id, Note.deck_id)
            .filter(Note.id.in_(normalized[offset:offset + chunk_size]))
            .all()
        )
        found.update({str(note_id): deck_id for note_id, deck_id in rows})
    return found


def _load_field_defs_by_ids(
    field_ids: set[str],
    *,
    chunk_size: int = 500,
) -> dict[str, FieldDef]:
    rows_by_id: dict[str, FieldDef] = {}
    normalized = sorted({str(field_id) for field_id in field_ids if field_id})
    for offset in range(0, len(normalized), chunk_size):
        rows = FieldDef.query.filter(FieldDef.id.in_(normalized[offset:offset + chunk_size])).all()
        rows_by_id.update({str(row.id): row for row in rows})
    return rows_by_id


def _overlay_state_payload(install: DeckInstall) -> dict[str, Any]:
    updated_defs = [
        {
            "id": row.id,
            "source_field_def_id": row.source_field_def_id,
            "is_disabled": bool(row.is_disabled),
            "properties": dict(row.properties or {}),
        }
        for row in (
            DeckCloneFieldDefOverride.query.filter_by(deck_install_id=install.id)
            .order_by(
                DeckCloneFieldDefOverride.source_field_def_id.asc(),
                DeckCloneFieldDefOverride.id.asc(),
            )
            .all()
        )
    ]
    added_defs = [
        {
            "id": row.id,
            "name": row.name,
            "field_type": row.field_type,
            "position": int(row.position or 0),
            "required": bool(row.required),
            "properties": dict(row.properties or {}),
        }
        for row in (
            DeckCloneAddedFieldDef.query.filter_by(deck_install_id=install.id)
            .order_by(
                DeckCloneAddedFieldDef.position.asc(),
                DeckCloneAddedFieldDef.created_at.asc(),
                DeckCloneAddedFieldDef.id.asc(),
            )
            .all()
        )
    ]
    order_override = DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=install.id).first()
    note_overrides = [
        {
            "id": row.id,
            "source_note_id": row.source_note_id,
            "source_field_def_id": row.source_field_def_id,
            "base_release_id": row.base_release_id,
            "field_name": row.field_name,
            "operation": row.operation,
            "value": row.value,
        }
        for row in (
            DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install.id)
            .order_by(
                DeckCloneNoteFieldOverride.source_note_id.asc(),
                DeckCloneNoteFieldOverride.field_name.asc(),
                DeckCloneNoteFieldOverride.id.asc(),
            )
            .all()
        )
    ]
    return {
        "updated_defs": updated_defs,
        "added_defs": added_defs,
        "ordered_def_ids": list(order_override.ordered_def_ids or []) if order_override else [],
        "note_field_overrides": note_overrides,
    }


def compute_overlay_fingerprint(install: DeckInstall) -> str:
    payload = _overlay_state_payload(install)
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _source_field_snapshot(field_def: FieldDef | None) -> dict[str, Any]:
    if field_def is None:
        return dict(MISSING_MARKER)
    return {
        "id": field_def.id,
        "name": field_def.name,
        "field_type": field_def.field_type,
        "position": int(field_def.position or 0),
        "required": bool(field_def.required),
        "identity_role": field_def.identity_role,
    }


def _added_field_snapshot(row: DeckCloneAddedFieldDef) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "field_type": row.field_type,
        "position": int(row.position or 0),
        "required": bool(row.required),
        "properties": dict(row.properties or {}),
    }


def _note_label(note: Note | None) -> str:
    if note is None:
        return "Unknown note"
    return _values_label(dict(note.field_values or {}), note.id)


def _values_label(values: dict[str, Any], note_id: Any, text_field_order: list[str] | None = None) -> str:
    """``text_field_order`` (note-type order, media left out) makes the
    fallback label stable instead of following dict order."""
    for key_name in ("Word", "word", "Front", "front", "Expression", "expression", *(text_field_order or [])):
        candidate = field_value_text(values.get(key_name)).strip()
        if candidate:
            return candidate[:80]
    for raw_value in values.values():
        candidate = field_value_text(raw_value).strip()
        if candidate:
            return candidate[:80]
    return f"Note {note_id}"


def _apply_schema_only_values(
    source_note: Note,
    *,
    removed_field_names: set[str],
    renamed_field_names: dict[str, str],
) -> dict[str, Any]:
    values = dict(source_note.field_values or {})
    for removed_name in removed_field_names:
        values.pop(removed_name, None)
    for old_name, new_name in renamed_field_names.items():
        if old_name == new_name or old_name not in values:
            continue
        if new_name not in values:
            values[new_name] = values.get(old_name)
        values.pop(old_name, None)
    for removed_name in removed_field_names:
        values.pop(removed_name, None)
    return values


def _order_token(*, kind: str, ref_id: str, name: str) -> dict[str, Any]:
    return {
        "kind": str(kind or "").strip() or "source",
        "id": str(ref_id or "").strip(),
        "name": str(name or "").strip(),
    }


def _build_visible_source_order_tokens(
    *,
    source_note_type_id: str,
    snapshot_at: datetime | None,
) -> list[dict[str, Any]]:
    field_defs = (
        flashcards_share_repository.get_field_defs_for_note_type(
            source_note_type_id,
            snapshot_at,
        )
        if source_note_type_id
        else []
    )
    return [
        _order_token(kind="source", ref_id=row.id, name=row.name)
        for row in field_defs
    ]


def _build_current_source_order_tokens(source_note_type_id: str) -> list[dict[str, Any]]:
    if not source_note_type_id:
        return []
    rows = (
        FieldDef.query.filter_by(note_type_id=source_note_type_id)
        .order_by(FieldDef.position.asc(), FieldDef.created_at.asc(), FieldDef.id.asc())
        .all()
    )
    return [_order_token(kind="source", ref_id=row.id, name=row.name) for row in rows]


def _request_schema_context(
    items: list[DeckChangeRequestItem],
    *,
    use_effective_values: bool,
) -> dict[str, Any]:
    rename_map: dict[str, str] = {}
    removed_field_names: set[str] = set()

    for item in items:
        if use_effective_values and _item_is_dropped_from_request(item):
            continue
        metadata = dict(item.metadata_json or {})
        if item.change_type == CHANGE_TYPE_FIELD_DEF_UPDATE:
            property_name = str(metadata.get("property_name") or item.path_key or "").strip()
            field_name = str(metadata.get("field_name") or "").strip()
            if property_name != "name":
                continue
            desired_name = _effective_after_value(item) if use_effective_values else item.after_value
            if field_name and isinstance(desired_name, str) and desired_name and desired_name != field_name:
                rename_map[field_name] = desired_name

    for item in items:
        if use_effective_values and _item_is_dropped_from_request(item):
            continue
        if item.change_type == CHANGE_TYPE_FIELD_DEF_DISABLE:
            metadata = dict(item.metadata_json or {})
            should_disable = _effective_disable_value(item) if use_effective_values else True
            if should_disable:
                field_name = str(metadata.get("field_name") or "").strip()
                if field_name:
                    removed_field_names.add(field_name)
                    renamed_name = rename_map.get(field_name)
                    if renamed_name:
                        removed_field_names.add(renamed_name)

    return {
        "rename_map": rename_map,
        "removed_field_names": removed_field_names,
    }


def _primary_conflict(item: DeckChangeRequestItem) -> DeckChangeRequestConflict | None:
    conflicts = list(item.conflicts or [])
    return conflicts[0] if conflicts else None


def _item_resolution_mode(item: DeckChangeRequestItem) -> str:
    conflict = _primary_conflict(item)
    return str(conflict.resolution_mode or "").strip().lower() if conflict else ""


def _item_review_decision(item: DeckChangeRequestItem) -> str | None:
    return dict(item.metadata_json or {}).get("review_decision")


def _item_is_dropped_from_request(item: DeckChangeRequestItem) -> bool:
    return (
        _item_resolution_mode(item) == "keep_upstream"
        or _item_review_decision(item) == REVIEW_DECISION_DECLINED
    )


def _change_attr(change: Any, name: str) -> Any:
    """Read a local change payload (dict) and a stored item row alike."""
    return change.get(name) if isinstance(change, dict) else getattr(change, name, None)


def change_note_id(change: Any) -> str | None:
    if _change_attr(change, "change_type") not in NOTE_CHANGE_TYPES:
        return None
    metadata = dict(_change_attr(change, "metadata_json") or {})
    return str(metadata.get("source_note_id") or _change_attr(change, "source_ref_id") or "").strip() or None


def change_signature(change: Any) -> tuple[str, str, str]:
    return (
        str(_change_attr(change, "change_type") or ""),
        str(_change_attr(change, "local_ref_id") or ""),
        str(_change_attr(change, "path_key") or ""),
    )


def end_page_on_note_boundary(page: list[Any], next_change: Any) -> list[Any]:
    """Never split one note's changes across pages; reviewers judge whole notes."""
    note_id = change_note_id(next_change)
    if note_id is None:
        return page
    trimmed = list(page)
    while trimmed and change_note_id(trimmed[-1]) == note_id:
        trimmed.pop()
    # A single note larger than the page stays split rather than never loading.
    return trimmed or page


def _selection_includes(selection: Any, key: str | None) -> bool:
    return (key in selection.ids) == (selection.mode == SELECTION_MODE_ONLY)


def with_required_field_additions(chosen: list[Any], candidates: list[Any]) -> list[Any]:
    """Keep candidate order; a learner-added field travels with its note values."""
    needed = {
        str(dict(_change_attr(change, "metadata_json") or {}).get("local_added_field_def_id") or "")
        for change in chosen
        if change_note_id(change)
    } - {""}
    chosen_ids = {id(change) for change in chosen}
    return [
        change
        for change in candidates
        if id(change) in chosen_ids
        or (
            _change_attr(change, "change_type") == CHANGE_TYPE_FIELD_DEF_ADD
            and str(_change_attr(change, "local_ref_id") or "") in needed
        )
    ]


def select_local_changes(payloads: list[dict[str, Any]], selection: Any) -> list[dict[str, Any]]:
    """Pick whole notes by note id; field-structure changes travel as one group."""
    chosen = [
        payload
        for payload in payloads
        if (
            _selection_includes(selection, note_id)
            if (note_id := change_note_id(payload))
            else selection.include_schema_changes
        )
    ]
    return with_required_field_additions(chosen, payloads)


def select_request_items(items: list[DeckChangeRequestItem], selection: Any) -> list[DeckChangeRequestItem]:
    chosen = [item for item in items if _selection_includes(selection, str(item.id))]
    return with_required_field_additions(chosen, items)


def _effective_after_value(item: DeckChangeRequestItem) -> Any:
    conflict = _primary_conflict(item)
    if conflict is None:
        return item.after_value
    mode = str(conflict.resolution_mode or "").strip().lower()
    if mode == "keep_upstream":
        return conflict.upstream_value
    if mode == "manual":
        return conflict.resolved_value
    return conflict.local_value if mode == "keep_mine" else item.after_value


def _effective_disable_value(item: DeckChangeRequestItem) -> bool:
    conflict = _primary_conflict(item)
    if conflict is None:
        return True
    mode = str(conflict.resolution_mode or "").strip().lower()
    if mode == "keep_upstream":
        return False
    if mode == "manual":
        resolved_value = conflict.resolved_value
        if isinstance(resolved_value, dict):
            return bool(resolved_value.get("disabled"))
        return bool(resolved_value)
    return True


def _make_request_title(
    *,
    deck_item: DeckMarketplaceItem,
    requester_id: int,
    requested_title: str,
) -> str:
    # An untitled contribution is labelled by the client in the reader's
    # language, next to the requester's name; never store a raw user id here.
    return requested_title or ""


def _get_request_install(request_obj: DeckChangeRequest) -> DeckInstall | None:
    deck_install_id = str(request_obj.deck_install_id or "").strip()
    if not deck_install_id:
        return None
    return DeckInstall.query.get(deck_install_id)


def _ensure_request_view_access(request_obj: DeckChangeRequest, *, user_id: int) -> None:
    if int(user_id) not in {int(request_obj.requester_user_id), int(request_obj.owner_user_id)}:
        raise ChangeRequestError(
            "You do not have access to this change request.",
            status=403,
        )


def _ensure_requester_access(request_obj: DeckChangeRequest, *, user_id: int) -> None:
    if int(request_obj.requester_user_id) != int(user_id):
        raise ChangeRequestError(
            "Only the requester can modify this change request.",
            status=403,
        )


def _ensure_owner_access(request_obj: DeckChangeRequest, *, user_id: int) -> None:
    if int(request_obj.owner_user_id) != int(user_id):
        raise ChangeRequestError(
            "Only the deck owner can review this change request.",
            status=403,
        )


def _validate_request_install_binding(
    request_obj: DeckChangeRequest,
    install: DeckInstall,
    *,
    requester_user_id: int | None = None,
) -> None:
    """Reject stale/corrupt request-to-install bindings before mutation."""

    if str(install.id) != str(request_obj.deck_install_id or ""):
        raise ChangeRequestError(
            "The change request is no longer bound to its installed clone.",
            status=409,
            error="CHANGE_REQUEST_INSTALL_MISMATCH",
        )
    if str(install.deck_item_id or "") != str(request_obj.deck_item_id or ""):
        raise ChangeRequestError(
            "The shared deck for this request no longer matches the installed clone.",
            status=409,
            error="CHANGE_REQUEST_INSTALL_MISMATCH",
        )
    if requester_user_id is not None and int(install.user_id) != int(requester_user_id):
        raise ChangeRequestError(
            "Only the owner of the installed clone can modify this change request.",
            status=403,
        )


def _validate_request_base_release(
    request_obj: DeckChangeRequest,
    install: DeckInstall,
) -> None:
    """Keep contribution comparison anchored to one immutable applied release."""
    from app.services.note_base_context import published_base_enabled
    if published_base_enabled():
        return  # Contributions compare the current Base; no per-install pin.

    request_base_id = str(request_obj.base_release_id or "").strip() or None
    install_base_id = str(install.applied_release_id or "").strip() or None
    if request_base_id != install_base_id:
        raise ChangeRequestError(
            "The installed deck moved to another release. Rebuild the contribution draft.",
            status=409,
            error="CHANGE_REQUEST_BASE_RELEASE_CHANGED",
        )
    if request_base_id is None:
        return
    release = db.session.get(DeckRelease, request_base_id)
    if (
        release is None
        or str(release.deck_item_id or "") != str(request_obj.deck_item_id or "")
        or str(release.status or "") != "published"
    ):
        raise ChangeRequestError(
            "The contribution base release is invalid.",
            status=409,
            error="CHANGE_REQUEST_BASE_RELEASE_INVALID",
        )


def _validate_install_release_for_contribution(
    install: DeckInstall,
    deck_item: DeckMarketplaceItem,
) -> None:
    from app.services.note_base_context import published_base_enabled
    if published_base_enabled():
        return
    release_id = str(install.applied_release_id or "").strip() or None
    if str(install.version_mode or "") == "release" and release_id is None:
        raise ChangeRequestError(
            "The installed deck does not have a valid applied release.",
            status=409,
            error="CHANGE_REQUEST_BASE_RELEASE_INVALID",
        )
    if release_id is None:
        return
    release = db.session.get(DeckRelease, release_id)
    if (
        release is None
        or str(release.deck_item_id or "") != str(deck_item.id)
        or str(release.status or "") != "published"
    ):
        raise ChangeRequestError(
            "The installed deck's applied release is invalid.",
            status=409,
            error="CHANGE_REQUEST_BASE_RELEASE_INVALID",
        )


