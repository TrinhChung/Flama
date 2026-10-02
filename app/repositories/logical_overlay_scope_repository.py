"""Logical-overlay source Card scope for NOTE-authority readers.

Mirrors the LEGACY dashboard / Browse-tree merge filters: each install's
mapped source decks, its source owner and its base snapshot. Per-install
evaluation matches both the single-query and the cross-install-overlap
branches of the LEGACY Browse tree.
"""

from __future__ import annotations

from typing import Iterable

from models.flashcard import Card, DeckCloneDeckMap, Note


def logical_overlay_cards(
    installs: Iterable, *, visible_deck_ids: set[int]
) -> tuple[list[tuple[Card, int]], dict[int, str]]:
    """Return (Card, mapped local deck ID) pairs and install NoteType per local deck.

    The NoteType map matches LEGACY, which records the install NoteType for a
    mapped local deck even when no source Card is visible yet.
    """
    result: list[tuple[Card, int]] = []
    note_type_by_local_deck: dict[int, str] = {}
    for install in installs:
        if install.clone_mode != "logical_overlay" or not install.id or not install.local_deck_id:
            continue
        source_to_local = {
            int(row.source_deck_id): int(row.local_deck_id)
            for row in DeckCloneDeckMap.query.filter_by(deck_install_id=install.id)
            .order_by(DeckCloneDeckMap.local_deck_id.asc(), DeckCloneDeckMap.source_deck_id.asc())
            .all()
            if row.source_deck_id is not None
            and row.local_deck_id is not None
            and int(row.local_deck_id) in visible_deck_ids
        }
        if not source_to_local:
            continue
        if install.source_note_type_id:
            for local_deck_id in source_to_local.values():
                note_type_by_local_deck.setdefault(local_deck_id, str(install.source_note_type_id))
        query = Card.query.add_columns(Note.deck_id).join(Note, Card.note_id == Note.id).filter(
            Note.deck_id.in_(source_to_local.keys())
        )
        if install.source_owner_user_id is not None:
            query = query.filter(Note.user_id == install.source_owner_user_id)
        snapshot_at = install.base_snapshot_at or install.installed_at
        if snapshot_at is not None:
            query = query.filter(Note.created_at <= snapshot_at, Card.created_at <= snapshot_at)
        for card, source_deck_id in query.order_by(Card.id.asc()).all():
            local_deck_id = source_to_local.get(int(source_deck_id))
            if local_deck_id is not None:
                result.append((card, local_deck_id))
    return result, note_type_by_local_deck
