"""Deck model controllers for stats-related deck visibility and hierarchy."""

from __future__ import annotations

from models import db
from models.flashcard import DeckInstall, Note
from models.deck import Deck
from models.study_progress_subject import StudyProgressSubject
from sqlalchemy import or_
from sqlalchemy.orm import defer


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
            Deck.query.options(defer(Deck.description))
            .filter(
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
                Deck.query.options(defer(Deck.description))
                .filter(
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

    owned_decks = (
        Deck.query.options(defer(Deck.description))
        .filter(
            Deck.owner_user_id == user_id,
            Deck.deleted_at.is_(None),
        )
        .all()
    )
    by_id: dict[int, Deck] = {int(deck.id): deck for deck in owned_decks}
    already_owned = set(by_id)

    installed_root_ids = {
        int(deck_id)
        for (deck_id,) in (
            db.session.query(DeckInstall.local_deck_id)
            .filter(
                DeckInstall.user_id == user_id,
                DeckInstall.local_deck_id.isnot(None),
            )
            .distinct()
            .all()
        )
        if deck_id is not None
    }
    if not by_id and not installed_root_ids:
        return []

    missing_roots = installed_root_ids - set(by_id)
    if missing_roots:
        for deck in (
            Deck.query.options(defer(Deck.description))
            .filter(
                Deck.id.in_(missing_roots),
                Deck.deleted_at.is_(None),
            )
            .all()
        ):
            by_id[int(deck.id)] = deck

    # BFS downward for installed roots – collect any non-owned children
    expanded: set[int] = set()
    frontier: set[int] = set(installed_root_ids)
    while frontier:
        expanded |= frontier
        child_ids: set[int] = set()
        for deck in (
            Deck.query.options(defer(Deck.description))
            .filter(
                Deck.parent_id.in_(frontier),
                Deck.deleted_at.is_(None),
            )
            .all()
        ):
            deck_id = int(deck.id)
            by_id[deck_id] = deck
            child_ids.add(deck_id)
        frontier = child_ids - already_owned - expanded

    # Walk upward – ensure ancestor folders not already loaded are included
    ancestor_frontier = {
        int(deck.parent_id)
        for deck in by_id.values()
        if deck.parent_id is not None and int(deck.parent_id) not in by_id
    }
    checked_missing: set[int] = set()
    while ancestor_frontier:
        checked_missing |= ancestor_frontier
        parent_decks = (
            Deck.query.options(defer(Deck.description))
            .filter(
                Deck.id.in_(ancestor_frontier),
                Deck.deleted_at.is_(None),
            )
            .all()
        )
        if not parent_decks:
            break
        for deck in parent_decks:
            by_id[int(deck.id)] = deck
        ancestor_frontier = {
            int(deck.parent_id)
            for deck in parent_decks
            if deck.parent_id is not None
            and int(deck.parent_id) not in by_id
            and int(deck.parent_id) not in checked_missing
        }

    return sorted(
        by_id.values(),
        key=lambda deck: (
            deck.parent_id is not None,
            deck.position or 0,
            deck.created_at,
            deck.id,
        ),
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
        .select_from(StudyProgressSubject)
        .join(Note, Note.id == StudyProgressSubject.live_note_id)
        .filter(
            StudyProgressSubject.learner_user_id == user_id,
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
