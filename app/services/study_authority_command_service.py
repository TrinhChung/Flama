"""Existing-state NOTE review command on the consolidated progress row (ADR P10).

The caller holds the learner fence, the subject row and its read-locked Card
siblings. The command stages one native ReviewEvent, the next state, revision
and availability on the row, and the native history fact in the caller's
transaction. It never commits or rolls back. Study Session v4 and direct
REST/MCP answers compose it with durable receipts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthorityCompatibility,
    LockedStudyAuthoritySiblings,
    LockedStudyAuthoritySubject,
    StudyAuthorityRoute,
    is_consolidated,
)
from app.services.study_authority_cas_service import (
    StudyAuthorityCASExpectation,
    verify_study_authority_cas,
)
from app.services.study_authority_evidence_service import StudyAuthorityEvidenceResult
from app.services.study_authority_write_service import (
    StudyAuthorityStateWrite,
    StudyAuthorityWriteResult,
    apply_study_authority_canonical_write,
)
from app.services.study_progress_contract import (
    ALGORITHM_KEY,
    ALGORITHM_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_history_service import (
    NativeHistoryFactInput,
    NativeHistoryFactResult,
    append_native_history_fact,
)
from app.services.study_progress_shadow_codec import (
    STATE_DECODERS,
    StudyProgressCodecError,
    algorithm_state_hash,
    serialize_card_state,
)
from app.services.study_service import (
    NativeReviewMutationInput,
    stage_native_review_event,
)
from models.review_event import ReviewEvent


class StudyAuthorityCommandError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


@dataclass(frozen=True)
class ExistingStateNoteReviewCommand:
    route: StudyAuthorityRoute
    locked: LockedStudyAuthoritySubject
    expected: StudyAuthorityCASExpectation
    siblings: LockedStudyAuthoritySiblings
    compatibility: LockedStudyAuthorityCompatibility
    review: NativeReviewMutationInput
    now_utc: datetime


@dataclass(frozen=True)
class ExistingStateNoteReviewResult:
    review_event: ReviewEvent
    # No legacy projection exists any more (ADR P10); always None.
    projection: None
    write: StudyAuthorityWriteResult
    evidence: StudyAuthorityEvidenceResult
    history: NativeHistoryFactResult


def _fail(code: str, message: str) -> StudyAuthorityCommandError:
    return StudyAuthorityCommandError(code, message)


def _validate_and_build_state_write(
    command: ExistingStateNoteReviewCommand,
) -> tuple[StudyAuthorityStateWrite, bytes]:
    route = command.route
    locked = command.locked
    siblings = command.siblings
    compatibility = command.compatibility
    review = command.review
    now_utc = command.now_utc

    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE":
        raise _fail(
            "AUTHORITY_MODE_CONFLICT",
            "Existing-state NOTE review requires a fenced NOTE route.",
        )
    if not isinstance(locked, LockedStudyAuthoritySubject) or locked.state is None:
        raise _fail(
            "AUTHORITY_STATE_REQUIRED",
            "Existing-state NOTE review requires a locked current state.",
        )
    if not isinstance(siblings, LockedStudyAuthoritySiblings) or not isinstance(
        compatibility, LockedStudyAuthorityCompatibility
    ):
        raise _fail(
            "INCOMPLETE_AUTHORITY_COMPATIBILITY",
            "Locked sibling and compatibility vectors are required.",
        )
    if not isinstance(review, NativeReviewMutationInput):
        raise _fail("INVALID_AUTHORITY_COMMAND", "Native review input is missing.")
    if review.progress_input is not None:
        raise _fail(
            "LEGACY_PROGRESS_MUTATION_FORBIDDEN",
            "NOTE command owns the full compatibility projection.",
        )
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail(
            "INVALID_AUTHORITY_TIME", "Authority command time must be naive UTC."
        )
    if (
        not isinstance(review.reviewed_at, datetime)
        or review.reviewed_at.tzinfo is not None
    ):
        raise _fail(
            "INVALID_REVIEW_TIME", "Review time must be a naive UTC datetime."
        )
    if (
        isinstance(review.user_id, bool)
        or not isinstance(review.user_id, int)
        or review.user_id != route.learner_user_id
    ):
        raise _fail("WRONG_LEARNER", "Native review belongs to another learner.")

    subject = locked.subject
    generation = int(subject.subject_generation)
    if (
        int(subject.learner_user_id) != route.learner_user_id
        or int(siblings.learner_user_id) != route.learner_user_id
        or int(compatibility.learner_user_id) != route.learner_user_id
        or int(siblings.subject_id) != int(subject.id)
        or int(compatibility.subject_id) != int(subject.id)
        or int(siblings.subject_generation) != generation
        or int(compatibility.subject_generation) != generation
    ):
        raise _fail(
            "AUTHORITY_CONTEXT_DIVERGED",
            "Authority command inputs do not describe one fenced learner/Note.",
        )

    card_id = str(review.card.id or "")
    card_by_id = {str(card.id): card for card in siblings.cards}
    if card_id not in card_by_id:
        raise _fail(
            "CARD_OUTSIDE_AUTHORITY_SUBJECT",
            "Reviewed Card is outside the locked authority subject.",
        )
    if review.card is not card_by_id[card_id]:
        raise _fail(
            "LOCKED_CARD_REQUIRED",
            "Native review must use the Card instance from the locked sibling vector.",
        )
    if str(review.card.note_id or "") != siblings.live_note_id:
        raise _fail(
            "CARD_OUTSIDE_AUTHORITY_SUBJECT",
            "Reviewed Card does not belong to the locked Note.",
        )

    transition = review.transition
    identity = transition.algorithm
    if (
        identity.key != ALGORITHM_KEY
        or identity.version != ALGORITHM_VERSION
        or identity.state_schema_version != STATE_SCHEMA_VERSION
    ):
        raise _fail(
            "STATE_DECODER_UNAVAILABLE",
            "NOTE command cannot encode this Algorithm version.",
        )
    if transition.state.lastReviewAt != review.reviewed_at:
        raise _fail(
            "REVIEW_TRANSITION_MISMATCH",
            "Scheduler transition time differs from ReviewEvent time.",
        )

    verified = verify_study_authority_cas(
        route=route,
        locked=locked,
        expected=command.expected,
        require_note_authority=True,
    )
    if verified.semantic_state_hash is None:
        raise _fail(
            "AUTHORITY_STATE_REQUIRED",
            "Existing-state NOTE review requires a semantic state hash.",
        )
    state = locked.state
    try:
        current_state = STATE_DECODERS.decode(
            algorithm_key=str(state.algorithm_key),
            algorithm_version=str(state.algorithm_version),
            state_schema_version=str(state.state_schema_version),
            storage_codec=str(state.storage_codec),
            payload=state.state_payload,
            expected_size=int(state.state_payload_size),
            expected_hash=bytes(state.algorithm_state_hash),
        )
        next_document = serialize_card_state(transition.state)
        next_hash = algorithm_state_hash(next_document.payload)
    except StudyProgressCodecError as exc:
        raise _fail(exc.code, str(exc)) from exc
    if current_state != review.current_state:
        raise _fail(
            "AUTHORITY_CURRENT_STATE_MISMATCH",
            "Native review was not calculated from the locked authority state.",
        )

    return (
        StudyAuthorityStateWrite(
            algorithm_key=identity.key,
            algorithm_version=identity.version,
            state_schema_version=identity.state_schema_version,
            storage_codec=STORAGE_CODEC,
            state_payload=next_document.payload,
            state_payload_size=next_document.size,
            algorithm_state_hash=next_hash,
        ),
        verified.semantic_state_hash,
    )


def apply_existing_state_note_review(
    session: Session,
    *,
    command: ExistingStateNoteReviewCommand,
) -> ExistingStateNoteReviewResult:
    """Stage one complete existing-state NOTE review; never commit or rollback."""

    if not isinstance(command, ExistingStateNoteReviewCommand):
        raise _fail("INVALID_AUTHORITY_COMMAND", "NOTE review command is missing.")
    next_state, before_state_hash = _validate_and_build_state_write(command)

    review_event = stage_native_review_event(command.review, session=session)
    session.flush()
    if review_event.id is None:
        raise _fail(
            "UNFLUSHED_REVIEW_EVENT",
            "Canonical ReviewEvent did not receive a durable transaction identity.",
        )

    if not is_consolidated(command.route):
        raise _fail(
            "AUTHORITY_MODE_CONFLICT",
            "Existing-state NOTE review requires a CONSOLIDATED_V1 route.",
        )
    # ADR P10 §2.4: state, revision and availability are one row.
    from app.services import study_consolidated_progress_service as consolidated

    projection = consolidated.project_subject_state(
        next_state.state_payload, burial=consolidated.note_burial(command.locked.subject)
    )
    write_result = apply_study_authority_canonical_write(
        session,
        route=command.route,
        locked=command.locked,
        expected=command.expected,
        next_state=next_state,
        semantic_state_hash=projection.semantic_state_hash,
        now_utc=command.now_utc,
    )
    evidence = consolidated.finalize_consolidated_review(
        route=command.route,
        locked=command.locked,
        write_result=write_result,
        projection=projection,
        review_event=review_event,
        now_utc=command.now_utc,
    )
    return _with_history_fact(
        session,
        command=command,
        review_event=review_event,
        write_result=write_result,
        evidence=evidence,
        before_state_hash=before_state_hash,
    )


def _with_history_fact(
    session: Session,
    *,
    command: ExistingStateNoteReviewCommand,
    review_event: ReviewEvent,
    write_result: StudyAuthorityWriteResult,
    evidence: StudyAuthorityEvidenceResult,
    before_state_hash: bytes,
) -> ExistingStateNoteReviewResult:
    # History facts key the Card by logical identity on the row's generation.
    history = append_native_history_fact(
        session,
        command=NativeHistoryFactInput(
            learner_user_id=command.route.learner_user_id,
            subject=command.locked.subject,
            review_event=review_event,
            history_completeness_code=str(command.locked.subject.history_completeness_code),
            before_state_hash=before_state_hash,
            after_state_hash=write_result.semantic_state_hash,
            require_scheduler_grade=True,
        ),
        now_utc=command.now_utc,
        # review_event was inserted above in this uncommitted transaction.
        event_created_in_transaction=True,
    )
    return ExistingStateNoteReviewResult(
        review_event=review_event,
        projection=None,
        write=write_result,
        evidence=evidence,
        history=history,
    )
