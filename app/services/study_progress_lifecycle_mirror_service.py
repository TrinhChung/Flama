"""NOTE progress lifecycle on the consolidated row (ADR P10 §2.5).

Reset, Note deletion and first-state materialization write the learner's
``study_progress_subjects`` row (plus a lifecycle event for destructive
transitions). Adding or removing a Template writes no progress: Cards carry
none (§2.3). LEGACY learners keep ``card_progress`` and have no lifecycle
bookkeeping here. Nothing in this module commits or rolls back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthorityCompatibility,
    LockedStudyAuthoritySiblings,
    LockedStudyAuthoritySubject,
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
    is_consolidated,
    lock_study_authority_compatibility,
    lock_study_authority_siblings,
    lock_study_authority_subject,
)
from app.repositories.study_inserted_rows import SUBJECT, remember_inserted
from app.services.study_progress_contract import MAPPER_VERSION
from models.card import Card, load_cards
from models.note import Note
from models.study_progress_subject import StudyProgressSubject


@dataclass(frozen=True)
class LifecycleMirrorResult:
    subject_count: int
    lifecycle_event_count: int
    statuses: tuple[str, ...]


@dataclass
class NoteAuthorityResetPlan:
    """Locked NOTE rows of a reset or Note deletion, staged in the caller transaction."""

    session: Session
    route: StudyAuthorityRoute
    removed_card_ids: frozenset[str]
    locked_by_note_id: dict[str, LockedStudyAuthoritySubject]
    siblings_by_note_id: dict[str, LockedStudyAuthoritySiblings]
    compatibility_by_note_id: dict[str, LockedStudyAuthorityCompatibility]
    starting_ease_by_note_id: dict[str, float]
    finalized: bool = False


@dataclass(frozen=True)
class CloneProgressRekey:
    old_note_id: str
    new_note_id: str
    card_id_map: dict[str, str]


def _utc_naive(value: datetime | None = None) -> datetime:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        return moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _require_consolidated(route: StudyAuthorityRoute, message: str) -> None:
    if not isinstance(route, StudyAuthorityRoute) or not is_consolidated(route):
        raise StudyAuthorityFenceError("AUTHORITY_MODE_CONFLICT", message)


def prepare_note_authority_reset(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    removed_card_ids: Iterable[str],
    skip_pristine: bool = True,
    now_utc: datetime | None = None,
    starting_ease_by_note_id: Mapping[str, float] | None = None,
) -> NoteAuthorityResetPlan | None:
    """Lock the NOTE rows of every Note whose Cards are all in ``removed_card_ids``.

    Notes without current state need nothing. ``skip_pristine`` also skips a
    Note still in its pristine state (a reset would not change it).
    ``starting_ease_by_note_id`` supplies the deck options LEGACY would use for
    a logical-overlay source Note (the learner's mapped local deck).
    """

    _require_consolidated(route, "NOTE reset requires a fenced CONSOLIDATED_V1 NOTE route.")
    card_ids = frozenset(str(value) for value in removed_card_ids if str(value))
    if not card_ids:
        return None
    prepared_at = _utc_naive(now_utc)
    by_given_id = load_cards(session, card_ids)
    card_rows = tuple(sorted(by_given_id.values(), key=lambda card: (str(card.note_id), str(card.id))))
    if set(by_given_id) != set(card_ids):
        raise StudyAuthorityFenceError(
            "AUTHORITY_CARD_MISSING",
            "NOTE reset contains a Card that no longer exists.",
        )
    card_ids = frozenset(str(card.id) for card in card_rows)  # presentation keys
    note_ids = sorted({str(card.note_id) for card in card_rows}, key=lambda value: value.encode("utf-8"))
    subjects = tuple(
        session.execute(
            select(StudyProgressSubject)
            .where(
                StudyProgressSubject.learner_user_id == route.learner_user_id,
                StudyProgressSubject.logical_note_key.in_([note_id.encode("utf-8") for note_id in note_ids]),
            )
            .order_by(StudyProgressSubject.logical_note_key.asc())
            .with_for_update()
        ).scalars()
    )
    subject_by_note_id = {bytes(subject.logical_note_key).decode("utf-8"): subject for subject in subjects}

    from app.services.scheduler_config_service import resolve_deck_options
    from app.services.study_consolidated_progress_service import is_pristine_row

    locked_by_note_id: dict[str, LockedStudyAuthoritySubject] = {}
    siblings_by_note_id: dict[str, LockedStudyAuthoritySiblings] = {}
    compatibility_by_note_id: dict[str, LockedStudyAuthorityCompatibility] = {}
    ease_by_note_id: dict[str, float] = {}
    for note_id in note_ids:
        subject = subject_by_note_id.get(note_id)
        if subject is None:
            continue
        locked = lock_study_authority_subject(session, route=route, subject=subject, now_utc=prepared_at)
        locked_by_note_id[note_id] = locked
        if locked.state is None:
            continue
        siblings = lock_study_authority_siblings(session, route=route, locked=locked)
        # Cards of a retired occurrence still belong to the Note but are no
        # longer offered (ADR P11), so callers need only name the offered ones.
        offered = {str(card.id) for card in siblings.cards if card.application_status == "ACTIVE"}
        if not offered.issubset(card_ids):
            raise StudyAuthorityFenceError(
                "PARTIAL_AUTHORITY_SUBJECT_RESET",
                "A NOTE reset must include every Card sibling of the authority Note.",
            )
        compatibility = lock_study_authority_compatibility(
            session, route=route, locked=locked, siblings=siblings
        )
        if starting_ease_by_note_id is not None and note_id in starting_ease_by_note_id:
            starting_ease = float(starting_ease_by_note_id[note_id])
        else:
            starting_ease = float(
                resolve_deck_options(
                    user_id=route.learner_user_id, deck_id=siblings.cards[0].note.deck_id
                ).startingEase
            )
        if skip_pristine and is_pristine_row(locked.subject, starting_ease=starting_ease):
            continue
        siblings_by_note_id[note_id] = siblings
        compatibility_by_note_id[note_id] = compatibility
        ease_by_note_id[note_id] = starting_ease

    if not siblings_by_note_id:
        return None
    return NoteAuthorityResetPlan(
        session=session,
        route=route,
        removed_card_ids=frozenset(
            card_id for siblings in siblings_by_note_id.values() for card_id in siblings.card_ids
        ),
        locked_by_note_id=locked_by_note_id,
        siblings_by_note_id=siblings_by_note_id,
        compatibility_by_note_id=compatibility_by_note_id,
        starting_ease_by_note_id=ease_by_note_id,
    )


def _ordered_note_ids(plan: NoteAuthorityResetPlan) -> list[str]:
    return sorted(plan.siblings_by_note_id, key=lambda value: value.encode("utf-8"))


def _claim(plan: NoteAuthorityResetPlan | None, message: str) -> bool:
    if plan is None:
        return False
    if plan.finalized:
        raise StudyAuthorityFenceError("AUTHORITY_LIFECYCLE_REPLAY", message)
    plan.finalized = True
    return True


def finalize_note_authority_reset(
    plan: NoteAuthorityResetPlan | None,
    *,
    source_path: str,
    operation_key: str,
    now_utc: datetime | None = None,
) -> LifecycleMirrorResult | None:
    """Restart each planned Note at a fresh generation with its pristine state."""

    if not _claim(plan, "A NOTE reset plan may be finalized only once."):
        return None
    from app.services.study_consolidated_progress_service import reset_consolidated_note

    finalized_at = _utc_naive(now_utc)
    for note_id in _ordered_note_ids(plan):
        reset_consolidated_note(
            plan.session,
            learner_user_id=plan.route.learner_user_id,
            subject=plan.locked_by_note_id[note_id].subject,
            note_id=note_id,
            cards=plan.siblings_by_note_id[note_id].cards,
            starting_ease=float(plan.starting_ease_by_note_id[note_id]),
            source_path=source_path,
            operation_key=operation_key,
            now_utc=finalized_at,
        )
    plan.session.flush()
    statuses = tuple(
        str(plan.locked_by_note_id[note_id].subject.status_code) for note_id in _ordered_note_ids(plan)
    )
    return LifecycleMirrorResult(subject_count=len(statuses), lifecycle_event_count=len(statuses), statuses=statuses)


def finalize_note_authority_delete(
    plan: NoteAuthorityResetPlan | None,
    *,
    source_path: str,
    operation_key: str,
    now_utc: datetime | None = None,
) -> LifecycleMirrorResult | None:
    """Tombstone each planned Note's row; history and receipts stay."""

    if not _claim(plan, "A NOTE delete plan may be finalized only once."):
        return None
    from app.services.study_consolidated_progress_service import delete_consolidated_note

    finalized_at = _utc_naive(now_utc)
    for note_id in _ordered_note_ids(plan):
        delete_consolidated_note(
            plan.session,
            learner_user_id=plan.route.learner_user_id,
            subject=plan.locked_by_note_id[note_id].subject,
            note_id=note_id,
            card_ids=plan.siblings_by_note_id[note_id].card_ids,
            source_path=source_path,
            operation_key=operation_key,
            now_utc=finalized_at,
        )
    plan.session.flush()
    count = len(plan.siblings_by_note_id)
    return LifecycleMirrorResult(
        subject_count=count, lifecycle_event_count=count,
        statuses=("TOMBSTONED_SUBJECT_DELETED",) * count,
    )


def materialize_new_note_authority(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    note: Note,
    cards: Iterable[Card],
    provenance_code: str = "NATIVE_DIRECT",
    now_utc: datetime | None = None,
) -> LifecycleMirrorResult | None:
    """First state of a new (or still pristine) owned Note of a NOTE learner."""

    if route.mode_code == "LEGACY":
        return None
    if route.mode_code != "NOTE":
        raise StudyAuthorityFenceError("AUTHORITY_MODE_CONFLICT", "New Note authority route is invalid.")
    if provenance_code not in {"NATIVE_DIRECT", "NATIVE_MCP", "UNKNOWN_LEGACY"}:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_SOURCE", "New Note authority provenance is not supported."
        )
    if int(note.user_id) != route.learner_user_id or note.id is None:
        raise StudyAuthorityFenceError("WRONG_LEARNER", "New Note is outside the fenced learner scope.")
    return _materialize_note_authority(
        session, route=route, note=note, cards=cards, provenance_code=provenance_code,
        now_utc=now_utc, starting_ease=None,
    )


