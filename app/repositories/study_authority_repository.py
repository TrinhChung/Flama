"""Learner authority fence and NOTE progress-row locking (ADR P10).

LEGACY learners keep ``card_progress``. A NOTE learner's progress for a Note
is one ``study_progress_subjects`` row under the ``CONSOLIDATED_V1`` storage
profile; the token and state of a locked subject are views of that row.
Callers hold the learner fence and own the transaction; nothing here commits
or switches enrollment.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from types import MappingProxyType
from typing import Mapping

from sqlalchemy import literal, select, union_all
from sqlalchemy.orm import Session

from app.services.study_progress_contract import (
    CONSOLIDATED_STORAGE_PROFILE,
    DEFAULT_STORAGE_PROFILE,
    STORAGE_PROFILES,
)
from models.card import Card
from models.note import Note
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
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


# Storage profiles this release can serve NOTE authority under. PROJECTION_V1
# and CANONICAL_V1 were retired after the P10-08 switch (P10-09); a database
# still on either is refused (fail closed). A database without a profile row
# is a fresh CONSOLIDATED_V1 install.
SUPPORTED_STORAGE_PROFILES = frozenset({CONSOLIDATED_STORAGE_PROFILE})


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


def projection_is_live(session: Session) -> bool:
    """Whether ``card_progress`` can still name a learner of some Content.

    LEGACY learners keep writing it, and frozen rows of NOTE learners stay
    until it is retired, so content-wide learner discovery still reads it.
    """

    return True


def bind_storage_profile(session: Session, route: "StudyAuthorityRoute") -> "StudyAuthorityRoute":
    """Give a NOTE route built outside the fence the current storage profile.

    The caller already holds the learner's User row; the profile row is read
    under the same shared lock the fence takes.
    """

    if route.mode_code != "NOTE":
        return route
    return _with_supported_profile(route, read_study_storage_profile(session, lock="share"))


def _with_supported_profile(route: "StudyAuthorityRoute", profile_code: str) -> "StudyAuthorityRoute":
    if profile_code not in SUPPORTED_STORAGE_PROFILES:
        raise StudyAuthorityFenceError(
            "STORAGE_PROFILE_UNSUPPORTED",
            f"This release cannot serve Note authority under storage profile {profile_code}.",
        )
    return replace(route, storage_profile=profile_code)


def is_consolidated(route: "StudyAuthorityRoute") -> bool:
    """Whether NOTE progress lives on the subject row (ADR P10); LEGACY routes never."""

    return route.mode_code == "NOTE" and route.storage_profile == CONSOLIDATED_STORAGE_PROFILE


class _SubjectRowView:
    """Read and write one attribute group of a consolidated subject row."""

    __slots__ = ("subject",)
    _FIELDS: tuple[str, ...] = ()

    def __init__(self, subject: StudyProgressSubject) -> None:
        object.__setattr__(self, "subject", subject)

    def __getattr__(self, name: str):
        if name == "subject_id":
            return self.subject.id
        if name in self._FIELDS:
            return getattr(self.subject, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name not in self._FIELDS:
            raise AttributeError(f"{type(self).__name__} has no writable {name!r}.")
        if getattr(self.subject, name) != value:
            setattr(self.subject, name, value)


class ConsolidatedSubjectToken(_SubjectRowView):
    """CAS token of a CONSOLIDATED_V1 subject: its own row (ADR P10 §2.4)."""

    __slots__ = ()
    _FIELDS = (
        "subject_generation",
        "authority_revision",
        "semantic_state_hash",
        "created_at",
        "updated_at",
    )


class ConsolidatedSubjectState(_SubjectRowView):
    """Current Algorithm State of a CONSOLIDATED_V1 subject: its own row."""

    __slots__ = ()
    _FIELDS = (
        "subject_generation",
        "mirror_revision",
        "algorithm_key",
        "algorithm_version",
        "state_schema_version",
        "storage_codec",
        "state_payload",
        "state_payload_size",
        "algorithm_state_hash",
        "semantic_state_hash",
        "created_at",
        "updated_at",
    )


@dataclass(frozen=True)
class LockedStudyAuthoritySubject:
    """A locked progress row and its token/state views; the caller owns the transaction."""

    subject: StudyProgressSubject
    token: "ConsolidatedSubjectToken"
    state: "ConsolidatedSubjectState | None"
    token_created: bool


def consolidated_locked_subject(subject: StudyProgressSubject) -> LockedStudyAuthoritySubject:
    """The locked triple of a subject row already selected ``FOR UPDATE``."""

    revision = int(subject.authority_revision or 0)
    if revision < 0:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_TOKEN", "Authority revision must be non-negative."
        )
    has_state = subject.state_payload is not None
    semantic_hash = _validate_hash(
        bytes(subject.semantic_state_hash) if subject.semantic_state_hash is not None else None,
        nullable=not has_state,
        field_name="subject.semantic_state_hash",
    )
    if not has_state and semantic_hash is not None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_STATE_DIVERGED",
            "Authority revision references a missing current state.",
        )
    return LockedStudyAuthoritySubject(
        subject=subject,
        token=ConsolidatedSubjectToken(subject),
        state=ConsolidatedSubjectState(subject) if has_state else None,
        token_created=False,
    )


@dataclass(frozen=True)
class LockedStudyAuthoritySiblings:
    """The live Card siblings of a locked Note (read-locked); Cards carry no progress."""

    learner_user_id: int
    subject_id: int
    subject_generation: int
    live_note_id: str
    cards: tuple[Card, ...]
    progress_by_card_id: Mapping[str, object] = MappingProxyType({})

    @property
    def card_ids(self) -> tuple[str, ...]:
        return tuple(str(card.id) for card in self.cards)


@dataclass(frozen=True)
class LockedStudyAuthorityCompatibility:
    """Identity of a locked subject generation; ADR P10 keeps no per-Card vector."""

    learner_user_id: int
    subject_id: int
    subject_generation: int
    expected_mirror_revision: int
    contributor_by_card_id: Mapping[str, object] = MappingProxyType({})
    availability_by_contributor_id: Mapping[int, object] = MappingProxyType({})
    contributor_revision_by_card_id: Mapping[str, int] = MappingProxyType({})
    contributor_raw_hash_by_card_id: Mapping[str, bytes] = MappingProxyType({})


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


def lock_study_authority_subject(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    subject: StudyProgressSubject,
    now_utc: datetime,
    create_token_if_missing: bool = True,
    subject_created_in_transaction: bool = False,
) -> LockedStudyAuthoritySubject:
    """Verify a subject row the caller already selected ``FOR UPDATE``.

    The row is the whole authority (ADR P10 §2.4): its revision is the CAS
    token and its state columns the current state.
    """

    if not isinstance(route, StudyAuthorityRoute):
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_ROUTE", "Authority route is missing."
        )
    if not is_consolidated(route):
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT", "Subject locking requires a CONSOLIDATED_V1 NOTE route."
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
    if int(subject.subject_generation) < 1:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_GENERATION", "Subject generation must be positive."
        )
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_TIME", "Authority time must be naive UTC."
        )
    return consolidated_locked_subject(subject)


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
    return LockedStudyAuthoritySiblings(
        learner_user_id=route.learner_user_id,
        subject_id=int(subject.id),
        subject_generation=int(subject.subject_generation),
        live_note_id=live_note_id,
        cards=cards,
    )


def lock_study_authority_compatibility(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    siblings: LockedStudyAuthoritySiblings,
) -> LockedStudyAuthorityCompatibility:
    """Check that ``locked`` and ``siblings`` describe one fenced subject generation."""

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
    return LockedStudyAuthorityCompatibility(
        learner_user_id=route.learner_user_id,
        subject_id=subject_id,
        subject_generation=generation,
        expected_mirror_revision=int(subject.mirror_revision),
    )


def lock_study_authority_siblings_many(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    locked_by_logical_note_key: Mapping[str, LockedStudyAuthoritySubject],
) -> Mapping[str, LockedStudyAuthoritySiblings]:
    """Read-lock complete sibling vectors after all session Subjects are locked.

    Session callers already hold learner -> session -> every Subject lock in
    logical-key order. Acquire shared Note/Card locks in bounded, deterministic
    groups; direct review continues using its single-Subject helper. No learner
    ownership predicate is applied to Notes: overlay source Notes belong to the
    publisher, while progress ownership remains on the locked Subject.
    """
    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE":
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT", "Complete sibling locking requires NOTE authority.",
        )
    keys = sorted(locked_by_logical_note_key, key=lambda value: value.encode("utf-8"))
    for key in keys:
        locked = locked_by_logical_note_key[key]
        if not isinstance(locked, LockedStudyAuthoritySubject):
            raise StudyAuthorityFenceError(
                "INVALID_AUTHORITY_SUBJECT", "Locked authority subject is missing.",
            )
        subject = locked.subject
        if int(subject.learner_user_id) != route.learner_user_id:
            raise StudyAuthorityFenceError("WRONG_LEARNER", "Authority subject belongs to another learner.")
        live_note_id = str(subject.live_note_id or "").strip()
        if not live_note_id:
            raise StudyAuthorityFenceError(
                "DETACHED_AUTHORITY_SUBJECT", "Detached authority subject has no resolvable live Note.",
            )
        if key != live_note_id or bytes(subject.logical_note_key) != live_note_id.encode("utf-8"):
            raise StudyAuthorityFenceError(
                "UNSUPPORTED_AUTHORITY_IDENTITY", "Authority subject logical identity does not match its live Note.",
            )

    result: dict[str, LockedStudyAuthoritySiblings] = {}
    for offset in range(0, len(keys), 500):
        chunk = keys[offset:offset + 500]
        # Only existence is needed, but this is a current locking read just as
        # in the per-Note helper. Keep the full Card vector, including siblings
        # outside the selected session composition.
        note_read = select(Note.id).where(Note.id.in_(chunk))
        if session.get_bind().dialect.name == "mysql":
            # A covering PRIMARY scan for IN(...) can lock unrelated Notes
            # under REPEATABLE READ, even with FORCE INDEX. Drive point reads
            # from the bounded key relation instead. UNION prevents merging
            # it into a Note scan; STRAIGHT_JOIN keeps the keys on the left.
            key_rows = union_all(*(
                select(literal(key).label("note_id")) for key in chunk
            )).subquery("session_note_keys")
            note_read = (
                select(Note.id).select_from(key_rows)
                .join(Note, Note.id == key_rows.c.note_id)
                .prefix_with("STRAIGHT_JOIN", dialect="mysql")
                .with_hint(Note, "FORCE INDEX (PRIMARY)", dialect_name="mysql")
            )
        existing = set(session.execute(
            note_read.order_by(Note.id.asc()).with_for_update(read=True)
        ).scalars())
        if existing != set(chunk):
            raise StudyAuthorityFenceError("AUTHORITY_NOTE_NOT_FOUND", "Authority Note no longer exists.")
        cards_by_note: dict[str, list[Card]] = {key: [] for key in chunk}
        for card in session.execute(
            select(Card).where(Card.note_id.in_(chunk))
            .with_hint(Card, "FORCE INDEX (ix_cards_note_id)", dialect_name="mysql")
            .order_by(Card.note_id.asc(), Card.id.asc()).with_for_update(read=True)
        ).scalars():
            cards_by_note[str(card.note_id)].append(card)
        for key in chunk:
            cards = tuple(cards_by_note[key])
            if not cards:
                raise StudyAuthorityFenceError("AUTHORITY_SIBLINGS_EMPTY", "Authority Note has no active Card sibling.")
            subject = locked_by_logical_note_key[key].subject
            result[key] = LockedStudyAuthoritySiblings(
                learner_user_id=route.learner_user_id,
                subject_id=int(subject.id),
                subject_generation=int(subject.subject_generation),
                live_note_id=key,
                cards=cards,
            )
    return MappingProxyType(result)
