"""Internal NOTE batch continuation; public async admission remains disabled.

Frozen session pins never change. Completed batch payloads plus canonical
command receipts prove which token this session may continue from. They do not
replace the current Note state, which is still locked/checked by the command.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
import hashlib
import json
from types import MappingProxyType
from typing import Any, Mapping

from sqlalchemy import select

from app.repositories.study_authority_repository import lock_study_authority_route
from app.services.study_artifact_service import canonical_digest
from app.validators.study_session_wire import SESSION_SCHEMA_V4, StudyNoteAuthorityWireIdentity
from app.validators.study_note_batch import validate_note_batch_envelope
from models import db
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch


NOTE_BATCH_RECEIPT_SCHEMA = "study-note-batch-receipt.v1"


class StudyNoteBatchError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class NoteBatchContinuation:
    # None only for a read-only status check before the first admission.
    batch: StudySessionBatch | None
    previous_events: tuple[dict[str, Any], ...]
    expected_by_note: Mapping[str, StudyNoteAuthorityWireIdentity] = field(default_factory=dict)
    receipt_by_event: Mapping[str, StudyAuthorityCommandReceipt] = field(default_factory=dict)

    @property
    def previous_event_count(self) -> int:
        return len(self.previous_events)


def _invalid(message: str) -> StudyNoteBatchError:
    return StudyNoteBatchError("NOTE_BATCH_EVIDENCE_INVALID", message)


def decode_note_batch_receipt(batch: StudySessionBatch) -> dict[str, Any]:
    try:
        response = json.loads(batch.response_json)
        digest = response.pop("receipt_hash")
        if (
            digest != canonical_digest(response)
            or response["batch_receipt_schema_version"] != NOTE_BATCH_RECEIPT_SCHEMA
            or response["schema_version"] != "study-commit-receipt.v2"
            or response["batch_id"] != batch.batch_id
            or response["commit_id"] != batch.batch_id
            or response["commit_reason"] != batch.commit_reason
            or response["session_id"] != batch.session_id
            or response["batch_sequence"] != batch.batch_sequence
            or response["request_hash"] != batch.request_hash
            or response["applied_event_count"] != batch.event_count
            or response["is_final"] != bool(batch.is_final)
            or not isinstance(response["is_final"], bool)
            or response["authority_mode"] != "NOTE"
            or response["success"] is not True
            or not isinstance(response["cumulative_event_count"], int)
            or isinstance(response["cumulative_event_count"], bool)
            or response["cumulative_event_count"] < batch.event_count
        ):
            raise _invalid("Stored NOTE batch receipt differs from admission.")
        response["receipt_hash"] = digest
        return response
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise _invalid("Stored NOTE batch receipt cannot be decoded.") from exc


def decode_note_batch_payload(batch: StudySessionBatch, study_session: StudySession) -> dict[str, Any]:
    try:
        payload = json.loads(batch.payload_json)
        envelope = validate_note_batch_envelope(payload)
        token = payload["session_token"]
        if (
            canonical_digest(payload) != batch.request_hash
            or envelope.batch_id != batch.batch_id
            or envelope.sequence != batch.batch_sequence
            or batch.user_id != study_session.user_id
            or batch.session_id != study_session.id
            or envelope.reason != batch.commit_reason or envelope.is_final != bool(batch.is_final)
            or not isinstance(payload.get("events"), list)
            or len(payload["events"]) != batch.event_count
            or not isinstance(token, str)
            or hashlib.sha256(token.encode("utf-8")).hexdigest() != study_session.token_hash
            or payload.get("snapshot_hash") != study_session.snapshot_hash
            or batch.enqueued_at > study_session.expires_at
            or batch.enqueued_at < study_session.opened_at
        ):
            raise _invalid("NOTE batch admission does not match its stored payload/lease.")
        return payload
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise _invalid("NOTE batch admission cannot be decoded.") from exc


def _continuation(
    study_session: StudySession, batch: StudySessionBatch, payload: dict[str, Any], *, max_events: int,
) -> NoteBatchContinuation:
    # Also bound empty batches; never allocate a range from an untrusted sequence.
    if batch.batch_sequence > max_events + 1 or len(payload["events"]) > max_events:
        raise StudyNoteBatchError("COMMIT_TOO_LARGE", "NOTE batch session exceeds its replay bound.")
    # Session mutex serializes this prefix. Do not trust queue order or a mutable
    # CardProgress revision to infer which earlier admissions have completed.
    rows = db.session.execute(
        select(StudySessionBatch)
        .where(
            StudySessionBatch.session_id == study_session.id,
            StudySessionBatch.batch_sequence <= batch.batch_sequence,
        )
        .order_by(StudySessionBatch.batch_sequence, StudySessionBatch.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalars().all()
    if len(rows) != batch.batch_sequence or any(
        row.batch_sequence != number for number, row in enumerate(rows, start=1)
    ):
        raise StudyNoteBatchError("NOTE_BATCH_ORDER_CONFLICT", "Batch sequence has a gap or duplicate.")
    if rows[-1].id != batch.id:
        raise _invalid("Batch prefix does not end at the requested admission.")
    if batch.is_final and db.session.execute(
        select(StudySessionBatch.id).where(
            StudySessionBatch.session_id == study_session.id,
            StudySessionBatch.batch_sequence > batch.batch_sequence,
        ).limit(1).with_for_update()
    ).first() is not None:
        raise StudyNoteBatchError("BATCH_AFTER_FINAL", "Later admissions exist after the final batch.")
    previous_events = []
    for previous in rows[:-1]:
        if previous.status == "failed":
            raise StudyNoteBatchError("BATCH_PREDECESSOR_FAILED", "A prior batch failed permanently.")
        if previous.status != "completed":
            raise StudyNoteBatchError("NOTE_BATCH_PREDECESSOR_PENDING", "A prior batch is not completed.")
        if previous.is_final:
            raise StudyNoteBatchError("BATCH_AFTER_FINAL", "A prior batch finalized this session.")
        prior_payload = decode_note_batch_payload(previous, study_session)
        receipt = decode_note_batch_receipt(previous)
        previous_events.extend(prior_payload["events"])
        if receipt["cumulative_event_count"] != len(previous_events):
            raise _invalid("Prior batch cumulative count differs from its event prefix.")
        if len(previous_events) + len(payload["events"]) > max_events:
            raise StudyNoteBatchError("COMMIT_TOO_LARGE", "NOTE batch session exceeds its replay bound.")

    return NoteBatchContinuation(batch=batch, previous_events=tuple(previous_events))


def verify_note_batch_continuation(
    *, study_session: StudySession, context: NoteBatchContinuation, route, memberships, pins,
) -> NoteBatchContinuation:
    """Verify current-read receipt evidence AFTER canonical subject/vector locks.

    The synchronous NOTE writer locks subjects before receipts. Keep that order
    and use locking reads so an earlier MySQL repeatable-read snapshot cannot
    hide a just-completed predecessor batch.
    """
    identity_by_card = {
        member.card_id: pins.identity_by_session_card_id[member.id]
        for member in memberships
    }
    expected = {pin.logical_note_key: pin for pin in identity_by_card.values()}
    records = db.session.execute(
        select(ReviewEvent, StudyAuthorityCommandReceipt)
        .outerjoin(
            StudyAuthorityCommandReceipt,
            StudyAuthorityCommandReceipt.review_event_id == ReviewEvent.id,
        )
        .where(ReviewEvent.study_session_id == study_session.id)
        .order_by(ReviewEvent.sequence_no)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    if len(records) != context.previous_event_count:
        raise _invalid("Completed batch prefix does not account for every session event.")
    receipt_by_event = {}
    for number, (event, (record, receipt)) in enumerate(zip(context.previous_events, records), start=1):
        try:
            pin = identity_by_card[event["card_id"]]
            prior = expected[pin.logical_note_key]
            if (
                receipt is None
                or event["sequence"] != number or record.sequence_no != number
                or record.client_event_id != event["event_id"]
                or record.card_id != event["card_id"]
                or record.user_id != route.learner_user_id
                or receipt.learner_user_id != route.learner_user_id
                or bytes(receipt.operation_key).decode("utf-8") != event["operation_key"]
                or bytes(receipt.logical_note_key).decode("utf-8") != pin.logical_note_key
                or receipt.subject_generation != int(pin.subject_generation)
                or receipt.enrollment_epoch != int(pin.enrollment_epoch)
                or receipt.authority_revision_before != int(prior.base_authority_revision)
                or receipt.authority_revision_after != receipt.authority_revision_before + 1
                or bytes(receipt.before_state_hash).hex() != prior.base_authority_state_hash
                or len(bytes(receipt.after_state_hash)) != 32
            ):
                raise _invalid("A prior event cannot prove its NOTE revision/hash chain.")
            expected[pin.logical_note_key] = replace(
                prior,
                base_authority_revision=str(receipt.authority_revision_after),
                base_authority_state_hash=bytes(receipt.after_state_hash).hex(),
            )
            receipt_by_event[event["event_id"]] = receipt
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            raise _invalid("A prior NOTE event/receipt is malformed.") from exc
    return replace(
        context,
        expected_by_note=MappingProxyType(expected),
        receipt_by_event=MappingProxyType(receipt_by_event),
    )


def commit_note_study_session_batch(*, user, session_id: str, batch_id: str, now: datetime | None = None):
    """Apply one already-admitted NOTE batch atomically; no API/queue enablement.

    Owns commit/rollback, like synchronous session commit. Only identifiers are
    accepted; payload, sequence, lease and retry identity come from the DB.
    """
    # Lazy import keeps the synchronous core independent of worker transport.
    from app.services.study_session_service import MAX_COMMIT_EVENTS, StudySessionError, commit_study_session

    try:
        route = lock_study_authority_route(
            db.session, learner_user_id=int(user.id), allow_note_authority=True
        )
        study_session = db.session.execute(
            select(StudySession)
            .where(StudySession.id == session_id, StudySession.user_id == int(user.id))
            .with_for_update().execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if study_session is None:
            raise StudySessionError("SESSION_NOT_FOUND", "Study session was not found.", status=404)
        if route.mode_code != "NOTE" or study_session.wire_schema_version != SESSION_SCHEMA_V4:
            raise StudyNoteBatchError("AUTHORITY_MODE_CONFLICT", "NOTE batches require a v4 NOTE lease.")
        batch = db.session.execute(
            select(StudySessionBatch)
            .where(StudySessionBatch.session_id == session_id, StudySessionBatch.batch_id == batch_id)
            .with_for_update().execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if batch is None:
            raise StudyNoteBatchError("BATCH_ADMISSION_REQUIRED", "No durable NOTE batch admission exists.")
        payload = decode_note_batch_payload(batch, study_session)
        if batch.status == "completed":
            result = decode_note_batch_receipt(batch)
            db.session.rollback()
            return result
        if batch.status != "enqueued":
            raise StudyNoteBatchError("BATCH_FAILED", "Batch is not executable.")
        context = _continuation(
            study_session, batch, payload, max_events=MAX_COMMIT_EVENTS
        )
        internal_payload = {
            **payload,
            "schema_version": "study-commit.v3",
            "commit_id": batch.batch_id,
            "commit_reason": batch.commit_reason,
            "events": [*context.previous_events, *payload["events"]],
        }
        return commit_study_session(
            user=user, session_id=session_id, payload=internal_payload, now=now,
            _note_batch=context,
        )
    except Exception as exc:
        db.session.rollback()
        if isinstance(exc, StudySessionError):
            raise
        code = getattr(exc, "code", None)
        if code:
            raise StudySessionError(code, str(exc), status=409) from exc
        raise
