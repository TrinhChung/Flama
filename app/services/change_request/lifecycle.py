"""Draft creation, conflict resolution, submission, and querying of change requests."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.repositories import deck_change_request_repository, flashcards_share_repository
from app.services import flashcards_share
from app.services.change_request.helpers import (
    CHANGE_REQUEST_DIFF_FILTERS,
    CHANGE_TYPE_FIELD_DEF_ADD,
    CHANGE_TYPE_FIELD_DEF_DISABLE,
    CHANGE_TYPE_FIELD_DEF_UPDATE,
    CHANGE_TYPE_FIELD_ORDER_UPDATE,
    CHANGE_TYPE_NOTE_FIELD_REMOVE,
    CHANGE_TYPE_NOTE_FIELD_SET,
    DEFAULT_INBOX_PAGE_LIMIT,
    DEFAULT_ITEM_PAGE_LIMIT,
    MAX_INBOX_PAGE_LIMIT,
    MAX_ITEM_PAGE_LIMIT,
    MISSING_MARKER,
    OPEN_EDITABLE_REQUEST_STATUSES,
    OPEN_REQUEST_STATUSES,
    REQUEST_STATUS_DRAFT,
    REQUEST_STATUS_HAS_CONFLICT,
    REQUEST_STATUS_MERGED,
    REQUEST_STATUS_NEEDS_SYNC,
    REQUEST_STATUS_PENDING_REVIEW,
    REQUEST_STATUS_REJECTED,
    RESOLUTION_MODES,
    ChangeRequestError,
    _added_field_snapshot,
    _apply_schema_only_values,
    _audit,
    _build_current_source_order_tokens,
    _coerce_page_limit,
    _decode_cursor,
    _effective_after_value,
    _effective_disable_value,
    _encode_cursor,
    _ensure_owner_access,
    _ensure_request_view_access,
    _ensure_requester_access,
    _get_request_install,
    _install_snapshot_at,
    _is_missing,
    _item_is_dropped_from_request,
    _item_resolution_mode,
    _load_field_defs_by_ids,
    _load_notes_by_ids,
    _make_request_title,
    _normalize_item_filters,
    _note_label,
    _order_token,
    _primary_conflict,
    _request_schema_context,
    _source_field_snapshot,
    _stable_json,
    _utcnow,
    _validate_install_release_for_contribution,
    _validate_request_base_release,
    _validate_request_install_binding,
    compute_overlay_fingerprint,
)
from app.services.change_request.preview import (
    _build_local_change_payloads,
    preview_local_changes_for_install,
)
from app.services.change_request.serializers import (
    serialize_request_page,
    serialize_request_summary,
)
from models import db
from models.deck_change_request import DeckChangeRequest
from models.deck_change_request_conflict import DeckChangeRequestConflict
from models.deck_change_request_item import DeckChangeRequestItem
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.field_def import FieldDef
from models.note import Note


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
    return active_request


def has_pending_review_request_for_install(deck_install_id: str) -> bool:
    if not deck_install_id:
        return False
    row = deck_change_request_repository.get_active_request_for_install(
        deck_install_id,
        statuses={REQUEST_STATUS_PENDING_REVIEW},
    )
    return row is not None


