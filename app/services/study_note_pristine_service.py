"""Never-studied Notes under NOTE authority.

A pristine Note has no state on the learner's progress row (or no row).
Readers serve it as NEW, exactly as LEGACY serves Cards without
``CardProgress``; the first write materializes revision-zero state on the row
in the same transaction. This covers overlay source Notes a publisher adds
after an installer enrolled, without fanning writes out to every installer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
)
from app.services import study_progress_lifecycle_mirror_service as lifecycle
from models.card import Card
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
    storage_profile: str | None = None,
) -> tuple[frozenset[str], frozenset[str]]:
    """Split Notes into (stateful, pristine) or fail on partial evidence.

    Locking reads by default: a first-state write for these keys waits until
    the caller's transaction ends, so a read never mixes the two answers. A
    Note is stateful iff its row holds state (ADR P10 §2.5).
    """

    note_ids = sorted({str(value) for value in note_ids if str(value)})

    def read(statement):
        return statement.with_for_update() if for_update else statement

    stateful: set[str] = set()
    for chunk in _chunks(note_ids):
        # Classification needs only presence and identity, not the Algorithm
        # JSON document. Preserve JSON null's Python-None semantics as well as
        # SQL NULL; the full state is loaded later under the same row locks.
        has_state = and_(
            StudyProgressSubject.state_payload.isnot(None),
            func.lower(func.json_type(StudyProgressSubject.state_payload)) != "null",
        )
        for logical_key, status, live_note_id, state_present in session.execute(read(
            select(
                StudyProgressSubject.logical_note_key,
                StudyProgressSubject.status_code,
                StudyProgressSubject.live_note_id,
                has_state.label("has_state"),
            ).where(
                StudyProgressSubject.learner_user_id == int(learner_user_id),
                StudyProgressSubject.logical_note_key.in_([value.encode("utf-8") for value in chunk]),
            ).order_by(StudyProgressSubject.logical_note_key.asc())
        )):
            key = bytes(logical_key).decode("utf-8")
            if state_present:
                stateful.add(key)
            elif not (
                str(status) == "NO_CURRENT_PROGRESS"
                and str(live_note_id or "") == key
            ):
                raise StudyAuthorityFenceError(
                    "INCOMPLETE_AUTHORITY_COVERAGE",
                    "A Note has non-pristine authority evidence without current NOTE state.",
                )
    return frozenset(stateful), frozenset(set(note_ids) - stateful)


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
        session, learner_user_id=route.learner_user_id, note_ids=note_by_id,
        storage_profile=route.storage_profile)
    # Set-wise: a study session over thousands of never-studied overlay Notes
    # must open within one request (P5-11c). Same rows as the per-Note path.
    lifecycle.materialize_pristine_notes_bulk(
        session,
        route=route,
        note_ids=pristine,
        starting_ease_by_note_id=starting_ease_by_note_id,
        provenance_code=provenance_code,
        now_utc=now_utc,
    )
    return pristine
