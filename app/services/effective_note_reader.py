"""Published content adapters: never decode an author's draft property.

Callers authorize their listing/install and select a bounded page of identities
before asking for values. There is no release-history reconstruction or cache.
"""
from __future__ import annotations

from copy import deepcopy

from sqlalchemy import select

from models import db
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note


def _item(value):
    return value.deck_item if isinstance(value, DeckInstall) else value


def current_release_for_install(install):
    from app.services.note_base_context import published_base_enabled
    return install.deck_item.current_release if published_base_enabled() else install.applied_release


def install_release_id(install):
    from app.services.note_base_context import published_base_enabled
    return install.deck_item.current_release_id if published_base_enabled() else install.applied_release_id


def published_field_defs(item_or_install, *, include_deleted=False):
    """The published schema, including stable IDs after author rename/delete."""
    item = _item(item_or_install)
    snapshot = item.published_schema_json if item is not None else None
    if not isinstance(snapshot, dict):
        return {}
    return {str(identity): deepcopy(properties) for identity, properties in snapshot.items()
            if isinstance(properties, dict) and (include_deleted or not properties.get("deleted_at"))}


def published_note_values_for_ids(item_or_install, note_ids):
    """Batch read Base using its published labels, with no owner draft access.

    Scope and published/deleted checks are repeated here so a missed caller
    predicate cannot expose an unpublished Note or another author's values.
    """
    from app.repositories.deck_tree_query import collect_subtree_ids
    item = _item(item_or_install)
    ids = sorted({str(identity) for identity in note_ids if identity})
    if not ids or item is None or item.source_deck_id is None:
        return {}
    schema = published_field_defs(item)
    source_decks = collect_subtree_ids(item.source_deck_id)
    result = {}
    # Keep IN lists bounded while fetching only the requested page.
    for offset in range(0, len(ids), 500):
        rows = db.session.execute(select(Note.id, Note.field_values_by_id,
            Note.field_values_extras).where(Note.id.in_(ids[offset:offset + 500]),
                Note.user_id == item.owner_user_id, Note.deck_id.in_(source_decks),
                Note.published_at.isnot(None), Note.deleted_at.is_(None))
            .execution_options(include_deleted_drafts=True)).all()
        for identity, values, extras in rows:
            named = deepcopy(extras or {})
            for field_id, properties in schema.items():
                if field_id in (values or {}) and properties.get("name"):
                    named[str(properties["name"])] = deepcopy(values[field_id])
            result[str(identity)] = named
    return result


def base_note_values_for_ids(install, note_ids):
    """Compatibility adapter used by bounded Browse and external consumers."""
    from app.services.note_base_context import published_base_enabled
    if published_base_enabled():
        return published_note_values_for_ids(install, note_ids)
    from app.services import deck_release_service
    return deck_release_service.get_note_values_for_ids_at_release(install.applied_release, note_ids)


def published_note_membership(note_id_column):
    """Identity-only predicate safe with a literal ID or an aliased Note."""
    notes = Note.__table__.alias("published_note_membership")
    return select(notes.c.id).where(notes.c.id == note_id_column,
        notes.c.published_at.isnot(None), notes.c.deleted_at.is_(None)).correlate_except(notes).exists()


def expanded_source_deck_mapping(install, *, allowed_local_ids=None):
    """Map new source branches to the nearest mapped ancestor, without writes.

    All explicit mappings take precedence, even if outside the selected local
    subtree, preventing a sibling branch leaking into a narrowed Browse scope.
    """
    from models.deck_clone_deck_map import DeckCloneDeckMap
    if install.source_deck_id is None or install.local_deck_id is None:
        return {}
    mappings = {int(source): int(local) for source, local in db.session.execute(
        select(DeckCloneDeckMap.source_deck_id, DeckCloneDeckMap.local_deck_id)
        .where(DeckCloneDeckMap.deck_install_id == install.id)) if source is not None and local is not None}
    mappings.setdefault(int(install.source_deck_id), int(install.local_deck_id))
    resolved = {}
    frontier = [(int(install.source_deck_id), mappings[int(install.source_deck_id)])]
    visited = set()
    while frontier:
        inherited = dict(frontier)
        for source_id, local_id in frontier:
            if source_id in visited:
                raise ValueError("Cycle in shared deck tree")
            visited.add(source_id)
            resolved[source_id] = mappings.get(source_id, local_id)
        rows = db.session.execute(select(Deck.id, Deck.parent_id).where(
            Deck.parent_id.in_(inherited), Deck.deleted_at.is_(None),
            Deck.owner_user_id == install.source_owner_user_id)).all()
        frontier = [(int(child), mappings.get(int(child), resolved[int(parent)])) for child, parent in rows]
    if allowed_local_ids is not None:
        allowed = {int(identity) for identity in allowed_local_ids}
        resolved = {source: local for source, local in resolved.items() if local in allowed}
    return resolved
