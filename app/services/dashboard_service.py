import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Tuple

UTC = timezone.utc

from flask import current_app


from models import db
from models.deck import Deck
from app.repositories.study_authority_repository import read_study_authority_route
from app.repositories.study_repository import _today_day_index
from app.services.anki_scheduler import _day_index_to_datetime
from app.services.deck_aggregation_service import aggregate_deck_study_counts
from app.services.deck_count_snapshot_service import resolve_cached_owned_deck_counts
from app.services.scheduler_config_service import resolve_day_boundary_hour_local
from app.services.stats_overview import get_effective_timezone_name
from app.utils.permissions import is_admin_user


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class DeckNode:
    deck_id: int
    parent_id: int | None
    move_alias: str | None
    label: str
    depth: int
    new_count: int
    learn_count: int
    due_count: int
    note_type_id: str | None = None
    children: List["DeckNode"] = field(default_factory=list)


def build_dashboard_data(current_user) -> Tuple[List[DeckNode], bool]:
    admin_mode = is_admin_user(current_user)
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))
    # Same study-day boundary as the learner's Study queue counts.
    boundary_hour = resolve_day_boundary_hour_local(user_id=int(current_user.id))
    now = _utcnow()
    authority_route = read_study_authority_route(
        db.session,
        learner_user_id=int(current_user.id),
    )
    today_day_index = _today_day_index(
        now=now,
        timezone_name=timezone_name,
        day_boundary_hour_local=boundary_hour,
    )
    # A review with only due_at is due today iff it is before the next study day.
    day_cutoff_utc = _day_index_to_datetime(
        today_day_index + 1,
        boundary_hour,
        timezone_name=timezone_name,
    )

    from app.repositories.deck_tree_query import collect_accessible_decks
    decks = collect_accessible_decks(user_id=current_user.id, admin_mode=admin_mode)

    visible_deck_ids = [deck.id for deck in decks if deck.id is not None]
    count_by_note = bool(current_app.config.get("STUDY_NOTE_COUNT_ENABLED", False))
    cached_counts, dirty_ids = resolve_cached_owned_deck_counts(
        db.session, learner_user_id=int(current_user.id), visible_deck_ids=visible_deck_ids,
        today_day_index=today_day_index, day_cutoff_utc=day_cutoff_utc,
        timezone_name=timezone_name, day_boundary_hour_local=boundary_hour,
        is_note_mode=True, admin_mode=admin_mode,
        count_by_note=count_by_note, now_utc=now,
        authority_route=authority_route,
    )
    # Only the deck's own note type is sent; the derived fallback is read on
    # demand (GET /api/decks/<id>/note-type) when a sub-deck is created.
    card_counts_by_deck, _ = aggregate_deck_study_counts(
        db.session,
        learner_user_id=int(current_user.id),
        visible_deck_ids=dirty_ids,
        include_note_types=False,
        today_day_index=today_day_index,
        day_cutoff_utc=day_cutoff_utc,
        admin_mode=admin_mode,
        count_by_note=count_by_note,
    )
    card_counts_by_deck.update(cached_counts)

    by_parent: Dict[int, List[Deck]] = {}
    for deck in decks:
        # parent_id might be None, safely use a dict
        pid = deck.parent_id or 0
        by_parent.setdefault(pid, []).append(deck)

    for children in by_parent.values():
        children.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    # The admin row menu copies this display identifier; numeric PATCH IDs
    # still own authorization, so learners are sent none.
    move_alias_by_deck_id: Dict[int, str] = {}
    used_move_aliases: set[str] = set()
    alias_key = str(current_app.config.get("SECRET_KEY") or "").encode("utf-8")
    for deck in decks if admin_mode else ():
        digest = hmac.new(
            alias_key,
            f"deck-move-alias-v1:{current_user.id}:{deck.id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()
        alias_len = 10
        move_alias = f"MID-{digest[:alias_len]}"
        while move_alias in used_move_aliases and alias_len < len(digest):
            alias_len += 2
            move_alias = f"MID-{digest[:alias_len]}"
        if move_alias in used_move_aliases:
            move_alias = f"MID-{digest}"

        used_move_aliases.add(move_alias)
        move_alias_by_deck_id[deck.id] = move_alias

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
            deck_nt_id = str(deck.note_type_id) if deck.note_type_id else None
            nodes.append(
                DeckNode(
                    deck_id=deck.id,
                    parent_id=deck.parent_id,
                    move_alias=move_alias_by_deck_id.get(deck.id),
                    label=deck.name,
                    depth=depth,
                    new_count=deck_new,
                    learn_count=deck_learn,
                    due_count=deck_due,
                    note_type_id=deck_nt_id,
                    children=_build_nodes(deck.id, depth + 1),
                )
            )
        return nodes

    return _build_nodes(0, 0), admin_mode
