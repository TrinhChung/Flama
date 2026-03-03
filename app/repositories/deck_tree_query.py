"""Deck model controllers for stats-related deck visibility and hierarchy."""

from __future__ import annotations

from models import db
from models.flashcard import Card, Note
from models.deck import Deck
from models.card_progress import CardProgress


def query_accessible_stats_decks(*, user_id: int, admin_mode: bool) -> list[Deck]:
    query = Deck.query
    if admin_mode:
        query = query.filter(
            db.or_(
                Deck.owner_user_id == user_id,
                Deck.owner_user_id.is_(None),
            )
        )
    else:
        query = query.filter(Deck.owner_user_id == user_id)

    decks = (
        query.order_by(
            Deck.parent_id.isnot(None),
            Deck.position,
            Deck.created_at,
            Deck.id,
        )
        .all()
    )
    if decks:
        return decks

    # Backward-compatible fallback for decks created before owner_user_id was populated.
    all_decks = (
        Deck.query.order_by(
            Deck.parent_id.isnot(None),
            Deck.position,
            Deck.created_at,
            Deck.id,
        )
        .all()
    )
    note_deck_rows = (
        db.session.query(Note.deck_id)
        .select_from(CardProgress)
        .join(Card, CardProgress.card_id == Card.id)
        .join(Note, Card.note_id == Note.id)
        .filter(
            CardProgress.user_id == user_id,
            Note.deck_id.isnot(None),
        )
        .distinct()
        .all()
    )
    visible_ids = {
        int(row[0])
        for row in note_deck_rows
        if row and row[0] is not None
    }
    return [deck for deck in all_decks if deck.id in visible_ids]


def collect_subtree_ids(root_deck_id: int | None) -> list[int]:
    if root_deck_id is None:
        return []

    seen: set[int] = set()
    frontier: set[int] = {int(root_deck_id)}
    while frontier:
        current_ids = {deck_id for deck_id in frontier if deck_id not in seen}
        if not current_ids:
            break

        seen.update(current_ids)
        child_rows = (
            db.session.query(Deck.id)
            .filter(Deck.parent_id.in_(current_ids))
            .all()
        )
        frontier = {int(row[0]) for row in child_rows if row and row[0] is not None}

    return sorted(seen)


def collect_ancestor_ids(deck_id: int | None) -> list[int]:
    if deck_id is None:
        return []

    ancestors: list[int] = []
    current_deck_id = int(deck_id)
    seen: set[int] = set()

    while current_deck_id not in seen:
        seen.add(current_deck_id)
        ancestors.append(current_deck_id)
        parent_row = (
            db.session.query(Deck.parent_id)
            .filter(Deck.id == current_deck_id)
            .first()
        )
        if not parent_row or parent_row[0] is None:
            break
        current_deck_id = int(parent_row[0])

    return ancestors
