"""Deck model controllers for stats-related deck visibility and hierarchy."""

from __future__ import annotations

from models import db
from models.flashcard import Card, DeckInstall, Note
from models.deck import Deck
from models.card_progress import CardProgress
from sqlalchemy import or_


def collect_accessible_decks(*, user_id: int, admin_mode: bool) -> list[Deck]:
    """Return all decks visible to the user, including children and ancestor
    folders.  This is the canonical deck visibility query used by dashboard,
    import, and any other consumer that needs the full deck tree.

    The algorithm mirrors the original dashboard logic:
    1. Admin mode: owned + unowned decks.
    2. Normal mode: owned decks + installed (cloned) root decks, then BFS
       downward to collect all children, then walk upward to collect any
       missing ancestor folders so the tree is always complete.
    """
    if admin_mode:
        initial_decks = (
            Deck.query.filter(
                Deck.deleted_at.is_(None),
                or_(
                    Deck.owner_user_id == user_id,
                    Deck.owner_user_id.is_(None),
                ),
            )
            .all()
        )
        if not initial_decks:
            return []
        by_id: dict[int, Deck] = {deck.id: deck for deck in initial_decks}
        frontier = {
            deck.parent_id
            for deck in initial_decks
            if deck.parent_id is not None
        } - set(by_id)
        while frontier:
            parent_decks = (
                Deck.query.filter(
                    Deck.id.in_(frontier),
                    Deck.deleted_at.is_(None),
                )
                .all()
            )
            by_id.update({deck.id: deck for deck in parent_decks})
            frontier = {
                deck.parent_id
                for deck in parent_decks
                if deck.parent_id is not None
            } - set(by_id)
        return sorted(
            by_id.values(),
            key=lambda deck: (
                deck.parent_id is not None,
                deck.position or 0,
                deck.created_at,
                deck.id,
            ),
        )

    owned_root_ids = {
        int(deck_id)
        for (deck_id,) in (
            db.session.query(Deck.id)
            .filter(
                Deck.owner_user_id == user_id,
                Deck.deleted_at.is_(None),
            )
            .all()
        )
        if deck_id is not None
    }
    installs = DeckInstall.query.filter_by(user_id=user_id).all()
    installed_root_ids = {
        int(inst.local_deck_id)
        for inst in installs
        if inst.local_deck_id
    }
    root_ids = installed_root_ids | owned_root_ids
    if not root_ids:
        return []

    # BFS downward – collect children
    visible_ids: set[int] = set()
    frontier: set[int] = set(root_ids)
    while frontier:
        current_ids = {deck_id for deck_id in frontier if deck_id not in visible_ids}
        if not current_ids:
            break
        visible_ids.update(current_ids)
        child_rows = (
            db.session.query(Deck.id)
            .filter(
                Deck.parent_id.in_(current_ids),
                Deck.deleted_at.is_(None),
            )
            .all()
        )
        frontier = {int(row[0]) for row in child_rows if row and row[0] is not None}

    # Walk upward – ensure ancestor folders are included
    ancestor_frontier = set(visible_ids)
    while ancestor_frontier:
        parent_rows = (
            db.session.query(Deck.parent_id)
            .filter(
                Deck.id.in_(ancestor_frontier),
                Deck.parent_id.isnot(None),
                Deck.deleted_at.is_(None),
            )
            .all()
        )
        parent_ids = {int(row[0]) for row in parent_rows if row and row[0] is not None}
        next_parents = parent_ids - visible_ids
        if not next_parents:
            break
        visible_ids.update(next_parents)
        ancestor_frontier = next_parents

    return (
        Deck.query.filter(
            Deck.id.in_(visible_ids),
            Deck.deleted_at.is_(None),
        )
        .order_by(
            Deck.parent_id.isnot(None),
            Deck.position,
            Deck.created_at,
            Deck.id,
        )
        .all()
    )


def query_accessible_stats_decks(*, user_id: int, admin_mode: bool) -> list[Deck]:
    query = Deck.query.filter(Deck.deleted_at.is_(None))
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
    if not visible_ids:
        return []
    return (
        Deck.query.filter(Deck.deleted_at.is_(None), Deck.id.in_(visible_ids))
        .order_by(
            Deck.parent_id.isnot(None),
            Deck.position,
            Deck.created_at,
            Deck.id,
        )
        .all()
    )


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
