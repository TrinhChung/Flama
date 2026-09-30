"""Transaction-neutral learner authority fence primitives for Phase 5.

Callers remain LEGACY-only by default. Explicit NOTE-capable paths must opt in,
hold the same learner fence, and retain transaction ownership. This repository
does not commit or switch enrollment.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_inserted_rows import SUBJECT, inserted_in_transaction
from app.services.study_progress_contract import (
    DEFAULT_STORAGE_PROFILE,
    RAW_SCHEMA_VERSION,
    STORAGE_CODEC,
    STORAGE_PROFILES,
)
from app.services.study_progress_shadow_codec import (
    StudyProgressCodecError,
    serialize_raw_card_progress,
)
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
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
    storage_profile: str = DEFAULT_STORAGE_PROFILE


# Storage profiles this release can read and write NOTE authority under. A
# release that meets any other profile refuses the NOTE route (ADR P9-03 §2.1).
SUPPORTED_STORAGE_PROFILES = frozenset({"PROJECTION_V1"})


def read_study_storage_profile(session: Session, *, lock: str | None = None) -> str:
    """Return the system NOTE storage profile; ``lock`` is None, "share" or "update"."""

    statement = select(StudyAuthorityStorageProfile.profile_code).where(
        StudyAuthorityStorageProfile.id == 1
    )
    if lock is not None:
        if lock not in {"share", "update"}:
            raise ValueError("lock must be None, 'share' or 'update'.")
        statement = statement.with_for_update(read=lock == "share")
    profile_code = session.execute(statement).scalar_one_or_none()
    if profile_code is None:
        return DEFAULT_STORAGE_PROFILE
    if profile_code not in STORAGE_PROFILES:
        raise StudyAuthorityFenceError(
            "INVALID_STORAGE_PROFILE", "Persisted study storage profile is invalid."
        )
    return str(profile_code)


def _with_supported_profile(route: "StudyAuthorityRoute", profile_code: str) -> "StudyAuthorityRoute":
    if profile_code not in SUPPORTED_STORAGE_PROFILES:
        raise StudyAuthorityFenceError(
            "STORAGE_PROFILE_UNSUPPORTED",
            f"This release cannot serve Note authority under storage profile {profile_code}.",
        )
    return replace(route, storage_profile=profile_code)


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


def read_study_authority_route(session: Session, *, learner_user_id: int) -> StudyAuthorityRoute:
    """Resolve authority from the analytics snapshot, without a writer fence.

    Read-only summaries may represent an earlier committed epoch. They must
    read enrollment and all its evidence from one consistent snapshot, and
    must never use this route to admit writes or issue Study session pins.
    """
    learner_id = _positive_learner_id(learner_user_id)
    enrollment = session.execute(
        select(StudyAuthorityEnrollment)
        .where(StudyAuthorityEnrollment.learner_user_id == learner_id)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if enrollment is None:
        return StudyAuthorityRoute(learner_id, "LEGACY", 0, False)
    route = _decode_route(
        learner_user_id=learner_id, mode_code=enrollment.mode_code,
        epoch=enrollment.epoch, persisted=True, allow_note_authority=True,
    )
    if route.mode_code != "NOTE":
        return route
    return _with_supported_profile(route, read_study_storage_profile(session))


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
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
    if enrollment is None:
        return StudyAuthorityRoute(
            learner_user_id=learner_id,
            mode_code="LEGACY",
            epoch=0,
            persisted=False,
        )
    route = _decode_route(
        learner_user_id=learner_id,
        mode_code=enrollment.mode_code,
        epoch=enrollment.epoch,
        persisted=True,
        allow_note_authority=allow_note_authority,
    )
    if route.mode_code != "NOTE":
        return route
    # Shared, like the User row: the profile switch takes it exclusively and
    # so waits for every NOTE transaction that started under the old profile.
    return _with_supported_profile(
        route, read_study_storage_profile(session, lock="share")
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


_BULK_LOCK_CHUNK = 1000


def lock_study_authority_subject_rows(
    session: Session,
    *,
    subjects,
) -> dict[int, tuple[StudyAuthoritySubjectToken, StudyProgressState]]:
    """Lock the existing token and state rows of many locked subjects at once.

    Issuing one pair of ``FOR UPDATE`` reads per subject costs two round trips
    per Note on every session open and locking read. Rows visible in the
    snapshot are locked here by primary key in bulk (record locks only; the
    subject locks already serialize their writers) and returned current. A
    subject whose token or state is missing from the result is left to
    ``lock_study_authority_subject``'s per-row path, which creates or rejects
    it exactly as before.
    """

    subject_ids = sorted({int(subject.id) for subject in subjects})
    if not subject_ids:
        return {}
    tokens: dict[int, StudyAuthoritySubjectToken] = {}
    states: dict[int, StudyProgressState] = {}
    for start in range(0, len(subject_ids), _BULK_LOCK_CHUNK):
        chunk = subject_ids[start:start + _BULK_LOCK_CHUNK]
        visible_tokens = sorted(
            int(value)
            for value in session.execute(
                select(StudyAuthoritySubjectToken.subject_id).where(
                    StudyAuthoritySubjectToken.subject_id.in_(chunk)
                )
            ).scalars()
        )
        visible_states = sorted(
            int(value)
            for value in session.execute(
                select(StudyProgressState.subject_id).where(
                    StudyProgressState.subject_id.in_(chunk)
                )
            ).scalars()
        )
        if visible_tokens:
            for token in session.execute(
                select(StudyAuthoritySubjectToken)
                .where(StudyAuthoritySubjectToken.subject_id.in_(visible_tokens))
                .order_by(StudyAuthoritySubjectToken.subject_id.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            ).scalars():
                tokens[int(token.subject_id)] = token
        if visible_states:
            for state in session.execute(
                select(StudyProgressState)
                .where(StudyProgressState.subject_id.in_(visible_states))
                .order_by(StudyProgressState.subject_id.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            ).scalars():
                states[int(state.subject_id)] = state
    return {
        subject_id: (tokens[subject_id], states[subject_id])
        for subject_id in subject_ids
        if subject_id in tokens and subject_id in states
    }


def lock_study_authority_subject(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    subject: StudyProgressSubject,
    now_utc: datetime,
    create_token_if_missing: bool = True,
    locked_rows: tuple[StudyAuthoritySubjectToken, StudyProgressState] | None = None,
    subject_created_in_transaction: bool = False,
) -> LockedStudyAuthoritySubject:
    """Lock/create the independent token, then lock and verify current state.

    ``subject`` must already be selected ``FOR UPDATE`` after the learner
    prefix.  New tokens are initialized at revision zero from the existing
    exact state, or with a null hash when the subject has no current state.
    ``locked_rows`` are this subject's token and state already locked and
    refreshed by ``lock_study_authority_subject_rows``; the same checks apply.
    ``subject_created_in_transaction``: the caller inserted ``subject`` in
    this transaction, so only this transaction can have created its token or
    state (both have a foreign key to the uncommitted subject). They are read
    without ``FOR UPDATE``: that read would only take a gap lock at the end of
    the index, where concurrent inserts of other new subjects deadlock.
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

    if locked_rows is not None:
        token, state = locked_rows
        if (
            int(token.subject_id) != int(subject.id)
            or int(state.subject_id) != int(subject.id)
        ):
            raise StudyAuthorityFenceError(
                "AUTHORITY_CONTEXT_DIVERGED",
                "Preloaded authority rows belong to another subject.",
            )
        return _verified_locked_subject(
            subject=subject, token=token, state=state, token_created=False,
            generation=generation,
        )

    # Rows of a subject this transaction inserted can only be this
    # transaction's own: read them, but without a gap-locking FOR UPDATE.
    lock_children = not (
        subject_created_in_transaction
        or inserted_in_transaction(session, SUBJECT, subject.id)
    )
    token_query = select(StudyAuthoritySubjectToken).where(
        StudyAuthoritySubjectToken.subject_id == int(subject.id)
    )
    if lock_children:
        token_query = token_query.with_for_update()
    token = session.execute(
        token_query.execution_options(populate_existing=True)
    ).scalar_one_or_none()
    token_created = token is None
    if token is None:
        if not create_token_if_missing:
            raise StudyAuthorityFenceError(
                "AUTHORITY_TOKEN_REQUIRED", "Authority subject has no existing token."
            )
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

    state_query = select(StudyProgressState).where(
        StudyProgressState.subject_id == int(subject.id)
    )
    if lock_children:
        state_query = state_query.with_for_update()
    state = session.execute(
        state_query.execution_options(populate_existing=True)
    ).scalar_one_or_none()
    return _verified_locked_subject(
        subject=subject, token=token, state=state, token_created=token_created,
        generation=generation,
    )


def _verified_locked_subject(
    *,
    subject: StudyProgressSubject,
    token: StudyAuthoritySubjectToken,
    state: StudyProgressState | None,
    token_created: bool,
    generation: int,
) -> LockedStudyAuthoritySubject:
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
