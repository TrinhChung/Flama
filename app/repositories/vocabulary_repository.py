"""Vocabulary domain controllers shared by browse/study routes."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import selectinload

from app.repositories.deck_tree_query import collect_ancestor_ids
from app.repositories.study_repository import (
    LEARNING_QUEUE,
    LEARN_QUEUE,
    NEW_QUEUE,
    RELEARNING_QUEUE,
    REVIEW_QUEUE,
    is_due as _is_due,
    normalize_progress_queue as _normalize_progress_queue,
)
from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import Card, DeckCloneDeckMap, DeckInstall, Note


def next_deck_position(parent_deck_id: int | None) -> int:
    query = db.session.query(db.func.max(Deck.position))
    if parent_deck_id is None:
        max_pos = query.filter(Deck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(Deck.parent_id == parent_deck_id).scalar()
    return int(max_pos or 0) + 1


def deck_name_exists_under_parent(
    *,
    parent_id: int | None,
    name: str,
    exclude_deck_id: int | None = None,
) -> bool:
    normalized_name = (name or "").strip().lower()
    if not normalized_name:
        return False

    query = Deck.query.filter(db.func.lower(Deck.name) == normalized_name)
    if parent_id is None:
        query = query.filter(Deck.parent_id.is_(None))
    else:
        query = query.filter(Deck.parent_id == parent_id)
    if exclude_deck_id is not None:
        query = query.filter(Deck.id != exclude_deck_id)
    return query.first() is not None





def collect_accessible_browse_decks(*, user_id: int, admin_mode: bool) -> list[Deck]:
    all_decks = Deck.query.order_by(
        Deck.parent_id.isnot(None),
        Deck.position,
        Deck.created_at,
        Deck.id,
    ).all()
    if admin_mode:
        return all_decks

    deck_map = {deck.id: deck for deck in all_decks}
    visible_ids: set[int] = set()

    deck_rows = (
        db.session.query(Note.deck_id)
        .filter(Note.user_id == user_id, Note.deck_id.isnot(None))
        .distinct()
        .all()
    )
    visible_ids.update(int(row[0]) for row in deck_rows if row and row[0] is not None)

    install_root_rows = (
        db.session.query(DeckInstall.local_deck_id)
        .filter(
            DeckInstall.user_id == user_id,
            DeckInstall.local_deck_id.isnot(None),
        )
        .distinct()
        .all()
    )
    install_root_ids = {int(row[0]) for row in install_root_rows if row and row[0] is not None}
    if install_root_ids:
        frontier: set[int] = set(install_root_ids)
        while frontier:
            current = {deck_id for deck_id in frontier if deck_id not in visible_ids}
            if not current:
                break
            visible_ids.update(current)
            child_rows = (
                db.session.query(Deck.id)
                .filter(Deck.parent_id.in_(current))
                .all()
            )
            frontier = {int(row[0]) for row in child_rows if row and row[0] is not None}

    if not visible_ids:
        return []

    stack = list(visible_ids)
    while stack:
        current_id = stack.pop()
        deck_obj = deck_map.get(current_id)
        if not deck_obj or deck_obj.parent_id is None:
            continue
        if deck_obj.parent_id in visible_ids:
            continue
        visible_ids.add(deck_obj.parent_id)
        stack.append(deck_obj.parent_id)

    return [deck for deck in all_decks if deck.id in visible_ids]


def deck_children_map(deck_list: list[Deck]) -> dict[int | None, list[Deck]]:
    mapping: dict[int | None, list[Deck]] = {}
    for deck_obj in deck_list:
        mapping.setdefault(deck_obj.parent_id, []).append(deck_obj)
    for children in mapping.values():
        children.sort(
            key=lambda deck_obj: ((deck_obj.position or 0), deck_obj.created_at, deck_obj.id)
        )
    return mapping


def collect_subtree_ids(
    root_id: int,
    children_by_parent: dict[int | None, list[Deck]],
) -> list[int]:
    result: list[int] = []
    stack = [root_id]
    while stack:
        current_id = stack.pop()
        result.append(current_id)
        for child in children_by_parent.get(current_id, []):
            stack.append(child.id)
    return result


def build_browse_deck_tree_payload(*, user_id: int, admin_mode: bool) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    scoped_decks = collect_accessible_browse_decks(user_id=user_id, admin_mode=admin_mode)
    if not scoped_decks:
        return []

    scoped_ids = {deck.id for deck in scoped_decks}
    deck_lookup = {deck.id: deck for deck in scoped_decks}
    children_by_parent = deck_children_map(scoped_decks)

    direct_counts = {
        deck_id: {"total": 0, "new": 0, "learn": 0, "due": 0}
        for deck_id in scoped_ids
    }

    progress_join = db.and_(
        CardProgress.card_id == Card.id,
        CardProgress.user_id == user_id,
    )
    state_query = (
        db.session.query(
            Note.deck_id,
            CardProgress.queue,
            CardProgress.due_at,
        )
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .outerjoin(CardProgress, progress_join)
        .filter(Note.deck_id.in_(scoped_ids))
    )
    if not admin_mode:
        state_query = state_query.filter(Note.user_id == user_id)

    for deck_id, progress_queue, progress_due_at in state_query.all():
        if not deck_id:
            continue
        bucket = direct_counts.setdefault(
            int(deck_id), {"total": 0, "new": 0, "learn": 0, "due": 0}
        )
        bucket["total"] += 1

        queue_norm = _normalize_progress_queue(progress_queue)
        if queue_norm == NEW_QUEUE:
            bucket["new"] += 1
        elif queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE}:
            bucket["learn"] += 1
        elif queue_norm == REVIEW_QUEUE and (progress_due_at is None or progress_due_at <= now):
            bucket["due"] += 1

    if not admin_mode:
        logical_installs = (
            DeckInstall.query.filter(
                DeckInstall.user_id == user_id,
                DeckInstall.clone_mode == "logical_overlay",
                DeckInstall.local_deck_id.isnot(None),
            )
            .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
            .all()
        )
        for install in logical_installs:
            if install.id is None:
                continue
            map_rows = (
                DeckCloneDeckMap.query.filter_by(deck_install_id=install.id)
                .order_by(DeckCloneDeckMap.local_deck_id.asc(), DeckCloneDeckMap.source_deck_id.asc())
                .all()
            )
            source_to_local = {
                int(row.source_deck_id): int(row.local_deck_id)
                for row in map_rows
                if row.source_deck_id is not None
                and row.local_deck_id is not None
                and int(row.local_deck_id) in scoped_ids
            }
            if not source_to_local:
                continue

            clone_query = (
                db.session.query(
                    Note.deck_id,
                    CardProgress.queue,
                    CardProgress.due_at,
                )
                .select_from(Card)
                .join(Note, Card.note_id == Note.id)
                .outerjoin(CardProgress, progress_join)
                .filter(Note.deck_id.in_(source_to_local.keys()))
            )
            if install.source_owner_user_id is not None:
                clone_query = clone_query.filter(Note.user_id == install.source_owner_user_id)
            snapshot_at = install.base_snapshot_at or install.installed_at
            if snapshot_at is not None:
                clone_query = clone_query.filter(
                    Note.created_at <= snapshot_at,
                    Card.created_at <= snapshot_at,
                )

            for source_deck_id, progress_queue, progress_due_at in clone_query.all():
                if source_deck_id is None:
                    continue
                local_deck_id = source_to_local.get(int(source_deck_id))
                if local_deck_id is None:
                    continue
                bucket = direct_counts.setdefault(
                    int(local_deck_id),
                    {"total": 0, "new": 0, "learn": 0, "due": 0},
                )
                bucket["total"] += 1

                queue_norm = _normalize_progress_queue(progress_queue)
                if queue_norm == NEW_QUEUE:
                    bucket["new"] += 1
                elif queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE}:
                    bucket["learn"] += 1
                elif queue_norm == REVIEW_QUEUE and (progress_due_at is None or progress_due_at <= now):
                    bucket["due"] += 1

    def _build_node(deck_obj: Deck) -> dict[str, Any]:
        direct = direct_counts.get(deck_obj.id, {"total": 0, "new": 0, "learn": 0, "due": 0})
        counts = {
            "total": int(direct["total"]),
            "new": int(direct["new"]),
            "learn": int(direct["learn"]),
            "due": int(direct["due"]),
        }
        children_payload: list[dict[str, Any]] = []
        for child_obj in children_by_parent.get(deck_obj.id, []):
            child_payload = _build_node(child_obj)
            children_payload.append(child_payload)
            child_counts = child_payload["counts"]
            counts["total"] += int(child_counts["total"])
            counts["new"] += int(child_counts["new"])
            counts["learn"] += int(child_counts["learn"])
            counts["due"] += int(child_counts["due"])
        return {
            "id": deck_obj.id,
            "name": deck_obj.name,
            "parent_id": deck_obj.parent_id,
            "counts": counts,
            "children": children_payload,
        }

    roots = [
        deck_obj
        for deck_obj in scoped_decks
        if deck_obj.parent_id is None or deck_obj.parent_id not in deck_lookup
    ]
    roots.sort(key=lambda deck_obj: ((deck_obj.position or 0), deck_obj.created_at, deck_obj.id))
    return [_build_node(root_obj) for root_obj in roots]


def can_user_delete_cloned_deck(*, deck_obj: Deck, user_id: int) -> bool:
    if deck_obj.owner_user_id != user_id:
        return False

    ancestor_ids = collect_ancestor_ids(deck_obj.id)
    if not ancestor_ids:
        return False

    install_row = (
        db.session.query(DeckInstall.id)
        .filter(
            DeckInstall.user_id == user_id,
            DeckInstall.local_deck_id.in_(ancestor_ids),
        )
        .first()
    )
    return install_row is not None





def query_study_cards_for_deck_ids(*, user_id: int, deck_ids: list[int]) -> list[Card]:
    if not deck_ids:
        return []

    direct_cards = (
        Card.query.join(Note, Card.note_id == Note.id)
        .options(
            selectinload(Card.template),
            selectinload(Card.note).selectinload(Note.note_type),
            selectinload(Card.note).selectinload(Note.media_assets),
        )
        .filter(
            Note.user_id == user_id,
            Note.deck_id.in_(deck_ids),
        )
        .order_by(Card.created_at.asc(), Card.id.asc())
        .all()
    )
    seen_card_ids = {card_obj.id for card_obj in direct_cards}
    merged_cards = list(direct_cards)

    from app.services import flashcards_share

    seen_scope_keys: set[tuple[str, int]] = set()
    for local_deck_id in sorted({int(deck_id) for deck_id in deck_ids if deck_id is not None}):
        clone_scope = flashcards_share.resolve_clone_scope_for_local_deck(
            user_id=user_id,
            local_deck_id=local_deck_id,
        )
        if clone_scope is None:
            continue
        scope_key = (clone_scope.install.id, int(clone_scope.local_scope_deck_id))
        if scope_key in seen_scope_keys:
            continue
        seen_scope_keys.add(scope_key)

        clone_cards = (
            flashcards_share.query_clone_scope_cards(clone_scope)
            .options(
                selectinload(Card.template),
                selectinload(Card.note).selectinload(Note.note_type),
                selectinload(Card.note).selectinload(Note.media_assets),
            )
            .order_by(Card.created_at.asc(), Card.id.asc())
            .all()
        )
        for card_obj in clone_cards:
            if card_obj.id in seen_card_ids:
                continue
            seen_card_ids.add(card_obj.id)
            merged_cards.append(card_obj)

    merged_cards.sort(key=lambda card_obj: (card_obj.created_at or datetime.min, card_obj.id))
    return merged_cards


def count_due_note_cards(
    cards: list[Card],
    progress_map: dict[str, CardProgress],
    *,
    now: datetime,
) -> tuple[int, int, int]:
    due_new = 0
    due_learn = 0
    due_review = 0
    for card_obj in cards:
        progress = progress_map.get(card_obj.id)
        queue = _normalize_progress_queue(progress.queue) if progress else NEW_QUEUE
        if queue in {LEARNING_QUEUE, RELEARNING_QUEUE}:
            due_learn += 1
        elif queue == REVIEW_QUEUE and _is_due(progress, now):
            due_review += 1
        elif _is_due(progress, now):
            due_new += 1
    return due_new, due_learn, due_review
