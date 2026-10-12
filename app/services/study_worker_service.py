"""Background worker engine for asynchronous study review batches."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import time
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.repositories.study_repository import is_progress_suspended
from app.repositories.study_batch_repository import StudyBatchRecoveryCursor, read_admitted_batch_page
from app.services import (
    study_artifact_service,
    study_service,
)
from app.services.anki_scheduler import DeckOptions
from app.services.study_action_runtime import ReviewTransitionResult, resolve_review_action
from app.services.study_algorithm_registry import (
    AlgorithmResolutionPurpose,
    StudyAlgorithmNotFoundError,
    resolve_study_algorithm,
)
from app.services.study_queue_service import (
    acquire_batch_lock,
    acquire_session_lock,
    mark_batch_processed,
    pop_study_batch,
    push_to_dlq,
    release_batch_lock,
    release_session_lock,
)
from app.services.study_session_service import (
    SESSION_TTL,
    VALID_RATINGS,
    deserialize_card_state,
    deserialize_deck_options,
    study_batch_job_from_admission,
    StudySessionError,
)
from app.services.study_session_config import (
    StudySessionConfigError,
    decode_study_session_config,
    validate_payload_composition,
)
from app.services.study_note_batch_service import commit_note_study_session_batch
from app.services.study_note_batch_transport_service import NOTE_BATCH_JOB_SCHEMA
from app.validators.review_event import (
    ReviewEventPayloadError,
    validate_session_event_payload,
)
from app.validators.study_session_wire import (
    SESSION_SCHEMA_V2,
    SESSION_SCHEMA_V4,
    StudyWireContractError,
    resolve_wire_envelope_contract,
    validate_review_event_wire_contract,
)
from app.services.review_analytics_projection_service import flush_review_analytics_deltas
from models import db
from models.audit_log import AuditLog
from models.card import Card, load_cards
from models.review_event import ReviewEvent
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.study_session_card import StudySessionCard
from models.study_session_commit import StudySessionCommit
from models.user import User

logger = logging.getLogger(__name__)


def recover_admitted_study_batches(
    *, max_jobs: int = 100, after: StudyBatchRecoveryCursor | None = None,
) -> dict[str, Any]:
    """Requeue committed, incomplete admissions after a lost Redis/local push.

    Duplicate queue deliveries are expected; the worker's durable batch row and
    request hash remain the idempotency authority. No database row is changed.
    """

    if db.session().in_transaction():
        raise RuntimeError("Batch recovery requires a transaction-neutral worker session.")
    jobs: list[dict[str, Any]] = []
    blocked: list[dict[str, str]] = []
    try:
        rows, next_cursor = read_admitted_batch_page(limit=max_jobs, after=after)
        for batch in rows:
            enrollment = db.session.get(StudyAuthorityEnrollment, int(batch.user_id))
            session = db.session.get(StudySession, str(batch.session_id))
            if session is None:
                blocked.append({"batch_id": str(batch.batch_id), "code": "SESSION_NOT_FOUND"})
                continue
            is_note = enrollment is not None and enrollment.mode_code == "NOTE"
            if is_note != (session.wire_schema_version == SESSION_SCHEMA_V4):
                blocked.append({
                    "batch_id": str(batch.batch_id),
                    "code": "ASYNC_BATCH_NOTE_UNSUPPORTED",
                })
                continue
            try:
                jobs.append(study_batch_job_from_admission(batch, session))
            except StudySessionError as exc:
                blocked.append({"batch_id": str(batch.batch_id), "code": exc.code})
    finally:
        # Also release a failed read; never hold a transaction over Redis I/O.
        db.session.rollback()
    from app.services.study_queue_service import enqueue_study_batch

    for job in jobs:
        enqueue_study_batch(job)
    return {
        "scanned_count": len(rows),
        "requeued_count": len(jobs),
        "blocked": blocked,
        "next_cursor": next_cursor,
    }


def _process_admitted_note_batch(job, session, batch, *, user_id):
    """Dispatch only the versioned durable NOTE identity to the canonical core."""
    session_id, batch_id = session.id, batch.batch_id
    expected = {
        "schema_version": NOTE_BATCH_JOB_SCHEMA,
        "session_wire_schema_version": SESSION_SCHEMA_V4,
        "session_id": session.id, "batch_id": batch.batch_id,
        "user_id": user_id, "request_hash": batch.request_hash,
    }
    if (
        any(job.get(key) != value for key, value in expected.items())
        or set(job) - set(expected) - {"attempts", "max_retries", "enqueued_at"}
    ):
        db.session.rollback()
        return {"status": "batch_idempotency_conflict", "error_code": "BATCH_IDEMPOTENCY_CONFLICT", "batch_id": batch_id}
    was_completed = batch.status == "completed"
    if batch.status == "failed":
        db.session.rollback()
        return {"status": "already_failed", "batch_id": batch_id}
    try:
        receipt = commit_note_study_session_batch(
            user=db.session.get(User, user_id), session_id=session_id, batch_id=batch_id,
        )
        mark_batch_processed(f"{session_id}:{batch_id}")
        return {
            "status": "already_processed" if was_completed else "completed",
            "batch_id": batch_id, "receipt": receipt,
            "applied_event_count": receipt["applied_event_count"], "is_final": receipt["is_final"],
        }
    except StudySessionError as exc:
        db.session.rollback()
        if exc.code == "NOTE_BATCH_PREDECESSOR_PENDING":
            # The queue can contain a later hint even after the predecessor's
            # hint was lost. Recover that predecessor without waiting for idle.
            earlier = StudySessionBatch.query.filter(
                StudySessionBatch.session_id == session_id,
                StudySessionBatch.status == "enqueued",
                StudySessionBatch.batch_id != batch_id,
            ).order_by(StudySessionBatch.batch_sequence).first()
            earlier_job = study_batch_job_from_admission(
                earlier, db.session.get(StudySession, session_id),
            ) if earlier is not None else None
            db.session.rollback()
            if earlier_job is not None:
                from app.services.study_queue_service import enqueue_study_batch

                enqueue_study_batch(earlier_job)
            return {"status": "waiting_for_predecessor", "batch_id": batch_id}
        # The canonical core rolled back its writes. Re-lock session -> batch
        # before recording a permanent rejection; preserve another winner.
        StudySession.query.filter_by(id=session_id).populate_existing().with_for_update().first()
        current = StudySessionBatch.query.filter_by(
            session_id=session_id, batch_id=batch_id,
        ).populate_existing().with_for_update().one()
        if current.status == "completed":
            db.session.rollback()
            return {"status": "receipt_invalid", "batch_id": batch_id, "error_code": exc.code}
        current.status = "failed"
        current.error_message = json.dumps({"code": exc.code, "message": str(exc)})
        current.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        push_to_dlq(job, str(exc))
        return {"status": "failed", "batch_id": batch_id, "error_code": exc.code}


def process_single_study_batch(
    job_payload: dict[str, Any],
    *,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Process a single study review batch atomically with idempotency and retry handling."""
    batch_id = str(job_payload.get("batch_id") or "").strip()
    session_id = str(job_payload.get("session_id") or "").strip()
    user_id = job_payload.get("user_id")

    if not batch_id or not session_id or user_id is None:
        logger.error("Rejecting invalid study batch job payload: %s", job_payload)
        return {"status": "invalid_payload", "error": "Missing required job identifiers."}

    user_id = int(user_id)
    # Durable uniqueness is (session_id, batch_id). The Redis/memory cache and
    # batch lock must use that same identity or a different session can be
    # falsely acknowledged as already processed.
    batch_identity = f"{session_id}:{batch_id}"
    raw_events = job_payload.get("events")
    is_final = bool(job_payload.get("is_final", False))
    commit_reason = str(job_payload.get("commit_reason") or "rollover").strip()

    # Step 1: Distributed locking to prevent concurrent workers from touching the same batch or session
    batch_lock_token = acquire_batch_lock(batch_identity, timeout=60)
    if batch_lock_token is None:
        logger.warning("Study batch %s is already locked by another worker; skipping.", batch_id)
        return {"status": "locked", "batch_id": batch_id}

    session_lock_token = acquire_session_lock(session_id, timeout=60)
    if session_lock_token is None:
        release_batch_lock(batch_identity, batch_lock_token)
        logger.warning("Study session %s is locked by another batch; skipping for next pass.", session_id)
        return {"status": "session_locked", "session_id": session_id}

    start_time = time.time()
    try:
        # The processed cache is not authoritative. Always inspect the durable
        # admission hash before accepting even an already-completed replay.
        try:
            authority_route = lock_study_authority_route(
                db.session,
                learner_user_id=user_id,
                allow_note_authority=True,
            )
        except StudyAuthorityFenceError as exc:
            db.session.rollback()
            error_message = str(exc)
            logger.error(
                "Rejecting study batch %s at authority fence: %s",
                batch_id,
                error_message,
            )
            push_to_dlq(job_payload, error_message)
            return {
                "status": "authority_unavailable",
                "error_code": exc.code,
                "error": error_message,
                "batch_id": batch_id,
            }

        # Redis leases are advisory: expiry or a Redis outage must still leave
        # database serialization intact. Use current locking reads in the same
        # session -> batch order as admission and refresh any ORM identity cache.
        session = (
            StudySession.query.filter_by(id=session_id, user_id=user_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if session is None:
            db.session.rollback()
            err_msg = f"Study session {session_id} not found for user {user_id}."
            logger.error(err_msg)
            push_to_dlq(job_payload, err_msg)
            return {"status": "session_not_found", "error": err_msg}

        from app.services.study_retirement_telemetry_service import record_legacy_usage

        record_legacy_usage("worker.batch", wire=session.wire_schema_version)
        existing_batch = (
            StudySessionBatch.query.filter_by(session_id=session_id, batch_id=batch_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        job_request_hash = job_payload.get("request_hash")
        if (
            existing_batch is not None
            and (
                int(existing_batch.user_id) != user_id
                or (existing_batch.payload_json is not None and not job_request_hash)
                or (
                    job_request_hash is not None
                    and existing_batch.request_hash != job_request_hash
                )
            )
        ):
            db.session.rollback()
            err_msg = "Queued batch payload differs from its durable admission row."
            push_to_dlq(job_payload, err_msg)
            return {
                "status": "batch_idempotency_conflict",
                "error_code": "BATCH_IDEMPOTENCY_CONFLICT",
                "error": err_msg,
                "batch_id": batch_id,
            }
        if (
            authority_route.mode_code == "NOTE"
            and session.wire_schema_version == SESSION_SCHEMA_V4
            and job_payload.get("schema_version") == NOTE_BATCH_JOB_SCHEMA
            and existing_batch is not None
        ):
            return _process_admitted_note_batch(job_payload, session, existing_batch, user_id=user_id)
        if existing_batch and existing_batch.status == "completed":
            # The learner fence is a DB row lock even on an idempotent replay.
            db.session.rollback()
            mark_batch_processed(batch_identity)
            logger.info("Study batch %s already completed in DB; acknowledging.", batch_id)
            return {"status": "already_processed", "batch_id": batch_id}
        if existing_batch and existing_batch.status == "failed":
            db.session.rollback()
            return {"status": "already_failed", "batch_id": batch_id}

        db.session.rollback()
        err_msg = "NOTE authority batches require synchronous canonical commits."
        push_to_dlq(job_payload, err_msg)
        return {
            "status": "authority_mode_unsupported",
            "error_code": "ASYNC_BATCH_NOTE_UNSUPPORTED",
            "error": err_msg,
            "batch_id": batch_id,
        }


    except Exception as exc:
        db.session.rollback()
        # A queued admission is the retry-budget source of truth. Persist its
        # next attempt before another queue push so restart recovery cannot
        # silently reset the budget. Direct test-only jobs without admission
        # retain their historical in-payload retry behavior.
        try:
            failed_batch = (
                StudySessionBatch.query.filter_by(
                    session_id=session_id,
                    batch_id=batch_id,
                    user_id=user_id,
                )
                .populate_existing()
                .with_for_update()
                .first()
            )
            if failed_batch is not None and failed_batch.status in {"completed", "failed"}:
                # COMMIT may have succeeded before the connection raised, or a
                # replacement worker may have finished after our rollback. Never
                # overwrite a terminal receipt or consume another retry for it.
                terminal_status = failed_batch.status
                db.session.rollback()
                return {
                    "status": (
                        "already_processed" if terminal_status == "completed"
                        else "already_failed"
                    ),
                    "batch_id": batch_id,
                }
            if failed_batch is not None and failed_batch.payload_json is not None:
                if failed_batch.request_hash != job_payload.get("request_hash"):
                    db.session.rollback()
                    return {
                        "status": "batch_idempotency_conflict",
                        "error_code": "BATCH_IDEMPOTENCY_CONFLICT",
                        "batch_id": batch_id,
                    }
                attempts = int(failed_batch.attempt_count) + 1
                failed_batch.attempt_count = attempts
                if attempts >= max_retries:
                    failed_batch.status = "failed"
                    failed_batch.error_message = str(exc)
                flush_review_analytics_deltas(db.session)
                db.session.commit()
            else:
                db.session.rollback()
                attempts = int(job_payload.get("attempts", 0)) + 1
        except Exception:
            db.session.rollback()
            logger.exception(
                "Study batch %s retry metadata could not be persisted; "
                "leaving its admission row for later recovery.",
                batch_id,
            )
            return {
                "status": "retry_persist_failed",
                "batch_id": batch_id,
                "error": str(exc),
            }
        job_payload["attempts"] = attempts

        if attempts < max_retries:
            logger.warning(
                "Transient error in study batch %s (attempt %d/%d): %s; retrying.",
                batch_id,
                attempts,
                max_retries,
                exc,
            )
            # Re-enqueue to queue for retry
            from app.services.study_queue_service import enqueue_study_batch
            enqueue_study_batch(job_payload)
            return {"status": "retrying", "batch_id": batch_id, "attempts": attempts}
        else:
            logger.exception(
                "Study batch %s exceeded maximum retries (%d): %s; moving to DLQ.",
                batch_id,
                max_retries,
                exc,
            )
            push_to_dlq(job_payload, str(exc))
            return {"status": "failed", "batch_id": batch_id, "error": str(exc)}

    finally:
        release_session_lock(session_id, session_lock_token)
        release_batch_lock(batch_identity, batch_lock_token)


def drain_study_queue(
    *,
    max_jobs: int = 100,
    max_retries: int = 3,
    recover_when_idle: bool = True,
) -> dict[str, Any]:
    """Drain pending jobs from the study queue up to max_jobs."""
    processed_count = 0
    failed_count = 0
    retrying_count = 0
    skipped_count = 0

    while processed_count + failed_count + retrying_count + skipped_count < max_jobs:
        job = pop_study_batch(timeout=0)
        if not job:
            if processed_count + failed_count + retrying_count + skipped_count:
                break
            if not recover_when_idle:
                break
            # The durable admission row survives a crash between DB commit and
            # Redis push. Recover once at the start of an otherwise idle pass.
            recovery = recover_admitted_study_batches(max_jobs=max_jobs)
            if not recovery["requeued_count"]:
                break
            job = pop_study_batch(timeout=0)
            if not job:
                break
        result = process_single_study_batch(job, max_retries=max_retries)
        status = result.get("status")
        if status == "completed":
            processed_count += 1
        elif status == "already_processed":
            skipped_count += 1
        elif status == "retrying":
            retrying_count += 1
        elif status in {"locked", "session_locked", "waiting_for_predecessor"}:
            # A destructive queue pop must not discard a job awaiting a lease
            # or an earlier sequence. Move it to the tail and stop this pass.
            from app.services.study_queue_service import enqueue_study_batch

            enqueue_study_batch(job)
            retrying_count += 1
            break
        elif status == "failed":
            failed_count += 1
        elif status == "retry_persist_failed":
            failed_count += 1
        else:
            skipped_count += 1

    return {
        "processed_count": processed_count,
        "failed_count": failed_count,
        "retrying_count": retrying_count,
        "skipped_count": skipped_count,
    }
