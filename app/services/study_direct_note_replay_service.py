"""Read-only direct transport replay from a hash-bound canonical NOTE receipt.

Caller holds learner/subject fences. This never evaluates an Algorithm, applies
a command, repairs old receipts, or owns commit/rollback. Existing session
receipts keep their original fingerprint and frozen-session replay path.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from app.services.study_action_runtime import ReviewTransitionResult, resolve_review_action
from app.services.study_algorithm_registry import AlgorithmIdentity
from app.services.study_authority_receipt_service import DIRECT_REPLAY_SCHEMA, StudyAuthorityReceiptError
from app.services.study_progress_contract import AUTHORITY_RECEIPT_SCHEMA_VERSION, STORAGE_CODEC
from app.services.study_progress_history_service import native_review_fact_document, native_review_event_provenance
from app.services.study_progress_shadow_codec import (
    STATE_DECODERS, algorithm_state_hash, canonical_document,
    canonical_typed_document, decode_integer, state_document,
)
from app.services.study_progress_shadow_mapper import encode_identity
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_progress_history_fact import StudyProgressHistoryFact


def direct_note_request_fingerprint(**request) -> bytes:
    """Hash caller intent only; do not include resolved state, policy or time."""
    return canonical_typed_document(
        {"schema_version": DIRECT_REPLAY_SCHEMA, **request},
        too_large_code="AUTHORITY_REQUEST_TOO_LARGE",
    ).digest


def _corrupt(message):
    return StudyAuthorityReceiptError("AUTHORITY_RECEIPT_CORRUPT", message)


def _decode_state(payload, runtime):
    document = state_document(payload)
    return STATE_DECODERS.decode(
        algorithm_key=runtime["algorithm_key"], algorithm_version=runtime["algorithm_version"],
        state_schema_version=runtime["state_schema_version"], storage_codec=STORAGE_CODEC,
        payload=document.payload, expected_size=document.size,
        expected_hash=algorithm_state_hash(document.payload,
            algorithm_key=runtime["algorithm_key"], algorithm_version=runtime["algorithm_version"],
            state_schema_version=runtime["state_schema_version"]),
    )


def read_direct_note_replay(session, *, route, locked, card_id, operation_key, request_fingerprint):
    """Return the original service result, or None only when the key is unused."""
    from app.services.study_service import NativeReviewCommandResult

    encoded_key = encode_identity(operation_key, max_bytes=512, field_name="authority_operation_key")
    receipt = session.execute(select(StudyAuthorityCommandReceipt).where(
        StudyAuthorityCommandReceipt.learner_user_id == route.learner_user_id,
        StudyAuthorityCommandReceipt.operation_key_hash == hashlib.sha256(encoded_key).digest(),
    ).with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
    if receipt is None:
        return None
    if bytes(receipt.operation_key) != encoded_key:
        raise StudyAuthorityReceiptError("AUTHORITY_OPERATION_HASH_COLLISION", "Operation key hash collision.")
    subject = locked.subject
    if (
        route.mode_code != "NOTE" or receipt.subject_id != subject.id
        or bytes(receipt.logical_note_key) != bytes(subject.logical_note_key)
        or receipt.subject_generation != subject.subject_generation
        or receipt.enrollment_epoch != route.epoch
    ):
        raise StudyAuthorityReceiptError("AUTHORITY_RECEIPT_CONTEXT_CONFLICT", "Receipt belongs to another authority epoch or subject generation.")
    if receipt.receipt_schema_version != AUTHORITY_RECEIPT_SCHEMA_VERSION:
        raise StudyAuthorityReceiptError("AUTHORITY_RECEIPT_DECODER_UNAVAILABLE", "Unsupported authority receipt schema.")
    try:
        response = canonical_document(receipt.response_payload, too_large_code="AUTHORITY_RESPONSE_TOO_LARGE")
        if response.size != receipt.response_payload_size or response.digest != bytes(receipt.response_payload_hash):
            raise _corrupt("Authority response hash differs from stored receipt.")
        payload = response.payload
        envelope = payload.get("direct_replay")
        if not isinstance(envelope, dict) or envelope.get("schema_version") != DIRECT_REPLAY_SCHEMA:
            # An old/session receipt is not an unused operation. Never apply it
            # again or infer an original request from current learner progress.
            raise StudyAuthorityReceiptError("AUTHORITY_DIRECT_REPLAY_UNAVAILABLE", "Receipt has no supported direct transport replay envelope.")
        original = canonical_document(envelope["request"], too_large_code="AUTHORITY_REQUEST_TOO_LARGE")
        if original.digest != bytes(receipt.request_fingerprint):
            raise _corrupt("Original command fingerprint differs from receipt.")
        request = original.payload
        transport = request["direct_transport"]
        if transport["schema_version"] != DIRECT_REPLAY_SCHEMA:
            raise _corrupt("Original transport contract is unsupported.")
        if transport["input_fingerprint"] != request_fingerprint.hex():
            raise StudyAuthorityReceiptError("AUTHORITY_OPERATION_REUSED", "Authority operation key was reused with another request.")
        preview_json = envelope["intervals_preview_json"]
        if not isinstance(preview_json, str):
            raise _corrupt("Original preview JSON must be stored as text.")
        previews = canonical_document(json.loads(preview_json), too_large_code="AUTHORITY_RESPONSE_TOO_LARGE")
        if previews.encoded.decode("utf-8") != preview_json or previews.digest.hex() != transport["previews_hash"]:
            raise _corrupt("Original preview result differs from its command fingerprint.")
        expected = {
            "schema_version": AUTHORITY_RECEIPT_SCHEMA_VERSION,
            "operation_key": operation_key, "learner_user_id": route.learner_user_id,
            "subject_id": subject.id, "logical_note_key": bytes(subject.logical_note_key).decode(),
            "subject_generation": receipt.subject_generation, "enrollment_epoch": receipt.enrollment_epoch,
            "authority_revision_before": receipt.authority_revision_before,
            "authority_revision_after": receipt.authority_revision_after,
            "semantic_state_hash": bytes(receipt.after_state_hash).hex(),
            "review_event_id": receipt.review_event_id, "history_fact_id": receipt.history_fact_id,
            "card_id": card_id,
        }
        if any(payload.get(key) != value for key, value in expected.items()):
            raise _corrupt("Authority response identity differs from receipt columns.")
        command_identity = {
            "learner_user_id": str(route.learner_user_id), "card_id": card_id,
            "logical_note_key": bytes(subject.logical_note_key).hex(),
            "subject_generation": str(receipt.subject_generation), "enrollment_epoch": str(receipt.enrollment_epoch),
            "authority_revision": str(receipt.authority_revision_before),
            "semantic_state_hash": bytes(receipt.before_state_hash).hex(),
        }
        if any(request.get(key) != value for key, value in command_identity.items()):
            raise _corrupt("Original command identity differs from receipt columns.")
        runtime = request["runtime"]
        before = _decode_state(request["current_state"], runtime)
        after = _decode_state(request["next_state"], runtime)
        action = resolve_review_action(runtime["action_key"])
        if (
            runtime["trigger_key"] != action.trigger_key
            or runtime["trigger_contract_version"] != action.trigger_contract_version
            or runtime["action_contract_version"] != action.action_contract_version
        ):
            raise _corrupt("Original review action contract is inconsistent.")
        event = session.execute(select(ReviewEvent).where(ReviewEvent.id == receipt.review_event_id)
            .with_for_update(read=True).execution_options(populate_existing=True)).scalar_one_or_none()
        fact = session.execute(select(StudyProgressHistoryFact).where(StudyProgressHistoryFact.id == receipt.history_fact_id)
            .with_for_update(read=True).execution_options(populate_existing=True)).scalar_one_or_none()
        if event is None or fact is None:
            raise _corrupt("Direct replay event/history evidence is missing.")
        _, provenance, event_runtime = native_review_event_provenance(event)
        fact_document = canonical_document(fact.fact_payload, too_large_code="STATE_PAYLOAD_TOO_LARGE")
        if (
            event.user_id != route.learner_user_id or event.card_id != card_id
            or event.reviewed_at != after.lastReviewAt
            or event.rating != action.rating
            or event.duration_ms != (None if request["duration_ms"] is None else decode_integer(request["duration_ms"], field_name="duration_ms"))
            or provenance.get("request_id") != operation_key
            or provenance.get("source_path") != request["provenance"]["source_path"]
            or event_runtime != {**runtime, "scheduler_config_hash": request["scheduler_config_hash"]}
            or fact.review_event_id != event.id or fact.learner_user_id != route.learner_user_id
            or fact.subject_id != subject.id or fact.subject_generation != receipt.subject_generation
            or bytes(fact.before_state_hash or b"") != bytes(receipt.before_state_hash)
            or bytes(fact.after_state_hash or b"") != bytes(receipt.after_state_hash)
            or fact_document.digest != bytes(fact.fact_payload_hash) or fact_document.size != fact.fact_payload_size
            or native_review_fact_document(event).digest != fact_document.digest
        ):
            raise _corrupt("Direct replay event/history evidence is inconsistent.")
        revision = payload["projected_card_revisions"][card_id]
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise _corrupt("Direct replay Card revision is invalid.")
        return NativeReviewCommandResult(
            current_state=before,
            transition=ReviewTransitionResult(action=action, algorithm=AlgorithmIdentity(
                key=runtime["algorithm_key"], version=runtime["algorithm_version"], state_schema_version=runtime["state_schema_version"]),
                state=after, storage_profile=runtime.get("storage_profile")),
            intervals_preview=previews.payload,
            local_deck_id=None if request["local_deck_id"] is None else decode_integer(request["local_deck_id"], field_name="local_deck_id"),
            progress_revision=revision, scheduler_config_hash=request["scheduler_config_hash"],
            authority_mode="NOTE", authority_revision=receipt.authority_revision_after,
            operation_key=operation_key, replayed=True,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise _corrupt("Direct replay payload cannot be decoded.") from exc
