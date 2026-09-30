"""Durable NOTE batch admission and transport; production consumer gate is separate."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.services.db_errors import domain_error_code
from app.services.study_algorithm_registry import AlgorithmResolutionPurpose
from app.services.study_artifact_service import canonical_digest
from app.services.study_note_batch_service import decode_note_batch_payload, decode_note_batch_receipt
from app.services.study_session_authority_pin_service import lock_study_session_authority_pins
from app.validators.review_event import validate_session_event_payload
from app.validators.study_note_batch import validate_note_batch_envelope
from app.validators.study_session_wire import validate_review_event_wire_contract
from models import db
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.study_session_card import StudySessionCard


NOTE_BATCH_JOB_SCHEMA = "study-note-batch-job.v1"


def note_batch_job_from_admission(batch, session):
    """Queue only durable identity, not a second copy of executable events."""
    from app.services.study_session_service import StudySessionError

    if session.wire_schema_version != "study-session.v4" or batch.status != "enqueued":
        raise StudySessionError("BATCH_OUTBOX_INVALID", "Not an executable NOTE admission.", status=409)
    decode_note_batch_payload(batch, session)
    if int(batch.attempt_count) < 0:
        raise StudySessionError("BATCH_OUTBOX_INVALID", "Negative batch retry count.", status=409)
    return {
        "schema_version": NOTE_BATCH_JOB_SCHEMA,
        "session_wire_schema_version": session.wire_schema_version,
        "session_id": session.id,
        "batch_id": batch.batch_id,
        "user_id": batch.user_id,
        "request_hash": batch.request_hash,
        "attempts": int(batch.attempt_count),
    }


def _admission_receipt(batch):
    from app.services.study_session_service import _utc_iso

    result = {
        "schema_version": "study-batch-receipt.v1",
        "status": "already_processed" if batch.status == "completed" else "enqueued",
        "session_id": batch.session_id, "batch_id": batch.batch_id,
        "batch_sequence": batch.batch_sequence, "event_count": batch.event_count,
        "enqueued_at": _utc_iso(batch.enqueued_at),
    }
    if batch.status == "completed":
        result["receipt"] = decode_note_batch_receipt(batch)
    return result


def get_study_session_batch_status(*, user, session_id, batch_id):
    """Return durable completion, never treat a queue acknowledgment as success."""
    import json
    from app.services.study_session_service import StudySessionError, _utc_iso

    try:
        result = db.session.execute(select(StudySessionBatch, StudySession).join(
            StudySession, StudySession.id == StudySessionBatch.session_id,
        ).where(
            StudySession.id == session_id, StudySession.user_id == int(user.id),
            StudySessionBatch.batch_id == batch_id, StudySessionBatch.user_id == int(user.id),
        )).one_or_none()
        if result is None:
            raise StudySessionError("BATCH_NOT_FOUND", "Study batch was not found.", status=404)
        batch, session = result
        response = {
            "schema_version": "study-batch-status.v1", "session_id": session_id,
            "batch_id": batch_id, "batch_sequence": batch.batch_sequence, "status": batch.status,
            "event_count": batch.event_count, "attempt_count": batch.attempt_count,
            "is_final": bool(batch.is_final), "processed_at": _utc_iso(batch.processed_at),
        }
        if batch.status == "completed":
            if session.wire_schema_version == "study-session.v4":
                decode_note_batch_payload(batch, session)
                response["receipt"] = decode_note_batch_receipt(batch)
            else:
                response["receipt"] = json.loads(batch.response_json) if batch.response_json else None
        if batch.status == "failed":
            # Do not expose driver error strings/SQL from exhausted retries.
            response["error_code"] = "BATCH_FAILED"
            try:
                error = json.loads(batch.error_message or "null")
                code = error.get("code") if isinstance(error, dict) else None
                if isinstance(code, str) and len(code) <= 80 and code.replace("_", "").isalnum():
                    response["error_code"] = code
            except (TypeError, ValueError):
                pass
        db.session.rollback()
        return response
    except Exception as exc:
        db.session.rollback()
        if isinstance(exc, StudySessionError):
            raise
        code = domain_error_code(exc)
        if code:
            raise StudySessionError(code, str(exc), status=409) from exc
        raise


def enqueue_note_study_session_batch(*, user, session, route, payload, now=None):
    """Own admission commit/rollback; caller already holds learner/session locks."""
    from app.services.study_session_service import (
        MAX_COMMIT_EVENTS, SESSION_TTL, VALID_RATINGS, StudySessionError,
        _decode_and_validate_session_config, _require_session_algorithm, _validate_session_token,
    )
    from app.services.study_queue_service import enqueue_study_batch

    try:
        envelope = validate_note_batch_envelope(payload)
        admitted_at = now or datetime.utcnow()
        _validate_session_token(session, payload.get("session_token"))
        if payload.get("snapshot_hash") != session.snapshot_hash:
            raise StudySessionError("SNAPSHOT_MISMATCH", "Batch snapshot differs from its session.", status=409)
        config = _decode_and_validate_session_config(session, payload)
        request_hash = canonical_digest(payload)
        existing = db.session.execute(select(StudySessionBatch).where(
            StudySessionBatch.session_id == session.id,
            StudySessionBatch.batch_id == envelope.batch_id,
        ).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != request_hash or existing.user_id != int(user.id):
                raise StudySessionError("BATCH_IDEMPOTENCY_CONFLICT", "Batch ID already has another payload.", status=409)
            decode_note_batch_payload(existing, session)
            if existing.status == "failed":
                raise StudySessionError("BATCH_FAILED", "Batch already failed; its ID cannot be reused.", status=409)
            if existing.status not in {"enqueued", "completed"}:
                raise StudySessionError("BATCH_OUTBOX_INVALID", "Invalid durable batch status.", status=409)
            result = _admission_receipt(existing)
            job = note_batch_job_from_admission(existing, session) if existing.status == "enqueued" else None
            db.session.rollback()
            if job is not None:
                enqueue_study_batch(job)
            return result
        if session.status != "open":
            raise StudySessionError("SESSION_NOT_OPEN", "Study session is not open.", status=409)
        if admitted_at > session.expires_at:
            raise StudySessionError("SESSION_EXPIRED", "Study session has expired.", status=410)
        if admitted_at < session.opened_at:
            raise StudySessionError("INVALID_EVENT_TIME", "Admission predates the session.", status=422)
        _require_session_algorithm(
            key=session.scheduler_algorithm, version=session.algorithm_version,
            purpose=AlgorithmResolutionPurpose.EXISTING_LEASE,
        )
        predecessors = db.session.execute(select(StudySessionBatch).where(
            StudySessionBatch.session_id == session.id,
        ).order_by(StudySessionBatch.batch_sequence).with_for_update().execution_options(populate_existing=True)).scalars().all()
        if any(row.is_final for row in predecessors):
            raise StudySessionError("BATCH_AFTER_FINAL", "A final batch is already admitted.", status=409)
        if any(row.status == "failed" for row in predecessors):
            raise StudySessionError("BATCH_PREDECESSOR_FAILED", "A prior admission failed.", status=409)
        if envelope.sequence != len(predecessors) + 1 or any(
            row.batch_sequence != index for index, row in enumerate(predecessors, 1)
        ):
            raise StudySessionError("NOTE_BATCH_ORDER_CONFLICT", "Batch sequence must extend the admitted prefix.", status=409)
        previous_events = []
        for row in predecessors:
            previous_events.extend(decode_note_batch_payload(row, session)["events"])
        if len(previous_events) + len(envelope.events) > MAX_COMMIT_EVENTS or envelope.sequence > MAX_COMMIT_EVENTS + 1:
            raise StudySessionError("COMMIT_TOO_LARGE", "Session exceeds the NOTE replay bound.", status=413)
        memberships = db.session.execute(select(StudySessionCard).where(
            StudySessionCard.session_id == session.id,
        ).order_by(StudySessionCard.ordinal)).scalars().all()
        pins = lock_study_session_authority_pins(db.session, study_session=session, session_cards=memberships, route=route)
        by_card = {row.card_id: row for row in memberships}
        seen_ids = {event["event_id"] for event in previous_events}
        last_offset = previous_events[-1]["scheduler_offset_ms"] if previous_events else -1
        max_offset = min(int(SESSION_TTL.total_seconds() * 1000), int((admitted_at - session.opened_at).total_seconds() * 1000) + 300000)
        for index, event in enumerate(envelope.events, len(previous_events) + 1):
            event = validate_session_event_payload(event)
            if type(event.get("sequence")) is not int or event["sequence"] != index:
                raise StudySessionError("INVALID_EVENT_SEQUENCE", "Events must extend the admitted event prefix.", status=422)
            event_id = event.get("event_id")
            try:
                UUID(event_id)
            except (TypeError, ValueError, AttributeError) as exc:
                raise StudySessionError("INVALID_EVENT_ID", "Invalid review event UUID.", status=422) from exc
            if event_id in seen_ids:
                raise StudySessionError("DUPLICATE_EVENT_ID", "Event already belongs to an admitted batch.", status=409)
            seen_ids.add(event_id)
            card_id = event.get("card_id")
            member = by_card.get(card_id) if isinstance(card_id, str) else None
            if member is None:
                raise StudySessionError("CARD_OUTSIDE_SESSION", "Card is outside the frozen session.", status=422)
            offset = event.get("scheduler_offset_ms")
            if type(offset) is not int or offset < max(0, last_offset) or offset > max_offset:
                raise StudySessionError("INVALID_EVENT_TIME", "Scheduler offsets must remain within the admitted lease.", status=422)
            last_offset = offset
            if not isinstance(event.get("rating"), str) or event["rating"] not in VALID_RATINGS:
                raise StudySessionError("INVALID_RATING", "Unsupported rating.", status=422)
            if event.get("operation_key") != event_id:
                raise StudySessionError("WIRE_CONTRACT_MISMATCH", "NOTE operation key must equal the canonical event ID.", status=409)
            policy = config.policies.get(member.scheduler_config_hash)
            if not isinstance(policy, dict) or event.get("policy_key") != member.scheduler_config_hash:
                raise StudySessionError("CONFIG_MISMATCH", "Event policy differs from its frozen snapshot.", status=409)
            validate_review_event_wire_contract(
                event, session_schema=session.wire_schema_version, session_id=session.id,
                algorithm_key=session.scheduler_algorithm, algorithm_version=session.algorithm_version,
                policy=policy, event_index=index,
                note_authority=pins.identity_by_session_card_id[member.id],
            )
        batch = StudySessionBatch(
            session_id=session.id, user_id=int(user.id), batch_id=envelope.batch_id,
            batch_sequence=envelope.sequence, event_count=len(envelope.events), attempt_count=0,
            commit_reason=envelope.reason, is_final=envelope.is_final, status="enqueued",
            request_hash=request_hash, payload_json=envelope.encoded, enqueued_at=admitted_at,
        )
        db.session.add(batch)
        job = note_batch_job_from_admission(batch, session)
        result = _admission_receipt(batch)
        db.session.commit()
        enqueue_study_batch(job)
        return result
    except Exception as exc:
        db.session.rollback()
        if isinstance(exc, StudySessionError):
            raise
        code = domain_error_code(exc)
        if code:
            raise StudySessionError(code, str(exc), status=getattr(exc, "status", 409)) from exc
        raise
