"""Switch the system NOTE storage profile (P9-06, ADR P9-03 §2.1, §2.6).

``PROJECTION_V1 -> CANONICAL_V1`` is one-way. It runs inside a write freeze
as one transaction that takes the profile row exclusively: every NOTE route
fence holds that row shared, so the switch waits for writers that started
under the old profile and blocks new ones until it commits. The same
transaction maps each Connect source Card ref onto the Note authority fence:
a ref with no local change since its last sync (``applied_local_revision``
equal to the live CardProgress revision) gets the Note's current authority
revision; any other ref that already holds a snapshot needs confirmation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.repositories import study_authority_repository as repository
from models.card import Card
from models.card_progress import CardProgress
from models.connect_source_card_ref import ConnectSourceCardRef
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_subject import StudyProgressSubject
from models.study_session_batch import StudySessionBatch
from models.user import User

TARGET = "CANONICAL_V1"
_TERMINAL_BATCH_STATUSES = ("completed", "failed")
_CHUNK = 1000


class StorageProfileSwitchError(RuntimeError):
    def __init__(self, code: str, message: str, *, blockers: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.blockers = blockers


def _blockers(session: Session) -> list[str]:
    blockers = []
    if TARGET not in repository.SUPPORTED_STORAGE_PROFILES:
        blockers.append("RELEASE_DOES_NOT_SUPPORT_CANONICAL_V1")
    if session.execute(
        select(func.count()).select_from(StudyAuthorityEnrollment)
        .where(StudyAuthorityEnrollment.mode_code != "NOTE")
    ).scalar_one():
        blockers.append("LEGACY_LEARNERS")
    if session.execute(
        select(func.count()).select_from(User).where(
            ~select(StudyAuthorityEnrollment.learner_user_id)
            .where(StudyAuthorityEnrollment.learner_user_id == User.id)
            .exists()
        )
    ).scalar_one():
        blockers.append("UNENROLLED_USERS")
    if session.execute(
        select(func.count()).select_from(StudySessionBatch)
        .where(StudySessionBatch.status.notin_(_TERMINAL_BATCH_STATUSES))
    ).scalar_one():
        blockers.append("UNFINISHED_BATCHES")
    return blockers


def _ref_mapping(session: Session) -> tuple[dict[str, int], list[str]]:
    """(ref id -> authority revision) for unchanged refs; ids needing confirmation."""

    refs = session.execute(
        select(
            ConnectSourceCardRef.id,
            ConnectSourceCardRef.user_id,
            ConnectSourceCardRef.card_id,
            ConnectSourceCardRef.applied_local_revision,
        ).where(ConnectSourceCardRef.snapshot_hash.isnot(None))
    ).all()
    mapped: dict[str, int] = {}
    unconfirmed: list[str] = []
    for start in range(0, len(refs), _CHUNK):
        chunk = refs[start:start + _CHUNK]
        card_ids = sorted({str(row.card_id) for row in chunk if row.card_id})
        live: dict[tuple[int, str], tuple[int, int]] = {}
        if card_ids:
            # One row per (learner, Card): the live projection revision and
            # the Note authority revision, read in the same frozen snapshot.
            for user_id, card_id, progress_revision, authority_revision in session.execute(
                select(
                    CardProgress.user_id,
                    CardProgress.card_id,
                    CardProgress.revision,
                    StudyAuthoritySubjectToken.authority_revision,
                )
                .join(Card, Card.id == CardProgress.card_id)
                .join(StudyProgressSubject, and_(
                    StudyProgressSubject.learner_user_id == CardProgress.user_id,
                    StudyProgressSubject.live_note_id == Card.note_id,
                ))
                .join(StudyAuthoritySubjectToken, StudyAuthoritySubjectToken.subject_id == StudyProgressSubject.id)
                .where(CardProgress.card_id.in_(card_ids))
            ).all():
                live[(int(user_id), str(card_id))] = (int(progress_revision or 0), int(authority_revision))
        for row in chunk:
            current = live.get((int(row.user_id), str(row.card_id))) if row.card_id else None
            if (
                current is not None
                and row.applied_local_revision is not None
                and int(row.applied_local_revision) == current[0]
            ):
                mapped[str(row.id)] = current[1]
            else:
                unconfirmed.append(str(row.id))
    return mapped, unconfirmed


def plan_storage_profile_switch(session: Session) -> dict[str, Any]:
    """Read-only: what the switch would do now, and what blocks it."""

    current = repository.read_study_storage_profile(session)
    mapped, unconfirmed = _ref_mapping(session)
    blockers = _blockers(session)
    if current != repository.DEFAULT_STORAGE_PROFILE:
        blockers.append(f"PROFILE_IS_{current}")
    session.rollback()
    return {
        "current_profile": current,
        "target_profile": TARGET,
        "blockers": blockers,
        "connect_refs": {"authority": len(mapped), "needs_confirmation": len(unconfirmed)},
    }


def apply_storage_profile_switch(session: Session, *, now_utc: datetime | None = None) -> dict[str, Any]:
    """Switch to CANONICAL_V1 in the caller's transaction; the caller commits."""

    now = (now_utc or datetime.now(timezone.utc)).replace(tzinfo=None, microsecond=0)
    current = repository.read_study_storage_profile(session, lock="update")
    if current != repository.DEFAULT_STORAGE_PROFILE:
        raise StorageProfileSwitchError(
            "PROFILE_ALREADY_SWITCHED", f"The NOTE storage profile is already {current}."
        )
    blockers = _blockers(session)
    if blockers:
        raise StorageProfileSwitchError(
            "SWITCH_BLOCKED", "The NOTE storage profile cannot switch yet.", blockers=tuple(blockers)
        )
    mapped, unconfirmed = _ref_mapping(session)
    for ref_id, revision in mapped.items():
        session.execute(
            update(ConnectSourceCardRef)
            .where(ConnectSourceCardRef.id == ref_id)
            .values(applied_authority_revision=revision, applied_local_revision_state="AUTHORITY")
        )
    for start in range(0, len(unconfirmed), _CHUNK):
        session.execute(
            update(ConnectSourceCardRef)
            .where(ConnectSourceCardRef.id.in_(unconfirmed[start:start + _CHUNK]))
            .values(applied_authority_revision=None, applied_local_revision_state="NEEDS_CONFIRMATION")
        )
    profile = session.get(StudyAuthorityStorageProfile, 1)
    if profile is None:
        profile = StudyAuthorityStorageProfile(id=1, epoch=1, created_at=now, updated_at=now)
        session.add(profile)
    profile.profile_code = TARGET
    profile.epoch = int(profile.epoch or 1) + 1
    profile.switched_at = now
    profile.updated_at = now
    session.flush()
    return {
        "switched_at_utc": now.isoformat() + "Z",
        "profile": TARGET,
        "epoch": int(profile.epoch),
        "connect_refs": {"authority": len(mapped), "needs_confirmation": len(unconfirmed)},
    }
