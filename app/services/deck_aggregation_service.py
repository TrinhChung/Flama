"""Single-query deck counts from current Note availability.

Counts use consolidated subjects and fail closed on divergent evidence.
Buckets match ``study_repository.counter_bucket_for_progress_values``.
Queries take no locks and can run in ``analytics_read_transaction()``.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, Tuple

from sqlalchemy import and_, case, func, not_, or_, select
from sqlalchemy.orm import Session

from app.repositories import note_analytics_read_repository as note_reads
from models.card import Card
from models.flashcard import DeckCloneDeckMap, DeckInstall, Note

_LEARNING_QUEUES = ("learn", "learning", "relearning")


def _deck_note_types(
    session: Session,
    *,
    learner_user_id: int,
    visible_deck_ids: list[int],
    overlay_types: list[tuple[int, str]],
) -> Dict[int, str]:
    """Owned Notes first (oldest Note type per deck), then install note types."""

    if not visible_deck_ids:
        return {}
    rows = session.execute(
        select(Note.deck_id, Note.note_type_id, func.min(Note.created_at))
        .where(
            Note.user_id == learner_user_id,
            Note.deck_id.in_(visible_deck_ids),
            Note.note_type_id.isnot(None),
        )
        .group_by(Note.deck_id, Note.note_type_id)
    ).all()
    note_types: Dict[int, str] = {}
    # MIN(created_at) is a datetime on MySQL but ISO text on SQLite; both sort as text.
    for deck_id, note_type_id, _first_at in sorted(
        rows, key=lambda row: (int(row[0]), str(row[2] or ""), str(row[1]))
    ):
        note_types.setdefault(int(deck_id), str(note_type_id))
    requested_decks = set(visible_deck_ids)
    for deck_id, note_type_id in overlay_types:
        if deck_id in requested_decks:
            note_types.setdefault(deck_id, note_type_id)
    return note_types


def _overlay_scope(
    session: Session,
    *,
    learner_user_id: int,
    visible_deck_ids: list[int],
):
    """Logical-overlay source Cards under the learner's mapped local decks."""

    installs = session.execute(
        select(DeckInstall.id, DeckInstall.source_note_type_id)
        .where(
            DeckInstall.user_id == learner_user_id,
            DeckInstall.clone_mode == "logical_overlay",
            DeckInstall.local_deck_id.isnot(None),
        )
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
    ).all()
    if not installs:
        return None, []
    visible = set(visible_deck_ids)
    local_decks_by_install = defaultdict(list)
    has_mapped_source = False
    for install_id, local_deck_id, source_deck_id in session.execute(
        select(
            DeckCloneDeckMap.deck_install_id,
            DeckCloneDeckMap.local_deck_id,
            DeckCloneDeckMap.source_deck_id,
        )
        .where(DeckCloneDeckMap.deck_install_id.in_([str(row[0]) for row in installs]))
        .order_by(DeckCloneDeckMap.local_deck_id.asc(), DeckCloneDeckMap.source_deck_id.asc())
    ).all():
        if local_deck_id is None or int(local_deck_id) not in visible:
            continue
        local_decks_by_install[str(install_id)].append(int(local_deck_id))
        has_mapped_source = has_mapped_source or source_deck_id is not None
    overlay_types = [
        (local_deck_id, str(note_type_id))
        for install_id, note_type_id in installs
        if note_type_id
        for local_deck_id in local_decks_by_install[str(install_id)]
    ]
    if not has_mapped_source:
        return None, overlay_types
    from app.repositories.flashcards_share_repository import clone_source_card_visibility
    overlay = (
        select(
            DeckCloneDeckMap.local_deck_id.label("deck_id"),
            Card.id.label("card_id"),
            Card.note_id.label("note_id"),
        )
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .join(DeckCloneDeckMap, DeckCloneDeckMap.source_deck_id == Note.deck_id)
        .join(DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id)
        .where(
            DeckInstall.user_id == learner_user_id,
            DeckInstall.clone_mode == "logical_overlay",
            DeckCloneDeckMap.local_deck_id.in_(visible_deck_ids),
            or_(
                DeckInstall.source_owner_user_id.is_(None),
                Note.user_id == DeckInstall.source_owner_user_id,
            ),
            clone_source_card_visibility(DeckInstall),
        )
    )
    return overlay, overlay_types


