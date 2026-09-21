"""Inert, transaction-neutral material write for future NOTE authority.

The caller must already hold the learner/enrollment, subject, token/state and
all sibling ``CardProgress`` locks in the documented canonical order.  This
module deliberately owns no route selection, event, receipt, commit or
rollback.  Product NOTE authority remains unreachable while migration 40 is
LEGACY-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.repositories.study_authority_repository import (
    LockedStudyAuthoritySubject,
    LockedStudyAuthoritySiblings,
    StudyAuthorityRoute,
)
from app.services.study_authority_cas_service import (
    StudyAuthorityCASExpectation,
    verify_study_authority_cas,
)
from app.services.study_authority_projection_encoder import (
    EncodedLegacyProjection,
    EncodedLegacySibling,
)
from app.services.study_progress_shadow_codec import (
    RAW_CARD_PROGRESS_FIELDS,
    STATE_DECODERS,
    StudyProgressCodecError,
    algorithm_state_hash,
    serialize_raw_card_progress,
    state_document,
)
from models.card_progress import CardProgress
from models.study_progress_state import StudyProgressState


_IMMUTABLE_PROGRESS_FIELDS = frozenset({"id", "user_id", "card_id", "created_at"})
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
    state: StudyProgressState
    authority_revision: int
    semantic_state_hash: bytes
    projected_progress: tuple[CardProgress, ...]


def _fail(code: str, message: str) -> StudyAuthorityWriteError:
    return StudyAuthorityWriteError(code, message)


def _validate_next_state(
    state_write: StudyAuthorityStateWrite,
    projection: EncodedLegacyProjection,
) -> tuple[dict[str, object], bytes]:
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
        if algorithm_state_hash(document.payload) != state_write.algorithm_state_hash:
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
    return document.payload, semantic_hash


def _validate_projection_rows(
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    siblings: LockedStudyAuthoritySiblings,
    projection: EncodedLegacyProjection,
    now_utc: datetime,
) -> tuple[tuple[CardProgress, EncodedLegacySibling], ...]:
    if not isinstance(projection, EncodedLegacyProjection):
        raise _fail("INVALID_AUTHORITY_WRITE", "Legacy projection is missing.")
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail("INVALID_AUTHORITY_TIME", "Authority time must be naive UTC.")
    if not isinstance(siblings, LockedStudyAuthoritySiblings):
        raise _fail(
            "INCOMPLETE_LEGACY_PROJECTION",
            "Authoritative sibling lock result is missing.",
        )
    if (
        siblings.learner_user_id != route.learner_user_id
        or siblings.subject_id != int(locked.subject.id)
        or siblings.subject_generation != int(locked.subject.subject_generation)
    ):
        raise _fail(
            "AUTHORITY_SIBLING_FENCE_DIVERGED",
            "Sibling lock result differs from the fenced authority subject.",
        )
    expected_ids = tuple(sibling.card_id for sibling in projection.siblings)
    if not expected_ids or len(set(expected_ids)) != len(expected_ids):
        raise _fail(
            "INCOMPLETE_LEGACY_PROJECTION",
            "Legacy projection must contain a unique, non-empty sibling set.",
        )
    if set(siblings.card_ids) != set(expected_ids):
        raise _fail(
            "INCOMPLETE_LEGACY_PROJECTION",
            "Projection does not match the independently resolved sibling set.",
        )

    validated: list[tuple[CardProgress, EncodedLegacySibling]] = []
    for sibling in projection.siblings:
        row = siblings.progress_by_card_id[sibling.card_id]
        if not isinstance(row, CardProgress) or row.id is None:
            raise _fail(
                "INVALID_LEGACY_PROGRESS",
                f"Card {sibling.card_id} has no persisted compatibility row.",
            )
        if int(row.user_id) != route.learner_user_id or str(row.card_id) != sibling.card_id:
            raise _fail(
                "WRONG_LEARNER",
                f"Card {sibling.card_id} is outside the fenced learner scope.",
            )
        baseline = serialize_raw_card_progress(row)
        if (
            int(row.revision) != sibling.expected_base_revision
            or baseline.size != sibling.baseline_raw_size
            or baseline.digest != sibling.baseline_raw_hash
        ):
            raise _fail(
                "STALE_LEGACY_BASELINE",
                f"Card {sibling.card_id} changed after projection encoding.",
            )
        values = sibling.progress.as_dict()
        if values.get("revision") != sibling.expected_base_revision + 1:
            raise _fail(
                "INVALID_LEGACY_PROJECTION",
                f"Card {sibling.card_id} must advance exactly one legacy revision.",
            )
        if values.get("updated_at") != now_utc:
            raise _fail(
                "INVALID_LEGACY_PROJECTION",
                f"Card {sibling.card_id} projection time differs from authority time.",
            )
        for field_name in _IMMUTABLE_PROGRESS_FIELDS:
            if getattr(row, field_name) != values.get(field_name):
                raise _fail(
                    "INVALID_LEGACY_PROJECTION",
                    f"Card {sibling.card_id} changed immutable {field_name}.",
                )
        projected_raw = serialize_raw_card_progress(sibling.progress)
        if projected_raw.size != sibling.raw.size or projected_raw.digest != sibling.raw.digest:
            raise _fail(
                "INVALID_LEGACY_PROJECTION",
                f"Card {sibling.card_id} projected bytes changed after encoding.",
            )
        validated.append((row, sibling))
    return tuple(validated)


def apply_study_authority_material_write(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    expected: StudyAuthorityCASExpectation,
    next_state: StudyAuthorityStateWrite,
    siblings: LockedStudyAuthoritySiblings,
    projection: EncodedLegacyProjection,
    now_utc: datetime,
) -> StudyAuthorityWriteResult:
    """Stage one existing-state NOTE transition and projection; never commit.

    Event, scheduler-grade history fact and idempotency receipt are deliberately
    outside this slice.  A future canonical command must stage those objects in
    the same caller-owned transaction before exposing this helper to routing.
    """

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
    state_payload, semantic_hash = _validate_next_state(next_state, projection)
    if semantic_hash == verified.semantic_state_hash:
        raise _fail(
            "NON_MATERIAL_AUTHORITY_WRITE",
            "An unchanged state must not advance the authority revision.",
        )
    if verified.authority_revision >= _MYSQL_SIGNED_BIGINT_MAX:
        raise _fail(
            "AUTHORITY_REVISION_EXHAUSTED", "Authority revision cannot advance."
        )
    projected_rows = _validate_projection_rows(
        route=route,
        locked=locked,
        siblings=siblings,
        projection=projection,
        now_utc=now_utc,
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

    next_revision = verified.authority_revision + 1
    locked.token.subject_generation = int(subject.subject_generation)
    locked.token.authority_revision = next_revision
    locked.token.semantic_state_hash = semantic_hash
    locked.token.updated_at = now_utc

    applied_rows: list[CardProgress] = []
    for row, sibling in projected_rows:
        values = sibling.progress.as_dict()
        for field_name in RAW_CARD_PROGRESS_FIELDS:
            if field_name in _IMMUTABLE_PROGRESS_FIELDS:
                continue
            setattr(row, field_name, values[field_name])
            if field_name == "updated_at":
                flag_modified(row, field_name)
        applied_rows.append(row)

    return StudyAuthorityWriteResult(
        state=state,
        authority_revision=next_revision,
        semantic_state_hash=semantic_hash,
        projected_progress=tuple(applied_rows),
    )
