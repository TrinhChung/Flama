"""Transaction-neutral learner authority fence primitives for Phase 5.

The current physical schema can persist only LEGACY.  This repository makes
that fact explicit and fails closed if a NOTE or unknown row is observed.  It
does not commit, switch enrollment, or select a Note authority implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.study_progress_contract import RAW_SCHEMA_VERSION, STORAGE_CODEC
from app.services.study_progress_shadow_codec import (
    StudyProgressCodecError,
    serialize_raw_card_progress,
)
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.user import User


class StudyAuthorityFenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StudyAuthorityRoute:
    learner_user_id: int
    mode_code: str
    epoch: int
    persisted: bool


@dataclass(frozen=True)
class LockedStudyAuthoritySubject:
    """Locked subject/token/state triple; the caller owns the transaction."""

    subject: StudyProgressSubject
    token: StudyAuthoritySubjectToken
    state: StudyProgressState | None
    token_created: bool


@dataclass(frozen=True)
class LockedStudyAuthoritySiblings:
    """Complete current Card/progress vector locked after subject token/state."""

    learner_user_id: int
    subject_id: int
    subject_generation: int
    live_note_id: str
    cards: tuple[Card, ...]
    progress_by_card_id: Mapping[str, CardProgress]

    @property
    def card_ids(self) -> tuple[str, ...]:
        return tuple(str(card.id) for card in self.cards)


@dataclass(frozen=True)
class LockedStudyAuthorityCompatibility:
    """Locked current contributor/availability vector for NOTE compatibility."""

    learner_user_id: int
    subject_id: int
    subject_generation: int
    expected_mirror_revision: int
    contributor_by_card_id: Mapping[str, StudyProgressContributor]
    availability_by_contributor_id: Mapping[int, StudyProgressAvailability]
    contributor_revision_by_card_id: Mapping[str, int]
    contributor_raw_hash_by_card_id: Mapping[str, bytes]


def _positive_learner_id(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise StudyAuthorityFenceError(
            "INVALID_LEARNER_ID", "Learner ID must be a positive integer."
        )
    return value


def _decode_route(
    *,
    learner_user_id: int,
    mode_code: object,
    epoch: object,
    persisted: bool,
    allow_note_authority: bool = False,
) -> StudyAuthorityRoute:
    if not isinstance(mode_code, str) or mode_code not in {"LEGACY", "NOTE"}:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_MODE", "Persisted study authority mode is invalid."
        )
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_EPOCH", "Persisted study authority epoch is invalid."
        )
    if mode_code == "NOTE" and not allow_note_authority:
        raise StudyAuthorityFenceError(
            "NOTE_AUTHORITY_UNAVAILABLE",
            "Note authority is not enabled by the current runtime contract.",
        )
    if mode_code == "NOTE" and (not persisted or epoch < 1):
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_EPOCH",
            "Note authority requires a persisted positive enrollment epoch.",
        )
    return StudyAuthorityRoute(
        learner_user_id=learner_user_id,
        mode_code=mode_code,
        epoch=epoch,
        persisted=persisted,
    )


def lock_study_authority_route(
    session: Session,
    *,
    learner_user_id: int,
    allow_note_authority: bool = False,
) -> StudyAuthorityRoute:
    """Hold the stable learner shared fence and resolve the current route.

    The User row is deliberately locked before reading enrollment because an
    absent enrollment row is the normal LEGACY/0 state and is not a portable
    row-lock target.  A future mode switch must take the same User row FOR
    UPDATE, never upgrade this shared lock, and retain it until transaction end.
    NOTE remains fail-closed unless the caller explicitly opts into the native
    authority contract; existing LEGACY call sites therefore cannot drift.
    """

    learner_id = _positive_learner_id(learner_user_id)
    with session.no_autoflush:
        locked_user_id = session.execute(
            select(User.id)
            .where(User.id == learner_id)
            .with_for_update(read=True)
        ).scalar_one_or_none()
        if locked_user_id is None:
            raise StudyAuthorityFenceError(
                "LEARNER_NOT_FOUND", "Learner authority fence row does not exist."
            )
        enrollment = session.execute(
            select(StudyAuthorityEnrollment)
            .where(StudyAuthorityEnrollment.learner_user_id == learner_id)
            .with_for_update(read=True)
        ).scalar_one_or_none()
    if enrollment is None:
        return StudyAuthorityRoute(
            learner_user_id=learner_id,
            mode_code="LEGACY",
            epoch=0,
            persisted=False,
        )
    return _decode_route(
        learner_user_id=learner_id,
        mode_code=enrollment.mode_code,
        epoch=enrollment.epoch,
        persisted=True,
        allow_note_authority=allow_note_authority,
    )


def _validate_hash(value: object, *, nullable: bool, field_name: str) -> bytes | None:
    if value is None and nullable:
        return None
    if not isinstance(value, bytes) or len(value) != 32:
        null_suffix = " or null" if nullable else ""
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_TOKEN",
            f"{field_name} must contain 32 bytes{null_suffix}.",
        )
    return value


def lock_study_authority_subject(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    subject: StudyProgressSubject,
    now_utc: datetime,
) -> LockedStudyAuthoritySubject:
    """Lock/create the independent token, then lock and verify current state.

    ``subject`` must already be selected ``FOR UPDATE`` after the learner
    prefix.  New tokens are initialized at revision zero from the existing
    exact state, or with a null hash when the subject has no current state.
    """

    if not isinstance(route, StudyAuthorityRoute):
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_ROUTE", "Authority route is missing."
        )
    if (
        subject.id is None
        or isinstance(subject.id, bool)
        or not isinstance(subject.id, int)
        or subject.id <= 0
    ):
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_SUBJECT", "Authority subject must be persisted."
        )
    if int(subject.learner_user_id) != route.learner_user_id:
        raise StudyAuthorityFenceError(
            "WRONG_LEARNER", "Authority subject belongs to another learner."
        )
    generation = int(subject.subject_generation)
    if generation < 1:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_GENERATION", "Subject generation must be positive."
        )
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_TIME", "Authority time must be naive UTC."
        )

    token = session.execute(
        select(StudyAuthoritySubjectToken)
        .where(StudyAuthoritySubjectToken.subject_id == int(subject.id))
        .with_for_update()
    ).scalar_one_or_none()
    token_created = token is None
    if token is None:
        token = StudyAuthoritySubjectToken(
            subject_id=int(subject.id),
            subject_generation=generation,
            authority_revision=0,
            semantic_state_hash=None,
            created_at=now_utc,
            updated_at=now_utc,
        )
        session.add(token)
        session.flush()

    state = session.execute(
        select(StudyProgressState)
        .where(StudyProgressState.subject_id == int(subject.id))
        .with_for_update()
    ).scalar_one_or_none()
    state_hash = (
        _validate_hash(
            state.semantic_state_hash,
            nullable=False,
            field_name="state.semantic_state_hash",
        )
        if state is not None
        else None
    )
    if token_created:
        token.semantic_state_hash = state_hash

    if int(token.subject_generation) != generation:
        raise StudyAuthorityFenceError(
            "AUTHORITY_GENERATION_DIVERGED",
            "Authority token generation differs from the locked subject.",
        )
    if int(token.authority_revision) < 0:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_TOKEN", "Authority revision must be non-negative."
        )
    token_hash = _validate_hash(
        token.semantic_state_hash,
        nullable=True,
        field_name="token.semantic_state_hash",
    )
    if state is None and token_hash is not None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_STATE_DIVERGED",
            "Authority token references a missing current state.",
        )
    if state is not None:
        if int(state.subject_generation) != generation:
            raise StudyAuthorityFenceError(
                "AUTHORITY_GENERATION_DIVERGED",
                "Current state generation differs from the locked subject.",
            )
        if int(state.mirror_revision) != int(subject.mirror_revision):
            raise StudyAuthorityFenceError(
                "AUTHORITY_STATE_DIVERGED",
                "Current state mirror revision differs from the locked subject.",
            )
        if token_hash != state_hash:
            raise StudyAuthorityFenceError(
                "AUTHORITY_STATE_DIVERGED",
                "Authority token hash differs from current state.",
            )
    return LockedStudyAuthoritySubject(
        subject=subject,
        token=token,
        state=state,
        token_created=token_created,
    )


def lock_study_authority_siblings(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    requested_card_id: str | None = None,
) -> LockedStudyAuthoritySiblings:
    """Lock the complete live Card/progress vector for one current Note.

    The caller must already hold learner/enrollment, subject, token and state
    locks. Source Notes in logical-overlay installs may belong to the publisher;
    progress ownership is therefore checked on ``CardProgress.user_id`` rather
    than ``Note.user_id``. Missing compatibility rows fail closed until the
    first-state/new-sibling materialization contract is implemented.
    """

    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE":
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT",
            "Complete sibling locking is available only for NOTE authority.",
        )
    if not isinstance(locked, LockedStudyAuthoritySubject):
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_SUBJECT", "Locked authority subject is missing."
        )
    subject = locked.subject
    if int(subject.learner_user_id) != route.learner_user_id:
        raise StudyAuthorityFenceError(
            "WRONG_LEARNER", "Authority subject belongs to another learner."
        )
    live_note_id = str(subject.live_note_id or "").strip()
    if not live_note_id:
        raise StudyAuthorityFenceError(
            "DETACHED_AUTHORITY_SUBJECT",
            "Detached authority subject has no resolvable live Note.",
        )
    if bytes(subject.logical_note_key) != live_note_id.encode("utf-8"):
        raise StudyAuthorityFenceError(
            "UNSUPPORTED_AUTHORITY_IDENTITY",
            "Authority subject logical identity does not match its live Note.",
        )
    requested_id = str(requested_card_id or "").strip() or None

    note = session.execute(
        select(Note)
        .where(Note.id == live_note_id)
        .with_for_update(read=True)
    ).scalar_one_or_none()
    if note is None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_NOTE_NOT_FOUND", "Authority Note no longer exists."
        )
    cards = tuple(
        session.execute(
            select(Card)
            .where(Card.note_id == live_note_id)
            .order_by(Card.id.asc())
            .with_for_update(read=True)
        ).scalars()
    )
    if not cards:
        raise StudyAuthorityFenceError(
            "AUTHORITY_SIBLINGS_EMPTY", "Authority Note has no active Card sibling."
        )
    card_ids = tuple(str(card.id) for card in cards)
    if requested_id is not None and requested_id not in set(card_ids):
        raise StudyAuthorityFenceError(
            "CARD_OUTSIDE_AUTHORITY_SUBJECT",
            "Requested Card is outside the locked authority subject.",
        )
    progress_rows = tuple(
        session.execute(
            select(CardProgress)
            .where(
                CardProgress.user_id == route.learner_user_id,
                CardProgress.card_id.in_(card_ids),
            )
            .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
            .with_for_update()
        ).scalars()
    )
    progress_by_card_id = {
        str(row.card_id): row for row in progress_rows if row.card_id is not None
    }
    missing = tuple(card_id for card_id in card_ids if card_id not in progress_by_card_id)
    if missing:
        raise StudyAuthorityFenceError(
            "MISSING_LEGACY_PROGRESS",
            f"Authority Note has {len(missing)} Card sibling(s) without compatibility progress.",
        )
    if len(progress_rows) != len(cards) or len(progress_by_card_id) != len(cards):
        raise StudyAuthorityFenceError(
            "INVALID_LEGACY_PROGRESS",
            "Authority Note compatibility progress is not one row per Card.",
        )
    return LockedStudyAuthoritySiblings(
        learner_user_id=route.learner_user_id,
        subject_id=int(subject.id),
        subject_generation=int(subject.subject_generation),
        live_note_id=live_note_id,
        cards=cards,
        progress_by_card_id=MappingProxyType(progress_by_card_id),
    )


def lock_study_authority_compatibility(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    siblings: LockedStudyAuthoritySiblings,
) -> LockedStudyAuthorityCompatibility:
    """Lock the complete current contributor/availability compatibility vector.

    This follows the sibling CardProgress locks. Existing-state NOTE Actions
    fail closed unless every active compatibility row already exists and is
    attached to the same subject generation. First-state and new-sibling
    materialization remain a separate lifecycle command.
    """

    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE":
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT",
            "Compatibility locking is available only for NOTE authority.",
        )
    if not isinstance(locked, LockedStudyAuthoritySubject) or not isinstance(
        siblings, LockedStudyAuthoritySiblings
    ):
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_SUBJECT",
            "Locked authority subject and sibling vector are required.",
        )
    subject = locked.subject
    subject_id = int(subject.id)
    generation = int(subject.subject_generation)
    if (
        route.learner_user_id != siblings.learner_user_id
        or int(siblings.subject_id) != subject_id
        or int(siblings.subject_generation) != generation
        or int(subject.learner_user_id) != route.learner_user_id
    ):
        raise StudyAuthorityFenceError(
            "AUTHORITY_CONTEXT_DIVERGED",
            "Authority compatibility inputs do not describe one fenced subject.",
        )

    progress_by_id = {
        int(row.id): row
        for row in siblings.progress_by_card_id.values()
        if row.id is not None
    }
    if len(progress_by_id) != len(siblings.cards):
        raise StudyAuthorityFenceError(
            "INVALID_LEGACY_PROGRESS",
            "Compatibility locking requires one persisted progress row per Card.",
        )
    progress_ids = tuple(sorted(progress_by_id))
    contributors = tuple(
        session.execute(
            select(StudyProgressContributor)
            .where(
                StudyProgressContributor.subject_id == subject_id,
                StudyProgressContributor.subject_generation == generation,
                StudyProgressContributor.live_card_progress_id.in_(progress_ids),
            )
            .order_by(StudyProgressContributor.id.asc())
            .with_for_update()
        ).scalars()
    )
    contributor_by_progress_id = {
        int(row.live_card_progress_id): row
        for row in contributors
        if row.live_card_progress_id is not None
    }
    if (
        len(contributors) != len(progress_ids)
        or set(contributor_by_progress_id) != set(progress_ids)
    ):
        raise StudyAuthorityFenceError(
            "INCOMPLETE_AUTHORITY_COMPATIBILITY",
            "Authority subject has no complete current contributor vector.",
        )

    contributor_by_card_id: dict[str, StudyProgressContributor] = {}
    contributor_revision_by_card_id: dict[str, int] = {}
    contributor_raw_hash_by_card_id: dict[str, bytes] = {}
    for progress_id in progress_ids:
        progress = progress_by_id[progress_id]
        contributor = contributor_by_progress_id[progress_id]
        card_id = str(progress.card_id or "")
        if (
            str(contributor.contributor_status) != "ACTIVE"
            or int(contributor.source_progress_id) != progress_id
            or str(contributor.live_card_id or "") != card_id
            or bytes(contributor.logical_card_key) != card_id.encode("utf-8")
        ):
            raise StudyAuthorityFenceError(
                "INVALID_AUTHORITY_COMPATIBILITY",
                f"Card {card_id} has stale or detached contributor evidence.",
            )
        try:
            raw = serialize_raw_card_progress(progress)
        except StudyProgressCodecError as exc:
            raise StudyAuthorityFenceError(
                "INVALID_AUTHORITY_COMPATIBILITY",
                f"Card {card_id} raw compatibility evidence is invalid.",
            ) from exc
        contributor_raw_hash = bytes(contributor.raw_progress_hash)
        if (
            int(contributor.card_progress_revision) != int(progress.revision)
            or contributor.raw_schema_version != RAW_SCHEMA_VERSION
            or contributor.storage_codec != STORAGE_CODEC
            or contributor.raw_payload != raw.payload
            or int(contributor.raw_payload_size) != raw.size
            or contributor_raw_hash != raw.digest
        ):
            raise StudyAuthorityFenceError(
                "STALE_AUTHORITY_COMPATIBILITY",
                f"Card {card_id} contributor evidence differs from CardProgress.",
            )
        contributor_by_card_id[card_id] = contributor
        contributor_revision_by_card_id[card_id] = int(
            contributor.card_progress_revision
        )
        contributor_raw_hash_by_card_id[card_id] = contributor_raw_hash

    contributor_ids = tuple(sorted(int(row.id) for row in contributors))
    availability_rows = tuple(
        session.execute(
            select(StudyProgressAvailability)
            .where(StudyProgressAvailability.contributor_id.in_(contributor_ids))
            .order_by(StudyProgressAvailability.contributor_id.asc())
            .with_for_update()
        ).scalars()
    )
    availability_by_contributor_id = {
        int(row.contributor_id): row for row in availability_rows
    }
    if (
        len(availability_rows) != len(contributor_ids)
        or set(availability_by_contributor_id) != set(contributor_ids)
    ):
        raise StudyAuthorityFenceError(
            "INCOMPLETE_AUTHORITY_COMPATIBILITY",
            "Authority subject has no complete current availability vector.",
        )
    for contributor_id in contributor_ids:
        availability = availability_by_contributor_id[contributor_id]
        if (
            int(availability.subject_id) != subject_id
            or int(availability.subject_generation) != generation
        ):
            raise StudyAuthorityFenceError(
                "INVALID_AUTHORITY_COMPATIBILITY",
                "Authority availability evidence has stale subject identity.",
            )

    return LockedStudyAuthorityCompatibility(
        learner_user_id=route.learner_user_id,
        subject_id=subject_id,
        subject_generation=generation,
        expected_mirror_revision=int(subject.mirror_revision),
        contributor_by_card_id=MappingProxyType(contributor_by_card_id),
        availability_by_contributor_id=MappingProxyType(
            availability_by_contributor_id
        ),
        contributor_revision_by_card_id=MappingProxyType(
            contributor_revision_by_card_id
        ),
        contributor_raw_hash_by_card_id=MappingProxyType(
            contributor_raw_hash_by_card_id
        ),
    )