def materialize_pristine_note_authority(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    note: Note,
    cards: Iterable[Card],
    starting_ease: float,
    provenance_code: str = "NATIVE_DIRECT",
    now_utc: datetime | None = None,
) -> LifecycleMirrorResult | None:
    """First-state materialization of a pristine Note on its first write.

    The caller authorizes the learner's access context (owned Note or a
    logical-overlay source Note) and supplies the starting ease of the deck
    options that LEGACY would have used for the first review.
    """

    if route.mode_code != "NOTE" or note.id is None:
        raise StudyAuthorityFenceError("AUTHORITY_MODE_CONFLICT", "First-state materialization requires NOTE.")
    materialized_at = _utc_naive(now_utc)
    from app.repositories.study_progress_subject_repository import ensure_and_lock_subject

    # Idempotent create-or-lock closes the concurrent first-state key race.
    ensure_and_lock_subject(
        session,
        learner_user_id=route.learner_user_id,
        logical_note_key=str(note.id),
        live_note_id=str(note.id),
        now_utc=materialized_at,
    )
    return _materialize_note_authority(
        session, route=route, note=note, cards=cards, provenance_code=provenance_code,
        now_utc=materialized_at, starting_ease=float(starting_ease),
    )


_PRISTINE_CHUNK = 500


