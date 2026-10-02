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
    study_progress_shadow_mirror_service,
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
    serialize_card_state,
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
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
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

        if authority_route.mode_code == "NOTE":
            db.session.rollback()
            err_msg = "NOTE authority batches require synchronous canonical commits."
            push_to_dlq(job_payload, err_msg)
            return {
                "status": "authority_mode_unsupported",
                "error_code": "ASYNC_BATCH_NOTE_UNSUPPORTED",
                "error": err_msg,
                "batch_id": batch_id,
            }

        if session.status != "open":
            err_msg = f"Study session {session_id} is no longer open."
            if existing_batch is not None:
                existing_batch.status = "failed"
                existing_batch.error_message = err_msg
                db.session.commit()
            else:
                db.session.rollback()
            push_to_dlq(job_payload, err_msg)
            return {
                "status": "session_not_open",
                "error_code": "SESSION_NOT_OPEN",
                "error": err_msg,
                "batch_id": batch_id,
            }

        if session.wire_schema_version == SESSION_SCHEMA_V4:
            db.session.rollback()
            err_msg = "Study Session v4 cannot enter the legacy asynchronous Card worker."
            push_to_dlq(job_payload, err_msg)
            return {
                "status": "authority_mode_unsupported",
                "error_code": "ASYNC_BATCH_NOTE_UNSUPPORTED",
                "error": err_msg,
                "batch_id": batch_id,
            }

        if existing_batch is not None and existing_batch.payload_json is not None:
            try:
                admitted_job = study_batch_job_from_admission(existing_batch, session)
            except StudySessionError as exc:
                db.session.rollback()
                push_to_dlq(job_payload, str(exc))
                return {
                    "status": "wire_contract_invalid",
                    "error_code": exc.code,
                    "error": str(exc),
                    "batch_id": batch_id,
                }
            # A copied hash does not authenticate the remaining Redis fields.
            # Compare the complete execution envelope against the stored request;
            # retry/delivery metadata is deliberately not part of that contract.
            delivery_fields = {"attempts", "max_retries", "enqueued_at"}
            expected_execution = {
                key: value for key, value in admitted_job.items()
                if key not in delivery_fields
            }
            queued_execution = {
                key: job_payload.get(key) for key in expected_execution
            }
            if study_artifact_service.canonical_digest(
                queued_execution
            ) != study_artifact_service.canonical_digest(expected_execution):
                db.session.rollback()
                err_msg = "Queued execution payload differs from its durable admission."
                push_to_dlq(job_payload, err_msg)
                return {
                    "status": "batch_idempotency_conflict",
                    "error_code": "BATCH_IDEMPOTENCY_CONFLICT",
                    "error": err_msg,
                    "batch_id": batch_id,
                }
            job_payload = admitted_job
            raw_events = admitted_job["events"]
            is_final = admitted_job["is_final"]
            commit_reason = admitted_job["commit_reason"]

        try:
            resolve_study_algorithm(
                session.scheduler_algorithm,
                session.algorithm_version,
                purpose=AlgorithmResolutionPurpose.ACCEPTED_JOB,
            )
        except StudyAlgorithmNotFoundError as exc:
            db.session.rollback()
            err_msg = str(exc)
            logger.error(
                "Rejecting study batch %s because its pinned Algorithm is unavailable: %s",
                batch_id,
                err_msg,
            )
            push_to_dlq(job_payload, err_msg)
            return {
                "status": "algorithm_unavailable",
                "error": err_msg,
                "error_code": exc.code,
                "reason": exc.reason,
                "algorithm_key": exc.key,
                "algorithm_version": exc.version,
                "purpose": exc.purpose.value,
                "lifecycle_state": (
                    exc.lifecycle_state.value
                    if exc.lifecycle_state is not None
                    else None
                ),
            }

        session_cards = (
            StudySessionCard.query.filter_by(session_id=session.id)
            .order_by(StudySessionCard.ordinal.asc())
            .all()
        )
        membership = {row.card_id: row for row in session_cards}
        try:
            session_config = decode_study_session_config(
                session.config_snapshot_json
            )
            validate_payload_composition(session_config, job_payload)
            policies = session_config.policies
        except StudySessionConfigError as exc:
            db.session.rollback()
            err_msg = str(exc)
            logger.error(
                "Rejecting study batch %s because its frozen composition/config is invalid: %s",
                batch_id,
                err_msg,
            )
            push_to_dlq(job_payload, err_msg)
            return {
                "status": "wire_contract_invalid",
                "error_code": "COMPOSITION_SNAPSHOT_MISMATCH",
                "error": err_msg,
                "batch_id": batch_id,
            }

        def reject_wire_contract(code: str, message: str) -> dict[str, Any]:
            # At this point the queued execution envelope has been matched to
            # admission and no progress/mirror mutation has begun. Persist the
            # permanent validation failure so recovery cannot loop on this row.
            if existing_batch is not None:
                existing_batch.status = "failed"
                existing_batch.error_message = f"{code}: {message}"
                db.session.commit()
            else:
                db.session.rollback()
            logger.error("Rejecting study batch %s: %s", batch_id, message)
            push_to_dlq(job_payload, message)
            return {
                "status": "wire_contract_invalid",
                "error_code": code,
                "error": message,
                "batch_id": batch_id,
            }

        try:
            wire_contract = resolve_wire_envelope_contract(
                session.wire_schema_version
            )
        except StudyWireContractError as exc:
            return reject_wire_contract(exc.code, str(exc))
        supplied_session_schema = job_payload.get("session_wire_schema_version")
        if (
            supplied_session_schema is not None
            and supplied_session_schema != wire_contract.session_schema
        ):
            return reject_wire_contract(
                "WIRE_CONTRACT_MISMATCH",
                "Queued batch session schema differs from the pinned session.",
            )
        source_schema = job_payload.get("source_schema_version")
        if source_schema is None and wire_contract.session_schema == SESSION_SCHEMA_V2:
            # Jobs admitted before source-schema pinning were necessarily v2.
            source_schema = wire_contract.batch_schema
        if source_schema not in {
            wire_contract.batch_schema,
            wire_contract.commit_schema,
        }:
            return reject_wire_contract(
                "UNSUPPORTED_BATCH_SCHEMA",
                "Queued batch envelope is incompatible with the pinned session.",
            )
        if not isinstance(raw_events, list):
            return reject_wire_contract(
                "INVALID_EVENTS",
                "Queued batch events must be an array.",
            )

        validated_events: list[dict[str, Any]] = []
        previous_sequence: int | None = None
        previous_offset: int | None = None
        validated_event_ids: set[str] = set()
        for event_index, candidate in enumerate(raw_events, start=1):
            try:
                event = validate_session_event_payload(candidate)
            except ReviewEventPayloadError as exc:
                return reject_wire_contract(exc.code, str(exc))
            card_id = str(event.get("card_id") or "").strip()
            session_card = membership.get(card_id)
            if session_card is None:
                return reject_wire_contract(
                    "CARD_OUTSIDE_SESSION",
                    f"Queued event {event_index} references a card outside the session.",
                )
            event_id = str(event.get("event_id") or "").strip()
            try:
                UUID(event_id)
            except (TypeError, ValueError, AttributeError):
                return reject_wire_contract(
                    "INVALID_EVENT_ID",
                    f"Queued event {event_index} has an invalid event id.",
                )
            if event_id in validated_event_ids:
                return reject_wire_contract(
                    "DUPLICATE_EVENT_ID",
                    f"Queued event {event_index} reuses an event id.",
                )
            sequence = event.get("sequence")
            offset_ms = event.get("scheduler_offset_ms")
            if (
                not isinstance(sequence, int)
                or isinstance(sequence, bool)
                or sequence < 1
                or (
                    previous_sequence is not None
                    and sequence != previous_sequence + 1
                )
            ):
                return reject_wire_contract(
                    "INVALID_EVENT_SEQUENCE",
                    "Queued event sequence must be positive and contiguous.",
                )
            if (
                not isinstance(offset_ms, int)
                or isinstance(offset_ms, bool)
                or offset_ms < 0
                or offset_ms > int(SESSION_TTL.total_seconds() * 1000)
                or (previous_offset is not None and offset_ms < previous_offset)
            ):
                return reject_wire_contract(
                    "INVALID_EVENT_TIME",
                    "Queued scheduler offsets must be monotonic and within the lease.",
                )
            policy_key = str(event.get("policy_key") or "")
            if policy_key != session_card.scheduler_config_hash:
                return reject_wire_contract(
                    "CONFIG_MISMATCH",
                    f"Queued event {event_index} uses the wrong scheduler config.",
                )
            policy = policies.get(policy_key)
            if not isinstance(policy, dict):
                return reject_wire_contract(
                    "CONFIG_MISMATCH",
                    "Queued scheduler config snapshot is missing.",
                )
            try:
                validate_review_event_wire_contract(
                    event,
                    session_schema=session.wire_schema_version,
                    session_id=session.id,
                    algorithm_key=session.scheduler_algorithm,
                    algorithm_version=session.algorithm_version,
                    policy=policy,
                    event_index=event_index,
                )
            except StudyWireContractError as exc:
                return reject_wire_contract(exc.code, str(exc))
            validated_event_ids.add(event_id)
            previous_sequence = sequence
            previous_offset = offset_ms
            validated_events.append(event)
        raw_events = validated_events

        if is_final:
            earlier_admission = (
                StudySessionBatch.query.filter(
                    StudySessionBatch.session_id == session.id,
                    StudySessionBatch.batch_id != batch_id,
                    StudySessionBatch.status.in_(("enqueued", "failed")),
                )
                .with_for_update(read=True)
                .first()
            )
            if earlier_admission is not None:
                if earlier_admission.status == "failed":
                    return reject_wire_contract(
                        "BATCH_PREDECESSOR_FAILED",
                        "A prior admitted batch failed; this session cannot finalize.",
                    )
                # In particular, an empty final batch has no first event whose
                # sequence could otherwise prove its predecessors have finished.
                db.session.rollback()
                return {"status": "waiting_for_predecessor", "batch_id": batch_id}

        # A duplicate request is handled by its durable batch receipt above.
        # Reusing an event ID in a different batch is a conflict, not proof that
        # every other event in this batch was applied. Reject before preparing
        # mirror state or replaying any transition.
        existing_event = (
            ReviewEvent.query.filter(
                ReviewEvent.user_id == user_id,
                ReviewEvent.client_event_id.in_(sorted(validated_event_ids)),
            )
            .with_for_update(read=True)
            .first()
        ) if validated_event_ids else None
        event_conflict = existing_event is not None
        if not event_conflict and raw_events:
            last_session_event = (
                ReviewEvent.query.filter_by(study_session_id=session.id)
                .order_by(ReviewEvent.sequence_no.desc())
                .with_for_update(read=True)
                .first()
            )
            next_sequence = (
                int(last_session_event.sequence_no) + 1
                if last_session_event is not None else 1
            )
            first_sequence = int(raw_events[0]["sequence"])
            if first_sequence > next_sequence:
                # Queue delivery may be reordered after retry/recovery. Preserve
                # the admission and let its predecessor commit on a later pass.
                db.session.rollback()
                return {
                    "status": "waiting_for_predecessor",
                    "batch_id": batch_id,
                    "next_sequence": next_sequence,
                }
            event_conflict = first_sequence < next_sequence
        if event_conflict:
            err_msg = "BATCH_EVENT_CONFLICT: event identity/sequence belongs to an earlier commit."
            if existing_batch is not None:
                existing_batch.status = "failed"
                existing_batch.error_message = err_msg
                db.session.commit()
            else:
                db.session.rollback()
            push_to_dlq(job_payload, err_msg)
            return {
                "status": "failed",
                "error_code": "BATCH_EVENT_CONFLICT",
                "error": err_msg,
                "batch_id": batch_id,
            }

        # Fetch current states of cards
        touched_ids = {str(ev.get("card_id")) for ev in raw_events if ev.get("card_id")}
        card_rows = {
            str(c.id): c
            for c in Card.query.filter(Card.id.in_(sorted(touched_ids))).all()
        } if touched_ids else {}
        if set(card_rows) != touched_ids:
            return reject_wire_contract(
                "BATCH_CARD_MISSING", "An admitted Card no longer exists."
            )

        mirror_plan = None
        if touched_ids and study_progress_shadow_mirror_service.shadow_writes_enabled():
            mirror_plan = study_progress_shadow_mirror_service.prepare_native_mirror(
                db.session,
                learner_user_id=user_id,
                cards=card_rows.values(),
                now_utc=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            locked_progress = (
                study_progress_shadow_mirror_service.locked_progress_map(mirror_plan)
            )
            progress_rows = [
                locked_progress[card_id]
                for card_id in sorted(touched_ids)
                if card_id in locked_progress
            ]
        else:
            progress_rows = (
                CardProgress.query.filter(
                    CardProgress.user_id == user_id,
                    CardProgress.card_id.in_(sorted(touched_ids)),
                )
                .populate_existing()
                .with_for_update()
                .all()
            ) if touched_ids else []
        progress_map = {str(row.card_id): row for row in progress_rows if row.card_id}

        # Initialize card states: use existing progress if present, else session card initial state
        states = {}
        for card_id in touched_ids:
            prog = progress_map.get(card_id)
            if prog is not None:
                states[card_id] = study_service.card_state_from_progress(
                    prog,
                    datetime.now(timezone.utc).replace(tzinfo=None),
                    timezone_name=session.timezone,
                    user_id=user_id,
                )
            elif card_id in membership:
                states[card_id] = deserialize_card_state(
                    json.loads(membership[card_id].initial_state_json)
                )

        replayed_events: list[
            tuple[
                dict[str, Any],
                StudySessionCard,
                Any,
                Any,
                datetime,
                DeckOptions,
                ReviewTransitionResult,
            ]
        ] = []
        # Step 4: Replay review transitions
        for index, raw_event in enumerate(raw_events, start=1):
            card_id = str(raw_event.get("card_id") or "").strip()
            session_card = membership.get(card_id)
            if session_card is None:
                continue

            rating = str(raw_event.get("rating") or "").strip().lower()
            if rating not in VALID_RATINGS:
                continue
            action_contract = resolve_review_action(rating)

            offset_ms = int(raw_event.get("scheduler_offset_ms") or 0)
            answer_at = session.opened_at + timedelta(milliseconds=max(0, offset_ms))

            policy_key = str(raw_event.get("policy_key") or session_card.scheduler_config_hash)
            policy = policies.get(policy_key, {})
            options = deserialize_deck_options(policy.get("config"))

            before = states.get(card_id)
            if before is None:
                continue

            transition = study_service.execute_native_review_transition(
                study_service.NativeReviewTransitionInput(
                    state=before,
                    deck_options=options,
                    reviewed_at=answer_at,
                    action=rating,
                    timezone_name=session.timezone,
                    algorithm_key=session.scheduler_algorithm,
                    algorithm_version=session.algorithm_version,
                    trigger_key=action_contract.trigger_key,
                    trigger_contract_version=(
                        action_contract.trigger_contract_version
                    ),
                )
            )
            after = transition.state
            replayed_events.append(
                (
                    raw_event,
                    session_card,
                    before,
                    after,
                    answer_at,
                    options,
                    transition,
                )
            )
            states[card_id] = after

        # Step 6: Apply mutations to CardProgress and insert ReviewEvents
        created_progress_ids = []
        for card_id in sorted(touched_ids):
            if card_id not in progress_map:
                new_progress = CardProgress(
                    user_id=user_id,
                    card_id=card_id,
                    revision=0,
                )
                db.session.add(new_progress)
                progress_map[card_id] = new_progress
                created_progress_ids.append(card_id)

        if created_progress_ids:
            db.session.flush()

        last_review_event_by_card: dict[str, Any] = {}
        mirror_history_events: list[
            study_progress_shadow_mirror_service.NativeMirrorHistoryEvent
        ] = []
        last_replay_index_by_card = {
            session_card.card_id: index
            for index, (_, session_card, *_rest) in enumerate(replayed_events)
        }
        rating_counts = {r: 0 for r in sorted(VALID_RATINGS)}

        for replay_index, (
            raw_event,
            session_card,
            before,
            _after,
            answer_at,
            options,
            transition,
        ) in enumerate(replayed_events):
            card = card_rows.get(session_card.card_id)
            if not card:
                continue
            rating = str(raw_event["rating"]).lower()
            rating_counts[rating] += 1
            progress_input = None

            if last_replay_index_by_card.get(session_card.card_id) == replay_index:
                final_state = states[session_card.card_id]
                current_prog = progress_map[session_card.card_id]
                next_rev = int(getattr(current_prog, "revision", 0) or 0) + 1
                progress_input = study_service.NativeReviewProgressInput(
                    progress=current_prog,
                    state=final_state,
                    last_reviewed_at=final_state.lastReviewAt or answer_at,
                    revision=next_rev,
                )

            mutation_result = study_service.apply_native_review_mutation(
                study_service.NativeReviewMutationInput(
                    user_id=user_id,
                    card=card,
                    current_state=before,
                    transition=transition,
                    reviewed_at=answer_at,
                    duration_ms=study_service.normalize_review_duration(raw_event.get("duration_ms")),
                    payload=None,
                    local_deck_id=session_card.local_deck_id,
                    scheduler_preset_id=session_card.scheduler_preset_id,
                    scheduler_config_hash=session_card.scheduler_config_hash,
                    timezone_name=session.timezone,
                    deck_options=options,
                    note_type_id=session_card.note_type_id,
                    provenance=study_service.NativeReviewProvenance(
                        source_path="native.session.worker",
                        study_session_id=session.id,
                        client_event_id=str(raw_event.get("event_id")),
                        sequence_no=int(raw_event.get("sequence") or 0),
                        request_id=batch_id,
                        wire_schema_version=session.wire_schema_version,
                    ),
                    progress_input=progress_input,
                )
            )
            last_review_event_by_card[session_card.card_id] = mutation_result.review_event
            mirror_history_events.append(
                study_progress_shadow_mirror_service.NativeMirrorHistoryEvent(
                    review_event=mutation_result.review_event,
                    before_state_hash=study_artifact_service.canonical_digest(
                        serialize_card_state(before)
                    ),
                    after_state_hash=study_artifact_service.canonical_digest(
                        serialize_card_state(transition.state)
                    ),
                )
            )

        db.session.flush()

        # Update last_review_event_id on card progress
        for card_id in sorted(touched_ids):
            prog = progress_map.get(card_id)
            last_ev = last_review_event_by_card.get(card_id)
            if prog and last_ev and last_ev.id:
                prog.last_review_event_id = int(last_ev.id)

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        study_progress_shadow_mirror_service.finalize_native_mirror(
            mirror_plan,
            review_events=tuple(mirror_history_events),
            now_utc=now_utc,
        )

        # Step 7: Update or create StudySessionBatch record
        if existing_batch is None:
            existing_batch = StudySessionBatch(
                session_id=session.id,
                user_id=user_id,
                batch_id=batch_id,
                batch_sequence=int(job_payload.get("batch_sequence", 1) or 1),
                event_count=len(replayed_events),
                status="completed",
                commit_reason=commit_reason,
                is_final=is_final,
                request_hash=job_payload.get("request_hash") or "async-worker",
                processed_at=now_utc,
            )
            db.session.add(existing_batch)
        else:
            existing_batch.status = "completed"
            existing_batch.event_count = len(replayed_events)
            existing_batch.processed_at = now_utc

        # If final batch, commit session
        if is_final:
            session.status = "committed"
            session.committed_at = now_utc
            commit_row = StudySessionCommit.query.filter_by(session_id=session.id).first()
            if commit_row is None:
                db.session.add(
                    StudySessionCommit(
                        session_id=session.id,
                        user_id=user_id,
                        idempotency_key=batch_id,
                        request_hash=job_payload.get("request_hash") or "final-async-batch",
                        response_json=json.dumps({
                            "schema_version": "study-commit-receipt.v1",
                            "success": True,
                            "session_id": session.id,
                            "commit_id": batch_id,
                            "commit_reason": commit_reason,
                            "applied_event_count": len(replayed_events),
                        }),
                    )
                )
            db.session.add(
                AuditLog(
                    user_id=user_id,
                    action="study.session.batch_commit",
                    payload={
                        "session_id": session.id,
                        "batch_id": batch_id,
                        "event_count": len(replayed_events),
                        "is_final": is_final,
                        "commit_reason": commit_reason,
                    },
                )
            )

        db.session.commit()
        mark_batch_processed(batch_identity)

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Study worker finished batch %s for session %s (events=%d, latency=%dms, is_final=%s)",
            batch_id,
            session_id,
            len(replayed_events),
            latency_ms,
            is_final,
        )

        return {
            "status": "completed",
            "batch_id": batch_id,
            "applied_event_count": len(replayed_events),
            "latency_ms": latency_ms,
            "is_final": is_final,
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
