"""Application boundary for native flashcard review transitions."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_compatibility,
    lock_study_authority_route,
    lock_study_authority_siblings,
)
from app.repositories.study_repository import (
    apply_card_state_to_progress,
    card_state_from_progress,
    is_progress_suspended,
)
from app.repositories.review_event_repository import create_review_event_record
from app.services import (
    deck_working_tree_service,
    flashcards_share_service,
    study_artifact_service,
    study_progress_shadow_mirror_service,
)
from app.services.anki_scheduler import CardState, DeckOptions, _day_index
from app.services.db_errors import domain_error_code
from app.services.scheduler_config_service import resolve_deck_options
from app.services.stats_overview import normalize_review_mode
from app.services.study_action_runtime import (
    ReviewTransitionResult,
    compute_review_previews,
    execute_review_action,
)
from app.services.study_algorithm_registry import DEFAULT_ALGORITHM_IDENTITY
from app.services.study_policy_service import build_scheduler_policy
from app.services.study_note_storage_precision import (
    NOTE_STORAGE_PROFILE,
    StudyStoragePrecisionError,
    normalize_note_transition_state,
)
from app.validators.review_event import (
    ReviewEventPayloadError,
    build_native_review_event_payload,
    validate_native_client_payload,
    validate_review_duration,
)
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.review_event import ReviewEvent


class StudyReviewError(ValueError):
    """Typed failure returned consistently by native review transports."""

    def __init__(self, code: str, message: str, *, status: int = 409) -> None:
        super().__init__(message)
        self.code = str(code)
        self.status = int(status)


@dataclass(frozen=True)
class NativeReviewCommandResult:
    current_state: CardState
    transition: ReviewTransitionResult
    intervals_preview: dict[str, dict[str, float | int | str | None]]
    local_deck_id: int | None
    progress_revision: int
    scheduler_config_hash: str
    authority_mode: str = "LEGACY"
    authority_revision: int | None = None
    operation_key: str | None = None
    replayed: bool = False


@dataclass(frozen=True)
class NativeReviewProvenance:
    """Transport provenance attached to a canonical native review event."""

    source_path: str = "native.rest"
    study_session_id: str | None = None
    client_event_id: str | None = None
    sequence_no: int | None = None
    request_id: str | None = None
    wire_schema_version: str | None = None


@dataclass(frozen=True)
class NativeReviewProgressInput:
    """Final progress state applied by the non-committing mutation core."""

    progress: CardProgress
    state: CardState
    last_reviewed_at: datetime
    revision: int


@dataclass(frozen=True)
class NativeReviewTransitionInput:
    """Executable scheduler input shared by direct and durable review paths."""

    state: CardState
    deck_options: DeckOptions
    reviewed_at: datetime
    action: Any
    timezone_name: str
    algorithm_key: str = DEFAULT_ALGORITHM_IDENTITY.key
    algorithm_version: str = DEFAULT_ALGORITHM_IDENTITY.version
    trigger_key: str | None = None
    trigger_contract_version: str | None = None
    storage_profile: str | None = None


@dataclass(frozen=True)
class NativeReviewMutationInput:
    """Transport-neutral input for one canonical native review mutation."""

    user_id: int
    card: Card
    current_state: CardState
    transition: ReviewTransitionResult
    reviewed_at: datetime
    duration_ms: int | None
    payload: dict[str, Any] | None
    local_deck_id: int | None
    scheduler_preset_id: int | None
    scheduler_config_hash: str
    timezone_name: str
    deck_options: DeckOptions
    review_mode: str | None = None
    note_type_id: str | None = None
    provenance: NativeReviewProvenance = field(
        default_factory=NativeReviewProvenance
    )
    progress_input: NativeReviewProgressInput | None = None


@dataclass(frozen=True)
class NativeReviewMutationResult:
    """Objects mutated by the core; the caller still owns flush/commit/rollback."""

    review_event: ReviewEvent
    progress: CardProgress | None
    progress_revision: int | None


def normalize_review_duration(value: Any) -> int | None:
    """Validate native duration consistently across REST, MCP and sessions."""

    return validate_review_duration(value)


def execute_native_review_transition(
    command: NativeReviewTransitionInput,
) -> ReviewTransitionResult:
    """Execute the exact-version native scheduler without persistence effects."""

    if command.storage_profile not in (None, NOTE_STORAGE_PROFILE):
        raise StudyReviewError("UNSUPPORTED_STORAGE_PROFILE", "Unknown review storage profile.")
    result = execute_review_action(
        state=command.state,
        options=command.deck_options,
        now=command.reviewed_at,
        action=command.action,
        timezone_name=command.timezone_name,
        algorithm_key=command.algorithm_key,
        algorithm_version=command.algorithm_version,
        trigger_key=command.trigger_key,
        trigger_contract_version=command.trigger_contract_version,
    )
    if command.storage_profile == NOTE_STORAGE_PROFILE:
        try:
            return replace(
                result,
                state=normalize_note_transition_state(result.state),
                storage_profile=NOTE_STORAGE_PROFILE,
            )
        except StudyStoragePrecisionError as exc:
            raise StudyReviewError(exc.code, str(exc)) from exc
    return result


def _compute_days_late(
    current_state: CardState,
    now: datetime,
    timezone_name: str,
    deck_options: DeckOptions,
) -> int | None:
    if str(current_state.type or "").strip().lower() != "review":
        return None
    due_day = current_state.dueDay
    if due_day is None:
        due_day = _day_index(
            current_state.due or now,
            deck_options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )
    current_day = _day_index(
        now,
        deck_options.dayBoundaryHourLocal,
        timezone_name=timezone_name,
    )
    return int(current_day - int(due_day))


def resolve_effective_study_deck_id(
    *,
    card: Card,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    requested_scope_id: int | None = None,
) -> int | None:
    """Resolve the local deck supplying scheduler policy and usage attribution."""

    source_deck_id = getattr(card.note, "deck_id", None)
    if clone_scope is None:
        return int(source_deck_id) if source_deck_id is not None else None
    if (
        source_deck_id is not None
        and int(source_deck_id) in set(clone_scope.local_deck_ids)
        and flashcards_share_service.is_clone_added_note(
            scope=clone_scope,
            note_id=card.note.id,
        )
    ):
        return int(source_deck_id)
    if source_deck_id is not None:
        mapped = clone_scope.source_to_local_deck_id.get(int(source_deck_id))
        if mapped is not None:
            return int(mapped)
    if clone_scope.local_scope_deck_id is not None:
        return int(clone_scope.local_scope_deck_id)
    if requested_scope_id is not None:
        return int(requested_scope_id)
    if clone_scope.install.local_deck_id is not None:
        return int(clone_scope.install.local_deck_id)
    return None


def _append_audit(
    *,
    user_id: int,
    action: str,
    payload: dict[str, Any],
) -> None:
    db.session.add(
        AuditLog(
            user_id=int(user_id),
            action=str(action),
            payload=dict(payload),
        )
    )


def _apply_review_side_effects(
    *,
    user_id: int,
    card: Card,
    transition: ReviewTransitionResult,
    local_deck_id: int | None,
    reviewed_at: datetime,
) -> None:
    if transition.state.leeched and int(card.note.user_id) == int(user_id):
        tags = [
            str(tag).strip()
            for tag in (card.note.tags or [])
            if str(tag).strip()
        ]
        if (
            "leech" not in {tag.lower() for tag in tags}
            and not deck_working_tree_service.note_has_shared_release_dependents(
                card.note
            )
        ):
            card.note.tags = tags + ["leech"]

    flashcards_share_service.touch_note_type_install_usage(
        user_id=int(user_id),
        installed_note_type_id=str(card.note.note_type_id),
        activity_at=reviewed_at,
    )
    if local_deck_id is not None:
        flashcards_share_service.touch_deck_install_usage(
            user_id=int(user_id),
            local_deck_id=int(local_deck_id),
            activity_at=reviewed_at,
        )


def _record_native_review_transition(
    *,
    user_id: int,
    card: Card,
    current_state: CardState,
    transition: ReviewTransitionResult,
    reviewed_at: datetime,
    duration_ms: int | None,
    review_mode: str,
    local_deck_id: int | None,
    scheduler_preset_id: int | None,
    scheduler_config_hash: str,
    timezone_name: str,
    deck_options: DeckOptions,
    note_type_id: str | None = None,
    provenance: NativeReviewProvenance,
    payload_json: str,
    event_session: Any | None = None,
) -> Any:
    """Append one canonical native ReviewEvent without other side effects."""

    updated_state = transition.state
    review_event = create_review_event_record(
        user_id=int(user_id),
        card_id=str(card.id),
        deck_id=local_deck_id,
        note_type_id=str(note_type_id or card.note.note_type_id),
        scheduler_preset_id=scheduler_preset_id,
        study_session_id=provenance.study_session_id,
        client_event_id=provenance.client_event_id,
        sequence_no=provenance.sequence_no,
        scheduler_algorithm=transition.algorithm.key,
        algorithm_version=transition.algorithm.version,
        scheduler_config_hash=str(scheduler_config_hash),
        reviewed_at=reviewed_at,
        duration_ms=duration_ms,
        rating=transition.action.rating,
        mode=review_mode,
        scheduler_mode=str(updated_state.schedulerMode or "legacy"),
        review_kind=str(updated_state.reviewKind or "review"),
        queue_before=str(current_state.type),
        queue_after=str(updated_state.type),
        interval_days_before=float(current_state.intervalDays or 0),
        interval_days_after=float(updated_state.intervalDays or 0),
        due_day_before=current_state.dueDay,
        due_day_after=updated_state.dueDay,
        days_late=_compute_days_late(
            current_state,
            reviewed_at,
            timezone_name,
            deck_options,
        ),
        ease_factor_before=float(current_state.ease or 0),
        ease_factor_after=float(updated_state.ease or 0),
        memory_stability_before=(
            float(current_state.memoryState.stability)
            if current_state.memoryState is not None
            else None
        ),
        memory_stability_after=(
            float(updated_state.memoryState.stability)
            if updated_state.memoryState is not None
            else None
        ),
        memory_difficulty_before=(
            float(current_state.memoryState.difficulty)
            if current_state.memoryState is not None
            else None
        ),
        memory_difficulty_after=(
            float(updated_state.memoryState.difficulty)
            if updated_state.memoryState is not None
            else None
        ),
        leeched_after=bool(updated_state.leeched),
        suspended_after=bool(updated_state.suspended),
        payload_json=payload_json,
        session=event_session,
    )
    return review_event


def _prepare_native_review_event(
    command: NativeReviewMutationInput,
) -> tuple[int | None, str]:
    normalized_duration_ms = normalize_review_duration(command.duration_ms)
    payload_json = build_native_review_event_payload(
        source_path=command.provenance.source_path,
        runtime=command.transition.metadata(),
        scheduler_config_hash=command.scheduler_config_hash,
        client_payload=command.payload,
        study_session_id=command.provenance.study_session_id,
        client_event_id=command.provenance.client_event_id,
        sequence_no=command.provenance.sequence_no,
        request_id=command.provenance.request_id,
        wire_schema_version=command.provenance.wire_schema_version,
    )
    return normalized_duration_ms, payload_json


def stage_native_review_event(
    command: NativeReviewMutationInput,
    *,
    session: Any | None = None,
) -> ReviewEvent:
    """Stage only the canonical ReviewEvent; never commit or run side effects.

    NOTE authority composition uses this narrow primitive so the event ID can
    participate in the same caller-owned transaction as state, compatibility
    evidence and history. Existing native mutation paths continue to invoke
    their legacy marketplace/leech side effects separately.
    """

    normalized_duration_ms, payload_json = _prepare_native_review_event(command)
    return _record_native_review_transition(
        user_id=int(command.user_id),
        card=command.card,
        current_state=command.current_state,
        transition=command.transition,
        reviewed_at=command.reviewed_at,
        duration_ms=normalized_duration_ms,
        review_mode=(
            command.review_mode
            or normalize_review_mode(command.current_state.type)
        ),
        local_deck_id=command.local_deck_id,
        scheduler_preset_id=command.scheduler_preset_id,
        scheduler_config_hash=command.scheduler_config_hash,
        timezone_name=command.timezone_name,
        deck_options=command.deck_options,
        note_type_id=command.note_type_id,
        provenance=command.provenance,
        payload_json=payload_json,
        event_session=session,
    )


def stage_native_review_side_effects(command: NativeReviewMutationInput) -> None:
    """Stage leech and marketplace usage effects in the caller transaction."""

    if not isinstance(command, NativeReviewMutationInput):
        raise TypeError("Native review mutation input is required.")
    _apply_review_side_effects(
        user_id=int(command.user_id),
        card=command.card,
        transition=command.transition,
        local_deck_id=command.local_deck_id,
        reviewed_at=command.reviewed_at,
    )


def apply_native_review_mutation(
    command: NativeReviewMutationInput,
) -> NativeReviewMutationResult:
    """Apply one native review mutation without commit or rollback.

    Direct/MCP callers supply a progress input for every command. A durable
    session may append multiple events for one card and supplies the final
    progress input only on that card's last replayed event, preserving its
    one-revision-per-batch contract.
    """

    normalized_duration_ms, payload_json = _prepare_native_review_event(command)

    progress = None
    progress_revision = None
    if command.progress_input is not None:
        progress = command.progress_input.progress
        apply_card_state_to_progress(
            progress,
            command.progress_input.state,
            command.progress_input.last_reviewed_at,
            timezone_name=command.timezone_name,
            options=command.deck_options,
        )
        progress.revision = int(command.progress_input.revision)
        progress_revision = int(progress.revision)

    review_event = _record_native_review_transition(
        user_id=int(command.user_id),
        card=command.card,
        current_state=command.current_state,
        transition=command.transition,
        reviewed_at=command.reviewed_at,
        duration_ms=normalized_duration_ms,
        review_mode=(
            command.review_mode
            or normalize_review_mode(command.current_state.type)
        ),
        local_deck_id=command.local_deck_id,
        scheduler_preset_id=command.scheduler_preset_id,
        scheduler_config_hash=command.scheduler_config_hash,
        timezone_name=command.timezone_name,
        deck_options=command.deck_options,
        note_type_id=command.note_type_id,
        provenance=command.provenance,
        payload_json=payload_json,
    )
    stage_native_review_side_effects(command)
    return NativeReviewMutationResult(
        review_event=review_event,
        progress=progress,
        progress_revision=progress_revision,
    )


def _execute_note_authority_review_command(
    *,
    route: Any,
    user: Any,
    card: Card,
    action: Any,
    validated_payload: dict[str, Any],
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    local_deck_id: int | None,
    requested_scope_id: int | None,
    local_deck: Deck | None,
    options: DeckOptions,
    timezone_name: str,
    require_review_state_version: bool,
    review_state_version: str | None,
    reviewed_at: datetime,
    algorithm_key: str,
    algorithm_version: str,
    client_event_id: str | None,
    review_mode: str | None,
    source_path: str,
) -> NativeReviewCommandResult:
    """Execute one direct/MCP review through the canonical NOTE command."""

    from app.services.study_authority_cas_service import (
        StudyAuthorityCASExpectation,
    )
    from app.services.study_authority_command_service import (
        ExistingStateNoteReviewCommand,
    )
    from app.services.study_authority_receipt_service import (
        IdempotentExistingStateNoteReviewCommand,
        apply_idempotent_existing_state_note_review,
    )
    from app.services.study_session_authority_pin_service import (
        lock_study_session_authority_subjects,
    )
    from app.services.study_action_runtime import resolve_review_action
    from app.services.study_direct_note_replay_service import (
        direct_note_request_fingerprint, read_direct_note_replay,
    )

    from app.services.study_note_pristine_service import (
        classify_note_authority_keys,
        materialize_pristine_notes,
    )

    # Logical-overlay source Notes use the same learner/Note subject; the
    # caller already resolved and authorized the install scope.
    operation_key_value = validated_payload.get("operation_key")
    operation_key = (
        str(operation_key_value).strip()
        if operation_key_value is not None
        else str(client_event_id or uuid4())
    )
    if client_event_id is not None and operation_key_value is not None:
        if operation_key != str(client_event_id):
            raise StudyReviewError(
                "AUTHORITY_OPERATION_PROVENANCE_MISMATCH",
                "operation_key differs from the transport event identity.",
                status=422,
            )

    note_key = str(card.note_id)
    _stateful, pristine = classify_note_authority_keys(
        db.session,
        learner_user_id=int(user.id),
        note_ids=[note_key],
        storage_profile=route.storage_profile,
    )
    if pristine:
        # First review of a never-studied Note: the client saw the pristine
        # NEW read, so verify that version before materializing its state.
        if require_review_state_version:
            requested_version = str(review_state_version or "").strip()
            if not requested_version or requested_version != (
                study_artifact_service.pristine_note_review_state_version(
                    enrollment_epoch=int(route.epoch),
                    logical_note_key=note_key,
                    deck_options=options,
                    timezone_name=timezone_name,
                )
            ):
                raise StudyReviewError(
                    "STALE_REVIEW_STATE",
                    "Review state changed; reload the study manifest.",
                )
        materialize_pristine_notes(
            db.session,
            route=route,
            cards=(card,),
            starting_ease_by_note_id={note_key: float(options.startingEase)},
            provenance_code=(
                "NATIVE_MCP" if str(source_path).startswith("mcp") else "NATIVE_DIRECT"
            ),
            now_utc=reviewed_at,
        )
    authority_subjects = lock_study_session_authority_subjects(
        db.session,
        route=route,
        logical_note_keys=[note_key],
        now_utc=reviewed_at,
    )
    locked = authority_subjects.locked_by_logical_note_key[note_key]
    direct_fingerprint = direct_note_request_fingerprint(
        learner_user_id=int(user.id), card_id=str(card.id),
        action_key=resolve_review_action(action).action_key, client_payload=validated_payload,
        requested_scope_id=requested_scope_id, require_review_state_version=require_review_state_version,
        review_state_version=review_state_version, algorithm_key=algorithm_key,
        algorithm_version=algorithm_version, client_event_id=client_event_id,
        review_mode=review_mode, source_path=source_path,
    )
    replay = read_direct_note_replay(db.session, route=route, locked=locked,
        card_id=str(card.id), operation_key=operation_key, request_fingerprint=direct_fingerprint)
    if replay is not None:
        db.session.rollback()  # Release read locks; replay stages no new writes.
        return replay
    current_state = authority_subjects.state_by_logical_note_key[note_key]
    siblings = lock_study_authority_siblings(
        db.session,
        route=route,
        locked=locked,
        requested_card_id=str(card.id),
    )
    compatibility = lock_study_authority_compatibility(
        db.session,
        route=route,
        locked=locked,
        siblings=siblings,
    )
    locked_card = next(
        sibling for sibling in siblings.cards if str(sibling.id) == str(card.id)
    )
    # A first-state review was already checked against its pristine version.
    if require_review_state_version and not pristine:
        requested_version = str(review_state_version or "").strip()
        current_version = study_artifact_service.note_authority_review_state_version(
            enrollment_epoch=int(route.epoch),
            logical_note_key=note_key,
            subject_generation=int(locked.subject.subject_generation),
            authority_revision=int(locked.token.authority_revision),
            semantic_state_hash=bytes(locked.token.semantic_state_hash),
            deck_options=options,
            timezone_name=timezone_name,
        )
        if not requested_version or requested_version != current_version:
            raise StudyReviewError(
                "STALE_REVIEW_STATE",
                "Review state changed; reload the study manifest.",
            )
    if bool(current_state.suspended):
        raise StudyReviewError("CARD_SUSPENDED", "Card is suspended.")

    intervals_preview = compute_review_previews(
        state=current_state,
        options=options,
        now=reviewed_at,
        timezone_name=timezone_name,
        algorithm_key=algorithm_key,
        algorithm_version=algorithm_version,
    )
    transition = execute_native_review_transition(
        NativeReviewTransitionInput(
            state=current_state,
            deck_options=options,
            reviewed_at=reviewed_at,
            action=action,
            timezone_name=timezone_name,
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
            storage_profile=NOTE_STORAGE_PROFILE,
        )
    )
    policy = build_scheduler_policy(
        options=options,
        timezone_name=timezone_name,
        algorithm=transition.algorithm,
    )
    mutation = NativeReviewMutationInput(
        user_id=int(user.id),
        card=locked_card,
        current_state=current_state,
        transition=transition,
        reviewed_at=reviewed_at,
        duration_ms=validate_review_duration(validated_payload.get("duration_ms")),
        review_mode=(review_mode or normalize_review_mode(current_state.type)),
        payload=validated_payload,
        local_deck_id=local_deck_id,
        scheduler_preset_id=(
            int(local_deck.scheduler_preset_id)
            if local_deck is not None and local_deck.scheduler_preset_id is not None
            else None
        ),
        scheduler_config_hash=policy["config_hash"],
        timezone_name=timezone_name,
        deck_options=options,
        provenance=NativeReviewProvenance(
            source_path=source_path,
            client_event_id=client_event_id,
            request_id=operation_key,
        ),
        progress_input=None,
    )
    expected = StudyAuthorityCASExpectation(
        enrollment_epoch=int(route.epoch),
        subject_generation=int(locked.subject.subject_generation),
        authority_revision=int(locked.token.authority_revision),
        semantic_state_hash=bytes(locked.token.semantic_state_hash),
    )
    applied = apply_idempotent_existing_state_note_review(
        db.session,
        command=IdempotentExistingStateNoteReviewCommand(
            operation_key=operation_key,
            direct_request_fingerprint=direct_fingerprint,
            direct_previews=intervals_preview,
            command=ExistingStateNoteReviewCommand(
                route=route,
                locked=locked,
                expected=expected,
                siblings=siblings,
                compatibility=compatibility,
                review=mutation,
                now_utc=reviewed_at,
            ),
        ),
    )
    if not applied.replayed:
        stage_native_review_side_effects(mutation)
        _append_audit(
            user_id=int(user.id),
            action="study.answer",
            payload={
                "card_id": str(card.id),
                "rating": transition.action.rating,
                "authority_mode": "NOTE",
                "operation_key": operation_key,
            },
        )
    projected_revisions = applied.response_payload.get("projected_card_revisions")
    if not isinstance(projected_revisions, dict) or str(card.id) not in projected_revisions:
        raise StudyReviewError(
            "AUTHORITY_RECEIPT_CORRUPT",
            "NOTE review receipt has no projected revision for the reviewed Card.",
            status=500,
        )
    db.session.commit()
    return NativeReviewCommandResult(
        current_state=current_state,
        transition=transition,
        intervals_preview=intervals_preview,
        local_deck_id=local_deck_id,
        progress_revision=int(projected_revisions[str(card.id)]),
        scheduler_config_hash=policy["config_hash"],
        authority_mode="NOTE",
        authority_revision=int(applied.response_payload["authority_revision_after"]),
        operation_key=operation_key,
        replayed=bool(applied.replayed),
    )


def execute_native_review_command(
    *,
    user: Any,
    card: Card,
    action: Any,
    payload: dict[str, Any] | None,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    requested_scope_id: int | None,
    timezone_name: str,
    require_review_state_version: bool = False,
    review_state_version: str | None = None,
    now: datetime | None = None,
    algorithm_key: str = DEFAULT_ALGORITHM_IDENTITY.key,
    algorithm_version: str = DEFAULT_ALGORITHM_IDENTITY.version,
    client_event_id: str | None = None,
    study_session_id: str | None = None,
    sequence_no: int | None = None,
    review_mode: str | None = None,
    source_path: str = "native.rest",
) -> NativeReviewCommandResult:
    """Execute and commit one native review under one locked transaction."""

    try:
        validated_payload = validate_native_client_payload(
            payload,
            source_path=source_path,
        )
    except ReviewEventPayloadError as exc:
        raise StudyReviewError(exc.code, str(exc), status=exc.status) from exc

    reviewed_at = now or datetime.utcnow()
    local_deck_id = resolve_effective_study_deck_id(
        card=card,
        clone_scope=clone_scope,
        requested_scope_id=requested_scope_id,
    )
    try:
        authority_route = lock_study_authority_route(
            db.session,
            learner_user_id=int(user.id),
            allow_note_authority=True,
        )
        local_deck = (
            db.session.get(Deck, local_deck_id)
            if local_deck_id is not None
            else None
        )
        options = resolve_deck_options(
            user_id=int(user.id),
            deck_id=local_deck_id,
            deck_obj=local_deck,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise StudyReviewError(exc.code, str(exc), status=409) from exc
    except Exception:
        db.session.rollback()
        raise

    try:
        if authority_route.mode_code == "NOTE":
            return _execute_note_authority_review_command(
                route=authority_route,
                user=user,
                card=card,
                action=action,
                validated_payload=validated_payload,
                clone_scope=clone_scope,
                local_deck_id=local_deck_id,
                requested_scope_id=requested_scope_id,
                local_deck=local_deck,
                options=options,
                timezone_name=timezone_name,
                require_review_state_version=require_review_state_version,
                review_state_version=review_state_version,
                reviewed_at=reviewed_at.replace(microsecond=0),
                algorithm_key=algorithm_key,
                algorithm_version=algorithm_version,
                client_event_id=client_event_id,
                review_mode=review_mode,
                source_path=source_path,
            )
        if "operation_key" in validated_payload:
            raise StudyReviewError(
                "AUTHORITY_OPERATION_KEY_UNAVAILABLE",
                "operation_key is available only for NOTE authority reviews.",
                status=422,
            )
        mirror_plan = study_progress_shadow_mirror_service.prepare_native_mirror(
            db.session,
            learner_user_id=int(user.id),
            cards=(card,),
            now_utc=reviewed_at,
        )
        if mirror_plan is not None:
            progress = study_progress_shadow_mirror_service.locked_progress_map(
                mirror_plan
            ).get(str(card.id))
        else:
            progress = (
                CardProgress.query.filter_by(
                    user_id=int(user.id),
                    card_id=str(card.id),
                )
                .with_for_update()
                .first()
            )
        if require_review_state_version:
            requested_version = str(review_state_version or "").strip()
            current_version = study_artifact_service.review_state_version(
                progress=progress,
                deck_options=options,
                timezone_name=timezone_name,
            )
            if not requested_version or requested_version != current_version:
                raise StudyReviewError(
                    "STALE_REVIEW_STATE",
                    "Review state changed; reload the study manifest.",
                )

        if progress is not None and is_progress_suspended(progress):
            raise StudyReviewError("CARD_SUSPENDED", "Card is suspended.")

        if progress is None:
            progress = CardProgress(
                user_id=int(user.id),
                card_id=str(card.id),
                queue="new",
                step_index=0,
                due_at=None,
                due_day=None,
                interval_days=0,
                ease_factor=options.startingEase,
                reps=0,
                lapses=0,
                revision=0,
            )
            db.session.add(progress)
            try:
                db.session.flush()
            except IntegrityError as exc:
                raise StudyReviewError(
                    "CONCURRENT_REVIEW",
                    "This card was reviewed concurrently. Reload its latest state.",
                ) from exc

        current_state = card_state_from_progress(
            progress,
            reviewed_at,
            timezone_name=timezone_name,
            user_id=int(user.id),
            options=options,
        )
        intervals_preview = compute_review_previews(
            state=current_state,
            options=options,
            now=reviewed_at,
            timezone_name=timezone_name,
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
        )
        transition = execute_native_review_transition(
            NativeReviewTransitionInput(
                state=current_state,
                deck_options=options,
                reviewed_at=reviewed_at,
                action=action,
                timezone_name=timezone_name,
                algorithm_key=algorithm_key,
                algorithm_version=algorithm_version,
            )
        )
        policy = build_scheduler_policy(
            options=options,
            timezone_name=timezone_name,
            algorithm=transition.algorithm,
        )

        effective_review_mode = review_mode or normalize_review_mode(current_state.type)
        try:
            mutation_result = apply_native_review_mutation(
                NativeReviewMutationInput(
                    user_id=int(user.id),
                    card=card,
                    current_state=current_state,
                    transition=transition,
                    reviewed_at=reviewed_at,
                    duration_ms=validate_review_duration(
                        validated_payload.get("duration_ms")
                    ),
                    review_mode=effective_review_mode,
                    payload=validated_payload,
                    local_deck_id=local_deck_id,
                    scheduler_preset_id=(
                        int(local_deck.scheduler_preset_id)
                        if local_deck is not None
                        and local_deck.scheduler_preset_id is not None
                        else None
                    ),
                    scheduler_config_hash=policy["config_hash"],
                    timezone_name=timezone_name,
                    deck_options=options,
                    provenance=NativeReviewProvenance(
                        source_path=source_path,
                        study_session_id=study_session_id,
                        client_event_id=client_event_id,
                        sequence_no=sequence_no,
                    ),
                    progress_input=NativeReviewProgressInput(
                        progress=progress,
                        state=transition.state,
                        last_reviewed_at=reviewed_at,
                        revision=int(progress.revision or 0) + 1,
                    ),
                )
            )
        except ReviewEventPayloadError as exc:
            raise StudyReviewError(exc.code, str(exc), status=exc.status) from exc
        review_event = mutation_result.review_event
        db.session.flush()
        if review_event.id is not None:
            progress.last_review_event_id = int(review_event.id)
        _append_audit(
            user_id=int(user.id),
            action="study.answer",
            payload={
                "card_id": str(card.id),
                "rating": transition.action.rating,
            },
        )
        study_progress_shadow_mirror_service.finalize_native_mirror(
            mirror_plan,
            review_events=(review_event,),
            now_utc=reviewed_at,
        )
        db.session.commit()
        return NativeReviewCommandResult(
            current_state=current_state,
            transition=transition,
            intervals_preview=intervals_preview,
            local_deck_id=local_deck_id,
            progress_revision=int(progress.revision),
            scheduler_config_hash=policy["config_hash"],
        )
    except StudyReviewError:
        db.session.rollback()
        raise
    except Exception as exc:
        db.session.rollback()
        code = domain_error_code(exc)
        if code is not None:
            raise StudyReviewError(code, str(exc), status=409) from exc
        raise
