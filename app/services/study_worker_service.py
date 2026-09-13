"""Background worker engine for asynchronous study review batches."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import time
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.repositories.study_repository import is_progress_suspended
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
    is_batch_processed,
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
)
from app.services.study_session_config import (
    StudySessionConfigError,
    decode_study_session_config,
    validate_payload_composition,
)
from app.validators.review_event import (
    ReviewEventPayloadError,
    validate_session_event_payload,
)
from app.validators.study_session_wire import (
    SESSION_SCHEMA_V2,
    StudyWireContractError,
    resolve_wire_envelope_contract,
    validate_review_event_wire_contract,
)
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.study_session_card import StudySessionCard
from models.study_session_commit import StudySessionCommit

logger = logging.getLogger(__name__)


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
    raw_events = job_payload.get("events")
    is_final = bool(job_payload.get("is_final", False))
    commit_reason = str(job_payload.get("commit_reason") or "rollover").strip()

    # Step 1: Distributed locking to prevent concurrent workers from touching the same batch or session
    if not acquire_batch_lock(batch_id, timeout=60):
        logger.warning("Study batch %s is already locked by another worker; skipping.", batch_id)
        return {"status": "locked", "batch_id": batch_id}

    if not acquire_session_lock(session_id, timeout=60):
        release_batch_lock(batch_id)
        logger.warning("Study session %s is locked by another batch; skipping for next pass.", session_id)
        return {"status": "session_locked", "session_id": session_id}

    start_time = time.time()
    try:
        # Step 2: Idempotency check in Redis/memory cache
        if is_batch_processed(batch_id):
            logger.info("Study batch %s already processed (cache hit); acknowledging.", batch_id)
            return {"status": "already_processed", "batch_id": batch_id}

        # Check DB idempotency via StudySessionBatch
        existing_batch = StudySessionBatch.query.filter_by(
            session_id=session_id,
            batch_id=batch_id,
        ).first()
        if existing_batch and existing_batch.status == "completed":
            mark_batch_processed(batch_id)
            logger.info("Study batch %s already completed in DB; acknowledging.", batch_id)
            return {"status": "already_processed", "batch_id": batch_id}

        # Step 3: Load session and validate
        session = StudySession.query.filter_by(
            id=session_id,
            user_id=user_id,
        ).with_for_update().first()

        if session is None:
            err_msg = f"Study session {session_id} not found for user {user_id}."
            logger.error(err_msg)
            push_to_dlq(job_payload, err_msg)
            return {"status": "session_not_found", "error": err_msg}

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

        # Fetch current states of cards
        touched_ids = {str(ev.get("card_id")) for ev in raw_events if ev.get("card_id")}
        card_rows = {
            str(c.id): c
            for c in Card.query.filter(Card.id.in_(sorted(touched_ids))).all()
        } if touched_ids else {}

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
        last_offset = -1
        event_ids: set[str] = set()

        # Step 4: Replay review transitions
        for index, raw_event in enumerate(raw_events, start=1):
            event_id = str(raw_event.get("event_id") or "").strip()
            if event_id:
                event_ids.add(event_id)

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

        # Step 5: Check existing review events to prevent duplicate event insertion
        if event_ids:
            existing_event = ReviewEvent.query.filter(
                ReviewEvent.user_id == user_id,
                ReviewEvent.client_event_id.in_(sorted(event_ids)),
            ).first()
            if existing_event is not None:
                logger.info(
                    "Study batch %s contains already recorded review event %s; marking completed.",
                    batch_id,
                    existing_event.client_event_id,
                )
                if mirror_plan is not None:
                    # A duplicate delivery is a no-op: discard any first-create
                    # coordination row produced by prepare before preserving the
                    # established Redis-marker/DB-receipt order below.
                    db.session.rollback()
                mark_batch_processed(batch_id)
                if existing_batch:
                    existing_batch.status = "completed"
                    existing_batch.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.session.commit()
                return {"status": "already_processed", "batch_id": batch_id}

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
        mark_batch_processed(batch_id)

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
        attempts = int(job_payload.get("attempts", 0)) + 1
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
            try:
                failed_batch = StudySessionBatch.query.filter_by(
                    session_id=session_id,
                    batch_id=batch_id,
                ).first()
                if failed_batch:
                    failed_batch.status = "failed"
                    failed_batch.error_message = str(exc)
                    db.session.commit()
            except Exception:
                db.session.rollback()
            return {"status": "failed", "batch_id": batch_id, "error": str(exc)}

    finally:
        release_session_lock(session_id)
        release_batch_lock(batch_id)


def drain_study_queue(
    *,
    max_jobs: int = 100,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Drain pending jobs from the study queue up to max_jobs."""
    processed_count = 0
    failed_count = 0
    retrying_count = 0
    skipped_count = 0

    while processed_count + failed_count + retrying_count + skipped_count < max_jobs:
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
        elif status == "failed":
            failed_count += 1
        else:
            skipped_count += 1

    return {
        "processed_count": processed_count,
        "failed_count": failed_count,
        "retrying_count": retrying_count,
        "skipped_count": skipped_count,
    }
