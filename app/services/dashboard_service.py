import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple

UTC = timezone.utc

from flask import url_for


from models import db
from models.flashcard import Card, DeckCloneDeckMap, DeckInstall, Note
from models.deck import Deck
from models.card_progress import CardProgress
from app.repositories import study_repository
from app.repositories.study_authority_repository import lock_study_authority_route
from app.repositories.study_repository import default_deck_options, _today_day_index
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_authority_read_service import load_study_authority_card_reads
from app.services.stats_overview import get_effective_timezone_name, _build_timezone_obj
from app.utils.deck_move_token import create_deck_move_token
from app.utils.permissions import is_admin_user


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _note_overlay_cards(
    installs, *, visible_deck_ids: set[int]
) -> tuple[list[tuple[Card, int]], Dict[int, str]]:
    """Source Cards of each logical-overlay install, mapped to local decks.

    Mirrors the LEGACY dashboard merge filters: mapped source decks, source
    owner and install snapshot. Also returns the install NoteType per mapped
    local deck, which LEGACY records even when no source Card is visible.
    """
    result: list[tuple[Card, int]] = []
    note_type_by_local_deck: Dict[int, str] = {}
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
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Note.deck_id.in_(source_to_local.keys())
        )
        if install.source_owner_user_id is not None:
            query = query.filter(Note.user_id == install.source_owner_user_id)
        snapshot_at = install.base_snapshot_at or install.installed_at
        if snapshot_at is not None:
            query = query.filter(Note.created_at <= snapshot_at, Card.created_at <= snapshot_at)
        for card in query.order_by(Card.id.asc()).all():
            local_deck_id = source_to_local.get(int(card.note.deck_id))
            if local_deck_id is not None:
                result.append((card, local_deck_id))
    return result, note_type_by_local_deck


def _classify_progress_fast(
    progress_queue: str | None,
    progress_due_at: datetime | None,
    progress_due_day: int | None,
    progress_is_suspended: bool | None,
    today_day_index: int,
    timezone_obj,
    boundary_hour: int,
) -> str | None:
    if progress_is_suspended:
        return None
    queue = (progress_queue or "new").strip().lower()
    if queue == "new":
        return "new"
    if queue in ("learn", "learning", "relearning"):
        return "learning"
    if queue == "review":
        if progress_due_day is not None:
            r_due_day = int(progress_due_day)
        elif progress_due_at is not None:
            utc_moment = progress_due_at if progress_due_at.tzinfo else progress_due_at.replace(tzinfo=UTC)
            local_moment = utc_moment.astimezone(timezone_obj).replace(tzinfo=None)
            r_due_day = (local_moment - timedelta(hours=boundary_hour)).date().toordinal()
        else:
            r_due_day = today_day_index
        if r_due_day <= today_day_index:
            return "review"
        return None
    return "new"


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
    note_type_id: str | None = None
    children: List["DeckNode"] = field(default_factory=list)


