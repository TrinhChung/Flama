"""Pure validation for the Phase 5 learner/Note authority CAS token."""

from __future__ import annotations

from dataclasses import dataclass

from app.repositories.study_authority_repository import (
    LockedStudyAuthoritySubject,
    StudyAuthorityRoute,
)
from app.services.study_progress_shadow_codec import (
    STATE_DECODERS,
    StudyProgressCodecError,
    algorithm_state_hash,
    state_document,
)


class StudyAuthorityCASError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StudyAuthorityCASExpectation:
    enrollment_epoch: int
    subject_generation: int
    authority_revision: int
    semantic_state_hash: bytes | None


@dataclass(frozen=True)
class VerifiedStudyAuthorityCAS:
    learner_user_id: int
    enrollment_epoch: int
    subject_id: int
    subject_generation: int
    authority_revision: int
    semantic_state_hash: bytes | None
    has_current_state: bool


def _fail(code: str, message: str) -> StudyAuthorityCASError:
    return StudyAuthorityCASError(code, message)


def _nonnegative(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail("INVALID_AUTHORITY_CAS", f"{field_name} must be non-negative.")
    return value


def _semantic_hash(value: object) -> bytes | None:
    if value is None:
        return None
    if not isinstance(value, bytes) or len(value) != 32:
        raise _fail(
            "INVALID_AUTHORITY_CAS",
            "semantic_state_hash must contain 32 bytes or be null.",
        )
    return value


def verify_study_authority_cas(
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    expected: StudyAuthorityCASExpectation,
    require_note_authority: bool = True,
) -> VerifiedStudyAuthorityCAS:
    """Verify route, subject token and exact current-state decoder as one CAS."""

    if not isinstance(route, StudyAuthorityRoute):
        raise _fail("INVALID_AUTHORITY_CAS", "Authority route is missing.")
    if not isinstance(locked, LockedStudyAuthoritySubject):
        raise _fail("INVALID_AUTHORITY_CAS", "Locked authority subject is missing.")
    if not isinstance(expected, StudyAuthorityCASExpectation):
        raise _fail("INVALID_AUTHORITY_CAS", "CAS expectation is missing.")
    if require_note_authority and route.mode_code != "NOTE":
        raise _fail(
            "AUTHORITY_MODE_CONFLICT", "Learner is not enrolled in Note authority."
        )
    if route.mode_code not in {"LEGACY", "NOTE"}:
        raise _fail("INVALID_AUTHORITY_CAS", "Authority mode is invalid.")

    expected_epoch = _nonnegative(
        expected.enrollment_epoch, field_name="enrollment_epoch"
    )
    expected_generation = _nonnegative(
        expected.subject_generation, field_name="subject_generation"
    )
    expected_revision = _nonnegative(
        expected.authority_revision, field_name="authority_revision"
    )
    expected_hash = _semantic_hash(expected.semantic_state_hash)
    subject = locked.subject
    token = locked.token
    actual_generation = int(subject.subject_generation)
    actual_revision = int(token.authority_revision)
    actual_hash = _semantic_hash(token.semantic_state_hash)

    if route.epoch != expected_epoch:
        raise _fail(
            "AUTHORITY_EPOCH_CONFLICT", "Learner authority epoch changed."
        )
    if actual_generation != expected_generation:
        raise _fail(
            "SUBJECT_GENERATION_CONFLICT", "Study subject generation changed."
        )
    if actual_revision != expected_revision:
        raise _fail(
            "AUTHORITY_REVISION_CONFLICT", "Study authority revision changed."
        )
    if actual_hash != expected_hash:
        raise _fail(
            "AUTHORITY_STATE_CONFLICT", "Study authority state hash changed."
        )

    state = locked.state
    if state is None:
        if actual_hash is not None:
            raise _fail(
                "AUTHORITY_STATE_DIVERGED",
                "Authority token references a missing current state.",
            )
    else:
        try:
            document = state_document(state.state_payload)
            if document.size != int(state.state_payload_size):
                raise StudyProgressCodecError(
                    "STATE_HASH_MISMATCH", "Stored state size does not match."
                )
            if algorithm_state_hash(document.payload) != bytes(
                state.algorithm_state_hash
            ):
                raise StudyProgressCodecError(
                    "STATE_HASH_MISMATCH", "Stored Algorithm State hash does not match."
                )
            STATE_DECODERS.decode(
                algorithm_key=str(state.algorithm_key),
                algorithm_version=str(state.algorithm_version),
                state_schema_version=str(state.state_schema_version),
                storage_codec=str(state.storage_codec),
                payload=document.payload,
                expected_size=int(state.state_payload_size),
                expected_hash=bytes(state.algorithm_state_hash),
            )
        except StudyProgressCodecError as exc:
            raise _fail(exc.code, str(exc)) from exc
        if bytes(state.semantic_state_hash) != actual_hash:
            raise _fail(
                "AUTHORITY_STATE_DIVERGED",
                "Decoded state and authority token hashes differ.",
            )

    return VerifiedStudyAuthorityCAS(
        learner_user_id=route.learner_user_id,
        enrollment_epoch=route.epoch,
        subject_id=int(subject.id),
        subject_generation=actual_generation,
        authority_revision=actual_revision,
        semantic_state_hash=actual_hash,
        has_current_state=state is not None,
    )
