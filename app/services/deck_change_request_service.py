"""Service layer for clone deck change request workflow."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import Counter
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from app.repositories import deck_change_request_repository, flashcards_share_repository
from app.services import flashcards_share
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
    values = dict(note.field_values or {})
    for key_name in ("Word", "word", "Front", "front", "Expression", "expression"):
        candidate = str(values.get(key_name) or "").strip()
        if candidate:
            return candidate
    for raw_value in values.values():
        candidate = str(raw_value or "").strip()
        if candidate:
            return candidate[:80]
    return f"Note {note.id}"


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


def _item_is_dropped_from_request(item: DeckChangeRequestItem) -> bool:
    return _item_resolution_mode(item) == "keep_upstream"


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
    if requested_title:
        return requested_title
    deck_title = str(deck_item.title or "").strip() or "Shared deck"
    return f"Change Request for {deck_title} ({requester_id})"


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


def _build_local_change_payloads(
    install: DeckInstall,
) -> tuple[list[dict[str, Any]], str]:
    if install.clone_mode != "logical_overlay":
        raise ChangeRequestError(
            "This install does not support change requests.",
            status=409,
        )

    source_note_type_id = str(install.source_note_type_id or "").strip()
    if not source_note_type_id:
        raise ChangeRequestError(
            "This shared deck is not bound to a source note type.",
            status=409,
        )

    fingerprint = compute_overlay_fingerprint(install)
    snapshot_at = _install_snapshot_at(install)
    schema_view = flashcards_share.build_clone_schema_view(
        install=install,
        source_note_type_id=source_note_type_id,
    )
    base_field_defs: dict[str, dict[str, Any]] = {}
    uses_release_base = bool(
        install.version_mode == "release"
        and install.applied_release_id
        and install.applied_release is not None
    )
    if uses_release_base:
        from app.services import deck_release_service

        base_field_defs = deck_release_service.get_field_defs_at_release(
            install.applied_release
        )
    base_field_ids_by_name = {
        str(payload.get("name") or ""): str(field_id)
        for field_id, payload in base_field_defs.items()
        if str(payload.get("name") or "").strip()
    }
    if not base_field_ids_by_name and source_note_type_id:
        base_field_ids_by_name = {
            str(row.name): str(row.id)
            for row in FieldDef.query.filter_by(note_type_id=source_note_type_id).all()
            if str(row.name or "").strip()
        }
    removed_field_names = set(schema_view.removed_field_names or set())
    renamed_field_names = dict(schema_view.renamed_field_names or {})
    if uses_release_base:
        visible_source_order = [
            _order_token(
                kind="source",
                ref_id=field_id,
                name=str(payload.get("name") or ""),
            )
            for field_id, payload in sorted(
                base_field_defs.items(),
                key=lambda item: (
                    int(item[1].get("position") or 0),
                    str(item[1].get("name") or "").lower(),
                    item[0],
                ),
            )
        ]
    else:
        visible_source_order = _build_visible_source_order_tokens(
            source_note_type_id=source_note_type_id,
            snapshot_at=snapshot_at,
        )
    added_rows = (
        DeckCloneAddedFieldDef.query.filter_by(deck_install_id=install.id)
        .order_by(
            DeckCloneAddedFieldDef.position.asc(),
            DeckCloneAddedFieldDef.created_at.asc(),
            DeckCloneAddedFieldDef.id.asc(),
        )
        .all()
    )
    added_ids = {str(row.id) for row in added_rows}
    order_row = DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=install.id).first()
    items: list[dict[str, Any]] = []
    sort_order = 0

    override_rows = (
        DeckCloneFieldDefOverride.query.filter_by(deck_install_id=install.id)
        .order_by(
            DeckCloneFieldDefOverride.source_field_def_id.asc(),
            DeckCloneFieldDefOverride.id.asc(),
        )
        .all()
    )
    live_fields_by_id = _load_field_defs_by_ids(
        {str(row.source_field_def_id) for row in override_rows if row.source_field_def_id}
    )
    has_order_override = order_row is not None and bool(order_row.ordered_def_ids)

    for override in override_rows:
        source_field = live_fields_by_id.get(str(override.source_field_def_id))
        base_payload = base_field_defs.get(str(override.source_field_def_id))
        if source_field is None and base_payload is not None:
            source_field = SimpleNamespace(
                id=str(override.source_field_def_id),
                **base_payload,
            )
        if source_field is None:
            continue

        current_snapshot = (
            {"id": str(source_field.id), **dict(base_payload)}
            if base_payload is not None
            else _source_field_snapshot(source_field)
        )
        metadata = {
            "source_field_def_id": source_field.id,
            "field_name": source_field.name,
        }

        if bool(override.is_disabled):
            items.append(
                {
                    "change_type": CHANGE_TYPE_FIELD_DEF_DISABLE,
                    "source_ref_id": source_field.id,
                    "local_ref_id": override.id,
                    "path_key": source_field.name,
                    "path_label": f"Field {source_field.name} / disable",
                    "before_value": current_snapshot,
                    "after_value": {"disabled": True},
                    "metadata_json": metadata,
                    "sort_order": sort_order,
                }
            )
            sort_order += 1

        properties = dict(override.properties or {})
        for property_name in ("name", "field_type", "required", "position"):
            if property_name not in properties:
                continue
            if property_name == "position" and has_order_override:
                continue
            current_value = current_snapshot.get(property_name)
            proposed_value = properties.get(property_name)
            if current_value == proposed_value:
                continue
            item_metadata = dict(metadata)
            item_metadata["property_name"] = property_name
            items.append(
                {
                    "change_type": CHANGE_TYPE_FIELD_DEF_UPDATE,
                    "source_ref_id": source_field.id,
                    "local_ref_id": override.id,
                    "path_key": property_name,
                    "path_label": f"Field {source_field.name} / {property_name}",
                    "before_value": current_value,
                    "after_value": proposed_value,
                    "metadata_json": item_metadata,
                    "sort_order": sort_order,
                }
            )
            sort_order += 1

    for added_row in added_rows:
        items.append(
            {
                "change_type": CHANGE_TYPE_FIELD_DEF_ADD,
                "source_ref_id": None,
                "local_ref_id": added_row.id,
                "path_key": added_row.name,
                "path_label": f"New field {added_row.name}",
                "before_value": dict(MISSING_MARKER),
                "after_value": _added_field_snapshot(added_row),
                "metadata_json": {
                    "field_name": added_row.name,
                    "source_note_type_id": source_note_type_id,
                },
                "sort_order": sort_order,
            }
        )
        sort_order += 1

    if order_row is not None:
        desired_order = []
        for row in schema_view.field_defs:
            ref_id = str(row.id or "").strip()
            if not ref_id:
                continue
            desired_order.append(
                _order_token(
                    kind="added" if ref_id in added_ids else "source",
                    ref_id=ref_id,
                    name=str(row.name or "").strip(),
                )
            )
        if desired_order != visible_source_order:
            items.append(
                {
                    "change_type": CHANGE_TYPE_FIELD_ORDER_UPDATE,
                    "source_ref_id": source_note_type_id,
                    "local_ref_id": order_row.id,
                    "path_key": "field_order",
                    "path_label": "Field order",
                    "before_value": visible_source_order,
                    "after_value": desired_order,
                    "metadata_json": {"source_note_type_id": source_note_type_id},
                    "sort_order": sort_order,
                }
            )
            sort_order += 1

    note_override_rows = (
        DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install.id)
        .order_by(
            DeckCloneNoteFieldOverride.source_note_id.asc(),
            DeckCloneNoteFieldOverride.field_name.asc(),
            DeckCloneNoteFieldOverride.id.asc(),
        )
        .all()
    )
    base_note_values: dict[str, dict[str, Any]] = {}
    if uses_release_base and note_override_rows:
        from app.services import deck_release_service

        base_note_values = deck_release_service.get_note_values_for_ids_at_release(
            install.applied_release,
            {str(row.source_note_id) for row in note_override_rows},
        )
    source_notes_by_id = _load_notes_by_ids(
        {str(row.source_note_id) for row in note_override_rows if row.source_note_id}
    )
    inverse_rename_map = {
        str(renamed_name): str(source_name)
        for source_name, renamed_name in renamed_field_names.items()
        if str(source_name) and str(renamed_name)
    }
    for row in note_override_rows:
        source_note = source_notes_by_id.get(str(row.source_note_id))
        if source_note is None:
            continue
        stable_field_id = str(row.source_field_def_id or "").strip() or None
        if stable_field_id is None:
            lookup_name = inverse_rename_map.get(str(row.field_name), str(row.field_name))
            stable_field_id = base_field_ids_by_name.get(lookup_name)
        release_field_name = str(
            (
                base_field_defs.get(str(stable_field_id or ""), {})
                or {}
            ).get("name")
            or row.field_name
        )
        effective_field_name = renamed_field_names.get(
            release_field_name,
            release_field_name,
        )
        if effective_field_name in removed_field_names:
            continue
        if uses_release_base and str(source_note.id) not in base_note_values:
            continue
        base_note_proxy = SimpleNamespace(
            field_values=(
                base_note_values.get(str(source_note.id), {})
                if uses_release_base
                else source_note.field_values
            )
        )
        current_values = _apply_schema_only_values(
            base_note_proxy,
            removed_field_names=removed_field_names,
            renamed_field_names=renamed_field_names,
        )
        before_value = (
            current_values.get(effective_field_name)
            if effective_field_name in current_values
            else dict(MISSING_MARKER)
        )
        after_value = dict(MISSING_MARKER) if row.operation == "remove" else row.value
        if before_value == after_value:
            continue
        items.append(
            {
                "change_type": (
                    CHANGE_TYPE_NOTE_FIELD_REMOVE
                    if row.operation == "remove"
                    else CHANGE_TYPE_NOTE_FIELD_SET
                ),
                "source_ref_id": source_note.id,
                "local_ref_id": row.id,
                "path_key": effective_field_name,
                "path_label": f"Note {_note_label(source_note)} / {effective_field_name}",
                "before_value": before_value,
                "after_value": after_value,
                "metadata_json": {
                    "source_note_id": source_note.id,
                    "source_field_def_id": stable_field_id,
                    "field_name": effective_field_name,
                    "source_note_label": _note_label(source_note),
                },
                "sort_order": sort_order,
            }
        )
        sort_order += 1

    return items, fingerprint


def preview_local_changes_for_install(install: DeckInstall) -> dict[str, Any]:
    items, fingerprint = _build_local_change_payloads(install)
    return {
        "deck_install_id": install.id,
        "deck_item_id": install.deck_item_id,
        "overlay_fingerprint": fingerprint,
        "item_count": len(items),
        "change_counts": dict(Counter(item["change_type"] for item in items)),
        "items": items,
    }


def get_request_for_update(
    *,
    user_id: int,
    deck_item_id: str,
) -> tuple[DeckInstall, DeckMarketplaceItem, DeckChangeRequest | None]:
    install = flashcards_share.get_user_deck_install_for_item(
        user_id=user_id,
        deck_item_id=deck_item_id,
    )
    if install is None:
        raise ChangeRequestError(
            "Installed clone deck not found.",
            status=404,
            error="FIELD_NOT_FOUND",
        )
    deck_item = DeckMarketplaceItem.query.get(deck_item_id)
    if deck_item is None:
        raise ChangeRequestError(
            "Deck item not found.",
            status=404,
            error="FIELD_NOT_FOUND",
        )
    active_request = deck_change_request_repository.get_active_request_for_install(
        install.id,
        statuses=OPEN_REQUEST_STATUSES,
    )
    return install, deck_item, active_request


def build_or_refresh_draft_request(
    *,
    deck_item_id: str,
    requester_user_id: int,
    title: str,
    description: str,
) -> DeckChangeRequest:
    install, deck_item, active_request = get_request_for_update(
        user_id=requester_user_id,
        deck_item_id=deck_item_id,
    )
    _validate_install_release_for_contribution(install, deck_item)
    if active_request is not None and active_request.status == REQUEST_STATUS_PENDING_REVIEW:
        raise ChangeRequestError(
            "A change request for this install is already pending review.",
            status=409,
            error="CHANGE_REQUEST_PENDING",
        )
    if active_request is not None:
        _ensure_requester_access(active_request, user_id=requester_user_id)
        _validate_request_install_binding(
            active_request,
            install,
            requester_user_id=requester_user_id,
        )

    item_payloads, fingerprint = _build_local_change_payloads(install)
    if not item_payloads:
        raise ChangeRequestError(
            "No local overlay changes were found for this install.",
            status=400,
            error="NO_LOCAL_CHANGES",
        )

    request_obj = active_request
    if request_obj is None:
        owner_user_id = int(install.source_owner_user_id or deck_item.owner_user_id or 0)
        if not owner_user_id:
            raise ChangeRequestError(
                "The source deck owner could not be resolved.",
                status=409,
            )
        request_obj = DeckChangeRequest(
            deck_install_id=install.id,
            deck_item_id=deck_item.id,
            local_deck_id=install.local_deck_id,
            source_deck_id=install.source_deck_id,
            source_note_type_id=install.source_note_type_id,
            requester_user_id=requester_user_id,
            owner_user_id=owner_user_id,
            overlay_fingerprint=fingerprint,
            base_release_id=install.applied_release_id,
        )
        db.session.add(request_obj)
        db.session.flush()
    else:
        DeckChangeRequestConflict.query.filter_by(
            change_request_id=request_obj.id
        ).delete(synchronize_session=False)
        DeckChangeRequestItem.query.filter_by(
            change_request_id=request_obj.id
        ).delete(synchronize_session=False)
        db.session.expire(request_obj, ["items", "conflicts"])

    request_obj.deck_install_id = install.id
    request_obj.deck_item_id = deck_item.id
    request_obj.local_deck_id = install.local_deck_id
    request_obj.source_deck_id = install.source_deck_id
    request_obj.source_note_type_id = install.source_note_type_id
    request_obj.requester_user_id = requester_user_id
    request_obj.owner_user_id = int(install.source_owner_user_id or deck_item.owner_user_id or request_obj.owner_user_id)
    request_obj.title = _make_request_title(
        deck_item=deck_item,
        requester_id=requester_user_id,
        requested_title=title,
    )
    request_obj.description = description or None
    request_obj.status = REQUEST_STATUS_NEEDS_SYNC
    request_obj.install_snapshot_at = _install_snapshot_at(install)
    request_obj.base_release_id = install.applied_release_id
    request_obj.revision = int(request_obj.revision or 0) + 1
    request_obj.overlay_fingerprint = fingerprint
    request_obj.last_synced_overlay_fingerprint = None
    request_obj.last_sync_status = REQUEST_STATUS_NEEDS_SYNC
    request_obj.last_synced_at = None
    request_obj.submitted_at = None
    request_obj.reviewed_at = None
    request_obj.reviewed_by_user_id = None
    request_obj.merged_at = None
    request_obj.review_comment = None
    db.session.flush()

    for payload in item_payloads:
        db.session.add(
            DeckChangeRequestItem(
                change_request_id=request_obj.id,
                change_type=payload["change_type"],
                source_ref_id=payload.get("source_ref_id"),
                local_ref_id=payload.get("local_ref_id"),
                path_key=payload.get("path_key"),
                path_label=payload.get("path_label"),
                before_value=payload.get("before_value"),
                after_value=payload.get("after_value"),
                metadata_json=payload.get("metadata_json") or {},
                sort_order=int(payload.get("sort_order") or 0),
                is_conflict=False,
            )
        )

    install.last_sync_status = REQUEST_STATUS_NEEDS_SYNC
    _audit(
        requester_user_id,
        "market.deck_change_request.draft",
        {
            "change_request_id": request_obj.id,
            "deck_item_id": deck_item.id,
            "deck_install_id": install.id,
            "item_count": len(item_payloads),
            "overlay_fingerprint": fingerprint,
        },
    )
    db.session.flush()
    return request_obj


def _current_state_for_item(
    request_obj: DeckChangeRequest,
    item: DeckChangeRequestItem,
    *,
    context: dict[str, Any],
) -> Any:
    metadata = dict(item.metadata_json or {})
    change_type = str(item.change_type or "").strip()

    if change_type in {CHANGE_TYPE_NOTE_FIELD_SET, CHANGE_TYPE_NOTE_FIELD_REMOVE}:
        source_note_id = str(metadata.get("source_note_id") or item.source_ref_id or "").strip()
        source_field_id = str(metadata.get("source_field_def_id") or "").strip()
        field_defs_by_id = context.get("field_defs_by_id")
        source_field = (
            field_defs_by_id.get(source_field_id)
            if isinstance(field_defs_by_id, dict) and source_field_id
            else db.session.get(FieldDef, source_field_id) if source_field_id else None
        )
        field_name = str(
            (source_field.name if source_field is not None else None)
            or metadata.get("field_name")
            or item.path_key
            or ""
        ).strip()
        field_name = dict(context.get("rename_map") or {}).get(field_name, field_name)
        notes_by_id = context.get("notes_by_id")
        source_note = (
            notes_by_id.get(source_note_id)
            if isinstance(notes_by_id, dict)
            else Note.query.get(source_note_id)
        )
        if source_note is None:
            return dict(MISSING_MARKER)
        values = _apply_schema_only_values(
            source_note,
            removed_field_names=set(context.get("removed_field_names") or set()),
            renamed_field_names=dict(context.get("rename_map") or {}),
        )
        if field_name in values:
            return values.get(field_name)
        return dict(MISSING_MARKER)

    if change_type == CHANGE_TYPE_FIELD_DEF_UPDATE:
        field_id = str(metadata.get("source_field_def_id") or item.source_ref_id or "").strip()
        field_defs_by_id = context.get("field_defs_by_id")
        source_field = (
            field_defs_by_id.get(field_id)
            if isinstance(field_defs_by_id, dict)
            else FieldDef.query.get(field_id)
        )
        if source_field is None:
            return dict(MISSING_MARKER)
        property_name = str(metadata.get("property_name") or item.path_key or "").strip()
        snapshot = _source_field_snapshot(source_field)
        return snapshot.get(property_name, dict(MISSING_MARKER))

    if change_type == CHANGE_TYPE_FIELD_DEF_DISABLE:
        field_id = str(metadata.get("source_field_def_id") or item.source_ref_id or "").strip()
        field_defs_by_id = context.get("field_defs_by_id")
        source_field = (
            field_defs_by_id.get(field_id)
            if isinstance(field_defs_by_id, dict)
            else FieldDef.query.get(field_id)
        )
        return _source_field_snapshot(source_field)

    if change_type == CHANGE_TYPE_FIELD_DEF_ADD:
        source_note_type_id = str(metadata.get("source_note_type_id") or request_obj.source_note_type_id or "").strip()
        field_name = str(metadata.get("field_name") or item.path_key or "").strip()
        if not source_note_type_id or not field_name:
            return dict(MISSING_MARKER)
        fields_by_name = context.get("fields_by_name")
        source_field = (
            fields_by_name.get(field_name)
            if isinstance(fields_by_name, dict)
            else FieldDef.query.filter_by(note_type_id=source_note_type_id, name=field_name).first()
        )
        return _source_field_snapshot(source_field)

    if change_type == CHANGE_TYPE_FIELD_ORDER_UPDATE:
        source_note_type_id = str(metadata.get("source_note_type_id") or request_obj.source_note_type_id or "").strip()
        current_order = context.get("current_field_order")
        if isinstance(current_order, list):
            return current_order
        return _build_current_source_order_tokens(source_note_type_id)

    return dict(MISSING_MARKER)


def _preload_current_state_context(
    request_obj: DeckChangeRequest,
    items: list[DeckChangeRequestItem],
    *,
    schema_context: dict[str, Any],
) -> dict[str, Any]:
    """Batch-load live rows needed for conflict detection."""

    note_ids: set[str] = set()
    field_ids: set[str] = set()
    needs_fields_by_name = False
    needs_field_order = False
    for item in items:
        metadata = dict(item.metadata_json or {})
        if item.change_type in {CHANGE_TYPE_NOTE_FIELD_SET, CHANGE_TYPE_NOTE_FIELD_REMOVE}:
            note_id = str(metadata.get("source_note_id") or item.source_ref_id or "").strip()
            if note_id:
                note_ids.add(note_id)
            field_id = str(metadata.get("source_field_def_id") or "").strip()
            if field_id:
                field_ids.add(field_id)
        elif item.change_type in {CHANGE_TYPE_FIELD_DEF_UPDATE, CHANGE_TYPE_FIELD_DEF_DISABLE}:
            field_id = str(metadata.get("source_field_def_id") or item.source_ref_id or "").strip()
            if field_id:
                field_ids.add(field_id)
        elif item.change_type == CHANGE_TYPE_FIELD_DEF_ADD:
            needs_fields_by_name = True
        elif item.change_type == CHANGE_TYPE_FIELD_ORDER_UPDATE:
            needs_field_order = True

    context = dict(schema_context)
    context["notes_by_id"] = _load_notes_by_ids(note_ids)
    context["field_defs_by_id"] = _load_field_defs_by_ids(field_ids)
    source_note_type_id = str(request_obj.source_note_type_id or "").strip()
    if needs_fields_by_name and source_note_type_id:
        rows = FieldDef.query.filter_by(note_type_id=source_note_type_id).all()
        context["fields_by_name"] = {str(row.name): row for row in rows}
    if needs_field_order:
        context["current_field_order"] = _build_current_source_order_tokens(
            source_note_type_id
        )
    return context


def _build_conflict_for_item(
    request_obj: DeckChangeRequest,
    item: DeckChangeRequestItem,
    *,
    current_state: Any,
    base_value: Any,
    local_value: Any,
) -> DeckChangeRequestConflict:
    if item.change_type in {CHANGE_TYPE_NOTE_FIELD_SET, CHANGE_TYPE_NOTE_FIELD_REMOVE}:
        conflict_type = "note_field"
    elif item.change_type == CHANGE_TYPE_FIELD_ORDER_UPDATE:
        conflict_type = "field_order"
    else:
        conflict_type = "field_def"
    return DeckChangeRequestConflict(
        change_request_id=request_obj.id,
        item_id=item.id,
        conflict_type=conflict_type,
        source_ref_id=item.source_ref_id,
        upstream_value=current_state,
        local_value=local_value,
        base_value=base_value,
    )


def _item_has_conflict(
    item: DeckChangeRequestItem,
    *,
    current_state: Any,
    existing_conflict: DeckChangeRequestConflict | None = None,
) -> bool:
    if existing_conflict is not None and existing_conflict.resolved_at is not None and _item_is_dropped_from_request(item):
        return False
    if item.change_type == CHANGE_TYPE_FIELD_DEF_DISABLE and _is_missing(current_state):
        return False
    desired_value = _effective_after_value(item)
    if current_state == desired_value:
        return False
    comparison_base = item.before_value
    if existing_conflict is not None and existing_conflict.resolved_at is not None:
        comparison_base = existing_conflict.upstream_value
    return current_state != comparison_base


def sync_request(
    request_obj: DeckChangeRequest,
    *,
    actor_user_id: int,
    enforce_overlay_fingerprint: bool = True,
    status_on_clean: str | None = REQUEST_STATUS_DRAFT,
    audit_action: str = "market.deck_change_request.sync",
    allow_owner_actor: bool = False,
) -> DeckChangeRequest:
    if allow_owner_actor:
        _ensure_owner_access(request_obj, user_id=actor_user_id)
    else:
        _ensure_requester_access(request_obj, user_id=actor_user_id)
    install = _get_request_install(request_obj)
    if install is None:
        raise ChangeRequestError(
            "The installed clone for this change request no longer exists.",
            status=409,
            error="CHANGE_REQUEST_INSTALL_MISSING",
        )
    _validate_request_install_binding(
        request_obj,
        install,
        requester_user_id=None if allow_owner_actor else actor_user_id,
    )
    _validate_request_base_release(request_obj, install)

    if enforce_overlay_fingerprint:
        current_fingerprint = compute_overlay_fingerprint(install)
        if current_fingerprint != str(request_obj.overlay_fingerprint or "").strip():
            request_obj.status = REQUEST_STATUS_NEEDS_SYNC
            request_obj.revision = int(request_obj.revision or 0) + 1
            request_obj.last_sync_status = REQUEST_STATUS_NEEDS_SYNC
            install.last_sync_status = REQUEST_STATUS_NEEDS_SYNC
            db.session.flush()
            raise ChangeRequestError(
                "Local clone changes changed after this draft was built. Rebuild the draft first.",
                status=409,
                error="CHANGE_REQUEST_STALE",
            )

    request_items = list(request_obj.items or [])
    schema_context = _request_schema_context(request_items, use_effective_values=True)
    context = _preload_current_state_context(
        request_obj,
        request_items,
        schema_context=schema_context,
    )
    created_conflicts = 0
    for item in request_items:
        existing_conflict = _primary_conflict(item)
        current_state = _current_state_for_item(request_obj, item, context=context)
        if _item_has_conflict(
            item,
            current_state=current_state,
            existing_conflict=existing_conflict,
        ):
            comparison_base = (
                existing_conflict.upstream_value
                if existing_conflict is not None and existing_conflict.resolved_at is not None
                else item.before_value
            )
            local_value = _effective_after_value(item)
            if existing_conflict is None:
                conflict = _build_conflict_for_item(
                    request_obj,
                    item,
                    current_state=current_state,
                    base_value=comparison_base,
                    local_value=local_value,
                )
                conflict.change_request = request_obj
                conflict.item = item
                db.session.add(conflict)
            else:
                existing_conflict.conflict_type = (
                    "note_field"
                    if item.change_type in {CHANGE_TYPE_NOTE_FIELD_SET, CHANGE_TYPE_NOTE_FIELD_REMOVE}
                    else "field_order"
                    if item.change_type == CHANGE_TYPE_FIELD_ORDER_UPDATE
                    else "field_def"
                )
                existing_conflict.source_ref_id = item.source_ref_id
                existing_conflict.upstream_value = current_state
                existing_conflict.local_value = local_value
                existing_conflict.base_value = comparison_base
                existing_conflict.resolution_mode = None
                existing_conflict.resolved_value = None
                existing_conflict.resolved_by_user_id = None
                existing_conflict.resolved_at = None
            item.is_conflict = True
            created_conflicts += 1
        else:
            if existing_conflict is not None and existing_conflict.resolved_at is None:
                db.session.delete(existing_conflict)
            item.is_conflict = False

    now = _utcnow()
    request_obj.last_synced_at = now
    request_obj.last_synced_overlay_fingerprint = request_obj.overlay_fingerprint
    request_obj.last_sync_status = "has_conflict" if created_conflicts else "clean"
    install.last_synced_at = now
    install.last_sync_status = "has_conflict" if created_conflicts else "clean"
    if created_conflicts:
        request_obj.status = REQUEST_STATUS_HAS_CONFLICT
    elif status_on_clean:
        request_obj.status = status_on_clean
    request_obj.revision = int(request_obj.revision or 0) + 1

    _audit(
        actor_user_id,
        audit_action,
        {
            "change_request_id": request_obj.id,
            "deck_item_id": request_obj.deck_item_id,
            "deck_install_id": request_obj.deck_install_id,
            "conflict_count": created_conflicts,
        },
    )
    db.session.flush()
    return request_obj


def resolve_request_conflict(
    request_obj: DeckChangeRequest,
    *,
    conflict_id: str,
    actor_user_id: int,
    resolution_mode: str,
    resolved_value: Any,
) -> DeckChangeRequest:
    _ensure_requester_access(request_obj, user_id=actor_user_id)
    install = _get_request_install(request_obj)
    if install is None:
        raise ChangeRequestError(
            "The installed clone for this change request no longer exists.",
            status=409,
            error="CHANGE_REQUEST_INSTALL_MISSING",
        )
    _validate_request_install_binding(
        request_obj,
        install,
        requester_user_id=actor_user_id,
    )
    _validate_request_base_release(request_obj, install)
    if request_obj.status != REQUEST_STATUS_HAS_CONFLICT:
        raise ChangeRequestError(
            "This change request does not currently have unresolved conflicts.",
            status=409,
        )
    conflict = deck_change_request_repository.get_request_conflict(request_obj.id, conflict_id)
    if conflict is None:
        raise ChangeRequestError(
            "Conflict not found.",
            status=404,
            error="FIELD_NOT_FOUND",
        )
    if resolution_mode not in RESOLUTION_MODES:
        raise ChangeRequestError(
            "Unsupported conflict resolution mode.",
            status=400,
            field="resolution_mode",
        )

    if resolution_mode == "keep_mine":
        next_value = conflict.local_value
    elif resolution_mode == "keep_upstream":
        next_value = conflict.upstream_value
    else:
        next_value = resolved_value

    conflict.resolution_mode = resolution_mode
    conflict.resolved_value = next_value
    conflict.resolved_by_user_id = actor_user_id
    conflict.resolved_at = _utcnow()
    if conflict.item is not None:
        conflict.item.is_conflict = False

    unresolved_count = (
        DeckChangeRequestConflict.query.filter(
            DeckChangeRequestConflict.change_request_id == request_obj.id,
            DeckChangeRequestConflict.resolved_at.is_(None),
        ).count()
    )
    if unresolved_count == 0:
        request_obj.status = REQUEST_STATUS_DRAFT
        request_obj.last_sync_status = "clean"
        install = _get_request_install(request_obj)
        if install is not None:
            install.last_sync_status = "clean"
    request_obj.revision = int(request_obj.revision or 0) + 1

    _audit(
        actor_user_id,
        "market.deck_change_request.resolve_conflict",
        {
            "change_request_id": request_obj.id,
            "conflict_id": conflict.id,
            "resolution_mode": resolution_mode,
        },
    )
    db.session.flush()
    return request_obj


def _request_has_effective_changes(request_obj: DeckChangeRequest) -> bool:
    request_items = list(request_obj.items or [])
    schema_context = _request_schema_context(request_items, use_effective_values=True)
    context = _preload_current_state_context(
        request_obj,
        request_items,
        schema_context=schema_context,
    )
    for item in request_items:
        if _item_is_dropped_from_request(item):
            continue
        current_state = _current_state_for_item(request_obj, item, context=context)
        desired_value = _effective_after_value(item)
        if item.change_type == CHANGE_TYPE_FIELD_DEF_DISABLE:
            if _effective_disable_value(item) and not _is_missing(current_state):
                return True
            continue
        if current_state != desired_value:
            return True
    return False


def submit_request_for_review(
    request_obj: DeckChangeRequest,
    *,
    actor_user_id: int,
) -> DeckChangeRequest:
    _ensure_requester_access(request_obj, user_id=actor_user_id)
    if request_obj.last_synced_at is None or request_obj.status == REQUEST_STATUS_NEEDS_SYNC:
        raise ChangeRequestError(
            "Sync with upstream is required before submit.",
            status=409,
            error="CHANGE_REQUEST_SYNC_REQUIRED",
        )
    unresolved_conflicts = (
        DeckChangeRequestConflict.query.filter(
            DeckChangeRequestConflict.change_request_id == request_obj.id,
            DeckChangeRequestConflict.resolved_at.is_(None),
        ).count()
    )
    if unresolved_conflicts > 0:
        request_obj.status = REQUEST_STATUS_HAS_CONFLICT
        raise ChangeRequestError(
            "Resolve all conflicts before submit.",
            status=409,
            error="CHANGE_REQUEST_CONFLICTS_UNRESOLVED",
        )

    sync_request(
        request_obj,
        actor_user_id=actor_user_id,
        enforce_overlay_fingerprint=True,
        status_on_clean=REQUEST_STATUS_DRAFT,
        audit_action="market.deck_change_request.sync_before_submit",
    )
    if request_obj.status == REQUEST_STATUS_HAS_CONFLICT:
        raise ChangeRequestError(
            "Upstream changed during submit. Resolve conflicts and try again.",
            status=409,
            error="CHANGE_REQUEST_CONFLICTS_UNRESOLVED",
        )
    if not _request_has_effective_changes(request_obj):
        raise ChangeRequestError(
            "No effective changes remain to submit.",
            status=409,
            error="NO_EFFECTIVE_CHANGES",
        )

    request_obj.status = REQUEST_STATUS_PENDING_REVIEW
    request_obj.revision = int(request_obj.revision or 0) + 1
    request_obj.submitted_at = _utcnow()
    _audit(
        actor_user_id,
        "market.deck_change_request.submit",
        {
            "change_request_id": request_obj.id,
            "deck_item_id": request_obj.deck_item_id,
            "deck_install_id": request_obj.deck_install_id,
        },
    )
    db.session.flush()
    return request_obj


def get_request_detail_for_user(
    *,
    request_id: str,
    user_id: int,
) -> DeckChangeRequest:
    request_obj = deck_change_request_repository.get_request_with_detail(request_id)
    if request_obj is None:
        raise ChangeRequestError(
            "Change request not found.",
            status=404,
            error="FIELD_NOT_FOUND",
        )
    _ensure_request_view_access(request_obj, user_id=user_id)
    return request_obj


def list_incoming_requests(
    *,
    owner_user_id: int,
    deck_item_id: str | None = None,
    cursor: str | None = None,
    limit: Any = None,
) -> dict[str, Any]:
    page_limit = _coerce_page_limit(
        limit,
        default=DEFAULT_INBOX_PAGE_LIMIT,
        maximum=MAX_INBOX_PAGE_LIMIT,
    )
    normalized_deck_item_id = str(deck_item_id or "").strip() or None
    cursor_payload = _decode_cursor(cursor, expected_kind="change_request_inbox")
    cursor_updated_at = None
    cursor_id = None
    if cursor_payload is not None:
        if (str(cursor_payload.get("deck_item_id") or "").strip() or None) != normalized_deck_item_id:
            raise ChangeRequestError(
                "cursor does not match the current inbox filter.",
                status=400,
                field="cursor",
            )
        try:
            cursor_updated_at = datetime.fromisoformat(str(cursor_payload["updated_at"]))
            cursor_id = str(cursor_payload["id"]).strip()
            if not cursor_id:
                raise ValueError("empty cursor id")
        except (KeyError, TypeError, ValueError) as exc:
            raise ChangeRequestError(
                "cursor is invalid.",
                status=400,
                field="cursor",
            ) from exc

    rows, has_more = deck_change_request_repository.list_incoming_requests_for_owner(
        owner_user_id,
        statuses={REQUEST_STATUS_PENDING_REVIEW},
        deck_item_id=normalized_deck_item_id,
        cursor_updated_at=cursor_updated_at,
        cursor_id=cursor_id,
        limit=page_limit,
    )
    next_cursor = None
    if has_more and rows:
        last_request = rows[-1][0]
        next_cursor = _encode_cursor(
            {
                "kind": "change_request_inbox",
                "deck_item_id": normalized_deck_item_id,
                "updated_at": last_request.updated_at.isoformat(timespec="microseconds"),
                "id": str(last_request.id),
            }
        )
    return {
        "items": [
            serialize_request_summary(
                request_obj,
                item_count=item_count,
                unresolved_conflict_count=unresolved_count,
            )
            for request_obj, item_count, unresolved_count in rows
        ],
        "page": {
            "limit": page_limit,
            "has_more": has_more,
            "next_cursor": next_cursor,
        },
    }


def get_serialized_request_page_for_user(
    *,
    request_id: str,
    user_id: int,
    cursor: str | None = None,
    limit: Any = None,
    change_type: str | None = None,
    query_text: str | None = None,
    conflicts_only: bool = False,
) -> dict[str, Any]:
    request_obj = deck_change_request_repository.get_request_header(request_id)
    if request_obj is None:
        raise ChangeRequestError(
            "Change request not found.",
            status=404,
            error="FIELD_NOT_FOUND",
        )
    _ensure_request_view_access(request_obj, user_id=user_id)
    page_limit = _coerce_page_limit(
        limit,
        default=DEFAULT_ITEM_PAGE_LIMIT,
        maximum=MAX_ITEM_PAGE_LIMIT,
    )
    change_types, normalized_query, normalized_conflicts_only, filter_key = _normalize_item_filters(
        raw_change_type=change_type,
        query_text=query_text,
        conflicts_only=conflicts_only,
    )
    cursor_payload = _decode_cursor(cursor, expected_kind="change_request_items")
    after_sort_order = None
    after_id = None
    if cursor_payload is not None:
        try:
            if str(cursor_payload["request_id"]) != str(request_obj.id):
                raise ValueError("request mismatch")
            if int(cursor_payload["revision"]) != int(request_obj.revision or 0):
                raise ChangeRequestError(
                    "The change request changed while paging. Refresh the diff.",
                    status=409,
                    error="CHANGE_REQUEST_CURSOR_STALE",
                    field="cursor",
                )
            if str(cursor_payload["filter_key"]) != filter_key:
                raise ValueError("filter mismatch")
            after_sort_order = int(cursor_payload["sort_order"])
            after_id = str(cursor_payload["id"]).strip()
            if not after_id:
                raise ValueError("empty cursor id")
        except ChangeRequestError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ChangeRequestError(
                "cursor does not match the current request or filters.",
                status=400,
                field="cursor",
            ) from exc

    item_rows, has_more, filtered_count = deck_change_request_repository.list_request_items_page(
        request_obj.id,
        after_sort_order=after_sort_order,
        after_id=after_id,
        limit=page_limit,
        change_types=change_types,
        query_text=normalized_query,
        conflicts_only=normalized_conflicts_only,
    )
    item_count, unresolved_count, change_counts = deck_change_request_repository.get_request_counts(
        request_obj.id
    )
    next_cursor = None
    if has_more and item_rows:
        last_item = item_rows[-1]
        next_cursor = _encode_cursor(
            {
                "kind": "change_request_items",
                "request_id": str(request_obj.id),
                "revision": int(request_obj.revision or 0),
                "filter_key": filter_key,
                "sort_order": int(last_item.sort_order or 0),
                "id": str(last_item.id),
            }
        )
    return serialize_request_page(
        request_obj,
        viewer_user_id=user_id,
        item_rows=item_rows,
        item_count=item_count,
        unresolved_conflict_count=unresolved_count,
        change_counts=change_counts,
        page={
            "limit": page_limit,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "filtered_item_count": filtered_count,
            "revision": int(request_obj.revision or 0),
        },
    )


def get_active_request_for_deck_item(
    *,
    user_id: int,
    deck_item_id: str,
) -> DeckChangeRequest | None:
    install = flashcards_share.get_user_deck_install_for_item(
        user_id=user_id,
        deck_item_id=deck_item_id,
    )
    if install is None:
        return None
    active_request = deck_change_request_repository.get_active_request_for_install(
        install.id,
        statuses=OPEN_REQUEST_STATUSES,
    )
    if active_request is None:
        return None
    return deck_change_request_repository.get_request_header(active_request.id)


def has_pending_review_request_for_install(deck_install_id: str) -> bool:
    if not deck_install_id:
        return False
    row = deck_change_request_repository.get_active_request_for_install(
        deck_install_id,
        statuses={REQUEST_STATUS_PENDING_REVIEW},
    )
    return row is not None


def _rename_note_type_field_values(
    *,
    note_type_id: str,
    old_name: str,
    new_name: str,
) -> None:
    if not note_type_id or not old_name or not new_name or old_name == new_name:
        return
    rows = Note.query.filter_by(note_type_id=note_type_id).all()
    for note in rows:
        values = dict(note.field_values or {})
        if old_name in values and new_name not in values:
            values[new_name] = values.pop(old_name)
        elif old_name in values:
            values.pop(old_name)
        note.field_values = values


def _remove_note_type_field_values(
    *,
    note_type_id: str,
    field_name: str,
) -> None:
    if not note_type_id or not field_name:
        return
    rows = Note.query.filter_by(note_type_id=note_type_id).all()
    for note in rows:
        values = dict(note.field_values or {})
        if field_name in values:
            values.pop(field_name, None)
            note.field_values = values


def _normalize_field_positions(note_type_id: str) -> None:
    rows = (
        FieldDef.query.filter_by(note_type_id=note_type_id)
        .order_by(FieldDef.position.asc(), FieldDef.created_at.asc(), FieldDef.id.asc())
        .all()
    )
    for index, row in enumerate(rows):
        row.position = index


def _cleanup_install_overlay_rows(
    install: DeckInstall,
    request_obj: DeckChangeRequest,
) -> None:
    override_ids: set[str] = set()
    added_ids: set[str] = set()
    order_ids: set[str] = set()
    note_override_ids: set[str] = set()
    for item in request_obj.items:
        local_ref_id = str(item.local_ref_id or "").strip()
        if not local_ref_id:
            continue
        if item.change_type in {CHANGE_TYPE_FIELD_DEF_UPDATE, CHANGE_TYPE_FIELD_DEF_DISABLE}:
            override_ids.add(local_ref_id)
        elif item.change_type == CHANGE_TYPE_FIELD_DEF_ADD:
            added_ids.add(local_ref_id)
        elif item.change_type == CHANGE_TYPE_FIELD_ORDER_UPDATE:
            order_ids.add(local_ref_id)
        elif item.change_type in {CHANGE_TYPE_NOTE_FIELD_SET, CHANGE_TYPE_NOTE_FIELD_REMOVE}:
            note_override_ids.add(local_ref_id)

    if override_ids:
        DeckCloneFieldDefOverride.query.filter(
            DeckCloneFieldDefOverride.deck_install_id == install.id,
            DeckCloneFieldDefOverride.id.in_(sorted(override_ids)),
        ).delete(synchronize_session=False)
    if added_ids:
        DeckCloneAddedFieldDef.query.filter(
            DeckCloneAddedFieldDef.deck_install_id == install.id,
            DeckCloneAddedFieldDef.id.in_(sorted(added_ids)),
        ).delete(synchronize_session=False)
    if order_ids:
        DeckCloneFieldOrderOverride.query.filter(
            DeckCloneFieldOrderOverride.deck_install_id == install.id,
            DeckCloneFieldOrderOverride.id.in_(sorted(order_ids)),
        ).delete(synchronize_session=False)
    if note_override_ids:
        DeckCloneNoteFieldOverride.query.filter(
            DeckCloneNoteFieldOverride.deck_install_id == install.id,
            DeckCloneNoteFieldOverride.id.in_(sorted(note_override_ids)),
        ).delete(synchronize_session=False)


def approve_and_merge_request(
    request_obj: DeckChangeRequest,
    *,
    actor_user_id: int,
    review_comment: str,
) -> DeckChangeRequest:
    _ensure_owner_access(request_obj, user_id=actor_user_id)
    if request_obj.status != REQUEST_STATUS_PENDING_REVIEW:
        raise ChangeRequestError(
            "Only pending review requests can be approved.",
            status=409,
        )

    sync_request(
        request_obj,
        actor_user_id=actor_user_id,
        enforce_overlay_fingerprint=False,
        status_on_clean=REQUEST_STATUS_PENDING_REVIEW,
        audit_action="market.deck_change_request.sync_before_merge",
        allow_owner_actor=True,
    )
    if request_obj.status == REQUEST_STATUS_HAS_CONFLICT:
        raise ChangeRequestError(
            "Upstream changed after submission. The requester must resolve conflicts again.",
            status=409,
            error="CHANGE_REQUEST_CONFLICTS_UNRESOLVED",
        )

    if any(
        item.change_type == CHANGE_TYPE_FIELD_DEF_DISABLE
        and not _item_is_dropped_from_request(item)
        and _effective_disable_value(item)
        for item in request_obj.items
    ):
        # FieldDef is the stable identity used by releases and every clone
        # overlay.  Hard deletion would cascade-delete clone schema deltas and
        # make old release diffs impossible to address.  Keep this blocked
        # until the shared entity has an explicit soft-retirement lifecycle.
        raise ChangeRequestError(
            "Shared fields must be retired instead of deleted before this contribution can be merged.",
            status=409,
            error="SHARED_ENTITY_RETIRE_REQUIRED",
        )

    install = _get_request_install(request_obj)
    if install is None:
        raise ChangeRequestError(
            "The installed clone for this change request no longer exists.",
            status=409,
            error="CHANGE_REQUEST_INSTALL_MISSING",
        )

    source_note_type_id = str(request_obj.source_note_type_id or install.source_note_type_id or "").strip()
    current_context = _request_schema_context(list(request_obj.items or []), use_effective_values=True)
    field_order_item = next(
        (
            item
            for item in request_obj.items
            if item.change_type == CHANGE_TYPE_FIELD_ORDER_UPDATE and not _item_is_dropped_from_request(item)
        ),
        None,
    )

    position_updates: list[tuple[str, int]] = []
    added_field_id_map: dict[str, str] = {}

    for item in request_obj.items:
        if _item_is_dropped_from_request(item):
            continue
        if item.change_type != CHANGE_TYPE_FIELD_DEF_UPDATE:
            continue
        metadata = dict(item.metadata_json or {})
        field_id = str(metadata.get("source_field_def_id") or item.source_ref_id or "").strip()
        property_name = str(metadata.get("property_name") or item.path_key or "").strip()
        field_obj = FieldDef.query.get(field_id)
        if field_obj is None:
            continue
        desired_value = _effective_after_value(item)
        if property_name == "name":
            current_name = str(field_obj.name or "")
            next_name = str(desired_value or "").strip()
            if next_name and next_name != current_name:
                _rename_note_type_field_values(
                    note_type_id=field_obj.note_type_id,
                    old_name=current_name,
                    new_name=next_name,
                )
                field_obj.name = next_name
        elif property_name == "field_type":
            next_field_type = str(desired_value or "").strip().lower()
            if next_field_type:
                field_obj.field_type = next_field_type
        elif property_name == "required":
            field_obj.required = bool(desired_value)
        elif property_name == "position":
            try:
                position_updates.append((field_obj.id, int(desired_value)))
            except (TypeError, ValueError):
                continue

    for item in request_obj.items:
        if _item_is_dropped_from_request(item):
            continue
        if item.change_type != CHANGE_TYPE_FIELD_DEF_ADD:
            continue
        metadata = dict(item.metadata_json or {})
        desired_value = _effective_after_value(item)
        if not isinstance(desired_value, dict):
            continue
        field_name = str(desired_value.get("name") or metadata.get("field_name") or "").strip()
        if not field_name or not source_note_type_id:
            continue
        existing_field = FieldDef.query.filter_by(
            note_type_id=source_note_type_id,
            name=field_name,
        ).first()
        if existing_field is not None:
            added_field_id_map[str(item.local_ref_id or "")] = existing_field.id
            continue
        next_field = FieldDef(
            note_type_id=source_note_type_id,
            name=field_name,
            field_type=str(desired_value.get("field_type") or "text").strip().lower() or "text",
            position=int(desired_value.get("position") or 0),
            required=bool(desired_value.get("required")),
        )
        db.session.add(next_field)
        db.session.flush()
        added_field_id_map[str(item.local_ref_id or "")] = next_field.id

    rename_map = dict(current_context.get("rename_map") or {})
    note_change_items = [
        item
        for item in request_obj.items
        if not _item_is_dropped_from_request(item)
        and item.change_type in {CHANGE_TYPE_NOTE_FIELD_SET, CHANGE_TYPE_NOTE_FIELD_REMOVE}
    ]
    notes_by_id = _load_notes_by_ids(
        {
            str((dict(item.metadata_json or {})).get("source_note_id") or item.source_ref_id or "")
            for item in note_change_items
        }
    )
    note_field_defs_by_id = _load_field_defs_by_ids(
        {
            str((dict(item.metadata_json or {})).get("source_field_def_id") or "")
            for item in note_change_items
        }
    )
    for item in note_change_items:
        metadata = dict(item.metadata_json or {})
        source_note_id = str(metadata.get("source_note_id") or item.source_ref_id or "").strip()
        source_note = notes_by_id.get(source_note_id)
        if source_note is None:
            continue
        source_field_id = str(metadata.get("source_field_def_id") or "").strip()
        source_field = note_field_defs_by_id.get(source_field_id) if source_field_id else None
        field_name = str(
            (source_field.name if source_field is not None else None)
            or metadata.get("field_name")
            or item.path_key
            or ""
        ).strip()
        field_name = rename_map.get(field_name, field_name)
        desired_value = _effective_after_value(item)
        values = dict(source_note.field_values or {})
        if item.change_type == CHANGE_TYPE_NOTE_FIELD_REMOVE or _is_missing(desired_value):
            values.pop(field_name, None)
        else:
            values[field_name] = desired_value
        source_note.field_values = values

    for item in request_obj.items:
        if _item_is_dropped_from_request(item):
            continue
        if item.change_type != CHANGE_TYPE_FIELD_DEF_DISABLE:
            continue
        if not _effective_disable_value(item):
            continue
        metadata = dict(item.metadata_json or {})
        field_obj = FieldDef.query.get(str(metadata.get("source_field_def_id") or item.source_ref_id or "").strip())
        if field_obj is None:
            continue
        _remove_note_type_field_values(
            note_type_id=field_obj.note_type_id,
            field_name=field_obj.name,
        )
        db.session.delete(field_obj)

    if field_order_item is not None:
        desired_order = _effective_after_value(field_order_item)
        if isinstance(desired_order, list):
            assigned_ids: list[str] = []
            next_position = 0
            for token in desired_order:
                if not isinstance(token, dict):
                    continue
                ref_kind = str(token.get("kind") or "source").strip().lower()
                ref_id = str(token.get("id") or "").strip()
                target_field_id = added_field_id_map.get(ref_id) if ref_kind == "added" else ref_id
                if not target_field_id or target_field_id in assigned_ids:
                    continue
                field_obj = FieldDef.query.get(target_field_id)
                if field_obj is None:
                    continue
                field_obj.position = next_position
                next_position += 1
                assigned_ids.append(target_field_id)

            remaining_rows = (
                FieldDef.query.filter_by(note_type_id=source_note_type_id)
                .order_by(FieldDef.position.asc(), FieldDef.created_at.asc(), FieldDef.id.asc())
                .all()
            )
            for row in remaining_rows:
                if row.id in assigned_ids:
                    continue
                row.position = next_position
                next_position += 1
    else:
        for field_id, position in position_updates:
            field_obj = FieldDef.query.get(field_id)
            if field_obj is not None:
                field_obj.position = position

    if source_note_type_id:
        _normalize_field_positions(source_note_type_id)

    merged_at = _utcnow()
    install.last_synced_at = merged_at
    # A contribution merge updates the owner's working tree only. The
    # contributor keeps the local overlay and remains pinned to the release
    # they explicitly applied; publishing is the only operation that advances
    # the shared release head.
    install.last_sync_status = REQUEST_STATUS_NEEDS_SYNC

    request_obj.status = REQUEST_STATUS_MERGED
    request_obj.revision = int(request_obj.revision or 0) + 1
    request_obj.reviewed_by_user_id = actor_user_id
    request_obj.reviewed_at = merged_at
    request_obj.merged_at = merged_at
    request_obj.review_comment = review_comment or None
    request_obj.last_sync_status = "clean"
    if request_obj.deck_item is not None:
        request_obj.deck_item.updated_at = merged_at
        request_obj.deck_item.working_revision = int(
            request_obj.deck_item.working_revision or 0
        ) + 1

    _audit(
        actor_user_id,
        "market.deck_change_request.merge",
        {
            "change_request_id": request_obj.id,
            "deck_item_id": request_obj.deck_item_id,
            "deck_install_id": request_obj.deck_install_id,
            "merge_status": request_obj.status,
        },
    )
    db.session.flush()
    return request_obj


def reject_request(
    request_obj: DeckChangeRequest,
    *,
    actor_user_id: int,
    review_comment: str,
) -> DeckChangeRequest:
    _ensure_owner_access(request_obj, user_id=actor_user_id)
    if request_obj.status != REQUEST_STATUS_PENDING_REVIEW:
        raise ChangeRequestError(
            "Only pending review requests can be rejected.",
            status=409,
        )
    request_obj.status = REQUEST_STATUS_REJECTED
    request_obj.revision = int(request_obj.revision or 0) + 1
    request_obj.reviewed_by_user_id = actor_user_id
    request_obj.reviewed_at = _utcnow()
    request_obj.review_comment = review_comment or None
    install = _get_request_install(request_obj)
    if install is not None:
        install.last_sync_status = REQUEST_STATUS_NEEDS_SYNC
    _audit(
        actor_user_id,
        "market.deck_change_request.reject",
        {
            "change_request_id": request_obj.id,
            "deck_item_id": request_obj.deck_item_id,
            "deck_install_id": request_obj.deck_install_id,
        },
    )
    db.session.flush()
    return request_obj


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
        "requester": {
            "id": request_obj.requester.id if request_obj.requester else request_obj.requester_user_id,
            "username": request_obj.requester.username if request_obj.requester else "Unknown",
        },
        "owner": {
            "id": request_obj.owner.id if request_obj.owner else request_obj.owner_user_id,
            "username": request_obj.owner.username if request_obj.owner else "Unknown",
        },
        "reviewed_by": (
            {
                "id": request_obj.reviewed_by.id,
                "username": request_obj.reviewed_by.username,
            }
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
        "requester": {
            "id": request_obj.requester.id if request_obj.requester else request_obj.requester_user_id,
            "username": request_obj.requester.username if request_obj.requester else "Unknown",
        },
        "deck_item": (
            {
                "id": request_obj.deck_item.id,
                "title": request_obj.deck_item.title,
            }
            if request_obj.deck_item
            else None
        ),
        "item_count": int(item_count),
        "unresolved_conflict_count": int(unresolved_conflict_count),
        "submitted_at": request_obj.submitted_at.isoformat() if request_obj.submitted_at else None,
        "updated_at": request_obj.updated_at.isoformat() if request_obj.updated_at else None,
    }
