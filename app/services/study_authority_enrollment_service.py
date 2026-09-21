"""Explicit, transaction-neutral learner authority enrollment transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    StudyAuthorityRoute,
    lock_study_authority_compatibility,
    lock_study_authority_siblings,
    lock_study_authority_subject,
)
from models.card import Card
from models.card_progress import CardProgress
from models.deck_install import DeckInstall
from models.note import Note
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.user import User


class StudyAuthorityEnrollmentError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


@dataclass(frozen=True)
class StudyAuthorityEnrollmentResult:
    learner_user_id: int
    previous_mode: str
    previous_epoch: int
    mode_code: str
    epoch: int
    subject_count: int
    card_count: int
    cancelled_session_count: int


def _fail(code: str, message: str) -> StudyAuthorityEnrollmentError:
    return StudyAuthorityEnrollmentError(code, message)


def stage_note_authority_enrollment(
    session: Session,
    *,
    learner_user_id: int,
    now_utc: datetime,
) -> StudyAuthorityEnrollmentResult:
    """Fence, prove existing-state coverage, then stage LEGACY -> NOTE."""

    if (
        isinstance(learner_user_id, bool)
        or not isinstance(learner_user_id, int)
        or learner_user_id <= 0
    ):
        raise _fail("INVALID_LEARNER_ID", "Learner ID must be positive.")
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail(
            "INVALID_AUTHORITY_TIME",
            "Authority enrollment time must be naive UTC.",
        )

    learner = session.execute(
        select(User).where(User.id == learner_user_id).with_for_update()
    ).scalar_one_or_none()
    if learner is None:
        raise _fail("LEARNER_NOT_FOUND", "Learner authority fence row is missing.")
    enrollment = session.execute(
        select(StudyAuthorityEnrollment)
        .where(StudyAuthorityEnrollment.learner_user_id == learner_user_id)
        .with_for_update()
    ).scalar_one_or_none()
    previous_mode = str(enrollment.mode_code) if enrollment is not None else "LEGACY"
    previous_epoch = int(enrollment.epoch) if enrollment is not None else 0
    if previous_mode == "NOTE":
        return StudyAuthorityEnrollmentResult(
            learner_user_id=learner_user_id,
            previous_mode="NOTE",
            previous_epoch=previous_epoch,
            mode_code="NOTE",
            epoch=previous_epoch,
            subject_count=0,
            card_count=0,
            cancelled_session_count=0,
        )
    if previous_mode != "LEGACY" or previous_epoch < 0:
        raise _fail(
            "INVALID_AUTHORITY_ENROLLMENT",
            "Existing learner authority enrollment is invalid.",
        )
    if session.execute(
        select(DeckInstall.id)
        .where(
            DeckInstall.user_id == learner_user_id,
            DeckInstall.clone_mode == "logical_overlay",
        )
        .limit(1)
    ).scalar_one_or_none() is not None:
        raise _fail(
            "OVERLAY_AUTHORITY_NOT_READY",
            "NOTE enrollment for logical-overlay installs requires P5-06 routing.",
        )

    owned_card_ids = {
        str(card_id)
        for card_id, in session.execute(
            select(Card.id)
            .join(Note, Card.note_id == Note.id)
            .where(Note.user_id == learner_user_id)
            .order_by(Card.id.asc())
        ).all()
    }
    progress_rows = tuple(
        session.execute(
            select(CardProgress)
            .where(CardProgress.user_id == learner_user_id)
            .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
        ).scalars()
    )
    progress_card_ids = {str(row.card_id) for row in progress_rows}
    missing_owned = owned_card_ids - progress_card_ids
    if missing_owned:
        raise _fail(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            f"Learner has {len(missing_owned)} owned Card(s) without progress evidence.",
        )
    if not progress_rows:
        raise _fail(
            "NO_AUTHORITY_SUBJECTS",
            "Learner has no existing progress eligible for NOTE authority.",
        )

    card_note_rows = tuple(
        session.execute(
            select(Card.id, Card.note_id)
            .where(Card.id.in_(sorted(progress_card_ids)))
            .order_by(Card.id.asc())
        ).all()
    )
    note_by_card_id = {str(row.id): str(row.note_id) for row in card_note_rows}
    if set(note_by_card_id) != progress_card_ids:
        raise _fail(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "Learner progress references a missing Card.",
        )
    note_ids = sorted(set(note_by_card_id.values()), key=lambda value: value.encode("utf-8"))
    subjects = tuple(
        session.execute(
            select(StudyProgressSubject)
            .where(
                StudyProgressSubject.learner_user_id == learner_user_id,
                StudyProgressSubject.logical_note_key.in_(
                    [note_id.encode("utf-8") for note_id in note_ids]
                ),
            )
            .order_by(StudyProgressSubject.logical_note_key.asc())
            .with_for_update()
        ).scalars()
    )
    subject_by_note_id = {
        bytes(row.logical_note_key).decode("utf-8"): row for row in subjects
    }
    if set(subject_by_note_id) != set(note_ids):
        raise _fail(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "One or more learner Notes have no mirrored authority subject.",
        )

    next_epoch = previous_epoch + 1
    route = StudyAuthorityRoute(
        learner_user_id=learner_user_id,
        mode_code="NOTE",
        epoch=next_epoch,
        persisted=True,
    )
    locked_by_note_id = {}
    for note_id in note_ids:
        subject = subject_by_note_id[note_id]
        if (
            str(subject.live_note_id or "") != note_id
            or not str(subject.status_code or "").startswith("MIRRORED_")
        ):
            raise _fail(
                "AUTHORITY_SUBJECT_NOT_READY",
                "Learner authority subject is detached, quarantined, or tombstoned.",
            )
        locked = lock_study_authority_subject(
            session,
            route=route,
            subject=subject,
            now_utc=now_utc,
        )
        if locked.state is None:
            raise _fail(
                "AUTHORITY_STATE_REQUIRED",
                "NOTE enrollment requires an existing mirrored state.",
            )
        locked_by_note_id[note_id] = locked
    for note_id in note_ids:
        locked = locked_by_note_id[note_id]
        siblings = lock_study_authority_siblings(
            session,
            route=route,
            locked=locked,
        )
        lock_study_authority_compatibility(
            session,
            route=route,
            locked=locked,
            siblings=siblings,
        )

    open_sessions = tuple(
        session.execute(
            select(StudySession)
            .where(
                StudySession.user_id == learner_user_id,
                StudySession.status == "open",
            )
            .order_by(StudySession.id.asc())
            .with_for_update()
        ).scalars()
    )
    open_session_ids = [row.id for row in open_sessions]
    if open_session_ids:
        pending_batch = session.execute(
            select(StudySessionBatch.id)
            .where(
                StudySessionBatch.session_id.in_(open_session_ids),
                StudySessionBatch.status.in_(
                    ("enqueued", "processing", "retrying")
                ),
            )
            .limit(1)
            .with_for_update()
        ).scalar_one_or_none()
        if pending_batch is not None:
            raise _fail(
                "AUTHORITY_BATCH_IN_FLIGHT",
                "Learner has an asynchronous Study batch still in flight.",
            )
    for study_session in open_sessions:
        study_session.status = "cancelled"

    if enrollment is None:
        enrollment = StudyAuthorityEnrollment(
            learner_user_id=learner_user_id,
            created_at=now_utc,
        )
        session.add(enrollment)
    enrollment.mode_code = "NOTE"
    enrollment.epoch = next_epoch
    enrollment.updated_at = now_utc
    return StudyAuthorityEnrollmentResult(
        learner_user_id=learner_user_id,
        previous_mode=previous_mode,
        previous_epoch=previous_epoch,
        mode_code="NOTE",
        epoch=next_epoch,
        subject_count=len(subjects),
        card_count=len(progress_rows),
        cancelled_session_count=len(open_sessions),
    )
