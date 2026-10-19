"""Approval, merging, and rejection execution for deck change requests."""

from __future__ import annotations

from typing import Any

from app.repositories import deck_change_request_repository
from app.services import deck_working_tree_service, flashcards_share
from app.services.change_request.helpers import (
    CHANGE_TYPE_FIELD_DEF_ADD,
    CHANGE_TYPE_FIELD_DEF_DISABLE,
    CHANGE_TYPE_FIELD_DEF_UPDATE,
    CHANGE_TYPE_FIELD_ORDER_UPDATE,
    CHANGE_TYPE_NOTE_FIELD_REMOVE,
    CHANGE_TYPE_NOTE_FIELD_SET,
    REQUEST_STATUS_HAS_CONFLICT,
    REQUEST_STATUS_MERGED,
    REQUEST_STATUS_NEEDS_SYNC,
    REQUEST_STATUS_PENDING_REVIEW,
    REQUEST_STATUS_REJECTED,
    ChangeRequestError,
    _audit,
    _effective_after_value,
    _effective_disable_value,
    _ensure_owner_access,
    _get_request_install,
    _is_missing,
    _item_is_dropped_from_request,
    _load_field_defs_by_ids,
    _load_notes_by_ids,
    _order_token,
    _request_schema_context,
    _utcnow,
)
from app.services.change_request.lifecycle import sync_request
from models import db
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


def _build_merged_working_tree_changes(
    request_obj: DeckChangeRequest,
    *,
    added_field_id_map: dict[str, str],
    source_note_type_id: str,
) -> list[dict[str, Any]]:
    """Describe final owner state touched by one contribution merge."""

    changes: list[dict[str, Any]] = []
    field_property_values = {
        "name": lambda row: row.name,
        "field_type": lambda row: row.field_type,
        "position": lambda row: int(row.position or 0),
        "required": lambda row: bool(row.required),
        "identity_role": lambda row: row.identity_role,
    }
    has_field_order_change = False
    for request_item in request_obj.items:
        if _item_is_dropped_from_request(request_item):
            continue
        metadata = dict(request_item.metadata_json or {})
        if request_item.change_type == CHANGE_TYPE_FIELD_DEF_UPDATE:
            field_id = str(
                metadata.get("source_field_def_id") or request_item.source_ref_id or ""
            ).strip()
            property_key = str(
                metadata.get("property_name") or request_item.path_key or ""
            ).strip()
            field_obj = db.session.get(FieldDef, field_id) if field_id else None
            value_getter = field_property_values.get(property_key)
            if field_obj is None or value_getter is None:
                continue
            changes.append(
                {
                    "entity_kind": "field_def",
                    "entity_id": field_obj.id,
                    "field_def_id": field_obj.id,
                    "property_key": property_key,
                    "operation": "set",
                    "current_value": value_getter(field_obj),
                    "source_deck_id": request_obj.source_deck_id,
                    "metadata": {"field_name": field_obj.name},
                }
            )
            continue
        if request_item.change_type == CHANGE_TYPE_FIELD_DEF_ADD:
            field_id = added_field_id_map.get(str(request_item.local_ref_id or ""))
            field_obj = db.session.get(FieldDef, field_id) if field_id else None
            if field_obj is None:
                continue
            for property_key, value_getter in field_property_values.items():
                changes.append(
                    {
                        "entity_kind": "field_def",
                        "entity_id": field_obj.id,
                        "field_def_id": field_obj.id,
                        "property_key": property_key,
                        "operation": "add",
                        "current_value": value_getter(field_obj),
                        "source_deck_id": request_obj.source_deck_id,
                        "metadata": {"field_name": field_obj.name},
                    }
                )
            continue
        if request_item.change_type == CHANGE_TYPE_FIELD_ORDER_UPDATE:
            has_field_order_change = True
            continue
        if request_item.change_type not in {
            CHANGE_TYPE_NOTE_FIELD_SET,
            CHANGE_TYPE_NOTE_FIELD_REMOVE,
        }:
            continue
        note_id = str(
            metadata.get("source_note_id") or request_item.source_ref_id or ""
        ).strip()
        field_id = str(
            metadata.get("source_field_def_id")
            or added_field_id_map.get(
                str(metadata.get("local_added_field_def_id") or "")
            )
            or ""
        ).strip()
        note = db.session.get(Note, note_id) if note_id else None
        field_obj = db.session.get(FieldDef, field_id) if field_id else None
        if note is None or field_obj is None:
            continue
        values = dict(note.field_values or {})
        field_name = str(field_obj.name)
        exists = field_name in values
        changes.append(
            {
                "entity_kind": "note_field",
                "entity_id": note.id,
                "field_def_id": field_obj.id,
                "property_key": f"field:{field_obj.id}",
                "operation": "set" if exists else "remove",
                "current_value": values.get(field_name),
                "source_deck_id": note.deck_id,
                "metadata": {"field_name": field_name},
            }
        )

    if has_field_order_change and source_note_type_id:
        for field_obj in FieldDef.query.filter_by(
            note_type_id=source_note_type_id
        ).all():
            changes.append(
                {
                    "entity_kind": "field_def",
                    "entity_id": field_obj.id,
                    "field_def_id": field_obj.id,
                    "property_key": "position",
                    "operation": "set",
                    "current_value": int(field_obj.position or 0),
                    "source_deck_id": request_obj.source_deck_id,
                    "metadata": {"field_name": field_obj.name},
                }
            )
    return changes


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
            str(
                (dict(item.metadata_json or {})).get("source_field_def_id")
                or added_field_id_map.get(
                    str((dict(item.metadata_json or {})).get("local_added_field_def_id") or "")
                )
                or ""
            )
            for item in note_change_items
        }
    )
    for item in note_change_items:
        metadata = dict(item.metadata_json or {})
        source_note_id = str(metadata.get("source_note_id") or item.source_ref_id or "").strip()
        source_note = notes_by_id.get(source_note_id)
        if source_note is None:
            continue
        source_field_id = str(
            metadata.get("source_field_def_id")
            or added_field_id_map.get(str(metadata.get("local_added_field_def_id") or ""))
            or ""
        ).strip()
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
    dirty_changes = _build_merged_working_tree_changes(
        request_obj,
        added_field_id_map=added_field_id_map,
        source_note_type_id=source_note_type_id,
    )
    if request_obj.deck_item is not None:
        request_obj.deck_item.updated_at = merged_at
        if dirty_changes:
            deck_working_tree_service.mark_deck_item_batch_changed(
                item=request_obj.deck_item,
                changes=dirty_changes,
            )

    _audit(
        actor_user_id,
        "market.deck_change_request.merge",
        {
            "change_request_id": request_obj.id,
            "deck_item_id": request_obj.deck_item_id,
            "deck_install_id": request_obj.deck_install_id,
            "merge_status": request_obj.status,
            "dirty_change_count": len(dirty_changes),
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