def _chunked(values):
    values = tuple(values)
    for offset in range(0, len(values), _PRISTINE_CHUNK):
        yield values[offset : offset + _PRISTINE_CHUNK]


def _require_pristine_row(subject: StudyProgressSubject | None, note_id: str) -> None:
    if (
        subject is None
        or str(subject.live_note_id or "") != note_id
        or str(subject.status_code or "") != "NO_CURRENT_PROGRESS"
        or int(subject.contributor_count) != 0
        or subject.authority_vector_hash is not None
        or subject.lineage_vector_hash is not None
    ):
        raise StudyAuthorityFenceError(
            "AUTHORITY_SUBJECT_EXISTS",
            "Note already has non-pristine authority evidence.",
        )
    if subject.state_payload is not None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_STATE_DIVERGED", "New Note authority unexpectedly has current state."
        )


def materialize_pristine_notes_bulk(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    note_ids: Iterable[str],
    starting_ease_by_note_id: Mapping[str, float],
    provenance_code: str = "NATIVE_DIRECT",
    now_utc: datetime | None = None,
) -> int:
    """First-state materialize many pristine Notes with set-wise statements.

    Lock order: rows in key order. The caller has
    classified every Note as pristine under the learner fence. Returns the
    number of Notes.
    """

    _require_consolidated(route, "First-state materialization requires a CONSOLIDATED_V1 NOTE route.")
    ordered = sorted({str(value) for value in note_ids if str(value)}, key=lambda value: value.encode("utf-8"))
    if not ordered:
        return 0
    materialized_at = _utc_naive(now_utc)
    learner_id = route.learner_user_id

    cards_by_note: dict[str, list[Card]] = {note_id: [] for note_id in ordered}
    for chunk in _chunked(ordered):
        # Offered Cards are derived (ADR P11); a derived read takes no lock.
        for card in session.execute(
            select(Card).where(Card.note_id.in_(chunk)).order_by(Card.note_id.asc(), Card.id.asc())
        ).scalars():
            cards_by_note[str(card.note_id)].append(card)
    if any(not cards for cards in cards_by_note.values()):
        raise StudyAuthorityFenceError(
            "INCOMPLETE_AUTHORITY_COVERAGE", "A Note without Cards cannot be studied.")

    # Create-if-absent every row, then lock them in canonical key order.
    table = StudyProgressSubject.__table__
    dialect = session.get_bind().dialect.name
    for chunk in _chunked(ordered):
        values = [
            {
                "learner_user_id": learner_id,
                "logical_note_key": note_id.encode("utf-8"),
                "live_note_id": note_id,
                "created_at": materialized_at,
                "updated_at": materialized_at,
            }
            for note_id in chunk
        ]
        if dialect == "mysql":
            from sqlalchemy.dialects.mysql import insert as dialect_insert

            statement = dialect_insert(table).values(values)
            statement = statement.on_duplicate_key_update(id=table.c.id)
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert

            statement = dialect_insert(table).values(values).on_conflict_do_nothing(
                index_elements=[table.c.learner_user_id, table.c.logical_note_key]
            )
        session.execute(statement)
    subject_by_note: dict[str, StudyProgressSubject] = {}
    for chunk in _chunked(ordered):
        for subject in session.execute(
            select(StudyProgressSubject)
            .where(
                StudyProgressSubject.learner_user_id == learner_id,
                StudyProgressSubject.logical_note_key.in_([note_id.encode("utf-8") for note_id in chunk]),
            )
            .order_by(StudyProgressSubject.logical_note_key.asc())
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalars():
            subject_by_note[bytes(subject.logical_note_key).decode("utf-8")] = subject
    for note_id in ordered:
        _require_pristine_row(subject_by_note.get(note_id), note_id)

    from app.services.study_consolidated_progress_service import materialize_consolidated_pristine

    materialize_consolidated_pristine(
        items=[
            (note_id, subject_by_note[note_id], tuple(cards_by_note[note_id]),
             float(starting_ease_by_note_id[note_id]))
            for note_id in ordered
        ],
        provenance_code=provenance_code,
        now_utc=materialized_at,
    )
    session.flush()
    return len(ordered)


def _materialize_note_authority(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    note: Note,
    cards: Iterable[Card],
    provenance_code: str,
    now_utc: datetime | None,
    starting_ease: float | None,
) -> LifecycleMirrorResult:
    _require_consolidated(route, "First-state materialization requires a CONSOLIDATED_V1 NOTE route.")
    card_rows = tuple(sorted(cards, key=lambda card: str(card.id).encode("utf-8")))
    if not card_rows or any(card.id is None or str(card.note_id) != str(note.id) for card in card_rows):
        raise StudyAuthorityFenceError(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "New Note authority requires every generated Card.",
        )
    materialized_at = _utc_naive(now_utc)
    logical_note_key = str(note.id).encode("utf-8")
    # Plain read first: a locking read of an absent key takes a gap lock that
    # concurrent Note creations of the same learner (MCP batches) deadlock on.
    # A concurrent creation of the same key still fails on the unique index.
    existing_subject_id = session.execute(
        select(StudyProgressSubject.id).where(
            StudyProgressSubject.learner_user_id == route.learner_user_id,
            StudyProgressSubject.logical_note_key == logical_note_key,
        )
    ).scalar_one_or_none()
    if existing_subject_id is not None:
        subject = session.execute(
            select(StudyProgressSubject)
            .where(StudyProgressSubject.id == int(existing_subject_id))
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one()
        _require_pristine_row(subject, str(note.id))
    else:
        subject = StudyProgressSubject(
            learner_user_id=route.learner_user_id,
            logical_note_key=logical_note_key,
            live_note_id=str(note.id),
            subject_generation=1,
            mirror_revision=0,
            status_code="NO_CURRENT_PROGRESS",
            contributor_count=0,
            authority_vector_hash=None,
            lineage_vector_hash=None,
            mapper_version=MAPPER_VERSION,
            created_at=materialized_at,
            updated_at=materialized_at,
        )
        session.add(subject)
        session.flush()
        remember_inserted(session, SUBJECT, subject.id)
    lock_study_authority_subject(session, route=route, subject=subject, now_utc=materialized_at)
    if starting_ease is None:
        from app.services.scheduler_config_service import resolve_deck_options

        starting_ease = float(
            resolve_deck_options(user_id=route.learner_user_id, deck_id=note.deck_id).startingEase
        )
    from app.services.study_consolidated_progress_service import materialize_consolidated_pristine

    materialize_consolidated_pristine(
        items=[(str(note.id), subject, card_rows, float(starting_ease))],
        provenance_code=provenance_code,
        now_utc=materialized_at,
    )
    session.flush()
    return LifecycleMirrorResult(subject_count=1, lifecycle_event_count=0, statuses=(str(subject.status_code),))


def refuse_clone_rekey_of_note_progress(
    session: Session,
    *,
    learner_user_id: int,
    rekeys: Iterable[CloneProgressRekey],
) -> None:
    """A legacy full-copy cutover may only rekey LEGACY ``card_progress``.

    NOTE progress lives on rows keyed by Note; moving it between Notes is not a
    supported transition (production had no full-copy install at P9-06).
    """

    note_ids = sorted({value for item in rekeys for value in (item.old_note_id, item.new_note_id) if value})
    for chunk in _chunked(note_ids):
        found = session.execute(
            select(StudyProgressSubject.id).where(
                StudyProgressSubject.learner_user_id == int(learner_user_id),
                StudyProgressSubject.logical_note_key.in_([value.encode("utf-8") for value in chunk]),
                StudyProgressSubject.semantic_state_hash.isnot(None),
            ).limit(1)
        ).first()
        if found is not None:
            raise StudyAuthorityFenceError(
                "CLONE_REKEY_OF_NOTE_PROGRESS",
                "Legacy clone cutover cannot move NOTE progress between Notes.",
            )
