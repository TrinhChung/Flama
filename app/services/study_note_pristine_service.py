"""Never-studied Notes under NOTE authority.

A pristine Note has no canonical state, no compatibility progress on any
sibling Card and no contributor for the learner. Readers serve it as NEW,
exactly as LEGACY serves Cards without ``CardProgress``; the first write
materializes revision-zero state plus the full sibling projection in the same
transaction. This covers overlay source Notes a publisher adds after an
installer enrolled, without fanning writes out to every installer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
)
from app.services import study_progress_lifecycle_mirror_service as lifecycle
from models.card import Card
from models.card_progress import CardProgress
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject

_CHUNK = 500


def _chunks(values):
    values = tuple(values)
    for offset in range(0, len(values), _CHUNK):
        yield values[offset : offset + _CHUNK]


def classify_note_authority_keys(
    session: Session,
    *,
    learner_user_id: int,
    note_ids: Iterable[str],
    for_update: bool = True,
) -> tuple[frozenset[str], frozenset[str]]:
    """Split Notes into (stateful, pristine) or fail on partial evidence.

    Locking reads by default: a first-state insert for these keys waits until
    the caller's transaction ends, so a read never mixes the two answers.
    """

    note_ids = sorted({str(value) for value in note_ids if str(value)})

    def read(statement):
        return statement.with_for_update() if for_update else statement

    subjects = []
    for chunk in _chunks(note_ids):
        subjects.extend(session.execute(read(
            select(StudyProgressSubject).where(
                StudyProgressSubject.learner_user_id == int(learner_user_id),
                StudyProgressSubject.logical_note_key.in_([value.encode("utf-8") for value in chunk]),
            ).order_by(StudyProgressSubject.logical_note_key.asc())
        )).scalars())
    subject_ids = [int(subject.id) for subject in subjects]
    stateful_ids = set()
    for chunk in _chunks(subject_ids):
        stateful_ids.update(int(value) for value in session.execute(read(
            select(StudyProgressState.subject_id).where(StudyProgressState.subject_id.in_(chunk))
        )).scalars())
    stateful = {
        bytes(subject.logical_note_key).decode("utf-8")
        for subject in subjects
        if int(subject.id) in stateful_ids
    }
    candidates = set(note_ids) - stateful
    for subject in subjects:
        key = bytes(subject.logical_note_key).decode("utf-8")
        if key in candidates and not (
            str(subject.status_code) == "NO_CURRENT_PROGRESS"
            and int(subject.contributor_count) == 0
            and subject.authority_vector_hash is None
            and subject.lineage_vector_hash is None
            and str(subject.live_note_id or "") == key
        ):
            raise StudyAuthorityFenceError(
                "INCOMPLETE_AUTHORITY_COVERAGE",
                "A Note has non-pristine authority evidence without current NOTE state.",
            )
    candidate_subject_ids = [
        int(subject.id)
        for subject in subjects
        if bytes(subject.logical_note_key).decode("utf-8") in candidates
    ]
    for chunk in _chunks(candidate_subject_ids):
        if session.execute(read(
            select(StudyProgressContributor.id).where(
                StudyProgressContributor.subject_id.in_(chunk),
                StudyProgressContributor.contributor_status == "ACTIVE",
            ).limit(1)
        )).first() is not None:
            raise StudyAuthorityFenceError(
                "INCOMPLETE_AUTHORITY_COVERAGE",
                "A Note has contributor evidence without current NOTE state.",
            )
    for chunk in _chunks(sorted(candidates)):
        if session.execute(read(
            select(CardProgress.id).join(Card, Card.id == CardProgress.card_id).where(
                CardProgress.user_id == int(learner_user_id),
                Card.note_id.in_(chunk),
            ).limit(1)
        )).first() is not None:
            raise StudyAuthorityFenceError(
                "INCOMPLETE_AUTHORITY_COVERAGE",
                "Compatibility progress exists without current NOTE state.",
            )
    return frozenset(stateful), frozenset(candidates)


def materialize_pristine_notes(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    cards: Iterable[Card],
    starting_ease_by_note_id: Mapping[str, float],
    provenance_code: str = "NATIVE_DIRECT",
    now_utc: datetime | None = None,
) -> frozenset[str]:
    """Materialize every pristine Note of ``cards``; return their Note IDs.

    The caller has authorized the learner's access to these Cards (owned or
    logical-overlay scope) and holds the learner fence.
    """

    if route.mode_code != "NOTE":
        return frozenset()
    note_by_id = {str(card.note_id): card.note for card in cards}
    _stateful, pristine = classify_note_authority_keys(
        session, learner_user_id=route.learner_user_id, note_ids=note_by_id)
    for note_id in sorted(pristine, key=lambda value: value.encode("utf-8")):
        siblings = tuple(session.execute(
            select(Card).where(Card.note_id == note_id).order_by(Card.id.asc()).with_for_update(read=True)
        ).scalars())
        if not siblings:
            raise StudyAuthorityFenceError(
                "INCOMPLETE_AUTHORITY_COVERAGE", "A Note without Cards cannot be studied.")
        lifecycle.materialize_pristine_note_authority(
            session,
            route=route,
            note=note_by_id[note_id],
            cards=siblings,
            starting_ease=starting_ease_by_note_id[note_id],
            provenance_code=provenance_code,
            now_utc=now_utc,
        )
    return pristine