def build_dashboard_data(current_user) -> Tuple[List[DeckNode], int, int, int, bool]:
    admin_mode = is_admin_user(current_user)
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))
    timezone_obj = _build_timezone_obj(timezone_name)
    boundary_hour = int(default_deck_options().dayBoundaryHourLocal)
    now = _utcnow()
    authority_route = lock_study_authority_route(
        db.session,
        learner_user_id=int(current_user.id),
        allow_note_authority=True,
    )
    today_day_index = _today_day_index(
        now=now,
        timezone_name=timezone_name,
        day_boundary_hour_local=boundary_hour,
    )

    from app.repositories.deck_tree_query import collect_accessible_decks
    decks = collect_accessible_decks(user_id=current_user.id, admin_mode=admin_mode)

    # Needed below for logical_overlay clone card-count merging
    if not admin_mode or authority_route.mode_code == "NOTE":
        installs = DeckInstall.query.filter_by(user_id=current_user.id).all()
    else:
        installs = []

    visible_deck_ids = [deck.id for deck in decks if deck.id is not None]
    deck_note_types: Dict[int, str] = {}
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
                Note.note_type_id,
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
        for (
            deck_id,
            note_type_id,
            progress_queue,
            progress_due_at,
            progress_due_day,
            progress_is_suspended,
        ) in state_rows:
            if not deck_id:
                continue
            if note_type_id and int(deck_id) not in deck_note_types:
                deck_note_types[int(deck_id)] = str(note_type_id)
            bucket = card_counts_by_deck.setdefault(
                int(deck_id), {"total": 0, "new": 0, "learn": 0, "due": 0}
            )
            bucket["total"] += 1

            count_bucket = _classify_progress_fast(
                progress_queue=progress_queue,
                progress_due_at=progress_due_at,
                progress_due_day=progress_due_day,
                progress_is_suspended=progress_is_suspended,
                today_day_index=today_day_index,
                timezone_obj=timezone_obj,
                boundary_hour=boundary_hour,
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

                if install.source_note_type_id:
                    for local_deck_id in source_to_local.values():
                        deck_note_types.setdefault(int(local_deck_id), str(install.source_note_type_id))

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

                    count_bucket = _classify_progress_fast(
                        progress_queue=progress_queue,
                        progress_due_at=progress_due_at,
                        progress_due_day=progress_due_day,
                        progress_is_suspended=progress_is_suspended,
                        today_day_index=today_day_index,
                        timezone_obj=timezone_obj,
                        boundary_hour=boundary_hour,
                    )
                    if count_bucket == "new":
                        bucket["new"] += 1
                    elif count_bucket == "learning":
                        bucket["learn"] += 1
                    elif count_bucket == "review":
                        bucket["due"] += 1

    if authority_route.mode_code == "NOTE" and visible_deck_ids:
        canonical_cards = (
            Card.query.join(Note, Card.note_id == Note.id)
            .filter(
                Note.user_id == current_user.id,
                Note.deck_id.in_(visible_deck_ids),
            )
            .order_by(Card.id.asc())
            .all()
        )
        # Same logical-overlay scope as the LEGACY merge above: source Cards
        # count under the learner's mapped local deck.
        overlay_cards, overlay_note_types = (
            ([], {})
            if admin_mode
            else _note_overlay_cards(installs, visible_deck_ids=set(visible_deck_ids))
        )
        counted_cards = [
            (card, int(card.note.deck_id)) for card in canonical_cards
        ] + overlay_cards
        options_by_deck_id: Dict[int, Any] = {}
        deck_options_by_card_id = {}
        for card, deck_id in counted_cards:
            if deck_id not in options_by_deck_id:
                options_by_deck_id[deck_id] = resolve_deck_options(
                    user_id=int(current_user.id),
                    deck_id=deck_id,
                )
            deck_options_by_card_id.setdefault(str(card.id), options_by_deck_id[deck_id])
        authority_reads = load_study_authority_card_reads(
            db.session,
            learner_user_id=int(current_user.id),
            cards=tuple({str(card.id): card for card, _ in counted_cards}.values()),
            now_utc=now,
            timezone_name=timezone_name,
            deck_options_by_card_id=deck_options_by_card_id,
        )
        card_counts_by_deck = {
            int(deck_id): {"total": 0, "new": 0, "learn": 0, "due": 0}
            for deck_id in visible_deck_ids
        }
        deck_note_types = {}
        for card in canonical_cards:
            note = card.note
            if note.note_type_id and int(note.deck_id) not in deck_note_types:
                deck_note_types[int(note.deck_id)] = str(note.note_type_id)
        for local_deck_id, source_note_type_id in overlay_note_types.items():
            deck_note_types.setdefault(local_deck_id, source_note_type_id)
        for card, deck_id in counted_cards:
            bucket = card_counts_by_deck.setdefault(
                deck_id, {"total": 0, "new": 0, "learn": 0, "due": 0}
            )
            bucket["total"] += 1
            availability = authority_reads[str(card.id)].availability
            count_bucket = study_repository.counter_bucket_for_progress_values(
                queue=availability.normalized_queue,
                due_at=availability.due_at,
                due_day=availability.due_day,
                is_suspended=availability.is_suspended,
                is_buried=availability.is_buried,
                buried_until_day=availability.buried_until_day,
                now=now,
                timezone_name=timezone_name,
                day_boundary_hour_local=boundary_hour,
            )
            if count_bucket == study_repository.NEW_QUEUE:
                bucket["new"] += 1
            elif count_bucket == study_repository.LEARNING_QUEUE:
                bucket["learn"] += 1
            elif count_bucket == study_repository.REVIEW_QUEUE:
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
            deck_nt_id = (
                str(deck.note_type_id)
                if deck.note_type_id
                else deck_note_types.get(deck.id)
            )
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
                    note_type_id=deck_nt_id,
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
