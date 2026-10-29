"""Clone overlay view, clone scope resolution, field override mutations, and card query."""

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
from sqlalchemy import and_, case, exists, false, func, or_
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
from models.taxonomy import (
    TaxonomyDomain,
    TaxonomyFramework,
    TaxonomyFrameworkLevel,
    TaxonomySubject,
)
from models.template import Template
from models.user import User
from app.services.note_base_context import published_base_enabled
from app.services.effective_note_reader import (
    current_release_for_install, install_release_id, published_field_defs,
    published_note_membership, published_note_values_for_ids, expanded_source_deck_mapping,
)

logger = logging.getLogger(__name__)


import sys

from app.services.share.helpers import (
    ShareControllerError,
    _audit,
    _next_deck_position,
    _utcnow,
    is_card_visible_in_clone_scope,
    validate_marketplace_note_type_for_deck,
)
from app.services.share.note_types import ensure_note_type_install_for_user

def _get_release_note_membership_filter():
    mod = sys.modules.get("app.services.flashcards_share_service")
    if mod is not None and hasattr(mod, "release_note_membership_filter"):
        return mod.release_note_membership_filter
    return release_note_membership_filter

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


def clone_deck_subtree(
    *,
    source_deck_id: int,
    parent_id: int | None,
    deck_install_id: str | None = None,
    owner_user_id: int | None = None,
    note_type_id_map: dict[str, str] | None = None,
) -> Deck:
    mode = str(
        current_app.config.get("SHARED_DECK_TREE_CLONE_MODE", "batched")
    ).strip().lower()
    if mode == "recursive":
        return _clone_deck_subtree_recursive(
            source_deck_id=source_deck_id,
            parent_id=parent_id,
            deck_install_id=deck_install_id,
            owner_user_id=owner_user_id,
            note_type_id_map=note_type_id_map,
        )
    return _clone_deck_subtree_batched(
        source_deck_id=source_deck_id,
        parent_id=parent_id,
        deck_install_id=deck_install_id,
        owner_user_id=owner_user_id,
        note_type_id_map=note_type_id_map,
    )



