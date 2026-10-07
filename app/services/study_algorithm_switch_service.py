"""Requested Algorithm switch for one NOTE learner/Note row (P5-08, ADR P10).

Transaction-neutral: the caller owns commit/rollback. Lock order: learner
fence -> subject row -> sibling Cards (shared) -> receipt. The target state
must project onto the Note's row (queue, due, suspension), otherwise the switch
is refused before any write; it may carry fields the source state lacks. A Note
on a non-``legacy-anki`` identity is forward-only: ordinary reviews refuse to
rewrite its identity. The switch is evidenced by an idempotent command receipt
bound to the frozen history-cut hash; it is not a review, so it appends no
ReviewEvent or scheduler history fact. No product route calls this command
and no production Algorithm registers an initializer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    is_consolidated,
    lock_study_authority_compatibility,
    lock_study_authority_route,
    lock_study_authority_siblings,
)
from app.services.db_errors import domain_error_code
from app.services.study_algorithm_registry import StudyAlgorithmNotFoundError
from app.services.study_algorithm_switch_preflight_service import (
    StudyAlgorithmSwitchPreflightError,
    preflight_study_algorithm_switch,
)
from app.services.study_authority_cas_service import StudyAuthorityCASExpectation
from app.services.study_authority_write_service import (
    StudyAuthorityStateWrite,
    StudyAuthorityWriteError,
    apply_study_authority_canonical_write,
)
from app.services.study_progress_shadow_codec import (
    StudyProgressCodecError,
    canonical_document,
    canonical_typed_document,
)
from app.services.study_progress_shadow_mapper import encode_identity
from app.services.study_session_authority_pin_service import (
    lock_study_session_authority_subjects,
)
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_session import StudySession
from models.study_session_card import StudySessionCard

SWITCH_RECEIPT_SCHEMA_VERSION = "study-algorithm-switch-receipt.v1"


class StudyAlgorithmSwitchError(RuntimeError):
    def __init__(self, code: str, message: str, *, blockers: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.code = str(code)
        self.blockers = blockers


@dataclass(frozen=True)
class StudyAlgorithmSwitchRequest:
    learner_user_id: int
    logical_note_key: str
    target_key: str
    target_version: str
    operation_key: str
    expected_authority_revision: int | None = None


@dataclass(frozen=True)
class StudyAlgorithmSwitchResult:
    replayed: bool
    response: Mapping[str, Any]


def _fail(code: str, message: str, *, blockers: tuple[str, ...] = ()) -> StudyAlgorithmSwitchError:
    return StudyAlgorithmSwitchError(code, message, blockers=blockers)


def _request_identity(request: StudyAlgorithmSwitchRequest, epoch: int):
    for name in ("logical_note_key", "target_key", "target_version", "operation_key"):
        value = getattr(request, name)
        if not isinstance(value, str) or not value or value != value.strip():
            raise _fail("INVALID_ALGORITHM_SWITCH", f"{name} must be a non-empty canonical string.")
    try:
        operation_key = encode_identity(request.operation_key, max_bytes=512,
            field_name="authority_operation_key")
        fingerprint = canonical_typed_document({
            "schema_version": SWITCH_RECEIPT_SCHEMA_VERSION,
            "learner_user_id": int(request.learner_user_id),
            "enrollment_epoch": int(epoch),
            "logical_note_key": request.logical_note_key,
            "target_key": request.target_key,
            "target_version": request.target_version,
            "expected_authority_revision": request.expected_authority_revision,
        }, too_large_code="AUTHORITY_REQUEST_TOO_LARGE")
    except StudyProgressCodecError as exc:
        raise _fail(exc.code, str(exc)) from exc
    return operation_key, hashlib.sha256(operation_key).digest(), fingerprint.digest


def _replay(session, *, request, route, operation_key, operation_key_hash, fingerprint):
    receipt = session.execute(
        select(StudyAuthorityCommandReceipt).where(
            StudyAuthorityCommandReceipt.learner_user_id == route.learner_user_id,
            StudyAuthorityCommandReceipt.operation_key_hash == operation_key_hash,
        ).with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if receipt is None:
        return None
    if bytes(receipt.operation_key) != operation_key:
        raise _fail("AUTHORITY_OPERATION_HASH_COLLISION", "Operation hash resolves to another key.")
    if (
        receipt.receipt_schema_version != SWITCH_RECEIPT_SCHEMA_VERSION
        or bytes(receipt.request_fingerprint) != fingerprint
        or bytes(receipt.logical_note_key) != request.logical_note_key.encode("utf-8")
    ):
        raise _fail("AUTHORITY_OPERATION_REUSED", "Operation key was reused with another request.")
    response = canonical_document(receipt.response_payload, too_large_code="AUTHORITY_RESPONSE_TOO_LARGE")
    if response.size != int(receipt.response_payload_size) or response.digest != bytes(
        receipt.response_payload_hash
    ):
        raise _fail("AUTHORITY_RECEIPT_CORRUPT", "Stored switch receipt hash does not match.")
    return StudyAlgorithmSwitchResult(replayed=True, response=dict(response.payload))


def apply_study_algorithm_switch(
    session: Session,
    *,
    request: StudyAlgorithmSwitchRequest,
    now_utc: datetime,
) -> StudyAlgorithmSwitchResult:
    """Stage one requested switch atomically; never commit."""

    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail("INVALID_AUTHORITY_TIME", "Switch time must be naive UTC.")
    route = lock_study_authority_route(
        session, learner_user_id=int(request.learner_user_id), allow_note_authority=True)
    if route.mode_code != "NOTE":
        raise _fail("ALGORITHM_SWITCH_REQUIRES_NOTE", "Only NOTE authority stores a per-Note Algorithm.")
    operation_key, operation_key_hash, fingerprint = _request_identity(request, route.epoch)
    try:
        subjects = lock_study_session_authority_subjects(
            session, route=route, logical_note_keys=[request.logical_note_key], now_utc=now_utc)
    except Exception as exc:
        code = domain_error_code(exc)
        if code is None:
            raise
        raise _fail(str(code), str(exc)) from exc
    replay = _replay(session, request=request, route=route, operation_key=operation_key,
        operation_key_hash=operation_key_hash, fingerprint=fingerprint)
    if replay is not None:
        return replay

    locked = subjects.locked_by_logical_note_key[request.logical_note_key]
    current_revision = int(locked.token.authority_revision)
    if (
        request.expected_authority_revision is not None
        and int(request.expected_authority_revision) != current_revision
    ):
        raise _fail("STALE_AUTHORITY_STATE", "Note state changed since the switch was requested.")
    siblings = lock_study_authority_siblings(session, route=route, locked=locked)
    compatibility = lock_study_authority_compatibility(
        session, route=route, locked=locked, siblings=siblings)
    expected = StudyAuthorityCASExpectation(
        enrollment_epoch=int(route.epoch),
        subject_generation=int(locked.subject.subject_generation),
        authority_revision=current_revision,
        semantic_state_hash=bytes(locked.token.semantic_state_hash),
    )
    try:
        preflight = preflight_study_algorithm_switch(
            session, route=route, locked=locked, expected=expected, siblings=siblings,
            compatibility=compatibility, target_key=request.target_key,
            target_version=request.target_version)
    except StudyAlgorithmSwitchPreflightError as exc:
        raise _fail(exc.code, str(exc), blockers=exc.blockers) from exc
    except StudyAlgorithmNotFoundError as exc:
        raise _fail("ALGORITHM_SWITCH_TARGET_UNAVAILABLE", str(exc), blockers=(exc.reason,)) from exc

    target_identity = preflight.target.adapter.identity
    next_state = preflight.target.initializer.initialize(frozen_history_cut=preflight.history_cut)
    if not isinstance(next_state, StudyAuthorityStateWrite) or (
        next_state.algorithm_key, next_state.algorithm_version, next_state.state_schema_version,
        next_state.storage_codec,
    ) != (
        target_identity.key, target_identity.version, target_identity.state_schema_version,
        preflight.target.initializer.state_storage_codec,
    ):
        raise _fail("SWITCH_INITIALIZER_CONTRACT", "Initializer did not return the exact target state.")

    if not is_consolidated(route):
        raise _fail("AUTHORITY_MODE_CONFLICT", "Algorithm switch requires a CONSOLIDATED_V1 route.")
    write = _apply_consolidated_switch(
        session, route=route, locked=locked, expected=expected, next_state=next_state,
        now_utc=now_utc)
    return _finish_switch(
        session, request=request, route=route, locked=locked, expected=expected,
        siblings=siblings, preflight=preflight, write=write, current_revision=current_revision,
        operation_key=operation_key, operation_key_hash=operation_key_hash,
        fingerprint=fingerprint, now_utc=now_utc)


def _apply_consolidated_switch(session, *, route, locked, expected, next_state, now_utc):
    """CONSOLIDATED_V1: the target state must project onto the Note's row (ADR P10)."""

    from app.services import study_consolidated_progress_service as consolidated

    try:
        projection = consolidated.project_subject_state(
            next_state.state_payload, burial=consolidated.note_burial(locked.subject))
    except consolidated.StudyConsolidatedProgressError as exc:
        raise _fail("SWITCH_TARGET_NOT_PROJECTABLE", str(exc), blockers=(exc.code,)) from exc
    try:
        write = apply_study_authority_canonical_write(
            session, route=route, locked=locked, expected=expected, next_state=next_state,
            semantic_state_hash=projection.semantic_state_hash, now_utc=now_utc,
            allow_algorithm_identity_change=True)
    except StudyAuthorityWriteError as exc:
        raise _fail(exc.code, str(exc)) from exc
    consolidated.finalize_consolidated_rewrite(
        route=route, locked=locked, write_result=write, projection=projection, now_utc=now_utc)
    return write


