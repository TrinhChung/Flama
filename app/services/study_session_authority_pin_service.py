"""Persist and decode immutable Study Session v4 NOTE authority pins."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthoritySubject,
    StudyAuthorityRoute,
    lock_study_authority_subject,
)
from app.services.anki_scheduler import CardState
from app.services.db_errors import domain_error_code
from app.services.study_progress_shadow_codec import (
    STATE_DECODERS,
    StudyProgressCodecError,
)
from app.validators.study_session_wire import (
    SESSION_SCHEMA_V4,
    StudyNoteAuthorityWireIdentity,
    StudyWireContractError,
    build_note_authority_wire_identity,
)
from models.study_session import StudySession
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.study_session_card import StudySessionCard
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_subject import StudyProgressSubject


class StudySessionAuthorityPinError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


@dataclass(frozen=True)
class LockedStudySessionAuthorityPins:
    learner_user_id: int
    enrollment_epoch: int
    pin_by_session_card_id: Mapping[int, StudySessionAuthorityPin]
    identity_by_session_card_id: Mapping[int, StudyNoteAuthorityWireIdentity]


@dataclass(frozen=True)
class LockedStudySessionAuthoritySubjects:
    learner_user_id: int
    enrollment_epoch: int
    locked_by_logical_note_key: Mapping[str, LockedStudyAuthoritySubject]
    state_by_logical_note_key: Mapping[str, CardState]


PIN_SCHEMA_VERSION = "study-note-authority-pin.v1"


def _fail(code: str, message: str) -> StudySessionAuthorityPinError:
    return StudySessionAuthorityPinError(code, message)


def _validate_route(
    *,
    route: StudyAuthorityRoute,
    learner_user_id: int,
) -> None:
    if (
        not isinstance(route, StudyAuthorityRoute)
        or route.mode_code != "NOTE"
        or not route.persisted
        or route.epoch < 1
    ):
        raise _fail(
            "NOTE_AUTHORITY_UNAVAILABLE",
            "Study Session authority pins require a persisted NOTE enrollment.",
        )
    if route.learner_user_id != learner_user_id:
        raise _fail(
            "WRONG_LEARNER",
            "Study Session authority route belongs to another learner.",
        )


def decode_study_session_authority_pin(
    pin: StudySessionAuthorityPin,
) -> StudyNoteAuthorityWireIdentity:
    if not isinstance(pin, StudySessionAuthorityPin):
        raise _fail("INVALID_SESSION_AUTHORITY_PIN", "Authority pin is missing.")
    if pin.mode_code != "NOTE" or pin.wire_schema_version != SESSION_SCHEMA_V4:
        raise _fail(
            "INVALID_SESSION_AUTHORITY_PIN",
            "Authority pin mode or wire decoder is invalid.",
        )
    try:
        return build_note_authority_wire_identity(
            enrollment_epoch=pin.enrollment_epoch,
            logical_note_key=bytes(pin.logical_note_key),
            subject_generation=pin.subject_generation,
            base_authority_revision=pin.base_authority_revision,
            base_authority_state_hash=bytes(pin.base_semantic_state_hash),
        )
    except (StudyWireContractError, TypeError, ValueError) as exc:
        raise _fail(
            "INVALID_SESSION_AUTHORITY_PIN",
            f"Authority pin cannot be decoded: {exc}",
        ) from exc


def serialize_study_session_authority_pin(
    pin: StudySessionAuthorityPin,
) -> dict[str, str]:
    """Expose only the immutable v4 lease identity, never internal row IDs."""

    return serialize_study_note_authority_identity(
        decode_study_session_authority_pin(pin)
    )


def serialize_study_note_authority_identity(
    identity: StudyNoteAuthorityWireIdentity,
) -> dict[str, str]:
    if not isinstance(identity, StudyNoteAuthorityWireIdentity):
        raise _fail(
            "INVALID_SESSION_AUTHORITY_PIN",
            "Authority wire identity is missing.",
        )
    return {
        "schema_version": PIN_SCHEMA_VERSION,
        "authority_mode": "NOTE",
        "enrollment_epoch": identity.enrollment_epoch,
        "logical_note_key": identity.logical_note_key,
        "subject_generation": identity.subject_generation,
        "base_authority_revision": identity.base_authority_revision,
        "base_authority_state_hash": identity.base_authority_state_hash,
    }


def lock_study_session_authority_subjects(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    logical_note_keys: Sequence[str],
    now_utc: datetime,
    create_token_if_missing: bool = True,
) -> LockedStudySessionAuthoritySubjects:
    """Lock/decode the complete existing-state NOTE vector for v4 issuance."""

    _validate_route(route=route, learner_user_id=route.learner_user_id)
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail(
            "INVALID_AUTHORITY_TIME",
            "Authority session issuance time must be naive UTC.",
        )
    encoded_by_key: dict[str, bytes] = {}
    for raw_key in logical_note_keys:
        if not isinstance(raw_key, str) or not raw_key or raw_key != raw_key.strip():
            raise _fail(
                "INVALID_SESSION_AUTHORITY_SUBJECT",
                "Study Session NOTE identity must be a non-empty canonical string.",
            )
        try:
            encoded = raw_key.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise _fail(
                "INVALID_SESSION_AUTHORITY_SUBJECT",
                "Study Session NOTE identity must be canonical UTF-8.",
            ) from exc
        if len(encoded) > 144:
            raise _fail(
                "INVALID_SESSION_AUTHORITY_SUBJECT",
                "Study Session NOTE identity exceeds 144 UTF-8 bytes.",
            )
        encoded_by_key[raw_key] = encoded
    if not encoded_by_key:
        raise _fail(
            "INCOMPLETE_SESSION_AUTHORITY_SUBJECTS",
            "Study Session v4 requires at least one authority subject.",
        )

    encoded_keys = tuple(sorted(encoded_by_key.values()))
    subjects = tuple(
        session.execute(
            select(StudyProgressSubject)
            .where(
                StudyProgressSubject.learner_user_id == route.learner_user_id,
                StudyProgressSubject.logical_note_key.in_(encoded_keys),
            )
            .order_by(StudyProgressSubject.logical_note_key.asc())
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalars()
    )
    subject_by_encoded_key = {
        bytes(subject.logical_note_key): subject for subject in subjects
    }
    if set(subject_by_encoded_key) != set(encoded_keys):
        raise _fail(
            "INCOMPLETE_SESSION_AUTHORITY_SUBJECTS",
            "One or more Study Session Notes have no current authority subject.",
        )

    locked_by_key: dict[str, LockedStudyAuthoritySubject] = {}
    state_by_key: dict[str, CardState] = {}
    for logical_key in sorted(encoded_by_key, key=lambda item: encoded_by_key[item]):
        encoded_key = encoded_by_key[logical_key]
        subject = subject_by_encoded_key[encoded_key]
        if str(subject.live_note_id or "") != logical_key:
            raise _fail(
                "DETACHED_AUTHORITY_SUBJECT",
                "Study Session authority subject is detached from its live Note.",
            )
        try:
            locked = lock_study_authority_subject(
                session,
                route=route,
                subject=subject,
                now_utc=now_utc,
                create_token_if_missing=create_token_if_missing,
            )
        except Exception as exc:
            code = domain_error_code(exc)
            if code:
                raise _fail(code, str(exc)) from exc
            raise
        state = locked.state
        if state is None:
            raise _fail(
                "AUTHORITY_STATE_REQUIRED",
                "Study Session v4 cannot issue a first-state NOTE lease.",
            )
        try:
            decoded = STATE_DECODERS.decode(
                algorithm_key=str(state.algorithm_key),
                algorithm_version=str(state.algorithm_version),
                state_schema_version=str(state.state_schema_version),
                storage_codec=str(state.storage_codec),
                payload=state.state_payload,
                expected_size=int(state.state_payload_size),
                expected_hash=bytes(state.algorithm_state_hash),
            )
        except StudyProgressCodecError as exc:
            raise _fail(exc.code, str(exc)) from exc
        locked_by_key[logical_key] = locked
        state_by_key[logical_key] = decoded

    return LockedStudySessionAuthoritySubjects(
        learner_user_id=route.learner_user_id,
        enrollment_epoch=route.epoch,
        locked_by_logical_note_key=MappingProxyType(locked_by_key),
        state_by_logical_note_key=MappingProxyType(state_by_key),
    )


def stage_study_session_authority_pin(
    session: Session,
    *,
    study_session: StudySession,
    session_card: StudySessionCard,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    now_utc: datetime,
) -> StudySessionAuthorityPin:
    """Stage one v4 membership pin; never commit or roll back."""

    if (
        not isinstance(study_session, StudySession)
        or not isinstance(session_card, StudySessionCard)
        or session_card.id is None
        or study_session.id is None
        or session_card.session_id != study_session.id
    ):
        raise _fail(
            "INVALID_SESSION_AUTHORITY_PIN",
            "Authority pin requires one persisted session membership.",
        )
    learner_user_id = int(study_session.user_id)
    _validate_route(route=route, learner_user_id=learner_user_id)
    if study_session.wire_schema_version != SESSION_SCHEMA_V4:
        raise _fail(
            "WIRE_CONTRACT_MISMATCH",
            "Only Study Session v4 may persist NOTE authority pins.",
        )
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail(
            "INVALID_AUTHORITY_TIME",
            "Authority pin time must be naive UTC.",
        )
    if not isinstance(locked, LockedStudyAuthoritySubject) or locked.state is None:
        raise _fail(
            "AUTHORITY_STATE_REQUIRED",
            "Study Session v4 requires a locked current NOTE state.",
        )
    subject = locked.subject
    token = locked.token
    state = locked.state
    state_hash = bytes(state.semantic_state_hash)
    if (
        int(subject.learner_user_id) != learner_user_id
        or int(token.subject_id) != int(subject.id)
        or int(token.subject_generation) != int(subject.subject_generation)
        or int(state.subject_generation) != int(subject.subject_generation)
        or bytes(token.semantic_state_hash or b"") != state_hash
    ):
        raise _fail(
            "AUTHORITY_CONTEXT_DIVERGED",
            "Locked subject, token and state cannot produce one session pin.",
        )
    if session.get(StudySessionAuthorityPin, int(session_card.id)) is not None:
        raise _fail(
            "SESSION_AUTHORITY_PIN_EXISTS",
            "Study Session membership already has an authority pin.",
        )
    pin = StudySessionAuthorityPin(
        session_card_id=int(session_card.id),
        learner_user_id=learner_user_id,
        subject_id=int(subject.id),
        mode_code="NOTE",
        enrollment_epoch=int(route.epoch),
        logical_note_key=bytes(subject.logical_note_key),
        subject_generation=int(subject.subject_generation),
        base_authority_revision=int(token.authority_revision),
        base_semantic_state_hash=state_hash,
        wire_schema_version=SESSION_SCHEMA_V4,
        created_at=now_utc,
    )
    decode_study_session_authority_pin(pin)
    session.add(pin)
    return pin


def lock_study_session_authority_pins(
    session: Session,
    *,
    study_session: StudySession,
    session_cards: Sequence[StudySessionCard],
    route: StudyAuthorityRoute,
) -> LockedStudySessionAuthorityPins:
    """Lock and decode the complete v4 membership-pin vector."""

    if not isinstance(study_session, StudySession):
        raise _fail("INVALID_SESSION_AUTHORITY_PIN", "Study Session is missing.")
    learner_user_id = int(study_session.user_id)
    _validate_route(route=route, learner_user_id=learner_user_id)
    if study_session.wire_schema_version != SESSION_SCHEMA_V4:
        raise _fail(
            "WIRE_CONTRACT_MISMATCH",
            "Only Study Session v4 may load NOTE authority pins.",
        )
    membership_by_id: dict[int, StudySessionCard] = {}
    for row in session_cards:
        if (
            not isinstance(row, StudySessionCard)
            or row.id is None
            or row.session_id != study_session.id
            or int(row.id) in membership_by_id
        ):
            raise _fail(
                "INCOMPLETE_SESSION_AUTHORITY_PINS",
                "Session membership vector is invalid or incomplete.",
            )
        membership_by_id[int(row.id)] = row
    if not membership_by_id:
        raise _fail(
            "INCOMPLETE_SESSION_AUTHORITY_PINS",
            "Study Session v4 has no Card memberships.",
        )
    pins = session.execute(
        select(StudySessionAuthorityPin)
        .where(
            StudySessionAuthorityPin.session_card_id.in_(
                sorted(membership_by_id)
            )
        )
        .order_by(StudySessionAuthorityPin.session_card_id.asc())
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    if len(pins) != len(membership_by_id):
        raise _fail(
            "INCOMPLETE_SESSION_AUTHORITY_PINS",
            "Study Session v4 requires exactly one authority pin per Card.",
        )

    pin_by_id: dict[int, StudySessionAuthorityPin] = {}
    identity_by_id: dict[int, StudyNoteAuthorityWireIdentity] = {}
    identity_by_note: dict[str, StudyNoteAuthorityWireIdentity] = {}
    for pin in pins:
        pin_id = int(pin.session_card_id)
        if (
            pin_id not in membership_by_id
            or int(pin.learner_user_id) != learner_user_id
            or int(pin.enrollment_epoch) != route.epoch
        ):
            raise _fail(
                "SESSION_AUTHORITY_EPOCH_CONFLICT",
                "Study Session authority pin does not match its learner epoch.",
            )
        identity = decode_study_session_authority_pin(pin)
        prior = identity_by_note.get(identity.logical_note_key)
        if prior is not None and prior != identity:
            raise _fail(
                "SESSION_AUTHORITY_SUBJECT_CONFLICT",
                "Sibling Cards pin different tokens for one logical Note.",
            )
        identity_by_note[identity.logical_note_key] = identity
        pin_by_id[pin_id] = pin
        identity_by_id[pin_id] = identity
    return LockedStudySessionAuthorityPins(
        learner_user_id=learner_user_id,
        enrollment_epoch=route.epoch,
        pin_by_session_card_id=MappingProxyType(pin_by_id),
        identity_by_session_card_id=MappingProxyType(identity_by_id),
    )


def study_session_authority_pins_are_stale(
    session: Session,
    *,
    study_session: StudySession,
    session_cards: Sequence[StudySessionCard],
) -> bool:
    """Best-effort read check; commit locking remains the definitive fence."""

    if study_session.wire_schema_version != SESSION_SCHEMA_V4:
        return False
    enrollment = session.get(
        StudyAuthorityEnrollment,
        int(study_session.user_id),
    )
    if (
        enrollment is None
        or str(enrollment.mode_code) != "NOTE"
        or int(enrollment.epoch) < 1
    ):
        return True
    membership_ids = {
        int(row.id)
        for row in session_cards
        if row.id is not None and row.session_id == study_session.id
    }
    if len(membership_ids) != len(session_cards) or not membership_ids:
        return True
    pins = tuple(
        session.execute(
            select(StudySessionAuthorityPin).where(
                StudySessionAuthorityPin.session_card_id.in_(
                    sorted(membership_ids)
                )
            )
        ).scalars()
    )
    if len(pins) != len(membership_ids):
        return True
    subject_ids = {
        int(pin.subject_id) for pin in pins if pin.subject_id is not None
    }
    if len(subject_ids) == 0:
        return True
    token_by_subject_id = {
        int(token.subject_id): token
        for token in session.execute(
            select(StudyAuthoritySubjectToken).where(
                StudyAuthoritySubjectToken.subject_id.in_(
                    sorted(subject_ids)
                )
            )
        ).scalars()
    }
    identity_by_note: dict[str, StudyNoteAuthorityWireIdentity] = {}
    for pin in pins:
        try:
            identity = decode_study_session_authority_pin(pin)
        except StudySessionAuthorityPinError:
            return True
        token = (
            token_by_subject_id.get(int(pin.subject_id))
            if pin.subject_id is not None
            else None
        )
        if (
            int(pin.session_card_id) not in membership_ids
            or int(pin.learner_user_id) != int(study_session.user_id)
            or int(pin.enrollment_epoch) != int(enrollment.epoch)
            or token is None
            or int(token.subject_generation) != int(pin.subject_generation)
            or int(token.authority_revision) != int(pin.base_authority_revision)
            or bytes(token.semantic_state_hash or b"")
            != bytes(pin.base_semantic_state_hash)
        ):
            return True
        prior = identity_by_note.get(identity.logical_note_key)
        if prior is not None and prior != identity:
            return True
        identity_by_note[identity.logical_note_key] = identity
    return False