def _clone_deck_subtree_recursive(
    *,
    source_deck_id: int,
    parent_id: int | None,
    deck_install_id: str | None = None,
    owner_user_id: int | None = None,
    note_type_id_map: dict[str, str] | None = None,
) -> Deck:
    source_deck = db.session.get(Deck, source_deck_id)
    if not source_deck:
        raise ValueError(f"Deck not found: {source_deck_id}")

    source_note_type_id = (source_deck.note_type_id or "").strip()
    mapped_note_type_id = (
        note_type_id_map.get(source_note_type_id)
        if note_type_id_map and source_note_type_id
        else None
    )

    cloned_deck = Deck(
        parent_id=parent_id,
        owner_user_id=owner_user_id,
        note_type_id=mapped_note_type_id or source_deck.note_type_id,
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
        _clone_deck_subtree_recursive(
            source_deck_id=child.id,
            parent_id=cloned_deck.id,
            deck_install_id=deck_install_id,
            owner_user_id=owner_user_id,
            note_type_id_map=note_type_id_map,
        )

    return cloned_deck



def _clone_deck_subtree_batched(
    *,
    source_deck_id: int,
    parent_id: int | None,
    deck_install_id: str | None = None,
    owner_user_id: int | None = None,
    note_type_id_map: dict[str, str] | None = None,
) -> Deck:
    """Clone only deck shells/maps with query count proportional to tree depth."""
    root = db.session.get(Deck, int(source_deck_id))
    if root is None:
        raise ValueError(f"Deck not found: {source_deck_id}")

    source_by_id: dict[int, Deck] = {int(root.id): root}
    levels: list[list[Deck]] = [[root]]
    frontier = {int(root.id)}
    while frontier:
        children = (
            Deck.query.filter(Deck.parent_id.in_(frontier))
            .order_by(Deck.parent_id.asc(), Deck.position.asc(), Deck.id.asc())
            .all()
        )
        if not children:
            break
        next_frontier: set[int] = set()
        for child in children:
            child_id = int(child.id)
            if child_id in source_by_id:
                raise ValueError(f"Deck tree cycle or duplicate detected at deck {child_id}")
            if child.parent_id not in frontier:
                raise ValueError(f"Deck tree parent missing for deck {child_id}")
            if (
                root.owner_user_id is not None
                and child.owner_user_id is not None
                and int(child.owner_user_id) != int(root.owner_user_id)
            ):
                raise ValueError(f"Deck tree crosses owner boundary at deck {child_id}")
            source_by_id[child_id] = child
            next_frontier.add(child_id)
        levels.append(children)
        frontier = next_frontier

    if parent_id is None:
        max_position = (
            db.session.query(db.func.max(Deck.position))
            .filter(
                Deck.parent_id.is_(None),
                Deck.owner_user_id == owner_user_id,
            )
            .scalar()
        )
        root_position = int(max_position or 0) + 1
    else:
        root_position = _next_deck_position(parent_id)

    local_by_source: dict[int, Deck] = {}
    for depth, source_level in enumerate(levels):
        sibling_offsets: dict[int, int] = {}
        for source in source_level:
            source_id = int(source.id)
            if depth == 0:
                local_parent_id = parent_id
                position = root_position
            else:
                source_parent_id = int(source.parent_id)
                local_parent = local_by_source.get(source_parent_id)
                if local_parent is None:
                    raise ValueError(f"Deck tree parent missing for deck {source_id}")
                local_parent_id = int(local_parent.id)
                position = sibling_offsets.get(source_parent_id, 0)
                sibling_offsets[source_parent_id] = position + 1

            source_note_type_id = str(source.note_type_id or "").strip()
            mapped_note_type_id = (
                note_type_id_map.get(source_note_type_id)
                if note_type_id_map and source_note_type_id
                else None
            )
            clone = Deck(
                parent_id=local_parent_id,
                owner_user_id=owner_user_id,
                note_type_id=mapped_note_type_id or source.note_type_id,
                name=source.name,
                description=source.description,
                position=position,
            )
            db.session.add(clone)
            local_by_source[source_id] = clone
        db.session.flush()

    if deck_install_id:
        for source_id, clone in local_by_source.items():
            db.session.add(
                DeckCloneDeckMap(
                    deck_install_id=deck_install_id,
                    local_deck_id=int(clone.id),
                    source_deck_id=source_id,
                )
            )
        db.session.flush()

    return local_by_source[int(root.id)]


def _install_snapshot_at(install: DeckInstall) -> datetime | None:
    if published_base_enabled():
        return None
    return install.base_snapshot_at or install.installed_at



def _install_uses_release(install: DeckInstall) -> bool:
    if published_base_enabled():
        return False
    return bool(
        str(getattr(install, "version_mode", "") or "").strip() == "release"
        and getattr(install, "applied_release_id", None)
        and getattr(install, "applied_release", None) is not None
    )



def release_note_membership_filter(install: DeckInstall, note_id_column):
    """Build the note-membership predicate for an install's applied release."""

    if published_base_enabled():
        return published_note_membership(note_id_column)
    if not _install_uses_release(install):
        return None
    target_sequence = int(install.applied_release.sequence_no or 0)
    return exists().where(
        DeckReleaseEntityMembership.deck_item_id == install.deck_item_id,
        DeckReleaseEntityMembership.entity_kind == "note",
        DeckReleaseEntityMembership.entity_id == note_id_column,
        DeckReleaseEntityMembership.introduced_sequence <= target_sequence,
        or_(
            DeckReleaseEntityMembership.removed_sequence.is_(None),
            DeckReleaseEntityMembership.removed_sequence > target_sequence,
        ),
    )



def _note_is_member_of_applied_release(*, install: DeckInstall, note_id: str) -> bool:
    filter_fn = _get_release_note_membership_filter()
    predicate = filter_fn(install, str(note_id))
    if predicate is None:
        return True
    return db.session.query(predicate).scalar() is True


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

    if published_base_enabled():
        mapping = expanded_source_deck_mapping(install, allowed_local_ids=local_scope_ids)
        return CloneDeckScope(install=install, local_scope_deck_id=local_deck_id,
            local_deck_ids=local_scope_ids, source_deck_ids=sorted(mapping),
            source_to_local_deck_id=mapping, source_owner_user_id=install.source_owner_user_id,
            base_snapshot_at=None)

    map_rows = flashcards_share_repository.get_clone_deck_maps(install.id, local_scope_ids)
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
    from models.card import INCLUDE_RETIRED_CARDS

    active = Card.application_status == "ACTIVE"
    source_conditions = [Note.deck_id.in_(scope.source_deck_ids)]
    if scope.source_owner_user_id is not None:
        source_conditions.append(Note.user_id == scope.source_owner_user_id)
    release = current_release_for_install(scope.install)
    if release is not None and release.template_pins_initialized:
        from app.repositories.template_release_repository import deck_pins
        pins = deck_pins(db.session, release.id)
        application_conditions = []
        for template_id, pin in pins.items():
            application_ids = list((pin.get("applications_json") or {}).keys())
            for offset in range(0, len(application_ids), 500):
                application_conditions.append(and_(Card.template_id == template_id, Card.application_id.in_(application_ids[offset:offset + 500])))
        # A fully initialized empty manifest intentionally exposes no source
        # presentations. Author draft attachments cannot enter old installs,
        # and a pinned occurrence the author later retired stays visible.
        source_conditions.append(or_(*application_conditions) if application_conditions else false())
    else:
        source_conditions.append(active)
    filter_fn = _get_release_note_membership_filter()
    release_membership = filter_fn(scope.install, Note.id)
    if release_membership is not None:
        source_conditions.append(release_membership)
    elif scope.base_snapshot_at is not None:
        source_conditions.extend(
            [Note.created_at <= scope.base_snapshot_at, Card.created_at <= scope.base_snapshot_at]
        )
    local_added_exists = db.session.query(DeckCloneAddedNote.id).filter(
        DeckCloneAddedNote.deck_install_id == scope.install.id,
        DeckCloneAddedNote.note_id == Note.id,
    ).exists()
    local_condition = and_(
        Note.user_id == scope.install.user_id,
        Note.deck_id.in_(scope.local_deck_ids),
        local_added_exists,
        active,
    )
    # Pins decide source membership here, so the default ACTIVE-only Card
    # criteria is replaced by the explicit conditions above (ADR P11).
    return Card.query.join(Note, Card.note_id == Note.id).filter(
        or_(and_(*source_conditions), local_condition)
    ).execution_options(**{INCLUDE_RETIRED_CARDS: True})


def is_clone_added_note(*, scope: CloneDeckScope, note_id: str) -> bool:
    return DeckCloneAddedNote.query.filter_by(
        deck_install_id=scope.install.id,
        note_id=note_id,
    ).first() is not None


def resolve_clone_scope_for_card(
    *,
    user_id: int,
    card_obj: Card | None,
) -> CloneDeckScope | None:
    if card_obj is None or card_obj.note is None or card_obj.note.deck_id is None:
        return None

    source_deck_id = int(card_obj.note.deck_id)
    if published_base_enabled():
        installs = DeckInstall.query.filter_by(user_id=user_id, clone_mode="logical_overlay").all()
        for install in installs:
            if install.local_deck_id is None:
                continue
            scope = resolve_clone_scope_for_local_deck(user_id=user_id, local_deck_id=install.local_deck_id)
            if scope is not None and source_deck_id in scope.source_deck_ids and query_clone_scope_cards(scope).filter(
                Card.note_id == card_obj.note_id, Card.application_id == card_obj.application_id).first() is not None:
                return scope
        return None
    rows = flashcards_share_repository.find_logical_overlay_installs_for_card(user_id, source_deck_id)
    for install, local_deck_id in rows:
        if install.source_owner_user_id is not None and card_obj.note.user_id != install.source_owner_user_id:
            continue
        snapshot_at = _install_snapshot_at(install)
        if _install_uses_release(install):
            if not _note_is_member_of_applied_release(
                install=install,
                note_id=card_obj.note.id,
            ):
                continue
        elif snapshot_at is not None:
            note_created = card_obj.note.created_at or datetime.min
            card_created = card_obj.created_at or datetime.min
            if note_created > snapshot_at or card_created > snapshot_at:
                continue
        if local_deck_id is None:
            continue
        scope = resolve_clone_scope_for_local_deck(user_id=user_id, local_deck_id=int(local_deck_id))
        if scope is not None and query_clone_scope_cards(scope).filter(
            Card.note_id == card_obj.note_id, Card.application_id == card_obj.application_id,
        ).first() is not None:
            return scope
    return None


def resolve_local_clone_deck_id_for_source_deck(
    *,
    install_id: str,
    source_deck_id: int | None,
) -> int | None:
    if source_deck_id is None:
        return None
    if published_base_enabled():
        install = db.session.get(DeckInstall, install_id)
        return expanded_source_deck_mapping(install).get(int(source_deck_id)) if install else None
    row = flashcards_share_repository.get_clone_deck_map(install_id, source_deck_id)
    if not row or row.local_deck_id is None:
        return None
    return int(row.local_deck_id)


def build_clone_schema_view(
    *,
    install: DeckInstall,
    source_note_type_id: str,
) -> CloneSchemaView:
    cache = None
    cache_key = (
        str(install.id),
        str(install_release_id(install) or "legacy"),
        int(getattr(install, "overlay_revision", 0) or 0),
        str(source_note_type_id),
    )
    try:
        from flask import g, has_request_context

        if has_request_context():
            cache = getattr(g, "_clone_schema_view_cache", None)
            if cache is None:
                cache = {}
                setattr(g, "_clone_schema_view_cache", cache)
            cached_view = cache.get(cache_key)
            if cached_view is not None:
                return cached_view
    except (ImportError, RuntimeError):
        cache = None

    snapshot_at = _install_snapshot_at(install)
    if published_base_enabled() or _install_uses_release(install):
        from app.services import deck_release_service

        release_field_defs = (published_field_defs(install) if published_base_enabled()
            else deck_release_service.get_field_defs_at_release(install.applied_release))
        source_defs = [
            SimpleNamespace(
                id=field_id,
                name=str(payload.get("name") or ""),
                field_type=str(payload.get("field_type") or "text"),
                position=int(payload.get("position") or 0),
                required=bool(payload.get("required")),
                identity_role=payload.get("identity_role"),
            )
            for field_id, payload in release_field_defs.items()
            if str(payload.get("name") or "").strip()
        ]
    else:
        source_defs = flashcards_share_repository.get_field_defs_for_note_type(
            source_note_type_id,
            snapshot_at,
        )

    override_rows = flashcards_share_repository.get_clone_field_overrides(install.id)
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
        if resolved_field_type not in FIELD_TYPES:
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
                field_identity_key=str(source_def.id),
                name=resolved_name,
                field_type=resolved_field_type,
                position=resolved_position,
                required=resolved_required,
                identity_role=getattr(source_def, "identity_role", None),
            )
        )

    added_rows = flashcards_share_repository.get_clone_added_field_defs(install.id)
    for row in added_rows:
        properties = row.properties if isinstance(row.properties, dict) else {}
        resolved_name = str(properties.get("name") or row.name).strip() or row.name
        resolved_field_type = str(properties.get("field_type") or row.field_type or "text").strip().lower()
        if resolved_field_type not in FIELD_TYPES:
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
                field_identity_key=f"added:{install.id}:{row.id}",
                field_type=resolved_field_type,
                position=resolved_position,
                required=resolved_required,
                identity_role=None,
            )
        )

    order_override = flashcards_share_repository.get_clone_field_order_override(install.id)
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

    resolved_view = CloneSchemaView(
        field_defs=resolved_defs,
        removed_field_names=removed_field_names,
        renamed_field_names=renamed_field_names,
    )
    if cache is not None:
        cache[cache_key] = resolved_view
    return resolved_view


