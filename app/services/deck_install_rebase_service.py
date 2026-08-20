"""Three-way rebase of clone overlays onto immutable shared-deck releases."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.repositories import deck_install_rebase_repository
from models import db
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_field_order_override import DeckCloneFieldOrderOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_install_rebase import DeckInstallRebase
from models.deck_install_rebase_conflict import DeckInstallRebaseConflict
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.field_def import FieldDef


MISSING_MARKER = {"__missing__": True}
ACTIVE_REBASE_STATUSES = {"prepared", "has_conflict", "ready"}
RESOLUTION_MODES = {"keep_mine", "keep_upstream", "manual"}


class DeckInstallUpdateError(Exception):
    """Domain error raised by clone update/rebase operations."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        error: str = "VALIDATION_ERROR",
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.error = error
        self.field = field
        self.details = details


def _utcnow() -> datetime:
    return datetime.utcnow()


def _release_sequence(release: DeckRelease | None) -> int:
    return int(release.sequence_no or 0) if release is not None else 0


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _same(left: Any, right: Any) -> bool:
    return _stable(left) == _stable(right)


def _is_missing(value: Any) -> bool:
    return isinstance(value, dict) and value.get("__missing__") is True


def _encode_cursor(sequence_no: int, change_id: int) -> str:
    raw = f"{int(sequence_no)}:{int(change_id)}".encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(raw_cursor: str | None) -> tuple[int | None, int | None]:
    raw_cursor = str(raw_cursor or "").strip()
    if not raw_cursor:
        return None, None
    try:
        padded = raw_cursor + "=" * (-len(raw_cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
        sequence_text, change_id_text = decoded.split(":", 1)
        return int(sequence_text), int(change_id_text)
    except (ValueError, TypeError, UnicodeError):
        raise DeckInstallUpdateError(
            "cursor is invalid.",
            field="cursor",
        )


def _serialize_release(release: DeckRelease | None) -> dict[str, Any] | None:
    if release is None:
        return None
    return {
        "id": release.id,
        "sequence_no": int(release.sequence_no or 0),
        "version_label": release.version_label,
        "status": release.status,
        "change_count": int(release.change_count or 0),
        "changelog": release.changelog,
        "published_at": release.published_at.isoformat() if release.published_at else None,
    }


def _serialize_change(
    change: DeckReleaseChange,
    *,
    field_names_by_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "id": int(change.id),
        "release_id": change.release_id,
        "release_sequence_no": int(change.release_sequence_no or 0),
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
        "source_deck_id": change.source_deck_id,
        "sort_key": change.sort_key,
    }


def _require_install(install_id: str, *, user_id: int, for_update: bool = False) -> DeckInstall:
    install = deck_install_rebase_repository.get_install_for_user(
        install_id,
        user_id=user_id,
        for_update=for_update,
    )
    if install is None:
        raise DeckInstallUpdateError(
            "Installed deck not found.",
            status=404,
            error="FIELD_NOT_FOUND",
        )
    return install


def _require_target_release(install: DeckInstall, release_id: str) -> DeckRelease:
    release = deck_install_rebase_repository.get_release_for_install(install, release_id)
    if release is None:
        raise DeckInstallUpdateError(
            "Published release not found for this installed deck.",
            status=404,
            error="FIELD_NOT_FOUND",
        )
    applied_sequence = _release_sequence(install.applied_release)
    if _release_sequence(release) < applied_sequence:
        raise DeckInstallUpdateError(
            "Cannot apply a release older than the installed version.",
            status=409,
            error="RELEASE_DOWNGRADE_NOT_SUPPORTED",
        )
    return release


def _validate_expected_state(
    install: DeckInstall,
    *,
    expected_applied_release_id: str | None,
    expected_overlay_revision: int | None,
) -> None:
    if expected_applied_release_id is not None:
        current_id = str(install.applied_release_id or "")
        if current_id != str(expected_applied_release_id or ""):
            raise DeckInstallUpdateError(
                "The installed release changed. Refresh and try again.",
                status=409,
                error="APPLIED_RELEASE_STALE",
            )
    if expected_overlay_revision is not None:
        if int(install.overlay_revision or 0) != int(expected_overlay_revision):
            raise DeckInstallUpdateError(
                "Local changes changed while preparing the update. Refresh and try again.",
                status=409,
                error="OVERLAY_REVISION_STALE",
            )


def _coerce_optional_revision(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    try:
        revision = int(value)
    except (TypeError, ValueError) as exc:
        raise DeckInstallUpdateError(
            f"{field} must be an integer.",
            field=field,
        ) from exc
    if revision < 0:
        raise DeckInstallUpdateError(
            f"{field} must be zero or greater.",
            field=field,
        )
    return revision


def get_update_status(*, install_id: str, user_id: int) -> dict[str, Any]:
    install = _require_install(install_id, user_id=user_id)
    current_release = install.deck_item.current_release if install.deck_item else None
    applied_release = install.applied_release
    available = bool(
        current_release is not None
        and _release_sequence(current_release) > _release_sequence(applied_release)
    )
    unread = bool(
        available
        and str(install.seen_release_id or "") != str(current_release.id or "")
    )
    change_count = 0
    if available:
        change_count = deck_install_rebase_repository.count_release_changes(
            deck_item_id=install.deck_item_id,
            after_sequence=_release_sequence(applied_release),
            through_sequence=_release_sequence(current_release),
        )
    return {
        "install_id": install.id,
        "deck_item_id": install.deck_item_id,
        "version_mode": install.version_mode,
        "overlay_revision": int(install.overlay_revision or 0),
        "applied_release": _serialize_release(applied_release),
        "available_release": _serialize_release(current_release),
        "update_available": available,
        "unread_update": unread,
        "change_count": change_count,
    }


def get_update_diff(
    *,
    install_id: str,
    release_id: str,
    user_id: int,
    cursor: str | None,
    limit: int,
    entity_kind: str | None = None,
    operation: str | None = None,
    query_text: str | None = None,
) -> dict[str, Any]:
    install = _require_install(install_id, user_id=user_id)
    target = _require_target_release(install, release_id)
    try:
        page_size = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        raise DeckInstallUpdateError("limit must be an integer.", field="limit")
    cursor_sequence, cursor_id = _decode_cursor(cursor)
    normalized_kind = str(entity_kind or "").strip().lower()
    normalized_operation = str(operation or "").strip().lower()
    if not normalized_kind and normalized_operation in {"note_field", "field_def"}:
        normalized_kind = normalized_operation
        normalized_operation = ""
    if normalized_kind in {"", "all"}:
        normalized_kind = ""
    elif normalized_kind not in {"note_field", "field_def"}:
        raise DeckInstallUpdateError(
            "entity_kind must be note_field or field_def.",
            field="entity_kind",
        )
    operation_aliases = {
        "": "",
        "all": "",
        "add": "add",
        "added": "add",
        "set": "set",
        "modified": "set",
        "remove": "remove",
        "removed": "remove",
        "conflict": "__conflict__",
    }
    if normalized_operation not in operation_aliases:
        raise DeckInstallUpdateError(
            "operation must be added, modified, or removed.",
            field="operation",
        )
    normalized_operation = operation_aliases[normalized_operation]
    after_sequence = _release_sequence(install.applied_release)
    rows = deck_install_rebase_repository.list_release_changes_page(
        deck_item_id=install.deck_item_id,
        after_sequence=after_sequence,
        through_sequence=_release_sequence(target),
        cursor_sequence=cursor_sequence,
        cursor_id=cursor_id,
        limit=page_size + 1,
        entity_kind=(normalized_kind or None),
        operation=(normalized_operation or None),
        query_text=query_text,
    )
    has_more = len(rows) > page_size
    page_rows = rows[:page_size]
    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = _encode_cursor(last.release_sequence_no, last.id)
    from app.services import deck_release_service

    field_defs_by_id: dict[str, dict[str, Any]] = {}
    if install.applied_release is not None:
        field_defs_by_id.update(
            deck_release_service.get_field_defs_at_release(install.applied_release)
        )
    field_defs_by_id.update(deck_release_service.get_field_defs_at_release(target))
    field_names_by_id = {
        str(field_id): str(properties.get("name") or field_id)
        for field_id, properties in field_defs_by_id.items()
    }

    payload = {
        "install_id": install.id,
        "from_release": _serialize_release(install.applied_release),
        "to_release": _serialize_release(target),
        "items": [
            _serialize_change(row, field_names_by_id=field_names_by_id)
            for row in page_rows
        ],
        "page": {
            "limit": page_size,
            "has_more": has_more,
            "next_cursor": next_cursor,
        },
    }
    if not str(cursor or "").strip():
        applied_release = install.applied_release
        if (
            str(target.parent_release_id or "")
            == str(applied_release.id if applied_release else "")
        ):
            payload["summary"] = {
                "change_count": int(target.change_count or 0),
                "entity_count": int(target.entity_count or 0),
                "added_count": int(target.added_count or 0),
                "modified_count": int(target.modified_count or 0),
                "removed_count": int(target.removed_count or 0),
            }
        else:
            atomic_changes = deck_release_service.get_atomic_changes_between_releases(
                from_release_or_id=applied_release,
                to_release_or_id=target,
            )
            payload["summary"] = {
                "change_count": len(atomic_changes),
                "entity_count": len(
                    {
                        (row.get("entity_kind"), row.get("entity_id"))
                        for row in atomic_changes
                    }
                ),
                "added_count": sum(row.get("operation") == "add" for row in atomic_changes),
                "modified_count": sum(row.get("operation") == "set" for row in atomic_changes),
                "removed_count": sum(row.get("operation") == "remove" for row in atomic_changes),
            }
    return payload


@dataclass
class _LocalOverlay:
    kind: str
    row: Any
    property_key: str
    value: Any


def _field_name_for_change(change: DeckReleaseChange, field_names: dict[str, str]) -> str:
    if change.field_def_id and change.field_def_id in field_names:
        return field_names[change.field_def_id]
    key = str(change.property_key or "")
    return key[6:] if key.startswith("field:") else key


def _load_local_overlays(install: DeckInstall):
    note_rows = DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install.id).all()
    schema_rows = DeckCloneFieldDefOverride.query.filter_by(deck_install_id=install.id).all()
    order_row = DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=install.id).first()
    field_ids = {
        str(row.source_field_def_id)
        for row in note_rows
        if row.source_field_def_id
    } | {
        str(row.source_field_def_id)
        for row in schema_rows
        if row.source_field_def_id
    }
    field_names = {
        str(row.id): str(row.name)
        for row in FieldDef.query.filter(FieldDef.id.in_(sorted(field_ids) or [""])).all()
    }
    note_by_id = {
        (str(row.source_note_id), str(row.source_field_def_id)): row
        for row in note_rows
        if row.source_field_def_id
    }
    note_by_name = {
        (str(row.source_note_id), str(row.field_name)): row
        for row in note_rows
    }
    schema_by_id = {str(row.source_field_def_id): row for row in schema_rows}
    return note_rows, schema_rows, order_row, field_names, note_by_id, note_by_name, schema_by_id


def _local_overlay_for_change(
    change: DeckReleaseChange,
    *,
    field_names: dict[str, str],
    note_by_id: dict[tuple[str, str], DeckCloneNoteFieldOverride],
    note_by_name: dict[tuple[str, str], DeckCloneNoteFieldOverride],
    schema_by_id: dict[str, DeckCloneFieldDefOverride],
    order_row: DeckCloneFieldOrderOverride | None,
) -> _LocalOverlay | None:
    if change.entity_kind == "note_field":
        row = None
        if change.field_def_id:
            row = note_by_id.get((str(change.entity_id), str(change.field_def_id)))
        field_name = _field_name_for_change(change, field_names)
        row = row or note_by_name.get((str(change.entity_id), field_name))
        if row is None:
            return None
        value = MISSING_MARKER if row.operation == "remove" else row.value
        return _LocalOverlay("note_field", row, field_name, value)

    if change.entity_kind == "field_def":
        field_id = str(change.field_def_id or change.entity_id or "")
        row = schema_by_id.get(field_id)
        if row is None:
            return None
        property_key = str(change.property_key or "")
        if property_key in {"disabled", "is_disabled", "retired"}:
            return _LocalOverlay("field_def_disabled", row, property_key, bool(row.is_disabled))
        properties = dict(row.properties or {})
        if property_key not in properties:
            return None
        return _LocalOverlay("field_def", row, property_key, properties[property_key])

    if change.entity_kind == "field_order" and order_row is not None:
        return _LocalOverlay(
            "field_order",
            order_row,
            str(change.property_key or "order"),
            list(order_row.ordered_def_ids or []),
        )
    return None


def _collapse_changes(rows: list[DeckReleaseChange]) -> list[tuple[DeckReleaseChange, Any, Any]]:
    collapsed: dict[str, tuple[DeckReleaseChange, Any, Any]] = {}
    for row in rows:
        key = str(row.change_key or f"{row.entity_kind}:{row.entity_id}:{row.property_key}")
        row_before = MISSING_MARKER if row.operation == "add" else row.before_value
        row_after = MISSING_MARKER if row.operation == "remove" else row.after_value
        if key not in collapsed:
            collapsed[key] = (row, row_before, row_after)
        else:
            first, before_value, _ = collapsed[key]
            collapsed[key] = (row, before_value, row_after)
    return list(collapsed.values())


def _overlapping_changes(install: DeckInstall, target: DeckRelease):
    local_state = _load_local_overlays(install)
    note_rows, schema_rows, order_row, *_ = local_state
    rows = deck_install_rebase_repository.list_overlapping_release_changes(
        deck_item_id=install.deck_item_id,
        after_sequence=_release_sequence(install.applied_release),
        through_sequence=_release_sequence(target),
        note_ids={str(row.source_note_id) for row in note_rows},
        field_def_ids={str(row.source_field_def_id) for row in schema_rows if row.source_field_def_id},
        include_field_order=order_row is not None,
    )
    return _collapse_changes(rows), local_state


def prepare_update(
    *,
    install_id: str,
    release_id: str,
    user_id: int,
    expected_applied_release_id: str | None = None,
    expected_overlay_revision: int | None = None,
    idempotency_key: str | None = None,
) -> DeckInstallRebase:
    install = _require_install(install_id, user_id=user_id, for_update=True)
    target = _require_target_release(install, release_id)
    normalized_overlay_revision = _coerce_optional_revision(
        expected_overlay_revision,
        field="expected_overlay_revision",
    )
    clean_idempotency_key = str(idempotency_key or "").strip() or None
    if clean_idempotency_key and len(clean_idempotency_key) > 64:
        raise DeckInstallUpdateError(
            "Idempotency-Key must be at most 64 characters.",
            field="Idempotency-Key",
        )
    if clean_idempotency_key:
        existing = deck_install_rebase_repository.find_idempotent_rebase(
            install_id=install.id,
            idempotency_key=clean_idempotency_key,
        )
        if existing is not None:
            same_request = (
                existing.to_release_id == target.id
                and (
                    expected_applied_release_id is None
                    or str(existing.from_release_id or "")
                    == str(expected_applied_release_id or "")
                )
                and (
                    normalized_overlay_revision is None
                    or int(existing.expected_overlay_revision or 0)
                    == normalized_overlay_revision
                )
            )
            if not same_request:
                raise DeckInstallUpdateError(
                    "Idempotency key was already used for another update request.",
                    status=409,
                    error="IDEMPOTENCY_KEY_REUSED",
                )
            return existing

    _validate_expected_state(
        install,
        expected_applied_release_id=expected_applied_release_id,
        expected_overlay_revision=normalized_overlay_revision,
    )

    deck_install_rebase_repository.mark_other_active_rebases_stale(install_id=install.id)
    now = _utcnow()
    total_changes = deck_install_rebase_repository.count_release_changes(
        deck_item_id=install.deck_item_id,
        after_sequence=_release_sequence(install.applied_release),
        through_sequence=_release_sequence(target),
    )
    rebase = DeckInstallRebase(
        deck_install_id=install.id,
        from_release_id=install.applied_release_id,
        to_release_id=target.id,
        status="prepared",
        expected_overlay_revision=int(install.overlay_revision or 0),
        idempotency_key=clean_idempotency_key,
        change_count=total_changes,
        conflict_count=0,
        resolved_conflict_count=0,
        applied_change_count=0,
        prepared_at=now,
    )
    db.session.add(rebase)
    db.session.flush()

    collapsed, local_state = _overlapping_changes(install, target)
    _, _, order_row, field_names, note_by_id, note_by_name, schema_by_id = local_state
    conflict_count = 0
    for change, base_value, upstream_value in collapsed:
        local = _local_overlay_for_change(
            change,
            field_names=field_names,
            note_by_id=note_by_id,
            note_by_name=note_by_name,
            schema_by_id=schema_by_id,
            order_row=order_row,
        )
        if (
            local is None
            or _same(local.value, upstream_value)
            or _same(local.value, base_value)
            or _same(upstream_value, base_value)
        ):
            continue
        db.session.add(
            DeckInstallRebaseConflict(
                rebase_id=rebase.id,
                release_change_id=change.id,
                conflict_key=str(
                    change.change_key
                    or f"{change.entity_kind}:{change.entity_id}:{change.property_key}"
                ),
                entity_kind=change.entity_kind,
                entity_id=change.entity_id,
                field_def_id=change.field_def_id,
                property_key=change.property_key,
                base_value=base_value,
                upstream_value=upstream_value,
                local_value=local.value,
            )
        )
        conflict_count += 1

    rebase.conflict_count = conflict_count
    rebase.status = "has_conflict" if conflict_count else "ready"
    db.session.flush()
    return rebase


def _serialize_conflict(
    conflict: DeckInstallRebaseConflict,
    *,
    field_names_by_id: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "id": int(conflict.id),
        "conflict_key": conflict.conflict_key,
        "entity_kind": conflict.entity_kind,
        "entity_id": conflict.entity_id,
        "field_def_id": conflict.field_def_id,
        "field_name": (
            (field_names_by_id or {}).get(str(conflict.field_def_id))
            if conflict.field_def_id
            else None
        ),
        "property_key": conflict.property_key,
        "base_value": conflict.base_value,
        "upstream_value": conflict.upstream_value,
        "local_value": conflict.local_value,
        "resolution_mode": conflict.resolution_mode,
        "resolved_value": conflict.resolved_value,
        "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None,
    }


def serialize_rebase(rebase: DeckInstallRebase, *, include_conflicts: bool = True) -> dict[str, Any]:
    payload = {
        "id": rebase.id,
        "install_id": rebase.deck_install_id,
        "status": rebase.status,
        "from_release": _serialize_release(rebase.from_release),
        "to_release": _serialize_release(rebase.to_release),
        "expected_overlay_revision": int(rebase.expected_overlay_revision or 0),
        "change_count": int(rebase.change_count or 0),
        "conflict_count": int(rebase.conflict_count or 0),
        "resolved_conflict_count": int(rebase.resolved_conflict_count or 0),
        "applied_change_count": int(rebase.applied_change_count or 0),
        "prepared_at": rebase.prepared_at.isoformat() if rebase.prepared_at else None,
        "applied_at": rebase.applied_at.isoformat() if rebase.applied_at else None,
    }
    if include_conflicts:
        from app.services import deck_release_service

        field_defs_by_id: dict[str, dict[str, Any]] = {}
        if rebase.from_release is not None:
            field_defs_by_id.update(
                deck_release_service.get_field_defs_at_release(rebase.from_release)
            )
        if rebase.to_release is not None:
            field_defs_by_id.update(
                deck_release_service.get_field_defs_at_release(rebase.to_release)
            )
        field_names_by_id = {
            str(field_id): str(properties.get("name") or field_id)
            for field_id, properties in field_defs_by_id.items()
        }
        payload["conflicts"] = [
            _serialize_conflict(row, field_names_by_id=field_names_by_id)
            for row in rebase.conflicts
        ]
    return payload


def resolve_conflict(
    *,
    rebase_id: str,
    conflict_id: int,
    user_id: int,
    resolution_mode: str,
    resolved_value: Any = None,
    has_resolved_value: bool = False,
) -> DeckInstallRebase:
    rebase = deck_install_rebase_repository.get_rebase_for_user(
        rebase_id,
        user_id=user_id,
        for_update=True,
    )
    if rebase is None:
        raise DeckInstallUpdateError("Update preparation not found.", status=404, error="FIELD_NOT_FOUND")
    if rebase.status not in {"has_conflict", "ready"}:
        raise DeckInstallUpdateError("This update preparation is no longer editable.", status=409, error="REBASE_NOT_EDITABLE")
    mode = str(resolution_mode or "").strip().lower()
    if mode not in RESOLUTION_MODES:
        raise DeckInstallUpdateError("resolution_mode is invalid.", field="resolution_mode")
    if mode == "manual" and not has_resolved_value:
        raise DeckInstallUpdateError("resolved_value is required for manual resolution.", field="resolved_value")
    conflict = DeckInstallRebaseConflict.query.filter_by(id=conflict_id, rebase_id=rebase.id).first()
    if conflict is None:
        raise DeckInstallUpdateError("Conflict not found.", status=404, error="FIELD_NOT_FOUND")
    conflict.resolution_mode = mode
    conflict.resolved_value = resolved_value if mode == "manual" else None
    conflict.resolved_by_user_id = user_id
    conflict.resolved_at = _utcnow()
    resolved_count = sum(1 for row in rebase.conflicts if row.resolved_at is not None)
    rebase.resolved_conflict_count = resolved_count
    rebase.status = "ready" if resolved_count >= int(rebase.conflict_count or 0) else "has_conflict"
    db.session.flush()
    return rebase


def _clear_local_overlay(local: _LocalOverlay) -> bool:
    if local.kind in {"note_field", "field_order"}:
        db.session.delete(local.row)
        return True
    if local.kind == "field_def_disabled":
        local.row.is_disabled = False
    else:
        properties = dict(local.row.properties or {})
        properties.pop(local.property_key, None)
        local.row.properties = properties
    if not bool(local.row.is_disabled) and not dict(local.row.properties or {}):
        db.session.delete(local.row)
    return True


def _set_local_overlay(local: _LocalOverlay, value: Any) -> bool:
    if local.kind == "note_field":
        if _is_missing(value):
            local.row.operation = "remove"
            local.row.value = None
        else:
            local.row.operation = "set"
            local.row.value = value
        return True
    if local.kind == "field_order":
        if not isinstance(value, list):
            raise DeckInstallUpdateError("Manual field order must be a list.", field="resolved_value")
        local.row.ordered_def_ids = value
        return True
    if local.kind == "field_def_disabled":
        local.row.is_disabled = bool(value)
        return True
    properties = dict(local.row.properties or {})
    properties[local.property_key] = value
    local.row.properties = properties
    return True


def apply_prepared_update(*, rebase_id: str, user_id: int) -> DeckInstallRebase:
    rebase = deck_install_rebase_repository.get_rebase_for_user(
        rebase_id,
        user_id=user_id,
        for_update=True,
    )
    if rebase is None:
        raise DeckInstallUpdateError("Update preparation not found.", status=404, error="FIELD_NOT_FOUND")
    if rebase.status == "applied":
        return rebase
    if rebase.status not in ACTIVE_REBASE_STATUSES:
        raise DeckInstallUpdateError("This update preparation cannot be applied.", status=409, error="REBASE_NOT_APPLICABLE")
    install = _require_install(rebase.deck_install_id, user_id=user_id, for_update=True)
    if str(install.applied_release_id or "") != str(rebase.from_release_id or ""):
        rebase.status = "stale"
        raise DeckInstallUpdateError("The installed release changed. Prepare the update again.", status=409, error="APPLIED_RELEASE_STALE")
    if int(install.overlay_revision or 0) != int(rebase.expected_overlay_revision or 0):
        rebase.status = "stale"
        raise DeckInstallUpdateError("Local changes changed. Prepare the update again.", status=409, error="OVERLAY_REVISION_STALE")
    unresolved = [row for row in rebase.conflicts if row.resolved_at is None]
    if unresolved:
        rebase.status = "has_conflict"
        raise DeckInstallUpdateError(
            "Resolve all conflicts before applying this update.",
            status=409,
            error="REBASE_CONFLICTS_UNRESOLVED",
            details={"rebase": serialize_rebase(rebase)},
        )
    target = _require_target_release(install, rebase.to_release_id)
    collapsed, local_state = _overlapping_changes(install, target)
    _, _, order_row, field_names, note_by_id, note_by_name, schema_by_id = local_state
    conflicts_by_key = {str(row.conflict_key): row for row in rebase.conflicts}
    overlay_mutated = False
    for change, base_value, upstream_value in collapsed:
        local = _local_overlay_for_change(
            change,
            field_names=field_names,
            note_by_id=note_by_id,
            note_by_name=note_by_name,
            schema_by_id=schema_by_id,
            order_row=order_row,
        )
        if local is None:
            continue
        key = str(change.change_key or f"{change.entity_kind}:{change.entity_id}:{change.property_key}")
        conflict = conflicts_by_key.get(key)
        if _same(local.value, upstream_value) or _same(local.value, base_value):
            overlay_mutated = _clear_local_overlay(local) or overlay_mutated
        elif _same(upstream_value, base_value):
            continue
        elif conflict is None:
            raise DeckInstallUpdateError("Upstream changes no longer match this preparation.", status=409, error="REBASE_STALE")
        elif conflict.resolution_mode == "keep_upstream":
            overlay_mutated = _clear_local_overlay(local) or overlay_mutated
        elif conflict.resolution_mode == "manual":
            if _same(conflict.resolved_value, upstream_value):
                overlay_mutated = _clear_local_overlay(local) or overlay_mutated
            else:
                overlay_mutated = (
                    _set_local_overlay(local, conflict.resolved_value)
                    or overlay_mutated
                )

    now = _utcnow()
    if overlay_mutated:
        install.overlay_revision = int(install.overlay_revision or 0) + 1
    install.applied_release_id = target.id
    install.seen_release_id = target.id
    install.version_mode = "release"
    install.last_synced_at = now
    rebase.status = "applied"
    rebase.applied_change_count = int(rebase.change_count or 0)
    rebase.applied_at = now
    db.session.flush()
    return rebase


def prepare_and_apply_update(
    *,
    install_id: str,
    release_id: str,
    user_id: int,
    expected_applied_release_id: str | None = None,
    expected_overlay_revision: int | None = None,
    idempotency_key: str | None = None,
) -> DeckInstallRebase:
    rebase = prepare_update(
        install_id=install_id,
        release_id=release_id,
        user_id=user_id,
        expected_applied_release_id=expected_applied_release_id,
        expected_overlay_revision=expected_overlay_revision,
        idempotency_key=idempotency_key,
    )
    if rebase.status == "has_conflict":
        raise DeckInstallUpdateError(
            "Resolve conflicts before applying this update.",
            status=409,
            error="REBASE_CONFLICTS_UNRESOLVED",
            details={"rebase": serialize_rebase(rebase)},
        )
    return apply_prepared_update(rebase_id=rebase.id, user_id=user_id)


def mark_update_seen(*, install_id: str, release_id: str, user_id: int) -> dict[str, Any]:
    install = _require_install(install_id, user_id=user_id, for_update=True)
    target = _require_target_release(install, release_id)
    install.seen_release_id = target.id
    db.session.flush()
    return get_update_status(install_id=install.id, user_id=user_id)
