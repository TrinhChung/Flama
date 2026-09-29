"""Database-level aggregation seam for deck-level study counts.

Architecture & Decoupling Seam:
- Phase 5 (Current): Executes a single non-locking database-level aggregation query
  leveraging the indexed `card_progress` compatibility projection (ix_card_progress_user_queue_due_day).
  Unifies user-owned notes and Marketplace shared decks (Logical Overlay) mapped to local decks.
- Phase 6 (Decision D6-04): In NOTE mode (`is_note_mode=True`), counts New / Learn / Due
  at the NOTE level using `COUNT(DISTINCT note_id)` to avoid multi-template sibling inflation.
  In LEGACY mode (`is_note_mode=False`), counts at the CARD level using `COUNT(DISTINCT card_id)`.
- Phase 9 Readiness: This service provides an isolated seam. When `card_progress` is contracted
  and removed in Phase 9, this seam can be transitioned to native NOTE availability
  (`study_progress_availability` / `study_progress_subjects`) or rollup counters (`deck_counters`)
  without breaking dashboard or analytics callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

from sqlalchemy import and_, case, func, or_, select, union_all
from sqlalchemy.orm import Session

from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.flashcard import DeckCloneDeckMap, DeckInstall, Note
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_subject import StudyProgressSubject
from app.services.study_authority_read_service import StudyAuthorityReadError


@dataclass(frozen=True)
class DeckStudyCounts:
    total: int = 0
    new: int = 0
    learn: int = 0
    due: int = 0


def check_note_authority_integrity(session: Session, *, learner_user_id: int) -> None:
    """Fast non-locking check for Phase 5 NOTE authority token integrity.

    Verifies that all subjects for this learner have authority tokens without
    loading note entities or iterating in Python memory.
    """
    missing_token = session.execute(
        select(StudyProgressSubject.id)
        .outerjoin(
            StudyAuthoritySubjectToken,
            StudyAuthoritySubjectToken.subject_id == StudyProgressSubject.id,
        )
        .where(
            StudyProgressSubject.learner_user_id == learner_user_id,
            StudyAuthoritySubjectToken.subject_id.is_(None),
        )
        .limit(1)
    ).scalar_one_or_none()
    if missing_token is not None:
        raise StudyAuthorityReadError(
            "AUTHORITY_TOKEN_REQUIRED",
            "NOTE analytics requires an existing token.",
        )


def aggregate_deck_study_counts(
    session: Session,
    *,
    learner_user_id: int,
    visible_deck_ids: list[int],
    now_utc: datetime,
    today_day_index: int,
    is_note_mode: bool,
    admin_mode: bool = False,
    count_by_note: bool | None = None,
) -> Tuple[Dict[int, Dict[str, int]], Dict[int, str]]:
    """Aggregate New, Learn, Due counts per deck for the learner.

    Returns:
        (counts_by_deck, note_types_by_deck)
        where counts_by_deck maps int(deck_id) -> {"total": int, "new": int, "learn": int, "due": int}
        and note_types_by_deck maps int(deck_id) -> note_type_id_string
    """
    if not visible_deck_ids:
        return {}, {}

    if is_note_mode:
        check_note_authority_integrity(session, learner_user_id=learner_user_id)

    if count_by_note is not None:
        should_count_by_note = bool(count_by_note)
    else:
        try:
            from flask import current_app, has_app_context

            if has_app_context():
                should_count_by_note = is_note_mode and bool(
                    current_app.config.get("STUDY_NOTE_COUNT_ENABLED", False)
                )
            else:
                should_count_by_note = False
        except (ImportError, RuntimeError):
            should_count_by_note = False

    card_counts_by_deck: Dict[int, Dict[str, int]] = {
        int(deck_id): {"total": 0, "new": 0, "learn": 0, "due": 0}
        for deck_id in visible_deck_ids
    }
    deck_note_types: Dict[int, str] = {}

    # Query logical overlay installs for marketplace shared decks
    logical_installs: list[DeckInstall] = []
    install_ids: list[str] = []
    map_rows: list[DeckCloneDeckMap] = []
    source_to_local_all: dict[int, int] = {}

    if not admin_mode or is_note_mode:
        logical_installs = (
            session.execute(
                select(DeckInstall)
                .where(
                    DeckInstall.user_id == learner_user_id,
                    DeckInstall.clone_mode == "logical_overlay",
                    DeckInstall.local_deck_id.isnot(None),
                )
                .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
            )
            .scalars()
            .all()
        )
        if logical_installs:
            install_ids = [
                str(inst.id) for inst in logical_installs if inst.id is not None
            ]
            if install_ids:
                map_rows = (
                    session.execute(
                        select(DeckCloneDeckMap).where(
                            DeckCloneDeckMap.deck_install_id.in_(install_ids)
                        )
                    )
                    .scalars()
                    .all()
                )
                for inst in logical_installs:
                    if inst.source_note_type_id:
                        for m_row in map_rows:
                            if (
                                str(m_row.deck_install_id) == str(inst.id)
                                and m_row.local_deck_id is not None
                                and int(m_row.local_deck_id) in visible_deck_ids
                            ):
                                deck_note_types.setdefault(
                                    int(m_row.local_deck_id),
                                    str(inst.source_note_type_id),
                                )
                for m_row in map_rows:
                    if (
                        m_row.source_deck_id is not None
                        and m_row.local_deck_id is not None
                        and int(m_row.local_deck_id) in visible_deck_ids
                    ):
                        source_to_local_all[int(m_row.source_deck_id)] = int(
                            m_row.local_deck_id
                        )

    # Resolve note_type_id for owned decks if not yet set
    missing_deck_ids = [
        did for did in visible_deck_ids if did not in deck_note_types
    ]
    if missing_deck_ids:
        nt_rows = session.execute(
            select(Note.deck_id, Note.note_type_id)
            .where(
                Note.user_id == learner_user_id,
                Note.deck_id.in_(missing_deck_ids),
                Note.note_type_id.isnot(None),
            )
            .group_by(Note.deck_id, Note.note_type_id)
        ).all()
        for did, ntid in nt_rows:
            if did is not None and ntid:
                deck_note_types.setdefault(int(did), str(ntid))

    # Base select 1: Directly owned cards
    owned_select = (
        select(
            Note.deck_id.label("deck_id"),
            Card.id.label("card_id"),
            Card.note_id.label("note_id"),
            CardProgress.id.label("progress_id"),
            CardProgress.queue.label("queue"),
            CardProgress.due_day.label("due_day"),
            CardProgress.due_at.label("due_at"),
            CardProgress.is_suspended.label("is_suspended"),
            CardProgress.is_buried.label("is_buried"),
            CardProgress.buried_until_day.label("buried_until_day"),
        )
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .outerjoin(
            CardProgress,
            and_(
                CardProgress.card_id == Card.id,
                CardProgress.user_id == learner_user_id,
            ),
        )
        .where(
            Note.user_id == learner_user_id,
            Note.deck_id.in_(visible_deck_ids),
        )
    )

    if source_to_local_all and install_ids:
        # Base select 2: Logical overlay cards mapped to local_deck_id
        overlay_select = (
            select(
                DeckCloneDeckMap.local_deck_id.label("deck_id"),
                Card.id.label("card_id"),
                Card.note_id.label("note_id"),
                CardProgress.id.label("progress_id"),
                CardProgress.queue.label("queue"),
                CardProgress.due_day.label("due_day"),
                CardProgress.due_at.label("due_at"),
                CardProgress.is_suspended.label("is_suspended"),
                CardProgress.is_buried.label("is_buried"),
                CardProgress.buried_until_day.label("buried_until_day"),
            )
            .select_from(Card)
            .join(Note, Card.note_id == Note.id)
            .join(
                DeckCloneDeckMap,
                DeckCloneDeckMap.source_deck_id == Note.deck_id,
            )
            .join(
                DeckInstall,
                DeckInstall.id == DeckCloneDeckMap.deck_install_id,
            )
            .outerjoin(
                CardProgress,
                and_(
                    CardProgress.card_id == Card.id,
                    CardProgress.user_id == learner_user_id,
                ),
            )
            .where(
                DeckInstall.user_id == learner_user_id,
                DeckInstall.clone_mode == "logical_overlay",
                DeckCloneDeckMap.local_deck_id.in_(visible_deck_ids),
                or_(
                    DeckInstall.source_owner_user_id.is_(None),
                    Note.user_id == DeckInstall.source_owner_user_id,
                ),
                or_(
                    and_(
                        DeckInstall.base_snapshot_at.is_(None),
                        DeckInstall.installed_at.is_(None),
                    ),
                    and_(
                        Note.created_at
                        <= func.coalesce(
                            DeckInstall.base_snapshot_at,
                            DeckInstall.installed_at,
                        ),
                        Card.created_at
                        <= func.coalesce(
                            DeckInstall.base_snapshot_at,
                            DeckInstall.installed_at,
                        ),
                    ),
                ),
            )
        )
        combined_cards = union_all(owned_select, overlay_select).subquery(
            "combined_cards"
        )
    else:
        combined_cards = owned_select.subquery("combined_cards")

    # Fast SQL classification conditions
    is_active = or_(
        combined_cards.c.progress_id.is_(None),
        and_(
            or_(
                combined_cards.c.is_suspended.is_(False),
                combined_cards.c.is_suspended.is_(None),
            ),
            or_(
                combined_cards.c.is_buried.is_(False),
                combined_cards.c.is_buried.is_(None),
                combined_cards.c.buried_until_day < today_day_index,
            ),
        ),
    )

    norm_queue = func.lower(func.coalesce(combined_cards.c.queue, "new"))

    is_new = and_(
        is_active,
        or_(combined_cards.c.progress_id.is_(None), norm_queue == "new"),
    )

    is_learn = and_(
        is_active,
        norm_queue.in_(["learn", "learning", "relearning"]),
    )

    is_due_review = and_(
        is_active,
        norm_queue == "review",
        or_(
            combined_cards.c.due_day <= today_day_index,
            and_(
                combined_cards.c.due_day.is_(None),
                or_(
                    combined_cards.c.due_at.is_(None),
                    combined_cards.c.due_at <= now_utc,
                ),
            ),
        ),
    )

    # Phase 6 Decision D6-04: NOTE learner counts at NOTE level; LEGACY counts at CARD level
    target_id = (
        combined_cards.c.note_id if should_count_by_note else combined_cards.c.card_id
    )

    agg_query = (
        select(
            combined_cards.c.deck_id,
            func.count(func.distinct(combined_cards.c.card_id)).label("total"),
            func.count(
                func.distinct(case((is_new, target_id), else_=None))
            ).label("new"),
            func.count(
                func.distinct(case((is_learn, target_id), else_=None))
            ).label("learn"),
            func.count(
                func.distinct(case((is_due_review, target_id), else_=None))
            ).label("due"),
        )
        .group_by(combined_cards.c.deck_id)
    )

    rows = session.execute(agg_query).all()
    for row in rows:
        did = row[0]
        if did is not None and int(did) in card_counts_by_deck:
            card_counts_by_deck[int(did)] = {
                "total": int(row[1] or 0),
                "new": int(row[2] or 0),
                "learn": int(row[3] or 0),
                "due": int(row[4] or 0),
            }

    return card_counts_by_deck, deck_note_types
