"""Transaction-neutral NOTE state write onto a locked progress row (ADR P10 §2.4).

The caller holds the learner fence and the subject row ``FOR UPDATE``; the
token and state are views of that row. This module owns no route selection,
event, receipt, commit or rollback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthoritySubject,
    StudyAuthorityRoute,
)
from app.services.study_authority_cas_service import (
    StudyAuthorityCASExpectation,
    verify_study_authority_cas,
)
from app.services.study_progress_shadow_codec import (
    STATE_DECODERS,
    StudyProgressCodecError,
    algorithm_state_hash,
    state_document,
)



_MYSQL_SIGNED_BIGINT_MAX = (1 << 63) - 1


class StudyAuthorityWriteError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class StudyAuthorityStateWrite:
    algorithm_key: str
    algorithm_version: str
    state_schema_version: str
    storage_codec: str
    state_payload: Mapping[str, object]
    state_payload_size: int
    algorithm_state_hash: bytes


@dataclass(frozen=True)
class StudyAuthorityWriteResult:
    state: object
    authority_revision: int
    semantic_state_hash: bytes
    # No Card carries progress any more (ADR P10 §2.3); kept for receipts.
    projected_progress: tuple = ()


def _fail(code: str, message: str) -> StudyAuthorityWriteError:
    return StudyAuthorityWriteError(code, message)


def _validate_next_state(
    state_write: StudyAuthorityStateWrite,
    projection: EncodedLegacyProjection,
) -> tuple[dict[str, object], bytes]:
    payload = _validated_state_payload(state_write)
    if projection.comparison.algorithm_state_hash != state_write.algorithm_state_hash:
        raise _fail(
            "PROJECTION_STATE_MISMATCH",
            "Legacy projection was encoded from another Algorithm State.",
        )
    semantic_hash = projection.comparison.semantic_state_hash
    if not isinstance(semantic_hash, bytes) or len(semantic_hash) != 32:
        raise _fail(
            "INVALID_AUTHORITY_WRITE", "Projected semantic state hash is invalid."
        )
    return payload, semantic_hash


def _validated_state_payload(state_write: StudyAuthorityStateWrite) -> dict[str, object]:
    if not isinstance(state_write, StudyAuthorityStateWrite):
        raise _fail("INVALID_AUTHORITY_WRITE", "Next state contract is missing.")
    if (
        isinstance(state_write.state_payload_size, bool)
        or not isinstance(state_write.state_payload_size, int)
        or state_write.state_payload_size < 0
    ):
        raise _fail("INVALID_AUTHORITY_WRITE", "Next state size is invalid.")
    if (
        not isinstance(state_write.algorithm_state_hash, bytes)
        or len(state_write.algorithm_state_hash) != 32
    ):
        raise _fail(
            "INVALID_AUTHORITY_WRITE", "Next Algorithm State hash is invalid."
        )
    try:
        document = state_document(state_write.state_payload)
        if document.size != state_write.state_payload_size:
            raise StudyProgressCodecError(
                "STATE_HASH_MISMATCH", "Next state size does not match its payload."
            )
        # The Algorithm State hash binds the exact persisted identity.
        if algorithm_state_hash(
            document.payload,
            algorithm_key=state_write.algorithm_key,
            algorithm_version=state_write.algorithm_version,
            state_schema_version=state_write.state_schema_version,
            storage_codec=state_write.storage_codec,
        ) != state_write.algorithm_state_hash:
            raise StudyProgressCodecError(
                "STATE_HASH_MISMATCH", "Next Algorithm State hash does not match."
            )
        STATE_DECODERS.decode(
            algorithm_key=state_write.algorithm_key,
            algorithm_version=state_write.algorithm_version,
            state_schema_version=state_write.state_schema_version,
            storage_codec=state_write.storage_codec,
            payload=document.payload,
            expected_size=state_write.state_payload_size,
            expected_hash=state_write.algorithm_state_hash,
        )
    except StudyProgressCodecError as exc:
        raise _fail(exc.code, str(exc)) from exc
    return document.payload


def apply_study_authority_canonical_write(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    expected: StudyAuthorityCASExpectation,
    next_state: StudyAuthorityStateWrite,
    semantic_state_hash: bytes,
    now_utc: datetime,
    allow_algorithm_identity_change: bool = False,
) -> StudyAuthorityWriteResult:
    """Stage the next state and revision on the row; never commit.

    ``semantic_state_hash`` comes from ``project_note_state`` over the next
    state; the caller then writes the row's availability. CAS is the row's
    authority revision and semantic hash.
    """

    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail("INVALID_AUTHORITY_TIME", "Authority time must be naive UTC.")
    if not isinstance(semantic_state_hash, bytes) or len(semantic_state_hash) != 32:
        raise _fail("INVALID_AUTHORITY_WRITE", "Semantic state hash is invalid.")
    verified = verify_study_authority_cas(
        route=route,
        locked=locked,
        expected=expected,
        require_note_authority=True,
    )
    if locked.state is None:
        raise _fail(
            "AUTHORITY_STATE_REQUIRED",
            "First-state materialization requires the complete contributor command.",
        )
    state_payload = _validated_state_payload(next_state)
    state, next_revision = _stage_state_and_token(
        verified_revision=verified.authority_revision,
        verified_semantic_hash=verified.semantic_state_hash,
        locked=locked,
        next_state=next_state,
        state_payload=state_payload,
        semantic_hash=semantic_state_hash,
        now_utc=now_utc,
        allow_algorithm_identity_change=allow_algorithm_identity_change,
    )
    return StudyAuthorityWriteResult(
        state=state,
        authority_revision=next_revision,
        semantic_state_hash=semantic_state_hash,
        projected_progress=(),
    )


def _stage_state_and_token(
    *,
    verified_revision: int,
    verified_semantic_hash: bytes | None,
    locked: LockedStudyAuthoritySubject,
    next_state: StudyAuthorityStateWrite,
    state_payload: dict[str, object],
    semantic_hash: bytes,
    now_utc: datetime,
    allow_algorithm_identity_change: bool,
) -> tuple[object, int]:
    current_identity = (
        str(locked.state.algorithm_key),
        str(locked.state.algorithm_version),
        str(locked.state.state_schema_version),
        str(locked.state.storage_codec),
    )
    next_identity = (
        next_state.algorithm_key,
        next_state.algorithm_version,
        next_state.state_schema_version,
        next_state.storage_codec,
    )
    if next_identity != current_identity and not allow_algorithm_identity_change:
        raise _fail(
            "ALGORITHM_IDENTITY_CHANGE_UNAUTHORIZED",
            "Only a requested Algorithm switch may change the state identity.",
        )
    if semantic_hash == verified_semantic_hash and next_identity == current_identity:
        raise _fail(
            "NON_MATERIAL_AUTHORITY_WRITE",
            "An unchanged state must not advance the authority revision.",
        )
    if verified_revision >= _MYSQL_SIGNED_BIGINT_MAX:
        raise _fail(
            "AUTHORITY_REVISION_EXHAUSTED", "Authority revision cannot advance."
        )

    subject = locked.subject
    state = locked.state
    state.subject_generation = int(subject.subject_generation)
    # This remains the Phase 4 bookkeeping counter; it is not authority CAS.
    state.mirror_revision = int(subject.mirror_revision)
    state.algorithm_key = next_state.algorithm_key
    state.algorithm_version = next_state.algorithm_version
    state.state_schema_version = next_state.state_schema_version
    state.storage_codec = next_state.storage_codec
    state.state_payload = state_payload
    state.state_payload_size = next_state.state_payload_size
    state.algorithm_state_hash = next_state.algorithm_state_hash
    state.semantic_state_hash = semantic_hash
    state.updated_at = now_utc

    next_revision = verified_revision + 1
    locked.token.subject_generation = int(subject.subject_generation)
    locked.token.authority_revision = next_revision
    locked.token.semantic_state_hash = semantic_hash
    locked.token.updated_at = now_utc
    return state, next_revision
