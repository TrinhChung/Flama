"""Track owner working-tree mutations for versioned shared decks."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from app.repositories.deck_tree_query import collect_ancestor_ids
from models import db
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity
from models.field_def import FieldDef
from models.note import Note


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
    return (
        DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.owner_user_id == owner_user_id,
            DeckMarketplaceItem.source_deck_id.in_(source_candidates),
            DeckMarketplaceItem.publish_status.in_(["published", "unlisted"]),
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
        .filter(DeckMarketplaceItem.publish_status.in_(["published", "unlisted"]))
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


def mark_note_fields_changed(
    *,
    note: Note,
    field_names: Iterable[str],
    operation: str = "set",
    deck_id: int | None = None,
) -> int:
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
        item.working_revision = int(item.working_revision or 0) + 1
        for field_name in normalized_names:
            field_id = field_ids_by_name.get(field_name)
            property_key = f"field:{field_id}" if field_id else f"field_name:{field_name}"
            _upsert_dirty(
                item=item,
                entity_kind="note_field",
                entity_id=str(note.id),
                property_key=property_key,
                operation=operation,
                current_value=(note.field_values or {}).get(field_name),
                field_def_id=field_id,
                source_deck_id=resolved_deck_id,
                metadata={"field_name": field_name},
            )
    return len(items)


def mark_field_def_changed(
    *,
    field_def: FieldDef,
    owner_user_id: int,
    property_keys: Iterable[str],
    operation: str = "set",
) -> int:
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
        item.working_revision = int(item.working_revision or 0) + 1
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
    return len(items)


def note_has_shared_release_dependents(note: Note) -> bool:
    items = _items_covering_deck(
        deck_id=note.deck_id,
        owner_user_id=int(note.user_id),
    )
    if not items:
        return False
    item_ids = [item.id for item in items]
    return bool(
        any(item.current_release_id for item in items)
        or DeckInstall.query.filter(DeckInstall.deck_item_id.in_(item_ids)).first()
    )


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
