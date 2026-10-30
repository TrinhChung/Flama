"""Track owner working-tree mutations for versioned shared decks."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from sqlalchemy import event, inspect, select, tuple_, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.repositories.deck_tree_query import collect_ancestor_ids
from models import db
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity
from models.field_def import FieldDef
from models.note import Note
from models.study_application import StudyApplication
from models.template import Template
from app.services.note_base_context import published_base_enabled

_PRESENTATION_PENDING = "flama.deck_presentation.pending"
_PRESENTATION_ITEMS = "flama.deck_presentation.items"
_PRESENTATION_NESTED = "flama.deck_presentation.nested"
_PRESENTATION_CONTENT = ("front_html", "back_html", "shared_css", "input_schema")
_PRESENTATION_APPLICATION = ("template_id", "note_type_id", "input_bindings", "status_code", "occurrence_key", "display_name", "position", "is_default")


@event.listens_for(Session, "before_flush")
def _collect_presentation_mutations(session, _context, _instances):
    pending = session.info.setdefault(_PRESENTATION_PENDING, set())
    for row in list(session.new) + list(session.dirty) + list(session.deleted):
        properties = _PRESENTATION_CONTENT if isinstance(row, Template) else _PRESENTATION_APPLICATION if isinstance(row, StudyApplication) else None
        if properties is None:
            continue
        if isinstance(row, StudyApplication) and row.status_code not in (None, "ACTIVE") and "ACTIVE" not in inspect(row).attrs.status_code.history.deleted:
            continue
        if row in session.new or row in session.deleted or any(inspect(row).attrs[key].history.has_changes() for key in properties):
            if row not in session.new and row not in session.deleted:
                model = type(row)
                stored = session.execute(select(*(getattr(model, key) for key in properties)).where(model.id == row.id)).mappings().first()
                if stored is not None and all(stored[key] == getattr(row, key) for key in properties):
                    continue
            pending.add(row)


@event.listens_for(Session, "after_flush_postexec")
def _record_presentation_mutations(session, _context):
    pending = session.info.pop(_PRESENTATION_PENDING, set())
    if not pending:
        return
    template_ids = [row.id for row in pending if isinstance(row, Template) and row.id]
    note_type_ids = {row.note_type_id for row in pending if isinstance(row, StudyApplication) and row.note_type_id}
    if template_ids:
        note_type_ids.update(session.execute(select(StudyApplication.note_type_id).where(
            StudyApplication.template_id.in_(template_ids), StudyApplication.status_code == "ACTIVE",
        )).scalars())
    if not note_type_ids:
        return
    table = DeckMarketplaceItem.__table__
    items = session.execute(select(table).where(
        table.c.source_note_type_id.in_(sorted(note_type_ids)), table.c.current_release_id.is_not(None),
    ).order_by(table.c.id).with_for_update()).mappings().all()
    marked = session.info.setdefault(_PRESENTATION_ITEMS, set())
    for item in items:
        if item["id"] in marked:
            continue
        revision = int(item["working_revision"] or 0) + 1
        complete = int(item["dirty_tracking_revision"] or 0) == revision - 1
        values = {"working_revision": table.c.working_revision + 1}
        if complete:
            values["dirty_tracking_revision"] = table.c.dirty_tracking_revision + 1
        session.execute(update(table).where(table.c.id == item["id"]).values(**values))
        for loaded in list(session.identity_map.values()):
            if isinstance(loaded, DeckMarketplaceItem) and loaded.id == item["id"]:
                set_committed_value(loaded, "working_revision", revision)
                if complete:
                    set_committed_value(loaded, "dirty_tracking_revision", revision)
        marked.add(item["id"])


@event.listens_for(Session, "before_commit")
def _publish_presentation_mutations(session):
    if published_base_enabled():
        return
    if session.in_nested_transaction():
        return
    session.flush()
    for item_id in sorted(session.info.get(_PRESENTATION_ITEMS, set())):
        from app.services.deck_auto_publish_service import trigger_auto_publish_for_deck_item
        trigger_auto_publish_for_deck_item(deck_item_id=item_id, session=session)


@event.listens_for(Session, "after_transaction_create")
def _presentation_savepoint_started(session, transaction):
    if transaction.nested:
        session.info.setdefault(_PRESENTATION_NESTED, {})[transaction] = set(session.info.get(_PRESENTATION_ITEMS, set()))


@event.listens_for(Session, "after_soft_rollback")
def _presentation_savepoint_rolled_back(session, transaction):
    checkpoint = session.info.get(_PRESENTATION_NESTED, {}).pop(transaction, None)
    if checkpoint is not None:
        session.info[_PRESENTATION_ITEMS] = checkpoint
        session.info.pop(_PRESENTATION_PENDING, None)


@event.listens_for(Session, "after_transaction_end")
def _presentation_transaction_finished(session, transaction):
    if transaction.parent is None:
        for key in (_PRESENTATION_PENDING, _PRESENTATION_ITEMS, _PRESENTATION_NESTED):
            session.info.pop(key, None)


def _hash_value(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _items_covering_deck(*, deck_id: int | None, owner_user_id: int) -> list[DeckMarketplaceItem]:
    source_candidates = collect_ancestor_ids(deck_id)
    if not source_candidates:
        return []
    # Track every listing lineage, including archived/private listings.  A
    # listing can already have immutable releases or installs when it is
    # archived, and may later be made visible again.  Dropping those rows here
    # would make subsequent source edits invisible to release preview and
    # would also let hard-delete guards miss existing learner history.
    return (
        DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.owner_user_id == owner_user_id,
            DeckMarketplaceItem.source_deck_id.in_(source_candidates),
        )
        .order_by(DeckMarketplaceItem.id.asc())
        .all()
    )


def _items_for_note_type(*, note_type_id: str, owner_user_id: int) -> list[DeckMarketplaceItem]:
    return (
        DeckMarketplaceItem.query.filter_by(
            owner_user_id=owner_user_id,
            source_note_type_id=note_type_id,
        )
        .order_by(DeckMarketplaceItem.id.asc())
        .all()
    )


def _upsert_dirty(
    *,
    item: DeckMarketplaceItem,
    entity_kind: str,
    entity_id: str,
    property_key: str,
    operation: str,
    current_value: Any,
    field_def_id: str | None,
    source_deck_id: int | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if published_base_enabled():
        return
    row = DeckWorkingDirtyEntity.query.filter_by(
        deck_item_id=item.id,
        entity_kind=entity_kind,
        entity_id=str(entity_id),
        property_key=str(property_key),
    ).first()
    if row is None:
        row = DeckWorkingDirtyEntity(
            deck_item_id=item.id,
            entity_kind=entity_kind,
            entity_id=str(entity_id),
            property_key=str(property_key),
        )
        db.session.add(row)
    row.field_def_id = field_def_id
    row.operation = operation
    row.current_hash = None if operation in {"remove", "retire"} else _hash_value(current_value)
    row.source_deck_id = source_deck_id
    row.working_revision = int(item.working_revision or 0)
    row.metadata_json = dict(metadata or {})


def _resolve_note_field_value(
    note: Note,
    field_name: str,
    field_id: str | None,
) -> Any:
    pending = note.__dict__.get("_pending_named_field_values")
    if isinstance(pending, dict):
        return pending.get(field_name)
    by_id = getattr(note, "field_values_by_id", None)
    if (
        field_id
        and isinstance(by_id, dict)
        and getattr(note, "field_values_codec", None) == "field-id.v1"
    ):
        return by_id.get(field_id)
    extras = getattr(note, "field_values_extras", None)
    if isinstance(extras, dict) and field_name in extras:
        return extras.get(field_name)
    return (note.field_values or {}).get(field_name)


def mark_note_fields_changed(
    *,
    note: Note,
    field_names: Iterable[str],
    operation: str = "set",
    deck_id: int | None = None,
) -> int:
    if published_base_enabled():
        return 0  # The flush adapter owns draft tracking and its revision fence.
    resolved_deck_id = note.deck_id if deck_id is None else deck_id
    items = _items_covering_deck(
        deck_id=resolved_deck_id,
        owner_user_id=int(note.user_id),
    )
    normalized_names = sorted({str(name) for name in field_names if str(name).strip()})
    if not items or not normalized_names:
        return 0
    field_ids_by_name = {
        str(row.name): str(row.id)
        for row in FieldDef.query.filter_by(note_type_id=note.note_type_id).all()
    }
    for item in items:
        previous_revision = int(item.working_revision or 0)
        tracking_was_complete = (
            int(item.dirty_tracking_revision or 0) == previous_revision
        )
        item.working_revision = previous_revision + 1
        for field_name in normalized_names:
            field_id = field_ids_by_name.get(field_name)
            property_key = f"field:{field_id}" if field_id else f"field_name:{field_name}"
            _upsert_dirty(
                item=item,
                entity_kind="note_field",
                entity_id=str(note.id),
                property_key=property_key,
                operation=operation,
                current_value=_resolve_note_field_value(note, field_name, field_id),
                field_def_id=field_id,
                source_deck_id=resolved_deck_id,
                metadata={"field_name": field_name},
            )
        if tracking_was_complete:
            item.dirty_tracking_revision = int(item.working_revision or 0)
    _trigger_auto_publish_for_items(items)
    return len(items)


def _trigger_auto_publish_for_items(items: Iterable[DeckMarketplaceItem]) -> None:
    if published_base_enabled():
        return
    for item in items:
        if bool(getattr(item, "auto_publish_enabled", False)):
            try:
                from app.services import deck_auto_publish_service
                deck_auto_publish_service.trigger_auto_publish_for_deck_item(
                    deck_item_id=str(item.id),
                )
            except Exception:
                pass


def mark_field_def_changed(
    *,
    field_def: FieldDef,
    owner_user_id: int,
    property_keys: Iterable[str],
    operation: str = "set",
) -> int:
    if published_base_enabled():
        return 0  # The common schema flush fence advances affected listings.
    items = _items_for_note_type(
        note_type_id=str(field_def.note_type_id),
        owner_user_id=owner_user_id,
    )
    normalized_keys = sorted({str(key) for key in property_keys if str(key).strip()})
    if not items or not normalized_keys:
        return 0
    values = {
        "name": field_def.name,
        "field_type": field_def.field_type,
        "position": int(field_def.position or 0),
        "required": bool(field_def.required),
        "identity_role": field_def.identity_role,
    }
    for item in items:
        previous_revision = int(item.working_revision or 0)
        tracking_was_complete = (
            int(item.dirty_tracking_revision or 0) == previous_revision
        )
        item.working_revision = previous_revision + 1
        for property_key in normalized_keys:
            _upsert_dirty(
                item=item,
                entity_kind="field_def",
                entity_id=str(field_def.id),
                property_key=property_key,
                operation=operation,
                current_value=values.get(property_key),
                field_def_id=str(field_def.id),
                source_deck_id=item.source_deck_id,
            )
        if tracking_was_complete:
            item.dirty_tracking_revision = int(item.working_revision or 0)
    _trigger_auto_publish_for_items(items)
    return len(items)


def mark_note_field_batches_changed(
    *,
    mutations: Iterable[dict[str, Any]],
) -> int:
    """Track many note-field mutations with one revision per deck lineage.

    Import, synchronization, media, and TTS endpoints can update hundreds of
    notes in one transaction.  Resolving the marketplace lineage and field
    definitions for every note would be an N+1 query pattern and would advance
    ``working_revision`` once per field.  This adapter resolves each
    owner/deck and note type once, then delegates one atomic sparse batch to
    every affected marketplace item.
    """
    if published_base_enabled():
        return 0

    normalized: list[dict[str, Any]] = []
    note_type_ids: set[str] = set()
    for raw in mutations:
        if not isinstance(raw, dict):
            continue
        note = raw.get("note")
        if not isinstance(note, Note):
            continue
        operation = str(raw.get("operation") or "set").strip().lower()
        if operation not in {"add", "set", "remove", "retire"}:
            continue
        field_names = sorted(
            {
                str(name)
                for name in (raw.get("field_names") or [])
                if str(name).strip()
            }
        )
        if not field_names:
            continue
        resolved_deck_id = (
            note.deck_id if "deck_id" not in raw else raw.get("deck_id")
        )
        normalized.append(
            {
                "note": note,
                "operation": operation,
                "field_names": field_names,
                "deck_id": resolved_deck_id,
            }
        )
        note_type_ids.add(str(note.note_type_id))
    if not normalized:
        return 0

    field_ids_by_type_and_name = {
        (str(row.note_type_id), str(row.name)): str(row.id)
        for row in FieldDef.query.filter(
            FieldDef.note_type_id.in_(sorted(note_type_ids))
        ).all()
    }
    item_cache: dict[tuple[int, int | None], list[DeckMarketplaceItem]] = {}
    items_by_id: dict[str, DeckMarketplaceItem] = {}
    changes_by_item_id: dict[str, list[dict[str, Any]]] = {}
    fallback_item_ids: set[str] = set()

    for mutation in normalized:
        note = mutation["note"]
        owner_user_id = int(note.user_id)
        resolved_deck_id = mutation["deck_id"]
        cache_key = (owner_user_id, resolved_deck_id)
        items = item_cache.get(cache_key)
        if items is None:
            items = _items_covering_deck(
                deck_id=resolved_deck_id,
                owner_user_id=owner_user_id,
            )
            item_cache[cache_key] = items
        for item in items:
            item_id = str(item.id)
            items_by_id[item_id] = item
            item_changes = changes_by_item_id.setdefault(item_id, [])
            for field_name in mutation["field_names"]:
                field_id = field_ids_by_type_and_name.get(
                    (str(note.note_type_id), field_name)
                )
                if not field_id:
                    # A legacy name-only value cannot be represented by a
                    # release atom.  Mark this lineage incomplete so publish
                    # falls back to a full diff, while still advancing only one
                    # logical revision for the whole mutation batch.
                    fallback_item_ids.add(item_id)
                    continue
                item_changes.append(
                    {
                        "entity_kind": "note_field",
                        "entity_id": str(note.id),
                        "property_key": f"field:{field_id}",
                        "field_def_id": field_id,
                        "operation": mutation["operation"],
                        "current_value": _resolve_note_field_value(
                            note,
                            field_name,
                            field_id,
                        ),
                        "source_deck_id": resolved_deck_id,
                        "metadata": {"field_name": field_name},
                    }
                )

    tracked_change_count = 0
    for item_id, item_changes in changes_by_item_id.items():
        item = items_by_id[item_id]
        previous_dirty_revision = int(item.dirty_tracking_revision or 0)
        if item_changes:
            tracked_change_count += mark_deck_item_batch_changed(
                item=item,
                changes=item_changes,
            )
        elif item_id in fallback_item_ids:
            item.working_revision = int(item.working_revision or 0) + 1
        if item_id in fallback_item_ids:
            item.dirty_tracking_revision = previous_dirty_revision
    return tracked_change_count


def _load_dirty_rows_by_keys(
    *,
    deck_item_id: str,
    keys: Iterable[tuple[str, str, str]],
) -> dict[tuple[str, str, str], DeckWorkingDirtyEntity]:
    """Load only dirty rows touched by a batch, bounded below SQL param limits."""

    normalized_keys = list(keys)
    existing_by_key: dict[tuple[str, str, str], DeckWorkingDirtyEntity] = {}
    for offset in range(0, len(normalized_keys), 250):
        chunk = normalized_keys[offset : offset + 250]
        rows = DeckWorkingDirtyEntity.query.filter(
            DeckWorkingDirtyEntity.deck_item_id == deck_item_id,
            tuple_(
                DeckWorkingDirtyEntity.entity_kind,
                DeckWorkingDirtyEntity.entity_id,
                DeckWorkingDirtyEntity.property_key,
            ).in_(chunk),
        ).all()
        existing_by_key.update(
            {
                (str(row.entity_kind), str(row.entity_id), str(row.property_key)): row
                for row in rows
            }
        )
    return existing_by_key


def mark_deck_item_batch_changed(
    *,
    item: DeckMarketplaceItem,
    changes: Iterable[dict[str, Any]],
) -> int:
    """Record an atomic owner mutation batch with one working revision.

    Contribution merges can touch many fields and notes in one transaction.
    Calling the single-entity helpers would advance the deck revision once per
    field, while manually advancing it would leave sparse release tracking
    incomplete.  This helper keeps the whole merge at one logical revision.
    """
    if published_base_enabled():
        item.working_revision = int(item.working_revision or 0) + 1
        return 0

    normalized: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw_change in changes:
        if not isinstance(raw_change, dict):
            continue
        entity_kind = str(raw_change.get("entity_kind") or "").strip()
        entity_id = str(raw_change.get("entity_id") or "").strip()
        property_key = str(raw_change.get("property_key") or "").strip()
        field_def_id = str(raw_change.get("field_def_id") or "").strip()
        operation = str(raw_change.get("operation") or "set").strip().lower()
        if (
            entity_kind not in {"note_field", "field_def"}
            or not entity_id
            or not property_key
            or not field_def_id
            or operation not in {"add", "set", "remove", "retire"}
        ):
            continue
        normalized[(entity_kind, entity_id, property_key)] = {
            **raw_change,
            "entity_kind": entity_kind,
            "entity_id": entity_id,
            "property_key": property_key,
            "field_def_id": field_def_id,
            "operation": operation,
        }
    if not normalized:
        return 0

    previous_revision = int(item.working_revision or 0)
    tracking_was_complete = int(item.dirty_tracking_revision or 0) == previous_revision
    item.working_revision = previous_revision + 1
    existing_by_key = _load_dirty_rows_by_keys(
        deck_item_id=str(item.id),
        keys=normalized,
    )
    for key, change in normalized.items():
        row = existing_by_key.get(key)
        if row is None:
            row = DeckWorkingDirtyEntity(
                deck_item_id=item.id,
                entity_kind=change["entity_kind"],
                entity_id=change["entity_id"],
                property_key=change["property_key"],
            )
            db.session.add(row)
        row.field_def_id = change["field_def_id"]
        row.operation = change["operation"]
        row.current_hash = (
            None
            if change["operation"] in {"remove", "retire"}
            else _hash_value(change.get("current_value"))
        )
        row.source_deck_id = change.get("source_deck_id")
        row.working_revision = int(item.working_revision or 0)
        row.metadata_json = (
            dict(change.get("metadata") or {})
            if isinstance(change.get("metadata"), dict)
            else {}
        )
    if tracking_was_complete:
        item.dirty_tracking_revision = int(item.working_revision or 0)
    _trigger_auto_publish_for_items([item])
    return len(normalized)


def note_has_shared_release_dependents(note: Note) -> bool:
    if published_base_enabled():
        return False  # Published notes now support draft metadata and deletion.
    # Historical membership is authoritative after a note moves out of the
    # current source subtree.  Learners may still have an older release
    # applied, so hard delete/tag/card guards must not rely only on Note.deck_id.
    released_membership = (
        DeckReleaseEntityMembership.query.join(
            DeckMarketplaceItem,
            DeckMarketplaceItem.id
            == DeckReleaseEntityMembership.deck_item_id,
        )
        .filter(
            DeckMarketplaceItem.owner_user_id == int(note.user_id),
            DeckReleaseEntityMembership.entity_kind == "note",
            DeckReleaseEntityMembership.entity_id == str(note.id),
        )
        .first()
    )
    if released_membership is not None:
        return True
    items = _items_covering_deck(
        deck_id=note.deck_id,
        owner_user_id=int(note.user_id),
    )
    if not items:
        return False
    item_ids = [item.id for item in items]
    # A newly-created working-tree note inside an already released deck has no
    # learner dependants yet and remains freely editable until publish.  Only
    # legacy snapshot installs need the timestamp fallback; release installs
    # are covered exactly by immutable membership rows above.
    snapshot_at = note.created_at
    legacy_install_query = DeckInstall.query.filter(
        DeckInstall.deck_item_id.in_(item_ids),
        db.or_(
            DeckInstall.version_mode != "release",
            DeckInstall.applied_release_id.is_(None),
        ),
    )
    if snapshot_at is not None:
        legacy_install_query = legacy_install_query.filter(
            db.func.coalesce(
                DeckInstall.base_snapshot_at,
                DeckInstall.installed_at,
            )
            >= snapshot_at
        )
    return legacy_install_query.first() is not None


def note_type_has_shared_release_dependents(
    *,
    note_type_id: str,
    owner_user_id: int,
) -> bool:
    items = _items_for_note_type(
        note_type_id=note_type_id,
        owner_user_id=owner_user_id,
    )
    if not items:
        return False
    item_ids = [item.id for item in items]
    return bool(
        any(item.current_release_id for item in items)
        or DeckInstall.query.filter(DeckInstall.deck_item_id.in_(item_ids)).first()
    )


def clear_dirty_entities(*, deck_item_id: str) -> None:
    DeckWorkingDirtyEntity.query.filter_by(deck_item_id=deck_item_id).delete(
        synchronize_session=False
    )
