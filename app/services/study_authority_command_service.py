"""Existing-state NOTE review command for the Phase 5 cutover.

The caller must acquire the learner, subject/token/state, sibling progress and
compatibility locks in canonical order before invoking this command. The
command stages one native ReviewEvent, NOTE state/token mutation, full legacy
projection, refreshed compatibility evidence and native history fact in the
caller's transaction. It never commits or rolls back.

Study Session v4 and eligible direct REST/MCP paths compose this primitive with
durable receipts and native side effects. Overlay authorization, first-state
materialization and external lifecycle state-sync remain later Phase 5 gates.
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
)
from app.services.anki_scheduler import _round_review_interval
from app.services.study_authority_cas_service import (
    StudyAuthorityCASExpectation,
    verify_study_authority_cas,
)
from app.services.study_authority_evidence_service import (
    StudyAuthorityEvidenceResult,
    finalize_study_authority_evidence,
)
from app.services.study_authority_projection_encoder import (
    EncodedLegacyProjection,
    LegacyProjectionMetadata,
    LegacySiblingBaseline,
    encode_note_state_to_legacy_cards,
)
from app.services.study_authority_write_service import (
    StudyAuthorityStateWrite,
    StudyAuthorityWriteResult,
    apply_study_authority_material_write,
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
    serialize_raw_card_progress,
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
    projection: EncodedLegacyProjection
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


def _projection_metadata(
    command: ExistingStateNoteReviewCommand,
) -> LegacyProjectionMetadata:
    review = command.review
    state = review.transition.state
    progress = command.siblings.progress_by_card_id[str(review.card.id)]
    interval_days_rounded = (
        _round_review_interval(float(state.intervalDays or 0), review.deck_options)
        if str(state.type) == "review"
        else int(round(float(state.intervalDays or 0)))
    )
    if state.leeched:
        last_leech_at = review.reviewed_at
        last_leech_lapses = int(state.lapses or 0)
    else:
        last_leech_at = progress.last_leech_at
        last_leech_lapses = int(progress.last_leech_lapses or 0)
    return LegacyProjectionMetadata(
        interval_days_rounded=interval_days_rounded,
        is_buried=bool(progress.is_buried),
        buried_until_day=progress.buried_until_day,
        last_leech_at=last_leech_at,
        last_leech_lapses=last_leech_lapses,
        projected_at=command.now_utc,
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

    card_created_at = {
        str(card.id): card.created_at for card in command.siblings.cards
    }
    baselines: list[LegacySiblingBaseline] = []
    reviewed_card_id = str(command.review.card.id)
    for card_id in command.siblings.card_ids:
        progress = command.siblings.progress_by_card_id[card_id]
        raw = serialize_raw_card_progress(progress)
        baselines.append(
            LegacySiblingBaseline(
                card_id=card_id,
                expected_base_revision=int(progress.revision),
                card_created_at=card_created_at[card_id],
                raw_payload=raw.payload,
                raw_payload_size=raw.size,
                raw_payload_hash=raw.digest,
                projected_last_review_event_id=(
                    int(review_event.id)
                    if card_id == reviewed_card_id
                    else progress.last_review_event_id
                ),
            )
        )

    projection = encode_note_state_to_legacy_cards(
        expected_learner_user_id=command.route.learner_user_id,
        algorithm_key=next_state.algorithm_key,
        algorithm_version=next_state.algorithm_version,
        state_schema_version=next_state.state_schema_version,
        storage_codec=next_state.storage_codec,
        state_payload=next_state.state_payload,
        expected_state_payload_size=next_state.state_payload_size,
        expected_algorithm_state_hash=next_state.algorithm_state_hash,
        metadata=_projection_metadata(command),
        siblings=tuple(baselines),
    )
    write_result = apply_study_authority_material_write(
        session,
        route=command.route,
        locked=command.locked,
        expected=command.expected,
        next_state=next_state,
        siblings=command.siblings,
        projection=projection,
        now_utc=command.now_utc,
    )
    evidence = finalize_study_authority_evidence(
        session,
        route=command.route,
        locked=command.locked,
        siblings=command.siblings,
        compatibility=command.compatibility,
        write_result=write_result,
        review_event=review_event,
        now_utc=command.now_utc,
    )
    reviewed_contributor = evidence.contributor_by_card_id[reviewed_card_id]
    history = append_native_history_fact(
        session,
        command=NativeHistoryFactInput(
            learner_user_id=command.route.learner_user_id,
            subject=command.locked.subject,
            contributor=reviewed_contributor,
            review_event=review_event,
            history_completeness_code=str(
                reviewed_contributor.history_completeness_code
            ),
            before_state_hash=before_state_hash,
            after_state_hash=write_result.semantic_state_hash,
        ),
        now_utc=command.now_utc,
    )
    return ExistingStateNoteReviewResult(
        review_event=review_event,
        projection=projection,
        write=write_result,
        evidence=evidence,
        history=history,
    )
