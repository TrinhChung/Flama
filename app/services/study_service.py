"""Application boundary for native flashcard review transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.repositories.study_repository import (
    apply_card_state_to_progress,
    card_state_from_progress,
    is_progress_suspended,
)
from app.services import (
    deck_working_tree_service,
    flashcards_share_service,
    study_artifact_service,
)
from app.services.anki_scheduler import CardState, DeckOptions, _day_index
from app.services.scheduler_config_service import resolve_deck_options
from app.services.stats_overview import normalize_review_mode, record_review_event
from app.services.study_action_runtime import (
    ReviewTransitionResult,
    compute_review_previews,
    execute_review_action,
)
from app.services.study_algorithm_registry import DEFAULT_ALGORITHM_IDENTITY
from app.services.study_policy_service import build_scheduler_policy
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck


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


def _serialize_review_payload(payload: dict[str, Any] | None) -> str:
    try:
        return json.dumps(
            payload or {},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except (TypeError, ValueError):
        return "{}"


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


def record_native_review_transition(
    *,
    user_id: int,
    card: Card,
    current_state: CardState,
    transition: ReviewTransitionResult,
    reviewed_at: datetime,
    duration_ms: int | None,
    review_mode: str,
    payload: dict[str, Any] | None,
    local_deck_id: int | None,
    scheduler_preset_id: int | None,
    scheduler_config_hash: str,
    timezone_name: str,
    deck_options: DeckOptions,
    study_session_id: str | None = None,
    client_event_id: str | None = None,
    sequence_no: int | None = None,
) -> Any:
    """Append one canonical native ReviewEvent and its in-transaction effects."""

    updated_state = transition.state
    event_payload = dict(payload or {})
    event_payload["_study_runtime"] = {
        **transition.metadata(),
        "scheduler_config_hash": str(scheduler_config_hash),
    }
    review_event = record_review_event(
        user_id=int(user_id),
        card_id=str(card.id),
        deck_id=local_deck_id,
        note_type_id=str(card.note.note_type_id),
        scheduler_preset_id=scheduler_preset_id,
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
        payload_json=_serialize_review_payload(event_payload),
    )
    review_event.study_session_id = study_session_id
    review_event.client_event_id = client_event_id
    review_event.sequence_no = sequence_no
    _apply_review_side_effects(
        user_id=user_id,
        card=card,
        transition=transition,
        local_deck_id=local_deck_id,
        reviewed_at=reviewed_at,
    )
    return review_event


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
) -> NativeReviewCommandResult:
    """Execute and commit one native review under one locked transaction."""

    reviewed_at = now or datetime.utcnow()
    local_deck_id = resolve_effective_study_deck_id(
        card=card,
        clone_scope=clone_scope,
        requested_scope_id=requested_scope_id,
    )
    try:
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
    except Exception:
        db.session.rollback()
        raise

    try:
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
        transition = execute_review_action(
            state=current_state,
            options=options,
            now=reviewed_at,
            action=action,
            timezone_name=timezone_name,
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
        )
        policy = build_scheduler_policy(
            options=options,
            timezone_name=timezone_name,
            algorithm=transition.algorithm,
        )

        apply_card_state_to_progress(
            progress,
            transition.state,
            reviewed_at,
            timezone_name=timezone_name,
            options=options,
        )
        progress.revision = int(progress.revision or 0) + 1
        effective_client_event_id = client_event_id or (payload or {}).get("client_event_id")
        effective_study_session_id = study_session_id or (payload or {}).get("study_session_id")
        effective_sequence_no = sequence_no if sequence_no is not None else (payload or {}).get("sequence_no")
        effective_review_mode = review_mode or normalize_review_mode(current_state.type)
        review_event = record_native_review_transition(
            user_id=int(user.id),
            card=card,
            current_state=current_state,
            transition=transition,
            reviewed_at=reviewed_at,
            duration_ms=(payload or {}).get("duration_ms"),
            review_mode=effective_review_mode,
            payload=payload,
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
            study_session_id=effective_study_session_id,
            client_event_id=effective_client_event_id,
            sequence_no=effective_sequence_no,
        )
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
        db.session.commit()
        return NativeReviewCommandResult(
            current_state=current_state,
            transition=transition,
            intervals_preview=intervals_preview,
            local_deck_id=local_deck_id,
            progress_revision=int(progress.revision),
            scheduler_config_hash=policy["config_hash"],
        )
    except Exception:
        db.session.rollback()
        raise