def deck_note_type_metadata(session, *, learner_user_id, deck_ids, admin_mode=False):
    """Read fallback presentation metadata independently of cached counters."""
    if not deck_ids:
        return {}
    overlay_types = [] if admin_mode else _overlay_scope(
        session, learner_user_id=learner_user_id, visible_deck_ids=deck_ids,
    )[1]
    return _deck_note_types(session, learner_user_id=learner_user_id,
                            visible_deck_ids=deck_ids, overlay_types=overlay_types)


def aggregate_deck_study_counts(
    session: Session,
    *,
    learner_user_id: int,
    visible_deck_ids: list[int],
    today_day_index: int,
    day_cutoff_utc: datetime,
    admin_mode: bool = False,
    count_by_note: bool = False,
    owned_by_any_user: bool = False,
    include_note_types: bool = False,
) -> Tuple[Dict[int, Dict[str, int]], Dict[int, str]]:
    """Count total/new/learn/due per visible deck (subtrees are summed by the caller).

    ``day_cutoff_utc`` is the start of the learner's next study day (naive UTC):
    a review with only ``due_at`` is due today exactly when it is before it.
    ``count_by_note`` (Phase 6 D6-04) counts each Note once:
    all its Cards share one state, so a Note with two Templates is one due item.
    ``owned_by_any_user`` (admin-wide Browse) counts every Note in the visible
    decks with the learner's own state, not only the learner's Notes.
    Fallback note-type metadata is opt-in (``include_note_types=True``); no
    production caller needs it, and one deck's alone is ``deck_note_type_metadata``.
    Raises ``StudyAuthorityReadError`` when a NOTE learner's evidence diverges.
    """

    if not visible_deck_ids:
        return {}, {}

    # Admins see every deck but, as before, never count logical-overlay sources.
    overlay, overlay_types = (
        (None, [])
        if admin_mode
        else _overlay_scope(
            session,
            learner_user_id=learner_user_id,
            visible_deck_ids=visible_deck_ids,
        )
    )
    from app.repositories.note_analytics_scope_repository import deck_note_scope

    # Raises StudyAuthorityReadError for unreadable evidence in this scope.
    # Note units weigh each Note once, so the scope only proves membership.
    scope = deck_note_scope(
        session, learner_user_id=learner_user_id, deck_ids=visible_deck_ids,
        overlay=overlay, owned_by_any_user=owned_by_any_user, presence_only=count_by_note,
    )
    rows = note_reads.note_rows(scope, learner_user_id=learner_user_id).subquery("rows")

    # A Card without progress/state has NULL columns and reads as active NEW.
    is_active = and_(
        or_(rows.c.is_suspended.is_(None), rows.c.is_suspended.is_(False)),
        not_(and_(
            rows.c.is_buried.is_(True),
            or_(rows.c.buried_until_day.is_(None), rows.c.buried_until_day >= today_day_index),
        )),
    )
    queue = func.lower(func.trim(func.coalesce(rows.c.queue, "new")))
    is_learning = queue.in_(_LEARNING_QUEUES)
    is_review = queue == "review"
    is_new = and_(is_active, not_(is_learning), not_(is_review))
    is_learn = and_(is_active, is_learning)
    is_due = and_(
        is_active,
        is_review,
        or_(
            rows.c.due_day <= today_day_index,
            and_(
                rows.c.due_day.is_(None),
                or_(rows.c.due_at.is_(None), rows.c.due_at < day_cutoff_utc),
            ),
        ),
    )
    weight = 1 if count_by_note else rows.c.card_count
    aggregated = session.execute(
        select(
            rows.c.deck_id,
            func.sum(weight),
            func.sum(case((is_new, weight), else_=0)),
            func.sum(case((is_learn, weight), else_=0)),
            func.sum(case((is_due, weight), else_=0)),
        ).group_by(rows.c.deck_id).execution_options(include_retired_cards=True)
    ).all()

    counts: Dict[int, Dict[str, int]] = {
        int(deck_id): {"total": 0, "new": 0, "learn": 0, "due": 0}
        for deck_id in visible_deck_ids
    }
    for deck_id, total, new, learn, due in aggregated:
        if deck_id is not None and int(deck_id) in counts:
            counts[int(deck_id)] = {
                "total": int(total or 0),
                "new": int(new or 0),
                "learn": int(learn or 0),
                "due": int(due or 0),
            }
    note_types = _deck_note_types(
        session,
        learner_user_id=learner_user_id,
        visible_deck_ids=visible_deck_ids,
        overlay_types=overlay_types,
    ) if include_note_types else {}
    return counts, note_types
