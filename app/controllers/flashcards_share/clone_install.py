"""Extracted share submodule."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import OperationalError

from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import *

from app.controllers import flashcards_marketplace_controller as marketplace_ctrl
from app.controllers.deck_controller import collect_ancestor_ids, collect_subtree_ids

# We will let them import classes/constants from core
from .core import *

@dataclass
class CloneDeckScope:
    install: DeckInstall
    local_scope_deck_id: int
    local_deck_ids: list[int]
    source_deck_ids: list[int]
    source_to_local_deck_id: dict[int, int]
    source_owner_user_id: int | None
    base_snapshot_at: datetime | None

@dataclass
class CloneSchemaView:
    field_defs: list[SimpleNamespace]
    removed_field_names: set[str]
    renamed_field_names: dict[str, str]

def clone_note_type_for_user(source_note_type: NoteType, user_id: int) -> NoteType:
    clone = NoteType(
        user_id=user_id,
        name=make_unique_note_type_name(user_id, source_note_type.name),
        description=source_note_type.description,
        primary_category=source_note_type.primary_category,
        tags=list(source_note_type.tags or []),
        preview_text=source_note_type.preview_text,
        preview_image_url=source_note_type.preview_image_url,
        pricing_mode="free",
        price_cents=0,
        version=source_note_type.version or "1.0.0",
        changelog=source_note_type.changelog,
        publish_status="private",
        is_official=False,
        install_count=0,
        active_usage_count=0,
        rating_avg=0.0,
        rating_count=0,
    )
    db.session.add(clone)
    db.session.flush()

    for field_def in sorted(source_note_type.field_defs, key=lambda item: item.position):
        db.session.add(
            FieldDef(
                note_type_id=clone.id,
                name=field_def.name,
                field_type=field_def.field_type,
                position=field_def.position,
                required=bool(field_def.required),
            )
        )

    for template in sorted(source_note_type.templates, key=lambda item: item.position):
        db.session.add(
            Template(
                note_type_id=clone.id,
                name=template.name,
                front_html=template.front_html,
                back_html=template.back_html,
                shared_css=template.shared_css,
                position=template.position,
                is_default=bool(template.is_default),
            )
        )

    return clone

def clone_deck_subtree(
    *,
    source_deck_id: int,
    parent_id: int | None,
    deck_install_id: str | None = None,
    owner_user_id: int | None = None,
    note_type_id_overrides: dict[str, str] | None = None,
    default_note_type_id: str | None = None,
) -> Deck:
    source_deck = Deck.query.get(source_deck_id)
    if not source_deck:
        raise ValueError(f"Deck not found: {source_deck_id}")

    resolved_note_type_id = source_deck.note_type_id or default_note_type_id
    if source_deck.note_type_id and note_type_id_overrides:
        resolved_note_type_id = note_type_id_overrides.get(source_deck.note_type_id, source_deck.note_type_id)

    cloned_deck = Deck(
        parent_id=parent_id,
        owner_user_id=owner_user_id,
        note_type_id=resolved_note_type_id,
        name=source_deck.name,
        description=source_deck.description,
        position=_next_deck_position(parent_id),
    )
    db.session.add(cloned_deck)
    db.session.flush()

    if deck_install_id:
        db.session.add(
            DeckCloneDeckMap(
                deck_install_id=deck_install_id,
                local_deck_id=cloned_deck.id,
                source_deck_id=source_deck.id,
            )
        )

    child_decks = (
        Deck.query.filter_by(parent_id=source_deck.id)
        .order_by(Deck.position.asc(), Deck.id.asc())
        .all()
    )
    for child in child_decks:
        clone_deck_subtree(
            source_deck_id=child.id,
            parent_id=cloned_deck.id,
            deck_install_id=deck_install_id,
            owner_user_id=owner_user_id,
            note_type_id_overrides=note_type_id_overrides,
            default_note_type_id=default_note_type_id,
        )

    return cloned_deck

def ensure_note_type_install_for_deck_clone(
    *,
    source_note_type_id: str | None,
    user_id: int,
) -> tuple[str | None, bool]:
    source_note_type_key = (source_note_type_id or "").strip()
    if not source_note_type_key:
        return None, False

    source_note_type = NoteType.query.get(source_note_type_key)
    if source_note_type is None:
        return None, False

    existing_install = NoteTypeInstall.query.filter_by(
        source_note_type_id=source_note_type.id,
        user_id=user_id,
    ).first()
    if existing_install and (existing_install.installed_note_type_id or "").strip():
        installed_note_type = NoteType.query.filter_by(
            id=existing_install.installed_note_type_id,
            user_id=user_id,
        ).first()
        if installed_note_type is not None:
            return installed_note_type.id, False

    installed_copy = clone_note_type_for_user(source_note_type, user_id)
    now = datetime.utcnow()
    if existing_install:
        existing_install.installed_note_type_id = installed_copy.id
        if existing_install.installed_at is None:
            existing_install.installed_at = now
    else:
        db.session.add(
            NoteTypeInstall(
                source_note_type_id=source_note_type.id,
                installed_note_type_id=installed_copy.id,
                user_id=user_id,
                purchase_price_cents=0,
                installed_at=now,
                purchased_at=None,
            )
        )
    return installed_copy.id, True

def _install_snapshot_at(install: DeckInstall) -> datetime | None:
    return install.base_snapshot_at or install.installed_at

def resolve_clone_scope_for_local_deck(
    *,
    user_id: int,
    local_deck_id: int,
) -> CloneDeckScope | None:
    installs = deck_installs_covering_deck(user_id=user_id, deck_id=local_deck_id)
    install = next(
        (
            row
            for row in installs
            if row.clone_mode == "logical_overlay"
            and row.source_deck_id is not None
            and row.local_deck_id is not None
        ),
        None,
    )
    if not install:
        return None

    local_scope_ids = collect_subtree_ids(local_deck_id)
    if not local_scope_ids:
        return None

    map_rows = (
        DeckCloneDeckMap.query.filter(
            DeckCloneDeckMap.deck_install_id == install.id,
            DeckCloneDeckMap.local_deck_id.in_(local_scope_ids),
        )
        .order_by(DeckCloneDeckMap.local_deck_id.asc(), DeckCloneDeckMap.source_deck_id.asc())
        .all()
    )
    if not map_rows:
        if install.local_deck_id != local_deck_id or install.source_deck_id is None:
            return None
        source_deck_ids = collect_subtree_ids(install.source_deck_id)
        source_to_local = {int(deck_id): local_deck_id for deck_id in source_deck_ids}
        return CloneDeckScope(
            install=install,
            local_scope_deck_id=local_deck_id,
            local_deck_ids=local_scope_ids,
            source_deck_ids=source_deck_ids,
            source_to_local_deck_id=source_to_local,
            source_owner_user_id=install.source_owner_user_id,
            base_snapshot_at=_install_snapshot_at(install),
        )

    source_deck_ids = sorted({int(row.source_deck_id) for row in map_rows if row.source_deck_id is not None})
    source_to_local = {
        int(row.source_deck_id): int(row.local_deck_id)
        for row in map_rows
        if row.source_deck_id is not None and row.local_deck_id is not None
    }
    return CloneDeckScope(
        install=install,
        local_scope_deck_id=local_deck_id,
        local_deck_ids=local_scope_ids,
        source_deck_ids=source_deck_ids,
        source_to_local_deck_id=source_to_local,
        source_owner_user_id=install.source_owner_user_id,
        base_snapshot_at=_install_snapshot_at(install),
    )

def query_clone_scope_cards(scope: CloneDeckScope):
    query = Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id.in_(scope.source_deck_ids))
    if scope.source_owner_user_id is not None:
        query = query.filter(Note.user_id == scope.source_owner_user_id)
    if scope.base_snapshot_at is not None:
        query = query.filter(
            Note.created_at <= scope.base_snapshot_at,
            Card.created_at <= scope.base_snapshot_at,
        )
    return query

def resolve_clone_scope_for_card(
    *,
    user_id: int,
    card_obj: Card | None,
) -> CloneDeckScope | None:
    if card_obj is None or card_obj.note is None or card_obj.note.deck_id is None:
        return None

    source_deck_id = int(card_obj.note.deck_id)
    rows = (
        db.session.query(DeckInstall, DeckCloneDeckMap.local_deck_id)
        .join(DeckCloneDeckMap, DeckCloneDeckMap.deck_install_id == DeckInstall.id)
        .filter(
            DeckInstall.user_id == user_id,
            DeckInstall.clone_mode == "logical_overlay",
            DeckCloneDeckMap.source_deck_id == source_deck_id,
        )
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
        .all()
    )
    for install, local_deck_id in rows:
        if install.source_owner_user_id is not None and card_obj.note.user_id != install.source_owner_user_id:
            continue
        snapshot_at = _install_snapshot_at(install)
        if snapshot_at is not None:
            note_created = card_obj.note.created_at or datetime.min
            card_created = card_obj.created_at or datetime.min
            if note_created > snapshot_at or card_created > snapshot_at:
                continue
        if local_deck_id is None:
            continue
        scope = resolve_clone_scope_for_local_deck(user_id=user_id, local_deck_id=int(local_deck_id))
        if scope is not None:
            return scope
    return None

def resolve_local_clone_deck_id_for_source_deck(
    *,
    install_id: str,
    source_deck_id: int | None,
) -> int | None:
    if source_deck_id is None:
        return None
    row = (
        DeckCloneDeckMap.query.filter_by(
            deck_install_id=install_id,
            source_deck_id=source_deck_id,
        )
        .order_by(DeckCloneDeckMap.created_at.asc(), DeckCloneDeckMap.id.asc())
        .first()
    )
    if not row or row.local_deck_id is None:
        return None
    return int(row.local_deck_id)

def build_clone_schema_view(
    *,
    install: DeckInstall,
    source_note_type_id: str,
) -> CloneSchemaView:
    snapshot_at = _install_snapshot_at(install)
    source_query = FieldDef.query.filter(FieldDef.note_type_id == source_note_type_id)
    if snapshot_at is not None:
        source_query = source_query.filter(FieldDef.created_at <= snapshot_at)
    source_defs = source_query.order_by(FieldDef.position.asc(), FieldDef.created_at.asc(), FieldDef.id.asc()).all()

    override_rows = DeckCloneFieldDefOverride.query.filter_by(deck_install_id=install.id).all()
    override_by_source_id = {
        row.source_field_def_id: row
        for row in override_rows
        if row.source_field_def_id
    }
    removed_field_names: set[str] = set()
    renamed_field_names: dict[str, str] = {}
    resolved_defs: list[SimpleNamespace] = []

    for source_def in source_defs:
        override = override_by_source_id.get(source_def.id)
        if override and bool(override.is_disabled):
            removed_field_names.add(source_def.name)
            continue

        properties = override.properties if override and isinstance(override.properties, dict) else {}
        resolved_name = str(properties.get("name") or source_def.name).strip() or source_def.name
        if resolved_name != source_def.name:
            renamed_field_names[source_def.name] = resolved_name
        resolved_field_type = str(properties.get("field_type") or source_def.field_type or "text").strip().lower()
        if resolved_field_type not in {"text", "richtext", "image", "audio", "diagram"}:
            resolved_field_type = str(source_def.field_type or "text")
        raw_position = properties.get("position")
        try:
            resolved_position = int(raw_position) if raw_position is not None else int(source_def.position or 0)
        except (TypeError, ValueError):
            resolved_position = int(source_def.position or 0)
        if "required" in properties:
            resolved_required = bool(properties.get("required"))
        else:
            resolved_required = bool(source_def.required)
        resolved_defs.append(
            SimpleNamespace(
                id=source_def.id,
                name=resolved_name,
                field_type=resolved_field_type,
                position=resolved_position,
                required=resolved_required,
            )
        )

    added_rows = (
        DeckCloneAddedFieldDef.query.filter_by(deck_install_id=install.id)
        .order_by(DeckCloneAddedFieldDef.position.asc(), DeckCloneAddedFieldDef.created_at.asc(), DeckCloneAddedFieldDef.id.asc())
        .all()
    )
    for row in added_rows:
        properties = row.properties if isinstance(row.properties, dict) else {}
        resolved_name = str(properties.get("name") or row.name).strip() or row.name
        resolved_field_type = str(properties.get("field_type") or row.field_type or "text").strip().lower()
        if resolved_field_type not in {"text", "richtext", "image", "audio", "diagram"}:
            resolved_field_type = str(row.field_type or "text")
        raw_position = properties.get("position")
        try:
            resolved_position = int(raw_position) if raw_position is not None else int(row.position or 0)
        except (TypeError, ValueError):
            resolved_position = int(row.position or 0)
        if "required" in properties:
            resolved_required = bool(properties.get("required"))
        else:
            resolved_required = bool(row.required)
        resolved_defs.append(
            SimpleNamespace(
                id=row.id,
                name=resolved_name,
                field_type=resolved_field_type,
                position=resolved_position,
                required=resolved_required,
            )
        )

    order_override = DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=install.id).first()
    ordered_def_ids = order_override.ordered_def_ids if order_override else []
    if isinstance(ordered_def_ids, list) and ordered_def_ids:
        order_index = {
            str(def_id): index
            for index, def_id in enumerate(ordered_def_ids)
            if isinstance(def_id, str) and def_id.strip()
        }
        resolved_defs.sort(
            key=lambda item: (
                order_index.get(str(item.id), 10_000_000),
                int(item.position or 0),
                str(item.name or "").lower(),
                str(item.id),
            )
        )
        for index, item in enumerate(resolved_defs):
            item.position = index
    else:
        resolved_defs.sort(
            key=lambda item: (
                int(item.position or 0),
                str(item.name or "").lower(),
                str(item.id),
            )
        )

    return CloneSchemaView(
        field_defs=resolved_defs,
        removed_field_names=removed_field_names,
        renamed_field_names=renamed_field_names,
    )

def apply_clone_note_field_overrides(
    *,
    install: DeckInstall,
    source_note: Note,
    schema_view: CloneSchemaView,
) -> dict[str, Any]:
    values = dict(source_note.field_values or {})

    for removed_name in schema_view.removed_field_names:
        values.pop(removed_name, None)

    for old_name, new_name in schema_view.renamed_field_names.items():
        if old_name == new_name:
            continue
        if old_name not in values:
            continue
        if new_name not in values:
            values[new_name] = values.get(old_name)
        values.pop(old_name, None)

    note_override_rows = (
        DeckCloneNoteFieldOverride.query.filter_by(
            deck_install_id=install.id,
            source_note_id=source_note.id,
        )
        .order_by(DeckCloneNoteFieldOverride.created_at.asc(), DeckCloneNoteFieldOverride.id.asc())
        .all()
    )
    for row in note_override_rows:
        if row.operation == "remove":
            values.pop(row.field_name, None)
        else:
            values[row.field_name] = row.value

    for removed_name in schema_view.removed_field_names:
        values.pop(removed_name, None)

    return values

def get_user_deck_install_for_item(
    *,
    user_id: int,
    deck_item_id: str,
) -> DeckInstall | None:
    return (
        DeckInstall.query.filter_by(
            user_id=user_id,
            deck_item_id=deck_item_id,
        )
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
        .first()
    )

def upsert_clone_overlay(
    *,
    deck_install: DeckInstall,
    payload: dict[str, Any],
) -> tuple[dict[str, int], str | None]:
    if deck_install.clone_mode != "logical_overlay":
        return {}, "This install does not support overlay edits."

    counters = {
        "updated_defs": 0,
        "disabled_defs": 0,
        "added_defs": 0,
        "updated_note_fields": 0,
        "removed_note_fields": 0,
    }

    source_note_type_id = (deck_install.source_note_type_id or "").strip()
    source_field_ids: set[str] = set()
    if source_note_type_id:
        source_field_rows = FieldDef.query.with_entities(FieldDef.id).filter(
            FieldDef.note_type_id == source_note_type_id
        )
        snapshot_at = _install_snapshot_at(deck_install)
        if snapshot_at is not None:
            source_field_rows = source_field_rows.filter(FieldDef.created_at <= snapshot_at)
        source_field_ids = {
            str(row[0])
            for row in source_field_rows.all()
            if row and row[0]
        }

    updated_defs_payload = payload.get("updated_defs")
    if updated_defs_payload is not None:
        if not isinstance(updated_defs_payload, list):
            return {}, "updated_defs must be a list."
        for item in updated_defs_payload:
            if not isinstance(item, dict):
                return {}, "Each updated_defs item must be an object."
            source_field_def_id = str(item.get("source_field_def_id") or "").strip()
            if not source_field_def_id:
                return {}, "source_field_def_id is required for updated_defs."
            if source_field_ids and source_field_def_id not in source_field_ids:
                return {}, "updated_defs references field outside pinned snapshot."

            override = DeckCloneFieldDefOverride.query.filter_by(
                deck_install_id=deck_install.id,
                source_field_def_id=source_field_def_id,
            ).first()
            if override is None:
                override = DeckCloneFieldDefOverride(
                    deck_install_id=deck_install.id,
                    source_field_def_id=source_field_def_id,
                    is_disabled=False,
                    properties={},
                )
                db.session.add(override)

            raw_properties = item.get("properties")
            next_properties = dict(override.properties or {})
            if isinstance(raw_properties, dict):
                for key in {"name", "field_type", "position", "required"}:
                    if key not in raw_properties:
                        continue
                    next_properties[key] = raw_properties.get(key)
            for key in {"name", "field_type", "position", "required"}:
                if key in item:
                    next_properties[key] = item.get(key)
            if next_properties:
                override.properties = next_properties
                counters["updated_defs"] += 1

            if "disabled" in item:
                override.is_disabled = bool(item.get("disabled"))
                if override.is_disabled:
                    counters["disabled_defs"] += 1

    disabled_def_ids_payload = payload.get("disabled_def_ids")
    if disabled_def_ids_payload is not None:
        if not isinstance(disabled_def_ids_payload, list):
            return {}, "disabled_def_ids must be a list."
        for raw_id in disabled_def_ids_payload:
            source_field_def_id = str(raw_id or "").strip()
            if not source_field_def_id:
                continue
            if source_field_ids and source_field_def_id not in source_field_ids:
                return {}, "disabled_def_ids references field outside pinned snapshot."
            override = DeckCloneFieldDefOverride.query.filter_by(
                deck_install_id=deck_install.id,
                source_field_def_id=source_field_def_id,
            ).first()
            if override is None:
                override = DeckCloneFieldDefOverride(
                    deck_install_id=deck_install.id,
                    source_field_def_id=source_field_def_id,
                    is_disabled=True,
                    properties={},
                )
                db.session.add(override)
            else:
                override.is_disabled = True
            counters["disabled_defs"] += 1

    added_defs_payload = payload.get("added_defs")
    if added_defs_payload is not None:
        if not isinstance(added_defs_payload, list):
            return {}, "added_defs must be a list."
        for item in added_defs_payload:
            if not isinstance(item, dict):
                return {}, "Each added_defs item must be an object."
            name = str(item.get("name") or "").strip()
            if not name:
                return {}, "added_defs.name is required."
            field_type = str(item.get("field_type") or "text").strip().lower()
            if field_type not in {"text", "richtext", "image", "audio", "diagram"}:
                return {}, "added_defs.field_type is invalid."
            try:
                position = int(item.get("position") if item.get("position") is not None else 0)
            except (TypeError, ValueError):
                return {}, "added_defs.position must be an integer."
            row = DeckCloneAddedFieldDef(
                deck_install_id=deck_install.id,
                name=name,
                field_type=field_type,
                position=position,
                required=bool(item.get("required")),
                properties=item.get("properties") if isinstance(item.get("properties"), dict) else {},
            )
            db.session.add(row)
            counters["added_defs"] += 1

    removed_added_def_ids = payload.get("removed_added_def_ids")
    if removed_added_def_ids is not None:
        if not isinstance(removed_added_def_ids, list):
            return {}, "removed_added_def_ids must be a list."
        for raw_id in removed_added_def_ids:
            added_def_id = str(raw_id or "").strip()
            if not added_def_id:
                continue
            row = DeckCloneAddedFieldDef.query.filter_by(
                deck_install_id=deck_install.id,
                id=added_def_id,
            ).first()
            if row is not None:
                db.session.delete(row)

    clear_order_override = bool(payload.get("clear_order_override"))
    if clear_order_override:
        existing_order_override = DeckCloneFieldOrderOverride.query.filter_by(
            deck_install_id=deck_install.id
        ).first()
        if existing_order_override:
            db.session.delete(existing_order_override)

    order_override_payload = payload.get("ordered_def_ids")
    if order_override_payload is not None:
        if not isinstance(order_override_payload, list):
            return {}, "ordered_def_ids must be a list."
        order_row = DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=deck_install.id).first()
        if order_row is None:
            order_row = DeckCloneFieldOrderOverride(
                deck_install_id=deck_install.id,
                ordered_def_ids=[],
            )
            db.session.add(order_row)
        order_row.ordered_def_ids = [
            str(item).strip()
            for item in order_override_payload
            if str(item).strip()
        ]

    note_field_overrides_payload = payload.get("note_field_overrides")
    if note_field_overrides_payload is not None:
        if not isinstance(note_field_overrides_payload, list):
            return {}, "note_field_overrides must be a list."
        snapshot_at = _install_snapshot_at(deck_install)
        for item in note_field_overrides_payload:
            if not isinstance(item, dict):
                return {}, "Each note_field_overrides item must be an object."
            source_note_id = str(item.get("source_note_id") or "").strip()
            field_name = str(item.get("field_name") or "").strip()
            if not source_note_id or not field_name:
                return {}, "note_field_overrides requires source_note_id and field_name."
            source_note = Note.query.get(source_note_id)
            if not source_note:
                return {}, "note_field_overrides references missing source note."
            if deck_install.source_owner_user_id is not None and source_note.user_id != deck_install.source_owner_user_id:
                return {}, "note_field_overrides references source note outside owner scope."
            if source_note.deck_id is None:
                return {}, "note_field_overrides source note has no deck."
            source_map_exists = DeckCloneDeckMap.query.filter_by(
                deck_install_id=deck_install.id,
                source_deck_id=source_note.deck_id,
            ).first()
            if source_map_exists is None:
                return {}, "note_field_overrides source note is outside clone scope."
            if snapshot_at is not None and (source_note.created_at or datetime.min) > snapshot_at:
                return {}, "note_field_overrides source note is newer than snapshot."

            operation = str(item.get("operation") or "set").strip().lower()
            if operation not in {"set", "remove"}:
                return {}, "note_field_overrides.operation must be set/remove."
            override = DeckCloneNoteFieldOverride.query.filter_by(
                deck_install_id=deck_install.id,
                source_note_id=source_note_id,
                field_name=field_name,
            ).first()
            if override is None:
                override = DeckCloneNoteFieldOverride(
                    deck_install_id=deck_install.id,
                    source_note_id=source_note_id,
                    field_name=field_name,
                )
                db.session.add(override)
            override.operation = operation
            if operation == "remove":
                override.value = None
                counters["removed_note_fields"] += 1
            else:
                override.value = item.get("value")
                counters["updated_note_fields"] += 1

    return counters, None

def deck_installs_covering_deck(*, user_id: int, deck_id: int) -> list[DeckInstall]:
    ancestor_ids = collect_ancestor_ids(deck_id)
    if not ancestor_ids:
        return []
    return (
        DeckInstall.query.filter(
            DeckInstall.user_id == user_id,
            DeckInstall.local_deck_id.in_(ancestor_ids),
        )
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
        .all()
    )

def _ensure_clone_map_rows_for_cutover(
    *,
    install: DeckInstall,
    source_root_deck_id: int,
    local_root_deck_id: int,
) -> list[DeckCloneDeckMap]:
    existing_rows = (
        DeckCloneDeckMap.query.filter_by(deck_install_id=install.id)
        .order_by(DeckCloneDeckMap.local_deck_id.asc(), DeckCloneDeckMap.source_deck_id.asc())
        .all()
    )
    if existing_rows:
        return existing_rows

    source_path_map = _deck_paths_for_cutover(source_root_deck_id)
    local_path_map = _deck_paths_for_cutover(local_root_deck_id)
    if not source_path_map or not local_path_map or set(source_path_map.keys()) != set(local_path_map.keys()):
        raise ShareControllerError(
            f"Install {install.id}: cannot infer source/local deck mapping for cutover.",
            status=409,
        )

    created_rows: list[DeckCloneDeckMap] = []
    for path_key in sorted(source_path_map.keys()):
        source_deck_id = source_path_map[path_key]
        local_deck_id = local_path_map[path_key]
        row = DeckCloneDeckMap(
            deck_install_id=install.id,
            source_deck_id=source_deck_id,
            local_deck_id=local_deck_id,
        )
        db.session.add(row)
        created_rows.append(row)
    db.session.flush()
    return created_rows

def _build_schema_overlay_payload_for_cutover(
    *,
    source_note_type_id: str,
    local_note_type_id: str | None,
) -> dict[str, Any]:
    if not source_note_type_id or not local_note_type_id or local_note_type_id == source_note_type_id:
        return {}

    source_defs = (
        FieldDef.query.filter_by(note_type_id=source_note_type_id)
        .order_by(FieldDef.position.asc(), FieldDef.created_at.asc(), FieldDef.id.asc())
        .all()
    )
    local_defs = (
        FieldDef.query.filter_by(note_type_id=local_note_type_id)
        .order_by(FieldDef.position.asc(), FieldDef.created_at.asc(), FieldDef.id.asc())
        .all()
    )
    if not source_defs and not local_defs:
        return {}

    updated_defs: list[dict[str, Any]] = []
    disabled_def_ids: list[str] = []
    added_defs: list[dict[str, Any]] = []

    pair_count = min(len(source_defs), len(local_defs))
    for idx in range(pair_count):
        source_def = source_defs[idx]
        local_def = local_defs[idx]
        properties: dict[str, Any] = {}
        if (local_def.name or "") != (source_def.name or ""):
            properties["name"] = local_def.name
        if (local_def.field_type or "") != (source_def.field_type or ""):
            properties["field_type"] = local_def.field_type
        if bool(local_def.required) != bool(source_def.required):
            properties["required"] = bool(local_def.required)
        if int(local_def.position or 0) != int(source_def.position or 0):
            properties["position"] = int(local_def.position or 0)
        if properties:
            updated_defs.append(
                {
                    "source_field_def_id": source_def.id,
                    "properties": properties,
                }
            )

    if len(source_defs) > pair_count:
        disabled_def_ids.extend(source_def.id for source_def in source_defs[pair_count:])
    if len(local_defs) > pair_count:
        for local_def in local_defs[pair_count:]:
            added_defs.append(
                {
                    "name": local_def.name,
                    "field_type": local_def.field_type,
                    "position": int(local_def.position or 0),
                    "required": bool(local_def.required),
                }
            )

    payload: dict[str, Any] = {}
    if updated_defs:
        payload["updated_defs"] = updated_defs
    if disabled_def_ids:
        payload["disabled_def_ids"] = disabled_def_ids
    if added_defs:
        payload["added_defs"] = added_defs
    return payload

def _build_note_override_payload_for_cutover(
    *,
    install: DeckInstall,
    source_note: Note,
    local_note: Note,
    schema_view: CloneSchemaView,
) -> list[dict[str, Any]]:
    base_values = _normalize_note_field_values_for_cutover(
        apply_clone_note_field_overrides(
            install=install,
            source_note=source_note,
            schema_view=schema_view,
        )
    )
    local_values = _normalize_note_field_values_for_cutover(local_note.field_values)
    override_items: list[dict[str, Any]] = []

    all_keys = sorted(set(base_values.keys()) | set(local_values.keys()))
    for field_name in all_keys:
        has_base = field_name in base_values
        has_local = field_name in local_values
        if has_base and has_local and base_values[field_name] == local_values[field_name]:
            continue
        if has_local:
            override_items.append(
                {
                    "source_note_id": source_note.id,
                    "field_name": field_name,
                    "operation": "set",
                    "value": local_values[field_name],
                }
            )
            continue
        if has_base and not has_local:
            override_items.append(
                {
                    "source_note_id": source_note.id,
                    "field_name": field_name,
                    "operation": "remove",
                }
            )
    return override_items

def cutover_clone_model_to_overlay_only(*, fail_on_mismatch: bool = True) -> dict[str, Any]:
    from .rating import migrate_legacy_clone_install_to_overlay

    legacy_installs = (
        DeckInstall.query.filter(
            db.or_(
                DeckInstall.clone_mode.is_(None),
                DeckInstall.clone_mode != "logical_overlay",
            )
        )
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
        .all()
    )
    summary = {
        "total_installs": len(legacy_installs),
        "migrated": 0,
        "failed": 0,
        "deck_map_rows": 0,
        "note_pairs": 0,
        "note_overrides": 0,
        "progress_rows": 0,
        "errors": [],
    }

    for install in legacy_installs:
        try:
            counters = migrate_legacy_clone_install_to_overlay(install)
            summary["migrated"] += 1
            summary["deck_map_rows"] += int(counters.get("deck_map_rows") or 0)
            summary["note_pairs"] += int(counters.get("note_pairs") or 0)
            summary["note_overrides"] += int(counters.get("note_overrides") or 0)
            summary["progress_rows"] += int(counters.get("progress_rows") or 0)
        except ShareControllerError as exc:
            db.session.rollback()
            summary["failed"] += 1
            summary["errors"].append(
                {
                    "deck_install_id": install.id,
                    "message": exc.message,
                    "status": exc.status,
                }
            )
            if fail_on_mismatch:
                raise

    return summary

def install_shared_deck_item_for_user(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    publish_statuses_visible: set[str] | None = None,
) -> dict[str, Any]:
    from .rating import recompute_deck_item_market_stats, recompute_note_type_market_stats

    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES

    status = str(deck_item.publish_status or "").strip().lower()
    if status not in visible_statuses:
        raise ShareControllerError(
            "This deck is not available for install.",
            status=409,
        )
    if deck_item.owner_user_id == user_id:
        raise ShareControllerError(
            "Owner cannot install own deck item.",
            status=409,
        )

    existing = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    if existing:
        return {
            "created": False,
            "response": {
                "deck_item_id": deck_item.id,
                "installed_deck_id": existing.local_deck_id,
                "already_installed": True,
            },
        }

    now = datetime.utcnow()
    source_deck_id = deck_item.source_deck_id
    if source_deck_id is None:
        raise ShareControllerError(
            "source_deck_id is required for install.",
            status=409,
            field="source_deck_id",
        )
    source_deck = Deck.query.get(source_deck_id)
    if source_deck is None:
        raise ShareControllerError(
            "Source deck not found.",
            status=404,
            error="FIELD_NOT_FOUND",
        )

    source_note_type_id = (deck_item.source_note_type_id or "").strip() or None
    installed_note_type_id = None
    note_type_install_created = False
    if source_note_type_id:
        installed_note_type_id, note_type_install_created = ensure_note_type_install_for_deck_clone(
            source_note_type_id=source_note_type_id,
            user_id=user_id,
        )

    purchase_price_cents = int(deck_item.price_cents or 0) if deck_item.pricing_mode == "paid" else 0
    install = DeckInstall(
        deck_item_id=deck_item.id,
        user_id=user_id,
        local_deck_id=None,
        clone_mode="logical_overlay",
        source_deck_id=source_deck.id,
        source_note_type_id=source_note_type_id,
        source_owner_user_id=deck_item.owner_user_id,
        base_snapshot_at=now,
        purchase_price_cents=purchase_price_cents,
        installed_at=now,
        purchased_at=now if deck_item.pricing_mode == "paid" else None,
    )
    db.session.add(install)
    db.session.flush()

    local_deck_id = None
    cloned_root = clone_deck_subtree(
        source_deck_id=source_deck.id,
        parent_id=None,
        deck_install_id=install.id,
        owner_user_id=user_id,
        note_type_id_overrides=(
            {source_note_type_id: installed_note_type_id}
            if source_note_type_id and installed_note_type_id
            else None
        ),
        default_note_type_id=installed_note_type_id or source_note_type_id,
    )
    local_deck_id = cloned_root.id
    install.local_deck_id = local_deck_id

    if note_type_install_created and source_note_type_id:
        source_note_type = NoteType.query.get(source_note_type_id)
        if source_note_type is not None:
            recompute_note_type_market_stats(source_note_type)

    recompute_deck_item_market_stats(deck_item)
    return {
        "created": True,
        "response": {
            "deck_item_id": deck_item.id,
            "installed_deck_id": local_deck_id,
            "purchase_price_cents": purchase_price_cents,
        },
        "audit": {
            "deck_item_id": deck_item.id,
            "local_deck_id": local_deck_id,
            "price_cents": purchase_price_cents,
        },
    }
