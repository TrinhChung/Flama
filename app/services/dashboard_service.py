import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Tuple

UTC = timezone.utc

from flask import url_for
from sqlalchemy import or_

from models import db
from models.flashcard import Card, DeckCloneDeckMap, DeckInstall, Note
from models.deck import Deck
from models.card_progress import CardProgress
from app.repositories.study_repository import counter_bucket_for_progress_values
from app.services.stats_overview import get_effective_timezone_name
from app.utils.deck_move_token import create_deck_move_token
from app.utils.permissions import is_admin_user


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class DeckNode:
    deck_id: int
    parent_id: int | None
    move_alias: str
    move_token: str
    parent_move_alias: str | None
    parent_move_token: str | None
    label: str
    href: str
    depth: int
    new_count: int
    learn_count: int
    due_count: int
    children: List["DeckNode"] = field(default_factory=list)


def build_dashboard_data(current_user) -> Tuple[List[DeckNode], int, int, int, bool]:
    admin_mode = is_admin_user(current_user)
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))

    if admin_mode:
        decks = (
            Deck.query.filter(
                Deck.deleted_at.is_(None),
                or_(
                    Deck.owner_user_id == current_user.id,
                    Deck.owner_user_id.is_(None),
                )
            )
            .order_by(
                Deck.parent_id.isnot(None),
                Deck.position,
                Deck.created_at,
                Deck.id,
            )
            .all()
        )
    else:
        owned_root_ids = {
            int(deck_id)
            for (deck_id,) in (
                db.session.query(Deck.id)
                .filter(
                    Deck.owner_user_id == current_user.id,
                    Deck.deleted_at.is_(None),
                )
                .all()
            )
            if deck_id is not None
        }
        installs = DeckInstall.query.filter_by(user_id=current_user.id).all()
        installed_root_ids = {inst.local_deck_id for inst in installs if inst.local_deck_id}
        root_ids = {int(deck_id) for deck_id in installed_root_ids if deck_id is not None} | owned_root_ids
        if root_ids:
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

            decks = (
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
        else:
            decks = []

    now = _utcnow()

    visible_deck_ids = [deck.id for deck in decks if deck.id is not None]
    card_counts_by_deck: Dict[int, Dict[str, int]] = {
        int(deck_id): {"total": 0, "new": 0, "learn": 0, "due": 0}
        for deck_id in visible_deck_ids
    }
    if visible_deck_ids:
        progress_join = db.and_(
            CardProgress.card_id == Card.id,
            CardProgress.user_id == current_user.id,
        )
        state_rows = (
            db.session.query(
                Note.deck_id,
                CardProgress.queue,
                CardProgress.due_at,
                CardProgress.due_day,
                CardProgress.is_suspended,
            )
            .select_from(Card)
            .join(Note, Card.note_id == Note.id)
            .outerjoin(CardProgress, progress_join)
            .filter(
                Note.user_id == current_user.id,
                Note.deck_id.in_(visible_deck_ids),
            )
            .all()
        )
        for deck_id, progress_queue, progress_due_at, progress_due_day, progress_is_suspended in state_rows:
            if not deck_id:
                continue
            bucket = card_counts_by_deck.setdefault(
                int(deck_id), {"total": 0, "new": 0, "learn": 0, "due": 0}
            )
            bucket["total"] += 1

            count_bucket = counter_bucket_for_progress_values(
                queue=progress_queue,
                due_at=progress_due_at,
                due_day=progress_due_day,
                is_suspended=progress_is_suspended,
                now=now,
                timezone_name=timezone_name,
            )
            if count_bucket == "new":
                bucket["new"] += 1
            elif count_bucket == "learning":
                bucket["learn"] += 1
            elif count_bucket == "review":
                bucket["due"] += 1

        if not admin_mode:
            logical_installs = [
                install
                for install in installs
                if install.clone_mode == "logical_overlay" and install.id and install.local_deck_id
            ]
            for install in logical_installs:
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
                    and int(row.local_deck_id) in card_counts_by_deck
                }
                if not source_to_local:
                    continue

                clone_query = (
                    db.session.query(
                        Note.deck_id,
                        CardProgress.queue,
                        CardProgress.due_at,
                        CardProgress.due_day,
                        CardProgress.is_suspended,
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

                for (
                    source_deck_id,
                    progress_queue,
                    progress_due_at,
                    progress_due_day,
                    progress_is_suspended,
                ) in clone_query.all():
                    if source_deck_id is None:
                        continue
                    local_deck_id = source_to_local.get(int(source_deck_id))
                    if local_deck_id is None:
                        continue
                    bucket = card_counts_by_deck.setdefault(
                        int(local_deck_id), {"total": 0, "new": 0, "learn": 0, "due": 0}
                    )
                    bucket["total"] += 1

                    count_bucket = counter_bucket_for_progress_values(
                        queue=progress_queue,
                        due_at=progress_due_at,
                        due_day=progress_due_day,
                        is_suspended=progress_is_suspended,
                        now=now,
                        timezone_name=timezone_name,
                    )
                    if count_bucket == "new":
                        bucket["new"] += 1
                    elif count_bucket == "learning":
                        bucket["learn"] += 1
                    elif count_bucket == "review":
                        bucket["due"] += 1
    
    by_parent: Dict[int, List[Deck]] = {}
    for deck in decks:
        # parent_id might be None, safely use a dict
        pid = deck.parent_id or 0
        by_parent.setdefault(pid, []).append(deck)

    for children in by_parent.values():
        children.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    move_alias_by_deck_id: Dict[int, str] = {}
    move_token_by_deck_id: Dict[int, str] = {}
    used_move_aliases: set[str] = set()
    for deck in decks:
        move_token = create_deck_move_token(deck.id, current_user.id)
        digest = hashlib.sha256(move_token.encode("utf-8")).hexdigest().upper()
        alias_len = 10
        move_alias = f"MID-{digest[:alias_len]}"
        while move_alias in used_move_aliases and alias_len < len(digest):
            alias_len += 2
            move_alias = f"MID-{digest[:alias_len]}"
        if move_alias in used_move_aliases:
            move_alias = f"MID-{digest}"

        used_move_aliases.add(move_alias)
        move_alias_by_deck_id[deck.id] = move_alias
        move_token_by_deck_id[deck.id] = move_token

    subtree_card_counts_cache: Dict[int, Dict[str, int]] = {}

    def _collect_subtree_card_counts(deck_id: int) -> Dict[str, int]:
        cached = subtree_card_counts_cache.get(deck_id)
        if cached is not None:
            return cached

        base = card_counts_by_deck.get(
            deck_id, {"total": 0, "new": 0, "learn": 0, "due": 0}
        )
        collected = {
            "total": int(base["total"]),
            "new": int(base["new"]),
            "learn": int(base["learn"]),
            "due": int(base["due"]),
        }
        for child in by_parent.get(deck_id, []):
            child_counts = _collect_subtree_card_counts(child.id)
            collected["total"] += int(child_counts["total"])
            collected["new"] += int(child_counts["new"])
            collected["learn"] += int(child_counts["learn"])
            collected["due"] += int(child_counts["due"])

        subtree_card_counts_cache[deck_id] = collected
        return collected

    def _build_nodes(parent_id_val: int, depth: int) -> List[DeckNode]:
        nodes: List[DeckNode] = []
        for deck in by_parent.get(parent_id_val, []):
            card_counts = _collect_subtree_card_counts(deck.id)
            deck_new = int(card_counts["new"])
            deck_learn = int(card_counts["learn"])
            deck_due = int(card_counts["due"])
            nodes.append(
                DeckNode(
                    deck_id=deck.id,
                    parent_id=deck.parent_id,
                    move_alias=move_alias_by_deck_id.get(deck.id, ""),
                    move_token=move_token_by_deck_id.get(deck.id, ""),
                    parent_move_alias=move_alias_by_deck_id.get(deck.parent_id) if deck.parent_id else None,
                    parent_move_token=move_token_by_deck_id.get(deck.parent_id) if deck.parent_id else None,
                    label=deck.name,
                    href=url_for("vocabulary.study_deck", deck_id=deck.id),
                    depth=depth,
                    new_count=deck_new,
                    learn_count=deck_learn,
                    due_count=deck_due,
                    children=_build_nodes(deck.id, depth + 1),
                )
            )
        return nodes

    rows = _build_nodes(0, 0)

    total_new = 0
    total_learn = 0
    total_due = 0
    for row in rows:
        total_new += row.new_count
        total_learn += row.learn_count
        total_due += row.due_count

    return rows, total_new, total_learn, total_due, admin_mode
