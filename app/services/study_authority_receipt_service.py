"""Durable replay receipt for the existing-state NOTE command.

The caller must already hold the learner and subject lock prefix. Receipt
lookup happens before NOTE CAS verification so an exact committed retry can
replay its stored response even though the subject revision has advanced. New
execution, event/fact and receipt remain in one caller-owned transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Any, Mapping

from sqlalchemy import and_ as sa_and, select
from sqlalchemy.orm import Session

from app.services.stats_overview import normalize_review_mode
from app.services.study_authority_command_service import (
    ExistingStateNoteReviewCommand,
    ExistingStateNoteReviewResult,
    apply_existing_state_note_review,
)
from app.repositories.study_authority_repository import StudyAuthorityRoute
from app.services.study_progress_contract import AUTHORITY_RECEIPT_SCHEMA_VERSION
from app.services.study_progress_shadow_codec import (
    StudyProgressCodecError,
    canonical_document,
    canonical_typed_document,
    serialize_card_state,
)
from app.services.study_progress_shadow_mapper import encode_identity
from app.services.study_service import normalize_review_duration
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_progress_subject import StudyProgressSubject

DIRECT_REPLAY_SCHEMA = "study-direct-note-replay.v1"


class StudyAuthorityReceiptError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


@dataclass(frozen=True)
class IdempotentExistingStateNoteReviewCommand:
    operation_key: str
    command: ExistingStateNoteReviewCommand
    direct_request_fingerprint: bytes | None = None
    direct_previews: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class IdempotentExistingStateNoteReviewResult:
    receipt: StudyAuthorityCommandReceipt
    replayed: bool
    response_payload: Mapping[str, Any]
    applied: ExistingStateNoteReviewResult | None


@dataclass(frozen=True)
class _ReceiptIdentity:
    operation_key: bytes
    operation_key_hash: bytes
    request_fingerprint: bytes
    request_payload: Mapping[str, Any]


def _fail(code: str, message: str) -> StudyAuthorityReceiptError:
    return StudyAuthorityReceiptError(code, message)


def _direct_transport_material(command: IdempotentExistingStateNoteReviewCommand) -> dict[str, Any]:
    if command.direct_request_fingerprint is None and command.direct_previews is None:
        return {}
    if (
        not isinstance(command.direct_request_fingerprint, bytes)
        or len(command.direct_request_fingerprint) != 32
        or not isinstance(command.direct_previews, Mapping)
        or set(command.direct_previews) != {"again", "hard", "good", "easy"}
        or command.command.review.provenance.source_path not in {"native.rest", "native.mcp"}
    ):
        raise _fail("INVALID_AUTHORITY_RECEIPT", "Direct replay context is invalid.")
    previews = canonical_document(command.direct_previews, too_large_code="AUTHORITY_RESPONSE_TOO_LARGE")
    return {"direct_transport": {
        "schema_version": DIRECT_REPLAY_SCHEMA,
        "input_fingerprint": command.direct_request_fingerprint.hex(),
        "previews_hash": previews.digest.hex(),
    }}


def _build_receipt_identity(
    command: IdempotentExistingStateNoteReviewCommand,
) -> _ReceiptIdentity:
    if not isinstance(command, IdempotentExistingStateNoteReviewCommand):
        raise _fail("INVALID_AUTHORITY_RECEIPT", "Receipt command is missing.")
    base = command.command
    if not isinstance(base, ExistingStateNoteReviewCommand):
        raise _fail("INVALID_AUTHORITY_RECEIPT", "NOTE command is missing.")
    route = base.route
    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE":
        raise _fail(
            "AUTHORITY_MODE_CONFLICT",
            "Authority receipt requires one fenced NOTE route.",
        )
    subject = base.locked.subject
    if (
        subject.id is None
        or int(subject.learner_user_id) != route.learner_user_id
        or int(subject.subject_generation) < 1
        or int(route.epoch) < 0
    ):
        raise _fail(
            "AUTHORITY_RECEIPT_CONTEXT_CONFLICT",
            "Authority receipt context does not identify one learner and subject.",
        )
    expected_hash = base.expected.semantic_state_hash
    if not isinstance(expected_hash, bytes) or len(expected_hash) != 32:
        raise _fail(
            "INVALID_AUTHORITY_RECEIPT",
            "Authority receipt requires a 32-byte expected state hash.",
        )
    operation_key = command.operation_key
    if (
        not isinstance(operation_key, str)
        or not operation_key
        or operation_key != operation_key.strip()
    ):
        raise _fail(
            "INVALID_AUTHORITY_OPERATION_KEY",
            "Authority operation key must be a non-empty canonical string.",
        )
    try:
        encoded_key = encode_identity(
            operation_key,
            max_bytes=512,
            field_name="authority_operation_key",
        )
    except StudyProgressCodecError as exc:
        raise _fail(exc.code, str(exc)) from exc

    provenance = base.review.provenance
    provenance_key = provenance.request_id or provenance.client_event_id
    if provenance_key != operation_key:
        raise _fail(
            "AUTHORITY_OPERATION_PROVENANCE_MISMATCH",
            "Authority operation key must match native event provenance.",
        )
    try:
        current_state = serialize_card_state(base.review.current_state)
        next_state = serialize_card_state(base.review.transition.state)
        fingerprint = canonical_typed_document(
            {
                "schema_version": AUTHORITY_RECEIPT_SCHEMA_VERSION,
                "learner_user_id": base.route.learner_user_id,
                "logical_note_key": bytes(subject.logical_note_key).hex(),
                "subject_generation": base.expected.subject_generation,
                "enrollment_epoch": base.expected.enrollment_epoch,
                "authority_revision": base.expected.authority_revision,
                "semantic_state_hash": expected_hash.hex(),
                "card_id": str(base.review.card.id),
                "current_state": current_state.payload,
                "next_state": next_state.payload,
                "runtime": base.review.transition.metadata(),
                "reviewed_at": base.review.reviewed_at,
                "duration_ms": normalize_review_duration(
                    base.review.duration_ms
                ),
                "client_payload": base.review.payload,
                "local_deck_id": base.review.local_deck_id,
                "scheduler_preset_id": base.review.scheduler_preset_id,
                "scheduler_config_hash": base.review.scheduler_config_hash,
                "timezone_name": base.review.timezone_name,
                "review_mode": (
                    base.review.review_mode
                    or normalize_review_mode(base.review.current_state.type)
                ),
                "note_type_id": str(
                    base.review.note_type_id
                    or base.review.card.note.note_type_id
                ),
                "provenance": {
                    "source_path": provenance.source_path,
                    "study_session_id": provenance.study_session_id,
                    "client_event_id": provenance.client_event_id,
                    "sequence_no": provenance.sequence_no,
                    "request_id": provenance.request_id,
                    "wire_schema_version": provenance.wire_schema_version,
                },
                **_direct_transport_material(command),
            },
            too_large_code="AUTHORITY_REQUEST_TOO_LARGE",
        )
    except StudyProgressCodecError as exc:
        raise _fail(exc.code, str(exc)) from exc
    return _ReceiptIdentity(
        operation_key=encoded_key,
        operation_key_hash=hashlib.sha256(encoded_key).digest(),
        request_fingerprint=fingerprint.digest,
        request_payload=fingerprint.payload,
    )


def _token_snapshot_is_current(session: Session, *, locked) -> bool:
    """True when no other transaction committed on this subject after our snapshot.

    Every receipt is written in the transaction that advances its subject's
    token, and the caller holds that token FOR UPDATE, so the locked token is
    current. If the snapshot shows the same token, a receipt committed for this
    subject would also be visible in the snapshot.
    """

    token = locked.token
    # The revision lives on the subject row (ADR P10 §2.4); a plain read is the snapshot.
    snapshot = session.execute(
        select(
            StudyProgressSubject.subject_generation,
            StudyProgressSubject.authority_revision,
            StudyProgressSubject.semantic_state_hash,
        ).where(StudyProgressSubject.id == int(locked.subject.id))
    ).first()
    return snapshot is not None and (
        int(snapshot.subject_generation) == int(token.subject_generation)
        and int(snapshot.authority_revision) == int(token.authority_revision)
        and snapshot.semantic_state_hash == token.semantic_state_hash
    )


def lock_operation_receipt(
    session: Session,
    *,
    learner_user_id: int,
    operation_key_hash: bytes,
    locked,
) -> StudyAuthorityCommandReceipt | None:
    """Current receipt for one learner operation, without locking an absent key.

    ``locked`` is the caller's locked subject (token held FOR UPDATE). Locking
    an absent unique key takes a gap lock that neighbouring learners' receipt
    inserts share, and they deadlock. So look in the snapshot first: a visible
    receipt is locked by primary key; an absent one needs no lock when the
    subject token proves the snapshot current. Otherwise read current rows
    with the original locking read.
    """

    operation_filter = (
        StudyAuthorityCommandReceipt.learner_user_id == int(learner_user_id),
        StudyAuthorityCommandReceipt.operation_key_hash == operation_key_hash,
    )
    visible_id = session.execute(
        select(StudyAuthorityCommandReceipt.id).where(*operation_filter)
    ).scalar_one_or_none()
    if visible_id is None and _token_snapshot_is_current(session, locked=locked):
        return None
    receipt = session.execute(
        select(StudyAuthorityCommandReceipt)
        .where(
            StudyAuthorityCommandReceipt.id == int(visible_id)
            if visible_id is not None
            else sa_and(*operation_filter)
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if receipt is None and visible_id is not None:
        # The visible receipt disappeared (reset/delete fence): read current.
        receipt = session.execute(
            select(StudyAuthorityCommandReceipt)
            .where(*operation_filter)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
    return receipt


def _locked_replay(
    session: Session,
    *,
    command: IdempotentExistingStateNoteReviewCommand,
    identity: _ReceiptIdentity,
) -> StudyAuthorityCommandReceipt | None:
    base = command.command
    receipt = lock_operation_receipt(
        session,
        learner_user_id=base.route.learner_user_id,
        operation_key_hash=identity.operation_key_hash,
        locked=base.locked,
    )
    if receipt is None:
        return None
    if bytes(receipt.operation_key) != identity.operation_key:
        raise _fail(
            "AUTHORITY_OPERATION_HASH_COLLISION",
            "Authority operation hash resolves to another operation key.",
        )
    subject = base.locked.subject
    if (
        receipt.subject_id != int(subject.id)
        or bytes(receipt.logical_note_key) != bytes(subject.logical_note_key)
        or int(receipt.subject_generation) != int(subject.subject_generation)
        or int(receipt.enrollment_epoch) != int(base.route.epoch)
    ):
        raise _fail(
            "AUTHORITY_RECEIPT_CONTEXT_CONFLICT",
            "Authority operation belongs to another epoch or subject generation.",
        )
    if bytes(receipt.request_fingerprint) != identity.request_fingerprint:
        raise _fail(
            "AUTHORITY_OPERATION_REUSED",
            "Authority operation key was reused with another request.",
        )
    if receipt.receipt_schema_version != AUTHORITY_RECEIPT_SCHEMA_VERSION:
        raise _fail(
            "AUTHORITY_RECEIPT_DECODER_UNAVAILABLE",
            "Authority receipt schema is not supported by this runtime.",
        )
    try:
        response = canonical_document(
            receipt.response_payload,
            too_large_code="AUTHORITY_RESPONSE_TOO_LARGE",
        )
    except StudyProgressCodecError as exc:
        raise _fail(exc.code, str(exc)) from exc
    if (
        response.size != int(receipt.response_payload_size)
        or response.digest != bytes(receipt.response_payload_hash)
    ):
        raise _fail(
            "AUTHORITY_RECEIPT_CORRUPT",
            "Stored authority receipt response hash does not match.",
        )
    return receipt


def _response_payload(
    command: IdempotentExistingStateNoteReviewCommand,
    result: ExistingStateNoteReviewResult,
) -> dict[str, Any]:
    base = command.command
    subject = base.locked.subject
    logical_note_key = bytes(subject.logical_note_key).decode("utf-8")
    return {
        "schema_version": AUTHORITY_RECEIPT_SCHEMA_VERSION,
        "operation_key": command.operation_key,
        "learner_user_id": base.route.learner_user_id,
        "subject_id": int(subject.id),
        "logical_note_key": logical_note_key,
        "subject_generation": int(subject.subject_generation),
        "enrollment_epoch": int(base.route.epoch),
        "authority_revision_before": int(base.expected.authority_revision),
        "authority_revision_after": int(result.write.authority_revision),
        "semantic_state_hash": result.write.semantic_state_hash.hex(),
        "mirror_revision": int(result.evidence.mirror_revision),
        "review_event_id": int(result.review_event.id),
        "history_fact_id": int(result.history.fact.id),
        "card_id": str(base.review.card.id),
        "projected_card_revisions": _card_revisions(base, result),
    }


def _card_revisions(base, result: ExistingStateNoteReviewResult) -> dict[str, int]:
    # No Card carries progress: every sibling reports the Note's authority
    # revision (ADR P9-03 §2.9); clients only echo it back.
    revision = int(result.write.authority_revision)
    return {card_id: revision for card_id in sorted(base.siblings.card_ids)}


def _stage_receipt(
    session: Session,
    *,
    command: IdempotentExistingStateNoteReviewCommand,
    identity: _ReceiptIdentity,
    result: ExistingStateNoteReviewResult,
) -> tuple[StudyAuthorityCommandReceipt, Mapping[str, Any]]:
    session.flush()
    if result.review_event.id is None or result.history.fact.id is None:
        raise _fail(
            "UNFLUSHED_AUTHORITY_RECEIPT",
            "Receipt requires persisted event and history identities.",
        )
    try:
        payload = _response_payload(command, result)
        if command.direct_request_fingerprint is not None:
            # Preserve the original canonical command, not a command rebuilt
            # from the newer Note state/time when the HTTP acknowledgment is lost.
            payload["direct_replay"] = {
                "schema_version": DIRECT_REPLAY_SCHEMA,
                "request": dict(identity.request_payload),
                # MySQL JSON's numeric text conversion can change an f64 bit
                # (e.g. 330 / 86400). Preserve exact preview JSON as text;
                # the original command binds its canonical digest separately.
                "intervals_preview_json": canonical_document(
                    command.direct_previews, too_large_code="AUTHORITY_RESPONSE_TOO_LARGE",
                ).encoded.decode("utf-8"),
            }
        response = canonical_document(
            payload,
            too_large_code="AUTHORITY_RESPONSE_TOO_LARGE",
        )
    except (StudyProgressCodecError, UnicodeDecodeError) as exc:
        code = getattr(exc, "code", "INVALID_AUTHORITY_RECEIPT")
        raise _fail(code, str(exc)) from exc
    base = command.command
    receipt = StudyAuthorityCommandReceipt(
        learner_user_id=base.route.learner_user_id,
        subject_id=int(base.locked.subject.id),
        logical_note_key=bytes(base.locked.subject.logical_note_key),
        subject_generation=int(base.locked.subject.subject_generation),
        enrollment_epoch=int(base.route.epoch),
        operation_key=identity.operation_key,
        operation_key_hash=identity.operation_key_hash,
        request_fingerprint=identity.request_fingerprint,
        authority_revision_before=int(base.expected.authority_revision),
        authority_revision_after=int(result.write.authority_revision),
        before_state_hash=bytes(base.expected.semantic_state_hash),
        after_state_hash=result.write.semantic_state_hash,
        review_event_id=int(result.review_event.id),
        history_fact_id=int(result.history.fact.id),
        receipt_schema_version=AUTHORITY_RECEIPT_SCHEMA_VERSION,
        response_payload=response.payload,
        response_payload_size=response.size,
        response_payload_hash=response.digest,
        created_at=base.now_utc,
    )
    session.add(receipt)
    session.flush()
    return receipt, MappingProxyType(dict(response.payload))


def apply_idempotent_existing_state_note_review(
    session: Session,
    *,
    command: IdempotentExistingStateNoteReviewCommand,
) -> IdempotentExistingStateNoteReviewResult:
    """Replay or stage one NOTE command plus receipt; never commit/rollback."""

    identity = _build_receipt_identity(command)
    existing = _locked_replay(session, command=command, identity=identity)
    if existing is not None:
        return IdempotentExistingStateNoteReviewResult(
            receipt=existing,
            replayed=True,
            response_payload=MappingProxyType(dict(existing.response_payload)),
            applied=None,
        )
    applied = apply_existing_state_note_review(session, command=command.command)
    receipt, response = _stage_receipt(
        session,
        command=command,
        identity=identity,
        result=applied,
    )
    return IdempotentExistingStateNoteReviewResult(
        receipt=receipt,
        replayed=False,
        response_payload=response,
        applied=applied,
    )


def require_existing_note_review_receipt(
    session: Session, *, command: IdempotentExistingStateNoteReviewCommand,
) -> StudyAuthorityCommandReceipt:
    """Verify a replay fingerprint without ever applying a missing command."""
    identity = _build_receipt_identity(command)
    receipt = _locked_replay(session, command=command, identity=identity)
    if receipt is None:
        raise _fail("AUTHORITY_RECEIPT_MISSING", "A completed batch command has no receipt.")
    return receipt
