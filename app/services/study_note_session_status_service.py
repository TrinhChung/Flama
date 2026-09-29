"""Read-only NOTE session continuation checks; current state stays canonical.

The caller holds learner -> session locks. We verify the immutable client log
against durable receipts, not replay ReviewEvent history to infer current state.
All locks are released by the status service's read transaction rollback.
"""

from datetime import datetime

from sqlalchemy import select

from app.services.study_note_batch_service import (
    NoteBatchContinuation, StudyNoteBatchError, decode_note_batch_payload,
    decode_note_batch_receipt, verify_note_batch_continuation,
)
from models import db
from models.study_session_batch import StudySessionBatch
from models.study_session_card import StudySessionCard


def _evidence_invalid(message):
    return StudyNoteBatchError("NOTE_BATCH_EVIDENCE_INVALID", message)


def _read_batch_stream(study_session, *, max_events):
    rows = db.session.execute(
        select(StudySessionBatch).where(StudySessionBatch.session_id == study_session.id)
        .order_by(StudySessionBatch.batch_sequence, StudySessionBatch.id)
        .limit(max_events + 2).with_for_update().execution_options(populate_existing=True)
    ).scalars().all()
    if len(rows) > max_events + 1:
        raise _evidence_invalid("NOTE batch stream exceeds its bound.")
    events = []
    total_events = 0
    completed_count = 0
    unfinished = False
    failed_id = None
    final = None
    for sequence, row in enumerate(rows, start=1):
        if row.batch_sequence != sequence or final is not None:
            raise _evidence_invalid("NOTE batch stream has a gap, duplicate, or batch after final.")
        payload = decode_note_batch_payload(row, study_session)
        total_events += len(payload["events"])
        if total_events > max_events:
            raise _evidence_invalid("NOTE batch stream exceeds its event bound.")
        if row.status == "completed":
            if unfinished:
                raise _evidence_invalid("Completed NOTE batches must form a contiguous prefix.")
            receipt = decode_note_batch_receipt(row)
            events.extend(payload["events"])
            if receipt["cumulative_event_count"] != len(events):
                raise _evidence_invalid("NOTE batch receipt has an invalid cumulative count.")
            completed_count += 1
        elif row.status in {"enqueued", "failed"}:
            unfinished = True
            if row.status == "failed" and failed_id is None:
                failed_id = row.batch_id
        else:
            raise _evidence_invalid("NOTE batch status is invalid.")
        if row.is_final:
            final = row
    if final is not None and final.status == "completed" and study_session.status != "committed":
        raise _evidence_invalid("Completed final batch has no committed session.")
    if rows and study_session.status == "committed" and (
        final is None or final.status != "completed"
    ):
        raise _evidence_invalid("Committed NOTE batch session has no completed final batch.")
    return NoteBatchContinuation(
        batch=rows[completed_count - 1] if completed_count else None,
        previous_events=tuple(events),
    ), {
        "schema_version": "study-note-batch-stream.v1",
        "admitted_batch_count": len(rows),
        "last_completed_batch_sequence": completed_count,
        "completed_event_count": len(events),
        "pending_batch_count": sum(row.status == "enqueued" for row in rows),
        "failed_batch_id": failed_id,
        "final_batch_id": final.batch_id if final else None,
        "final_batch_status": final.status if final else None,
    }


def inspect_note_session_continuation(*, user, study_session, route, check_current, now=None):
    # Lazy import avoids coupling the shared synchronous core to its reader.
    from app.services import study_session_service as core

    context, stream = _read_batch_stream(study_session, max_events=core.MAX_COMMIT_EVENTS)
    # Terminal receipts are historical: a later external review must not make a
    # successfully finalized session look invalid.
    if not check_current:
        return stream, None
    try:
        checked_at = now or datetime.utcnow()
        memberships = db.session.execute(
            select(StudySessionCard).where(StudySessionCard.session_id == study_session.id)
            .order_by(StudySessionCard.ordinal).with_for_update()
            .execution_options(populate_existing=True)
        ).scalars().all()
        pins = core.lock_study_session_authority_pins(
            db.session, study_session=study_session, session_cards=memberships, route=route,
        )
        cards, note_keys, subjects, vectors = core._lock_note_session_context(
            user=user, session=study_session, session_cards=memberships, route=route,
            pins=pins, event_card_ids=sorted(row.card_id for row in memberships),
            committed_at=checked_at, create_token_if_missing=False,
        )
        context = verify_note_batch_continuation(
            study_session=study_session, context=context, route=route, memberships=memberships, pins=pins,
        )
        for note_key in note_keys:
            locked = subjects.locked_by_logical_note_key[note_key]
            current = core.build_note_authority_wire_identity(
                enrollment_epoch=route.epoch, logical_note_key=bytes(locked.subject.logical_note_key),
                subject_generation=locked.subject.subject_generation,
                base_authority_revision=locked.token.authority_revision,
                base_authority_state_hash=locked.state.semantic_state_hash,
            )
            if current != context.expected_by_note[note_key]:
                return stream, "AUTHORITY_STATE_CONFLICT"
        if context.previous_events:
            # Stored admission carries the original composition selection. A
            # continuation cannot silently repin the lease or rehash an edited
            # action log; canonical command fingerprints remain the evidence.
            payload = decode_note_batch_payload(context.batch, study_session)
            _states, replayed, _touched, _ids = core._replay_session_events(
                session=study_session, payload=payload, session_cards=memberships,
                raw_events=list(context.previous_events), note_authority_pins=pins,
                committed_at=checked_at,
            )
            for event, member, before, _after, answer_at, options, transition in replayed:
                identity = pins.identity_by_session_card_id[member.id]
                locked = subjects.locked_by_logical_note_key[identity.logical_note_key]
                siblings, compatibility = vectors[identity.logical_note_key]
                receipt = context.receipt_by_event[event["event_id"]]
                expected = core.StudyAuthorityCASExpectation(
                    enrollment_epoch=receipt.enrollment_epoch, subject_generation=receipt.subject_generation,
                    authority_revision=receipt.authority_revision_before,
                    semantic_state_hash=bytes(receipt.before_state_hash),
                )
                _mutation, command = core._note_session_review_command(
                    user=user, session=study_session, session_card=member, card=cards[member.card_id],
                    raw_event=event, before=before, transition=transition, answer_at=answer_at,
                    options=options, route=route, locked=locked, siblings=siblings,
                    compatibility=compatibility, expected=expected, committed_at=checked_at,
                )
                verified = core.require_existing_note_review_receipt(db.session, command=command)
                if verified.id != receipt.id:
                    raise _evidence_invalid("NOTE batch receipt changed during verification.")
        return stream, "BATCH_FAILED" if stream["failed_batch_id"] else None
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code:
            return stream, str(code)
        raise
