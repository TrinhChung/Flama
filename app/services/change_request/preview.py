"""Local change computation and preview generation for deck change requests."""

from __future__ import annotations

from collections import Counter
from types import SimpleNamespace
from typing import Any

from app.repositories import deck_change_request_repository
from app.services import flashcards_share
from app.services.change_request.helpers import (
    CHANGE_REQUEST_DIFF_FILTERS,
    CHANGE_REQUEST_CHANGE_TYPES,
    CHANGE_TYPE_FIELD_DEF_ADD,
    CHANGE_TYPE_FIELD_DEF_DISABLE,
    CHANGE_TYPE_FIELD_DEF_UPDATE,
    CHANGE_TYPE_FIELD_ORDER_UPDATE,
    CHANGE_TYPE_NOTE_FIELD_REMOVE,
    CHANGE_TYPE_NOTE_FIELD_SET,
    DEFAULT_ITEM_PAGE_LIMIT,
    MAX_ITEM_PAGE_LIMIT,
    MISSING_MARKER,
    ChangeRequestError,
    _added_field_snapshot,
    _apply_schema_only_values,
    _build_visible_source_order_tokens,
    _coerce_page_limit,
    _decode_cursor,
    _encode_cursor,
    _ensure_requester_access,
    _install_snapshot_at,
    _is_missing,
    _load_field_defs_by_ids,
    _load_notes_by_ids,
    _normalize_item_filters,
    _note_label,
    _order_token,
    _overlay_state_payload,
    _request_schema_context,
    _source_field_snapshot,
    _stable_json,
    _utcnow,
    _validate_install_release_for_contribution,
    compute_overlay_fingerprint,
)
from models import db
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_field_order_override import DeckCloneFieldOrderOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_release import DeckRelease
from models.field_def import FieldDef
from models.note import Note


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
    added_field_ids_by_name = {
        str(row.name): str(row.id)
        for row in added_rows
        if str(row.name or "").strip()
    }
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
        if uses_release_base and base_payload is None:
            raise ChangeRequestError(
                "A schema override no longer maps to a field in the applied release.",
                status=409,
                error="CHANGE_REQUEST_FIELD_IDENTITY_MISSING",
            )
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
        local_added_field_def_id = (
            added_field_ids_by_name.get(str(row.field_name))
            if stable_field_id is None
            else None
        )
        if uses_release_base and stable_field_id is None and local_added_field_def_id is None:
            raise ChangeRequestError(
                "A note override no longer maps to a field in the applied release.",
                status=409,
                error="CHANGE_REQUEST_FIELD_IDENTITY_MISSING",
            )
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
                    "local_added_field_def_id": local_added_field_def_id,
                    "field_name": effective_field_name,
                    "source_note_label": _note_label(source_note),
                },
                "sort_order": sort_order,
            }
        )
        sort_order += 1

    return items, fingerprint


def preview_local_changes_for_install(
    install: DeckInstall,
    *,
    cursor: str | None = None,
    limit: Any = None,
    change_type: str | None = None,
    query_text: str | None = None,
) -> dict[str, Any]:
    items, fingerprint = _build_local_change_payloads(install)
    page_limit = _coerce_page_limit(
        limit,
        default=DEFAULT_ITEM_PAGE_LIMIT,
        maximum=MAX_ITEM_PAGE_LIMIT,
    )
    change_types, normalized_query, conflicts_only, filter_key = _normalize_item_filters(
        raw_change_type=change_type,
        query_text=query_text,
        conflicts_only=False,
    )
    if conflicts_only:
        filtered_items: list[dict[str, Any]] = []
    else:
        normalized_query_folded = str(normalized_query or "").casefold()
        filtered_items = [
            item
            for item in items
            if (not change_types or item["change_type"] in change_types)
            and (
                not normalized_query_folded
                or normalized_query_folded in str(item.get("path_label") or "").casefold()
                or normalized_query_folded in str(item.get("path_key") or "").casefold()
                or normalized_query_folded in str(item.get("source_ref_id") or "").casefold()
            )
        ]
    filtered_item_count = len(filtered_items)
    after_sort_order: int | None = None
    cursor_payload = _decode_cursor(cursor, expected_kind="local_change_items")
    if cursor_payload is not None:
        try:
            if str(cursor_payload["install_id"]) != str(install.id):
                raise ValueError("install mismatch")
            if str(cursor_payload["fingerprint"]) != fingerprint:
                raise ChangeRequestError(
                    "Local clone changes changed while paging. Refresh the diff.",
                    status=409,
                    error="CHANGE_REQUEST_CURSOR_STALE",
                    field="cursor",
                )
            if str(cursor_payload["filter_key"]) != filter_key:
                raise ValueError("filter mismatch")
            after_sort_order = int(cursor_payload["sort_order"])
        except ChangeRequestError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ChangeRequestError(
                "cursor does not match the current local diff or filters.",
                status=400,
                field="cursor",
            ) from exc
    if after_sort_order is not None:
        filtered_items = [
            item
            for item in filtered_items
            if int(item.get("sort_order") or 0) > after_sort_order
        ]
    page_items = filtered_items[:page_limit]
    has_more = len(filtered_items) > page_limit
    next_cursor = None
    if has_more and page_items:
        next_cursor = _encode_cursor(
            {
                "kind": "local_change_items",
                "install_id": str(install.id),
                "fingerprint": fingerprint,
                "filter_key": filter_key,
                "sort_order": int(page_items[-1].get("sort_order") or 0),
            }
        )
    return {
        "deck_install_id": install.id,
        "deck_item_id": install.deck_item_id,
        "overlay_fingerprint": fingerprint,
        "item_count": len(items),
        "change_counts": dict(Counter(item["change_type"] for item in items)),
        "items": page_items,
        "page": {
            "limit": page_limit,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "filtered_item_count": filtered_item_count,
        },
    }