def _finish_switch(session, *, request, route, locked, expected, siblings, preflight, write,
                   current_revision, operation_key, operation_key_hash, fingerprint, now_utc):

    # Old leases pinned the previous token; cancel them like other topology
    # and state rewrites so a stale session cannot commit across the switch.
    affected_sessions = select(StudySessionCard.session_id).where(
        StudySessionCard.card_id.in_(list(siblings.card_ids)))
    for study_session in session.execute(select(StudySession).where(
        StudySession.user_id == route.learner_user_id, StudySession.status == "open",
        StudySession.id.in_(affected_sessions)).order_by(StudySession.id).with_for_update()).scalars():
        study_session.status = "cancelled"

    state = locked.state
    response = canonical_document({
        "schema_version": SWITCH_RECEIPT_SCHEMA_VERSION,
        "operation_key": request.operation_key,
        "learner_user_id": route.learner_user_id,
        "logical_note_key": request.logical_note_key,
        "subject_id": int(locked.subject.id),
        "subject_generation": int(locked.subject.subject_generation),
        "enrollment_epoch": int(route.epoch),
        "authority_revision_before": current_revision,
        "authority_revision_after": int(write.authority_revision),
        "from_algorithm": {
            "key": preflight.history_cut.current_algorithm_key,
            "version": preflight.history_cut.current_algorithm_version,
        },
        "to_algorithm": {"key": state.algorithm_key, "version": state.algorithm_version},
        "history_cut_hash": preflight.history_cut.cut_hash.hex(),
        # No Card carries progress: each sibling reports the Note's authority
        # revision, as review receipts do (ADR P9-03 §2.9).
        "projected_card_revisions": {
            card_id: int(write.authority_revision) for card_id in sorted(siblings.card_ids)
        },
    }, too_large_code="AUTHORITY_RESPONSE_TOO_LARGE")
    session.add(StudyAuthorityCommandReceipt(
        learner_user_id=route.learner_user_id,
        subject_id=int(locked.subject.id),
        logical_note_key=bytes(locked.subject.logical_note_key),
        subject_generation=int(locked.subject.subject_generation),
        enrollment_epoch=int(route.epoch),
        operation_key=operation_key,
        operation_key_hash=operation_key_hash,
        request_fingerprint=fingerprint,
        authority_revision_before=current_revision,
        authority_revision_after=int(write.authority_revision),
        before_state_hash=bytes(expected.semantic_state_hash),
        after_state_hash=write.semantic_state_hash,
        review_event_id=None,
        history_fact_id=None,
        receipt_schema_version=SWITCH_RECEIPT_SCHEMA_VERSION,
        response_payload=response.payload,
        response_payload_size=response.size,
        response_payload_hash=response.digest,
        created_at=now_utc,
    ))
    session.flush()
    return StudyAlgorithmSwitchResult(replayed=False, response=dict(response.payload))
