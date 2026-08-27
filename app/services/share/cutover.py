"""Migration and cutover logic from legacy full-copy clone model to overlay-only model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import time
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flask import current_app
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload

from app.repositories import (
    deck_change_request_repository,
    deck_release_repository,
    flashcards_share_repository,
    marketplace_taxonomy_repository,
    study_repository,
    vocabulary_repository,
)
from app.repositories.deck_tree_query import (
    collect_ancestor_ids,
    collect_subtree_ids,
)
from app.services import (
    deck_release_service,
    deck_working_tree_service,
    marketplace_query_service,
    marketplace_taxonomy_service,
    note_sync_service,
    study_service,
)
from app.services.share.constants import (
    DECK_ACTIVE_REVIEW_THRESHOLD,
    DEFAULT_VISIBLE_PUBLISH_STATUSES,
    FIELD_TYPES,
    MARKET_ACTIVITY_POLICY_VERSION,
    NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
    NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
    PUBLISH_STATUSES_VISIBLE,
    SHARED_DECK_INSTALL_DEADLOCK_MESSAGE,
    SHARED_DECK_INSTALL_MAX_RETRIES,
    UTC,
)
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_change_request import DeckChangeRequest
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_field_order_override import DeckCloneFieldOrderOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_review import DeckReview
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.note_type_review import NoteTypeReview
from models.taxonomy import TaxonomyDomain, TaxonomyLevel, TaxonomySubject, TaxonomyTopic
from models.template import Template
from models.user import User

logger = logging.getLogger(__name__)


from app.services.share.helpers import (
    ShareControllerError,
    _audit,
    _utcnow,
)
from app.services.share.install import _installed_local_deck_ids
from app.services.share.note_types import ensure_note_type_install_for_user
from app.services.share.overlay import (
    CloneSchemaView,
    _install_snapshot_at,
    apply_clone_note_field_overrides,
    build_clone_schema_view,
    clone_deck_subtree,
    get_user_deck_install_for_item,
    upsert_clone_overlay,
    upsert_shared_deck_clone_overlay,
)

def _normalize_note_field_values_for_cutover(raw_values: dict | None) -> dict[str, str]:
    if not isinstance(raw_values, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw_values.items():
        key_name = str(key).strip()
        if not key_name:
            continue
        normalized[key_name] = "" if value is None else str(value)
    return normalized


def _deck_paths_for_cutover(root_deck_id: int) -> dict[tuple[int, ...], int]:
    deck_ids = collect_subtree_ids(root_deck_id)
    if not deck_ids:
        return {}
    deck_rows = Deck.query.filter(Deck.id.in_(deck_ids)).all()
    if not deck_rows:
        return {}
    children_by_parent: dict[int | None, list[Deck]] = {}
    for deck_obj in deck_rows:
        children_by_parent.setdefault(deck_obj.parent_id, []).append(deck_obj)
    for rows in children_by_parent.values():
        rows.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    path_to_deck: dict[tuple[int, ...], int] = {}

    def _walk(deck_id: int, path: tuple[int, ...]) -> None:
        path_to_deck[path] = deck_id
        for index, child in enumerate(children_by_parent.get(deck_id, [])):
            _walk(child.id, path + (index,))

    _walk(root_deck_id, ())
    return path_to_deck


def _pair_legacy_local_source_notes_for_cutover(
    *,
    install: DeckInstall,
    source_to_local_deck_id: dict[int, int],
    source_owner_user_id: int | None,
    source_note_type_id: str | None,
    snapshot_at: datetime | None,
) -> list[tuple[Note, Note]]:
    local_to_source = {
        int(local_deck_id): int(source_deck_id)
        for source_deck_id, local_deck_id in source_to_local_deck_id.items()
    }
    pairs: list[tuple[Note, Note]] = []

    for local_deck_id in sorted(local_to_source.keys()):
        source_deck_id = local_to_source[local_deck_id]
        
        local_notes = flashcards_share_repository.get_notes_for_user_deck(install.user_id, local_deck_id)
        source_notes = flashcards_share_repository.get_source_notes_for_cutover(
            source_deck_id, source_owner_user_id, source_note_type_id, snapshot_at
        )

        if len(local_notes) != len(source_notes):
            raise ShareControllerError(
                (
                    f"Install {install.id}: note count mismatch in deck pair "
                    f"(local_deck_id={local_deck_id}, source_deck_id={source_deck_id}, "
                    f"local={len(local_notes)}, source={len(source_notes)})."
                ),
                status=409,
            )
        pairs.extend(zip(local_notes, source_notes))

    return pairs


def _merge_card_progress_rows_for_cutover(
    *,
    user_id: int,
    local_card_id: str,
    source_card_id: str,
) -> int:
    moved_count = 0
    progress_rows = flashcards_share_repository.get_card_progress_rows_for_local_card(user_id, local_card_id)
    
    for row in progress_rows:
        target = flashcards_share_repository.get_card_progress_for_source_card(user_id, source_card_id)
        if target is None:
            row.card_id = source_card_id
            moved_count += 1
            continue

        row_newer = (row.updated_at or datetime.min) >= (target.updated_at or datetime.min)
        if row_newer:
            target.queue = row.queue
            target.step_index = row.step_index
            target.due_at = row.due_at
            target.due_day = row.due_day
            target.interval_days = row.interval_days
            if hasattr(target, "interval_days_raw"):
                target.interval_days_raw = getattr(row, "interval_days_raw", None)
            target.is_suspended = bool(row.is_suspended)
            if hasattr(target, "is_buried"):
                target.is_buried = bool(getattr(row, "is_buried", False))
            if hasattr(target, "buried_until_day"):
                target.buried_until_day = getattr(row, "buried_until_day", None)
            target.ease_factor = row.ease_factor
            if hasattr(target, "review_kind"):
                target.review_kind = getattr(row, "review_kind", target.review_kind)
            if hasattr(target, "scheduler_mode"):
                target.scheduler_mode = getattr(row, "scheduler_mode", target.scheduler_mode)
            if hasattr(target, "memory_stability"):
                target.memory_stability = getattr(row, "memory_stability", None)
            if hasattr(target, "memory_difficulty"):
                target.memory_difficulty = getattr(row, "memory_difficulty", None)
            if hasattr(target, "suspension_reason"):
                target.suspension_reason = getattr(row, "suspension_reason", None)
            if hasattr(target, "last_leech_at"):
                target.last_leech_at = getattr(row, "last_leech_at", None)
            if hasattr(target, "last_leech_lapses"):
                target.last_leech_lapses = int(getattr(row, "last_leech_lapses", 0) or 0)
            if hasattr(target, "last_review_event_id"):
                target.last_review_event_id = getattr(row, "last_review_event_id", None)
            target.last_reviewed_at = row.last_reviewed_at or target.last_reviewed_at
        target.reps = max(int(target.reps or 0), int(row.reps or 0))
        target.lapses = max(int(target.lapses or 0), int(row.lapses or 0))
        db.session.delete(row)
        moved_count += 1
    return moved_count


def _assert_cutover_note_equivalence(
    *,
    install: DeckInstall,
    pairs: list[tuple[Note, Note]],
    schema_view: CloneSchemaView,
) -> None:
    for local_note, source_note in pairs:
        migrated_values = _normalize_note_field_values_for_cutover(
            apply_clone_note_field_overrides(
                install=install,
                source_note=source_note,
                schema_view=schema_view,
            )
        )
        local_values = _normalize_note_field_values_for_cutover(local_note.field_values)
        if migrated_values != local_values:
            raise ShareControllerError(
                (
                    f"Install {install.id}: cutover mismatch for source_note_id={source_note.id}, "
                    f"local_note_id={local_note.id}."
                ),
                status=409,
            )


def migrate_legacy_clone_install_to_overlay(
    install: DeckInstall,
) -> dict[str, int]:
    deck_item = db.session.get(DeckMarketplaceItem, install.deck_item_id)
    source_deck_id = install.source_deck_id or (deck_item.source_deck_id if deck_item else None)
    if source_deck_id is None:
        raise ShareControllerError(
            f"Install {install.id}: source_deck_id is required for cutover.",
            status=409,
        )
    source_deck = db.session.get(Deck, source_deck_id)
    if source_deck is None:
        raise ShareControllerError(
            f"Install {install.id}: source deck not found ({source_deck_id}).",
            status=404,
        )
    if install.local_deck_id is None:
        raise ShareControllerError(
            f"Install {install.id}: local_deck_id is required for cutover.",
            status=409,
        )
    local_deck = db.session.get(Deck, install.local_deck_id)
    if local_deck is None:
        raise ShareControllerError(
            f"Install {install.id}: local deck not found ({install.local_deck_id}).",
            status=404,
        )

    source_owner_user_id = install.source_owner_user_id or (deck_item.owner_user_id if deck_item else None)
    source_note_type_id = (
        (install.source_note_type_id or "").strip()
        or ((deck_item.source_note_type_id or "").strip() if deck_item else "")
    )
    snapshot_at = install.base_snapshot_at or install.installed_at

    map_rows = _ensure_clone_map_rows_for_cutover(
        install=install,
        source_root_deck_id=source_deck.id,
        local_root_deck_id=local_deck.id,
    )
    source_to_local = {
        int(row.source_deck_id): int(row.local_deck_id)
        for row in map_rows
        if row.source_deck_id is not None and row.local_deck_id is not None
    }
    if not source_to_local:
        raise ShareControllerError(
            f"Install {install.id}: source/local deck map is empty for cutover.",
            status=409,
        )

    pairs = _pair_legacy_local_source_notes_for_cutover(
        install=install,
        source_to_local_deck_id=source_to_local,
        source_owner_user_id=source_owner_user_id,
        source_note_type_id=source_note_type_id or None,
        snapshot_at=snapshot_at,
    )

    local_note_type_ids = sorted(
        {
            str(local_note.note_type_id).strip()
            for local_note, _source_note in pairs
            if (local_note.note_type_id or "").strip()
        }
    )
    local_note_type_id = local_note_type_ids[0] if len(local_note_type_ids) == 1 else None
    if len(local_note_type_ids) > 1:
        raise ShareControllerError(
            f"Install {install.id}: local legacy clone has multiple note types; cutover is ambiguous.",
            status=409,
        )

    if not source_note_type_id:
        source_note_type_ids = sorted(
            {
                str(source_note.note_type_id).strip()
                for _local_note, source_note in pairs
                if (source_note.note_type_id or "").strip()
            }
        )
        if len(source_note_type_ids) == 1:
            source_note_type_id = source_note_type_ids[0]
        elif len(source_note_type_ids) > 1:
            raise ShareControllerError(
                f"Install {install.id}: source clone scope has multiple note types; source_note_type_id is required.",
                status=409,
            )

    install.clone_mode = "logical_overlay"
    DeckCloneFieldDefOverride.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    DeckCloneAddedFieldDef.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    db.session.flush()

    if source_note_type_id:
        schema_payload = _build_schema_overlay_payload_for_cutover(
            source_note_type_id=source_note_type_id,
            local_note_type_id=local_note_type_id,
        )
        if schema_payload:
            _counters, validation_error = upsert_clone_overlay(
                deck_install=install,
                payload=schema_payload,
            )
            if validation_error:
                raise ShareControllerError(
                    f"Install {install.id}: schema cutover failed: {validation_error}",
                    status=409,
                )
    elif local_note_type_id:
        raise ShareControllerError(
            f"Install {install.id}: source_note_type_id is required for schema cutover.",
            status=409,
        )

    if source_note_type_id:
        schema_view = build_clone_schema_view(
            install=install,
            source_note_type_id=source_note_type_id,
        )
    else:
        schema_view = CloneSchemaView(field_defs=[], removed_field_names=set(), renamed_field_names={})

    note_override_payload: list[dict[str, Any]] = []
    progress_migrated = 0
    local_note_ids: list[str] = []
    template_map_cache: dict[str, dict[str, str]] = {}

    for local_note, source_note in pairs:
        local_note_ids.append(local_note.id)
        note_override_payload.extend(
            _build_note_override_payload_for_cutover(
                install=install,
                source_note=source_note,
                local_note=local_note,
                schema_view=schema_view,
            )
        )

        local_note_type_key = str(local_note.note_type_id or "").strip()
        source_note_type_key = str(source_note.note_type_id or "").strip()
        template_key = f"{local_note_type_key}->{source_note_type_key}"
        template_map = template_map_cache.get(template_key)
        if template_map is None:
            local_templates = (
                Template.query.filter_by(note_type_id=local_note_type_key)
                .order_by(Template.position.asc(), Template.created_at.asc(), Template.id.asc())
                .all()
            )
            source_templates = (
                Template.query.filter_by(note_type_id=source_note_type_key)
                .order_by(Template.position.asc(), Template.created_at.asc(), Template.id.asc())
                .all()
            )
            if len(local_templates) != len(source_templates):
                raise ShareControllerError(
                    (
                        f"Install {install.id}: template count mismatch for note type pair "
                        f"({local_note_type_key} -> {source_note_type_key})."
                    ),
                    status=409,
                )
            template_map = {
                str(local_templates[idx].id): str(source_templates[idx].id)
                for idx in range(len(local_templates))
            }
            template_map_cache[template_key] = template_map

        source_cards_by_template = {
            str(card.template_id): card
            for card in Card.query.filter_by(note_id=source_note.id).all()
        }
        local_cards = Card.query.filter_by(note_id=local_note.id).all()
        for local_card in local_cards:
            source_template_id = template_map.get(str(local_card.template_id))
            if not source_template_id:
                raise ShareControllerError(
                    (
                        f"Install {install.id}: cannot map local template_id={local_card.template_id} "
                        f"for local_note_id={local_note.id}."
                    ),
                    status=409,
                )
            source_card = source_cards_by_template.get(str(source_template_id))
            if source_card is None:
                raise ShareControllerError(
                    (
                        f"Install {install.id}: source card not found for template_id={source_template_id} "
                        f"(source_note_id={source_note.id})."
                    ),
                    status=409,
                )
            progress_migrated += _merge_card_progress_rows_for_cutover(
                user_id=install.user_id,
                local_card_id=local_card.id,
                source_card_id=source_card.id,
            )

    if note_override_payload:
        _counters, validation_error = upsert_clone_overlay(
            deck_install=install,
            payload={"note_field_overrides": note_override_payload},
        )
        if validation_error:
            raise ShareControllerError(
                f"Install {install.id}: note cutover failed: {validation_error}",
                status=409,
            )

    if source_note_type_id:
        schema_view = build_clone_schema_view(
            install=install,
            source_note_type_id=source_note_type_id,
        )
    _assert_cutover_note_equivalence(
        install=install,
        pairs=pairs,
        schema_view=schema_view,
    )

    if local_note_ids:
        Note.query.filter(Note.id.in_(local_note_ids)).delete(synchronize_session=False)

    install.clone_mode = "logical_overlay"
    install.source_deck_id = source_deck.id
    install.source_note_type_id = source_note_type_id or None
    install.source_owner_user_id = source_owner_user_id
    install.base_snapshot_at = snapshot_at

    return {
        "deck_map_rows": len(source_to_local),
        "note_pairs": len(pairs),
        "note_overrides": len(note_override_payload),
        "progress_rows": progress_migrated,
    }


@dataclass

def _ensure_clone_map_rows_for_cutover(
    *,
    install: DeckInstall,
    source_root_deck_id: int,
    local_root_deck_id: int,
) -> list[DeckCloneDeckMap]:
    existing_rows = flashcards_share_repository.get_clone_deck_maps(install.id)
    if existing_rows:
        return existing_rows
    local_deck_ids = collect_subtree_ids(local_root_deck_id)
    if not local_deck_ids:
        return []

    local_decks = Deck.query.filter(Deck.id.in_(local_deck_ids)).all()
    local_decks_by_parent: dict[int | None, list[Deck]] = {}
    for local_deck in local_decks:
        local_decks_by_parent.setdefault(local_deck.parent_id, []).append(local_deck)
    for rows in local_decks_by_parent.values():
        rows.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    source_deck_ids = collect_subtree_ids(source_root_deck_id)
    if not source_deck_ids:
        return []
    source_decks = Deck.query.filter(Deck.id.in_(source_deck_ids)).all()
    source_decks_by_parent: dict[int | None, list[Deck]] = {}
    for source_deck in source_decks:
        source_decks_by_parent.setdefault(source_deck.parent_id, []).append(source_deck)
    for rows in source_decks_by_parent.values():
        rows.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    local_to_source: dict[int, int] = {local_root_deck_id: source_root_deck_id}

    def _walk_and_pair(local_pid: int, source_pid: int) -> None:
        local_children = local_decks_by_parent.get(local_pid, [])
        source_children = source_decks_by_parent.get(source_pid, [])
        for idx in range(min(len(local_children), len(source_children))):
            local_child_id = local_children[idx].id
            source_child_id = source_children[idx].id
            local_to_source[local_child_id] = source_child_id
            _walk_and_pair(local_child_id, source_child_id)

    _walk_and_pair(local_root_deck_id, source_root_deck_id)

    created_rows: list[DeckCloneDeckMap] = []
    for local_deck_id, source_deck_id in local_to_source.items():
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