def apply_clone_note_field_overrides(
    *,
    install: DeckInstall,
    source_note: Note,
    schema_view: CloneSchemaView,
    base_field_values: dict[str, Any] | None = None,
    note_override_rows: list[DeckCloneNoteFieldOverride] | None = None,
) -> dict[str, Any]:
    if published_base_enabled() and (source_note.published_at is None or source_note.deleted_at is not None):
        return {}
    if base_field_values is not None:
        values = dict(base_field_values)
    elif published_base_enabled():
        values = published_note_values_for_ids(install, [source_note.id]).get(str(source_note.id), {})
    elif _install_uses_release(install):
        from app.services import deck_release_service

        release_values = None
        note_cache = None
        cache_key = (str(install.applied_release_id), str(source_note.id))
        try:
            from flask import g, has_request_context

            if has_request_context():
                note_cache = getattr(g, "_clone_release_note_values_cache", None)
                if note_cache is None:
                    note_cache = {}
                    setattr(g, "_clone_release_note_values_cache", note_cache)
                if cache_key in note_cache:
                    release_values = note_cache[cache_key]
        except (ImportError, RuntimeError):
            note_cache = None
        if release_values is None:
            release_values = deck_release_service.get_note_values_at_release(
                install.applied_release,
                source_note.id,
            )
            if note_cache is not None:
                note_cache[cache_key] = release_values
        values = dict(release_values or {})
    else:
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

    if note_override_rows is None:
        note_override_rows = flashcards_share_repository.get_clone_note_field_overrides(install.id, source_note.id)
    from app.services.clone_field_identity_service import clone_override_field_label, clone_field_identity_labels
    identity_labels = clone_field_identity_labels(install, schema_view)
    for row in note_override_rows:
        field_name = clone_override_field_label(row, install, schema_view, identity_labels=identity_labels)
        if field_name is None:
            continue
        if row.operation == "remove":
            values.pop(field_name, None)
        else:
            values[field_name] = row.value

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
    from app.services.clone_field_identity_service import lock_clone_overlay_write
    deck_install = lock_clone_overlay_write(deck_install, expected_revision=payload.get("expected_overlay_revision"))
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
    removal_identity_labels = {}
    note_deltas = payload.get("note_field_overrides")
    if isinstance(note_deltas, list) and any(isinstance(item, dict)
            and str(item.get("operation") or "set").strip().lower() == "remove" for item in note_deltas):
        from app.services.clone_field_identity_service import clone_field_identity_labels
        initial_schema = build_clone_schema_view(install=deck_install, source_note_type_id=source_note_type_id)
        removal_identity_labels = clone_field_identity_labels(deck_install, initial_schema)
    source_field_ids: set[str] = set()
    source_fields_by_id: dict[str, FieldDef] = {}
    source_fields_by_name: dict[str, FieldDef] = {}
    if source_note_type_id:
        if published_base_enabled() or _install_uses_release(deck_install):
            from app.services import deck_release_service

            source_fields_by_id = {
                str(field_id): SimpleNamespace(id=field_id, **dict(properties or {}))
                for field_id, properties in (published_field_defs(deck_install) if published_base_enabled()
                    else deck_release_service.get_field_defs_at_release(deck_install.applied_release)).items()
            }
        else:
            source_field_rows = FieldDef.query.filter(
                FieldDef.note_type_id == source_note_type_id
            )
            snapshot_at = _install_snapshot_at(deck_install)
            if snapshot_at is not None:
                source_field_rows = source_field_rows.filter(FieldDef.created_at <= snapshot_at)
            source_fields_by_id = {
                str(row.id): row
                for row in source_field_rows.all()
                if row and row.id
            }
        source_field_ids = set(source_fields_by_id)
        source_fields_by_name = {
            str(row.name): row
            for row in source_fields_by_id.values()
            if row and str(row.name or "").strip()
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
            source_field = source_fields_by_id.get(source_field_def_id)
            if source_field is not None and source_field.identity_role == "primary":
                if str(next_properties.get("field_type") or source_field.field_type) != "text":
                    return {}, "The primary identity field must remain text in a clone."
                if not bool(next_properties.get("required", source_field.required)):
                    return {}, "The primary identity field must remain required in a clone."
            if next_properties:
                override.properties = next_properties
                counters["updated_defs"] += 1

            if "disabled" in item:
                source_field = source_fields_by_id.get(source_field_def_id)
                if bool(item.get("disabled")) and source_field is not None and source_field.identity_role == "primary":
                    return {}, "The primary identity field cannot be disabled in a clone."
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
            source_field = source_fields_by_id.get(source_field_def_id)
            if source_field is not None and source_field.identity_role == "primary":
                return {}, "The primary identity field cannot be disabled in a clone."
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
            if field_type not in FIELD_TYPES:
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
        from app.services.clone_field_identity_service import clone_field_identity_labels
        resolved_schema = build_clone_schema_view(install=deck_install, source_note_type_id=source_note_type_id)
        identity_labels = clone_field_identity_labels(deck_install, resolved_schema)
        for item in note_field_overrides_payload:
            if not isinstance(item, dict):
                return {}, "Each note_field_overrides item must be an object."
            source_note_id = str(item.get("source_note_id") or "").strip()
            field_name = str(item.get("field_name") or "").strip()
            field_identity_key = str(item.get("field_identity_key") or "").strip() or None
            if not source_note_id or not (field_name or field_identity_key):
                return {}, "note_field_overrides requires source_note_id and a field identity or current label."
            source_note = db.session.get(Note, source_note_id)
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
            if source_map_exists is None and not (published_base_enabled() and
                resolve_local_clone_deck_id_for_source_deck(install_id=deck_install.id, source_deck_id=source_note.deck_id) is not None):
                return {}, "note_field_overrides source note is outside clone scope."
            if (published_base_enabled() or _install_uses_release(deck_install)) and not _note_is_member_of_applied_release(
                install=deck_install,
                note_id=source_note.id,
            ):
                return {}, "note_field_overrides references note outside applied release."
            if (
                not _install_uses_release(deck_install)
                and snapshot_at is not None
                and (source_note.created_at or datetime.min) > snapshot_at
            ):
                return {}, "note_field_overrides source note is newer than snapshot."

            operation = str(item.get("operation") or "set").strip().lower()
            if operation not in {"set", "remove"}:
                return {}, "note_field_overrides.operation must be set/remove."
            from app.services.clone_field_identity_service import stage_clone_note_field_override
            override = stage_clone_note_field_override(install=deck_install, source_note=source_note,
                field_name=field_name, field_identity_key=field_identity_key,
                operation=operation, value=item.get("value"), identity_labels=identity_labels,
                removal_identity_labels=removal_identity_labels)
            if operation == "remove":
                override.value = None
                counters["removed_note_fields"] += 1
            else:
                override.value = item.get("value")
                counters["updated_note_fields"] += 1

    deck_install.last_sync_status = "needs_sync"
    deck_install.overlay_revision = int(deck_install.overlay_revision or 0) + 1
    return counters, None


def upsert_shared_deck_clone_overlay(deck_item_id: str, install: DeckInstall, user_id: int, payload: dict) -> tuple[dict | None, str | None]:
    counters, validation_error = upsert_clone_overlay(
        deck_install=install,
        payload=payload,
    )
    if validation_error:
        db.session.rollback()
        return None, validation_error

    _audit(
        user_id,
        "market.deck_item.clone_overlay.upsert",
        {
            "deck_item_id": deck_item_id,
            "deck_install_id": install.id,
            "changes": counters,
        },
    )
    db.session.commit()
    return counters, None



def deck_installs_covering_deck(*, user_id: int, deck_id: int) -> list[DeckInstall]:
    ancestors = collect_ancestor_ids(deck_id)
    if not ancestors:
        ancestors = []
    return flashcards_share_repository.get_user_deck_installs_covering_deck(user_id, ancestors + [deck_id])


