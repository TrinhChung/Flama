"""Frontend-driven study session snapshot and atomic batch commit."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from flask import current_app
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_compatibility,
    lock_study_authority_route,
    lock_study_authority_siblings_many,
)
from app.repositories.study_repository import (
    card_state_from_progress,
    is_progress_suspended,
)
from app.repositories import template_release_repository
from app.services import (
    flashcards_share_service,
    study_artifact_service,
    study_service,
)
from app.services.anki_scheduler import (
    CardState,
    DeckOptions,
    FsrsAnswerState,
    FsrsMemoryState,
    FsrsNextStates,
    _day_index,
)
from app.services.db_errors import domain_error_code
from app.services.study_action_runtime import (
    REVIEW_RATINGS,
    ReviewTransitionResult,
)
from app.services.study_algorithm_registry import (
    AlgorithmResolutionPurpose,
    DEFAULT_ALGORITHM_IDENTITY,
    StudyAlgorithmNotFoundError,
    resolve_study_algorithm,
)
from app.services.study_composition_service import (
    COMPOSITION_CONTRACT_VERSION,
    ResolvedCompositionSelection,
    StudyCompositionError,
    apply_composition_selection_to_query,
    resolve_composition_selection,
    resolve_compatibility_composition_for_card,
)
from app.services.study_session_config import (
    StudySessionConfigError,
    decode_study_session_config,
    encode_study_session_config,
    validate_payload_composition,
)
from app.services.template_binding_service import apply_binding_projection
from app.services import study_template_preset_service
from app.services.study_session_authority_pin_service import (
    LockedStudySessionAuthorityPins,
    StudySessionAuthorityPinError,
    lock_study_session_authority_pins,
    lock_study_session_authority_subjects,
    serialize_study_note_authority_identity,
    serialize_study_session_authority_pin,
    stage_study_session_authority_pin,
)
from app.services.study_authority_cas_service import StudyAuthorityCASExpectation
from app.services.study_authority_command_service import ExistingStateNoteReviewCommand
from app.services.study_authority_receipt_service import (
    IdempotentExistingStateNoteReviewCommand,
    apply_idempotent_existing_state_note_review,
    require_existing_note_review_receipt,
)
from app.services.study_note_batch_service import (
    NOTE_BATCH_RECEIPT_SCHEMA,
    NoteBatchContinuation,
    verify_note_batch_continuation,
)
from app.services.scheduler_config_service import (
    resolve_deck_options,
    resolve_scheduler_runtime_settings,
)
from app.services.study_policy_service import build_scheduler_policy, serialize_deck_options
from app.services.study_worker_readiness_service import has_ready_study_worker
from app.validators.review_event import (
    ReviewEventPayloadError,
    validate_session_event_payload,
)
from app.validators.study_session_wire import (
    BATCH_SCHEMA_V1,
    COMMIT_SCHEMA_V1,
    SESSION_SCHEMA_V2,
    SESSION_SCHEMA_V4,
    StudyWireContractError,
    build_note_authority_wire_identity,
    resolve_wire_envelope_contract,
    select_session_schema,
    validate_review_event_wire_contract,
)
from app.services.review_analytics_projection_service import flush_review_analytics_deltas
from models import db
from models.audit_log import AuditLog
from models.card import Card, canonical_card_ids, load_cards
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.study_session_commit import StudySessionCommit
from models.study_session_batch import StudySessionBatch
from models.template import Template


# Compatibility aliases retained for callers/tests that explicitly target v2.
WIRE_SCHEMA_VERSION = SESSION_SCHEMA_V2
COMMIT_SCHEMA_VERSION = COMMIT_SCHEMA_V1
BATCH_SCHEMA_VERSION = BATCH_SCHEMA_V1
SCHEDULER_ALGORITHM = DEFAULT_ALGORITHM_IDENTITY.key
ALGORITHM_VERSION = DEFAULT_ALGORITHM_IDENTITY.version
MAX_SESSION_CARDS = 5000
MAX_COMMIT_EVENTS = 5000
MAX_COMMIT_BYTES = 5 * 1024 * 1024
SESSION_TTL = timedelta(hours=24)
VALID_RATINGS = set(REVIEW_RATINGS)
VALID_COMMIT_REASONS = {
    "auto_finish",
    "manual_exit",
    "page_exit",
    "rollover",
}


class StudySessionError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details


def _require_session_algorithm(
    *,
    key: str,
    version: str,
    purpose: AlgorithmResolutionPurpose,
) -> None:
    try:
        resolve_study_algorithm(key, version, purpose=purpose)
    except StudyAlgorithmNotFoundError as exc:
        raise StudySessionError(
            exc.code,
            str(exc),
            status=409,
            details={
                "algorithm_key": exc.key,
                "algorithm_version": exc.version,
                "purpose": exc.purpose.value,
                "lifecycle_state": (
                    exc.lifecycle_state.value
                    if exc.lifecycle_state is not None
                    else None
                ),
                "reason": exc.reason,
            },
        ) from exc


def _wire_contract_or_session_error(
    session_schema: Any,
):
    try:
        return resolve_wire_envelope_contract(session_schema)
    except StudyWireContractError as exc:
        raise StudySessionError(exc.code, str(exc), status=exc.status) from exc


def negotiate_session_wire_schema(
    accepted_versions: Any,
    *,
    v3_enabled: bool,
    v4_enabled: bool = False,
) -> str:
    try:
        return select_session_schema(
            accepted_versions,
            v3_enabled=v3_enabled,
            v4_enabled=v4_enabled,
        )
    except StudyWireContractError as exc:
        raise StudySessionError(exc.code, str(exc), status=exc.status) from exc


def _utc_iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    value = moment
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return f"{value.isoformat(timespec='milliseconds')}Z"


def _parse_utc_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise StudySessionError(
            "INVALID_CARD_STATE",
            "Card state contains an invalid timestamp.",
            status=422,
        ) from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _has_actionable_session_card(
    states: dict[str, CardState],
    *,
    now: datetime,
    timezone_name: str,
    day_boundary_hour_local: int,
    learn_ahead_seconds: int,
) -> bool:
    today = _day_index(
        now,
        day_boundary_hour_local,
        timezone_name=timezone_name,
    )
    learn_ahead_at = now + timedelta(
        seconds=max(0, int(learn_ahead_seconds)),
    )
    for state in states.values():
        if state.suspended:
            continue
        if state.type == "new":
            return True
        if state.dueDay is not None:
            if int(state.dueDay) <= today:
                return True
            continue
        if state.due is None:
            return True
        if state.type in {"learning", "relearning"}:
            if state.due <= learn_ahead_at:
                return True
        elif state.type == "review" and state.due <= now:
            return True
    return False


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        normalized = default
    if not math.isfinite(normalized):
        raise StudySessionError(
            "INVALID_CARD_STATE",
            "Card state contains a non-finite number.",
            status=422,
        )
    return normalized


def _json_dumps(payload: Any) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _request_hash(payload: Any) -> str:
    return study_artifact_service.canonical_digest(payload)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def serialize_card_state(state: CardState) -> dict[str, Any]:
    memory = state.memoryState
    return {
        "type": str(state.type),
        "step_index": int(state.stepIndex or 0),
        "due_at": _utc_iso(state.due),
        "due_day": int(state.dueDay) if state.dueDay is not None else None,
        "interval_days": float(state.intervalDays or 0),
        "ease": float(state.ease or 0),
        "reps": int(state.reps or 0),
        "lapses": int(state.lapses or 0),
        "last_review_at": _utc_iso(state.lastReviewAt),
        "review_kind": str(state.reviewKind or "review"),
        "scheduler_mode": str(state.schedulerMode or "legacy"),
        "suspended": bool(state.suspended),
        "suspension_reason": state.suspensionReason,
        "leeched": bool(state.leeched),
        "memory_state": (
            {
                "stability": float(memory.stability),
                "difficulty": float(memory.difficulty),
            }
            if memory is not None
            else None
        ),
    }


def deserialize_card_state(payload: Any) -> CardState:
    if not isinstance(payload, dict):
        raise StudySessionError(
            "INVALID_CARD_STATE",
            "Card state must be an object.",
            status=422,
        )
    memory_payload = payload.get("memory_state")
    memory = None
    if isinstance(memory_payload, dict):
        memory = FsrsMemoryState(
            stability=_finite_float(memory_payload.get("stability")),
            difficulty=_finite_float(memory_payload.get("difficulty")),
        )
    due_day = payload.get("due_day")
    return CardState(
        type=str(payload.get("type") or "new"),  # type: ignore[arg-type]
        stepIndex=max(0, int(payload.get("step_index") or 0)),
        due=_parse_utc_iso(payload.get("due_at")),
        dueDay=int(due_day) if due_day is not None else None,
        intervalDays=_finite_float(payload.get("interval_days")),
        ease=_finite_float(payload.get("ease"), 2.5),
        reps=max(0, int(payload.get("reps") or 0)),
        lapses=max(0, int(payload.get("lapses") or 0)),
        lastReviewAt=_parse_utc_iso(payload.get("last_review_at")),
        reviewKind=str(payload.get("review_kind") or "review"),
        schedulerMode=str(payload.get("scheduler_mode") or "legacy"),
        suspended=bool(payload.get("suspended")),
        suspensionReason=(
            str(payload.get("suspension_reason"))
            if payload.get("suspension_reason") is not None
            else None
        ),
        leeched=bool(payload.get("leeched")),
        memoryState=memory,
    )


def _states_match_for_commit(
    submitted_state: CardState,
    authoritative_state: CardState,
) -> bool:
    """Compare replay states while allowing MySQL's lost sub-second anchor."""
    submitted = serialize_card_state(submitted_state)
    authoritative = serialize_card_state(authoritative_state)
    for field_name in ("due_at", "last_review_at"):
        submitted_time = _parse_utc_iso(submitted.pop(field_name, None))
        authoritative_time = _parse_utc_iso(
            authoritative.pop(field_name, None)
        )
        if submitted_time is None or authoritative_time is None:
            if submitted_time != authoritative_time:
                return False
            continue
        if abs(submitted_time - authoritative_time) >= timedelta(seconds=1):
            return False
    return submitted == authoritative


def deserialize_deck_options(payload: Any) -> DeckOptions:
    if not isinstance(payload, dict):
        raise StudySessionError(
            "INVALID_CONFIG_SNAPSHOT",
            "Scheduler config snapshot is invalid.",
            status=422,
        )

    def _steps(name: str) -> list[timedelta]:
        raw = payload.get(name)
        if not isinstance(raw, list):
            return []
        return [
            timedelta(milliseconds=max(0, int(item)))
            for item in raw
        ]

    def _fsrs_state(raw: Any) -> FsrsAnswerState:
        row = raw if isinstance(raw, dict) else {}
        memory_row = row.get("memory")
        memory = None
        if isinstance(memory_row, dict):
            memory = FsrsMemoryState(
                stability=_finite_float(memory_row.get("stability")),
                difficulty=_finite_float(memory_row.get("difficulty")),
            )
        return FsrsAnswerState(
            intervalDays=_finite_float(row.get("interval_days"), 1.0),
            memory=memory,
        )

    fsrs_payload = payload.get("fsrs_next_states")
    fsrs_states = None
    if isinstance(fsrs_payload, dict):
        fsrs_states = FsrsNextStates(
            again=_fsrs_state(fsrs_payload.get("again")),
            hard=_fsrs_state(fsrs_payload.get("hard")),
            good=_fsrs_state(fsrs_payload.get("good")),
            easy=_fsrs_state(fsrs_payload.get("easy")),
        )

    fuzz_factor = payload.get("review_fuzz_factor")
    return DeckOptions(
        learningSteps=_steps("learning_steps_ms"),
        graduatingIntervalDays=max(
            1,
            int(payload.get("graduating_interval_days") or 1),
        ),
        easyIntervalDays=max(1, int(payload.get("easy_interval_days") or 1)),
        relearningSteps=_steps("relearning_steps_ms"),
        minimumIntervalDays=max(
            1,
            int(payload.get("minimum_interval_days") or 1),
        ),
        startingEase=_finite_float(payload.get("starting_ease"), 2.5),
        easyBonus=_finite_float(payload.get("easy_bonus"), 1.3),
        intervalModifier=max(
            0.0,
            _finite_float(payload.get("interval_modifier"), 1.0),
        ),
        hardFactor=max(0.0, _finite_float(payload.get("hard_factor"), 1.2)),
        newIntervalFactor=max(
            0.0,
            _finite_float(payload.get("new_interval_factor"), 0.0),
        ),
        minEase=_finite_float(payload.get("min_ease"), 1.3),
        maxIntervalDays=max(1, int(payload.get("max_interval_days") or 36500)),
        dayBoundaryHourLocal=max(
            0,
            min(23, int(payload.get("day_boundary_hour_local") or 0)),
        ),
        learnAheadSeconds=max(
            0,
            int(payload.get("learn_ahead_seconds") or 0),
        ),
        leechThreshold=max(0, int(payload.get("leech_threshold") or 0)),
        leechSuspend=bool(payload.get("leech_suspend")),
        schedulerMode=str(payload.get("scheduler_mode") or "legacy"),  # type: ignore[arg-type]
        fsrsNextStates=fsrs_states,
        reviewFuzzFactor=(
            _finite_float(fuzz_factor) if fuzz_factor is not None else None
        ),
        fuzz=fuzz_factor is not None,
    )


def _has_async_study_worker() -> bool:
    # Test fixtures may explicitly exercise admission with a local drain. Real
    # admission requires the DB/namespace-scoped pool advertising all current
    # wire/job decoders; no client-provided schema selects a different pool.
    return current_app.testing or has_ready_study_worker(SESSION_SCHEMA_V4)


def open_study_session(
    *,
    user: Any,
    query: Any,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    scope_type: str,
    scope_id: str,
    timezone_name: str,
    now: datetime | None = None,
    composition_selection: ResolvedCompositionSelection | None = None,
    input_bindings: dict[str, str | None] | None = None,
    wire_schema_version: str = WIRE_SCHEMA_VERSION,
    legacy_wire_schema_version: str | None = None,
    accepted_batch_schema_versions: Any = None,
    accepted_note_storage_profiles: Any = None,
) -> dict[str, Any]:
    wire_contract = _wire_contract_or_session_error(wire_schema_version)
    _require_session_algorithm(
        key=DEFAULT_ALGORITHM_IDENTITY.key,
        version=DEFAULT_ALGORITHM_IDENTITY.version,
        purpose=AlgorithmResolutionPurpose.NEW_SESSION,
    )
    # Probe shared liveness before taking the learner/subject locks. Capability
    # is a snapshot hint, not an admission promise; POST checks readiness again.
    offer_note_batches = (
        wire_contract.requires_note_authority_identity
        and current_app.config.get("STUDY_ASYNC_BATCH_ENABLED")
        and isinstance(accepted_batch_schema_versions, list)
        and "study-batch.v3" in accepted_batch_schema_versions
        and _has_async_study_worker()
    )
    try:
        authority_route = lock_study_authority_route(
            db.session,
            learner_user_id=int(user.id),
            allow_note_authority=wire_contract.requires_note_authority_identity,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise StudySessionError(exc.code, str(exc), status=409) from exc
    if wire_contract.requires_note_authority_identity and authority_route.mode_code != "NOTE":
        if legacy_wire_schema_version is None:
            raise StudySessionError(
                "NOTE_AUTHORITY_UNAVAILABLE",
                "Study Session v4 requires an active NOTE authority enrollment.",
                status=409,
            )
        fallback_contract = _wire_contract_or_session_error(
            legacy_wire_schema_version
        )
        if fallback_contract.requires_note_authority_identity:
            raise StudySessionError(
                "WIRE_CONTRACT_MISMATCH",
                "LEGACY authority fallback must use a legacy wire decoder.",
                status=409,
            )
        wire_contract = fallback_contract
    # MySQL DATETIME (without an explicit fsp) truncates sub-second precision.
    # Use the same durable anchor in the snapshot and during commit replay.
    opened_at = (now or datetime.utcnow()).replace(microsecond=0)
    if composition_selection is None:
        try:
            saved_composition_id = study_template_preset_service.resolve_session_preset(
                int(user.id), scope_type, scope_id, None,
            )
            composition_selection = resolve_composition_selection(
                query,
                clone_scope=clone_scope,
                requested_composition_id=saved_composition_id,
                request_source="saved_preset" if saved_composition_id else "internal_legacy",
            )
        except StudyCompositionError as exc:
            raise StudySessionError(
                exc.code,
                str(exc),
                status=exc.status,
                details=exc.details,
            ) from exc
    if input_bindings is None:
        input_bindings = study_template_preset_service.session_input_bindings(
            int(user.id), scope_type, scope_id, composition_selection.composition.composition_id,
        )
    try:
        selected_query = apply_composition_selection_to_query(
            query,
            clone_scope=clone_scope,
            selection=composition_selection,
        )
    except StudyCompositionError as exc:
        raise StudySessionError(
            exc.code,
            str(exc),
            status=exc.status,
            details=exc.details,
        ) from exc
    # Each Card's Note, media and Template are read below; load them in three
    # set-wise queries instead of one query per Card.
    cards = (
        selected_query.options(
            selectinload(Card.note).selectinload(Note.media_assets),
            selectinload(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs),
            selectinload(Card.template),
            selectinload(Card.application),
        )
        .order_by(Card.created_at.asc(), Card.order_key.asc())
        .limit(MAX_SESSION_CARDS + 1)
        .all()
    )
    if len(cards) > MAX_SESSION_CARDS:
        raise StudySessionError(
            "SESSION_TOO_LARGE",
            f"A study session is limited to {MAX_SESSION_CARDS} cards.",
            status=413,
        )

    if not cards:
        raise StudySessionError(
            "NO_STUDY_CARDS",
            "Bộ thẻ này chưa có thẻ học phù hợp với chế độ đã chọn.",
            status=404,
        )
    release_pins = {}
    if clone_scope is not None and getattr(clone_scope.install, "applied_release_id", None):
        release_pins = template_release_repository.deck_pins(db.session, clone_scope.install.applied_release_id)
    template_overrides = template_release_repository.load_effective_template_overrides(
        db.session, user_id=int(user.id),
        source_template_ids=[str(card.template_id) for card in cards],
        release_pins=release_pins,
    )
    if input_bindings is not None:
        input_bindings = study_template_preset_service.validate_session_bindings(
            composition_selection.composition, input_bindings,
            clone_scope=clone_scope, template_overrides=template_overrides,
        )

    # Deck rows and options depend only on (learner, local deck) within this
    # request, so resolve each once instead of once per Card.
    deck_by_id: dict[int, Any] = {}
    options_by_deck_id: dict[int | None, Any] = {}
    runtime = resolve_scheduler_runtime_settings(user_id=int(user.id))
    policies_by_deck_id: dict[int | None, dict[str, Any]] = {}
    policies_by_material: dict[str, dict[str, Any]] = {}
    template_artifacts: dict[str, dict[str, Any]] = {}

    # Both first-state policy selection and artifact construction use this
    # membership. An empty loaded set must not fall back to per-Card queries.
    clone_added_note_ids: frozenset[str] | None = None
    note_override_rows_by_note_id: dict[str, list] | None = None
    if clone_scope is not None:
        from app.repositories.flashcards_share_repository import (
            get_clone_note_field_overrides_batch,
        )

        install_id = str(clone_scope.install.id)
        clone_added_note_ids = frozenset(
            str(value)
            for value in db.session.execute(
                select(DeckCloneAddedNote.note_id).where(
                    DeckCloneAddedNote.deck_install_id == install_id
                )
            ).scalars()
        )
        note_override_rows_by_note_id = {
            str(note_id): rows
            for (_install, note_id), rows in get_clone_note_field_overrides_batch(
                [install_id], sorted({str(card.note_id) for card in cards})
            ).items()
        }

    def local_deck_for(deck_id: int | None):
        if deck_id is None:
            return None
        if deck_id not in deck_by_id:
            deck_by_id[deck_id] = db.session.get(Deck, deck_id)
        return deck_by_id[deck_id]

    def options_for(deck_id: int | None):
        if deck_id not in options_by_deck_id:
            options_by_deck_id[deck_id] = resolve_deck_options(
                user_id=int(user.id),
                deck_id=deck_id,
                deck_obj=local_deck_for(deck_id),
                runtime_settings=runtime,
            )
        return options_by_deck_id[deck_id]

    def policy_for(deck_id: int | None):
        if deck_id not in policies_by_deck_id:
            options = options_for(deck_id)
            # The options were resolved once per deck and remain immutable
            # during issuance. Reuse only policies with identical executable
            # inputs, including timezone; different deck presets may coincide.
            material_key = study_artifact_service.canonical_digest({
                "config": serialize_deck_options(options),
                "timezone": timezone_name,
                "algorithm_key": DEFAULT_ALGORITHM_IDENTITY.key,
                "algorithm_version": DEFAULT_ALGORITHM_IDENTITY.version,
            })
            if material_key not in policies_by_material:
                policies_by_material[material_key] = build_scheduler_policy(
                    options=options, timezone_name=timezone_name,
                )
            policies_by_deck_id[deck_id] = policies_by_material[material_key]
        return policies_by_deck_id[deck_id]

    authority_subjects = None
    if authority_route.mode_code == "NOTE":
        from app.services.study_note_pristine_service import materialize_pristine_notes

        try:
            # A v4 pin needs current state: first-state materialize the
            # never-studied Notes (owned or overlay source) this lease covers,
            # using the same deck options LEGACY would use for a first review.
            starting_ease_by_note_id: dict[str, float] = {}
            for card in cards:
                if str(card.note_id) in starting_ease_by_note_id:
                    continue
                effective_deck_id = study_service.resolve_effective_study_deck_id(
                    card=card,
                    clone_scope=clone_scope,
                    clone_added_note_ids=clone_added_note_ids,
                )
                starting_ease_by_note_id[str(card.note_id)] = float(
                    options_for(effective_deck_id).startingEase
                )
            materialize_pristine_notes(
                db.session,
                route=authority_route,
                cards=cards,
                starting_ease_by_note_id=starting_ease_by_note_id,
                now_utc=opened_at,
            )
            authority_subjects = lock_study_session_authority_subjects(
                db.session,
                route=authority_route,
                logical_note_keys=[str(card.note_id) for card in cards],
                now_utc=opened_at,
            )
        except StudySessionAuthorityPinError as exc:
            db.session.rollback()
            raise StudySessionError(exc.code, str(exc), status=409) from exc
        except StudyAuthorityFenceError as exc:
            db.session.rollback()
            raise StudySessionError(exc.code, str(exc), status=409) from exc
    progress_map = {}
    session_id = str(uuid4())
    token = secrets.token_urlsafe(32)
    policies: dict[str, Any] = {}
    templates: dict[str, Any] = {}
    contents: dict[str, Any] = {}
    compositions: dict[str, Any] = {}
    card_payloads: list[dict[str, Any]] = []
    session_card_values: list[dict[str, Any]] = []
    frozen_binding: dict[str, Any] | None = None

    for ordinal, card in enumerate(cards):
        note = card.note
        local_deck_id = study_service.resolve_effective_study_deck_id(
            card=card,
            clone_scope=clone_scope,
            clone_added_note_ids=clone_added_note_ids,
        )
        local_deck = local_deck_for(local_deck_id)
        options = options_for(local_deck_id)
        policy = policy_for(local_deck_id)
        policy_key = policy["config_hash"]
        if policy_key not in policies:
            policies[policy_key] = {
                **policy,
                "preset_id": (
                    int(local_deck.scheduler_preset_id)
                    if local_deck is not None
                    and local_deck.scheduler_preset_id is not None
                    else None
                ),
            }

        progress = progress_map.get(str(card.id))
        if authority_subjects is not None:
            state = authority_subjects.state_by_logical_note_key[str(note.id)]
        else:
            state = card_state_from_progress(
                progress,
                opened_at,
                timezone_name=timezone_name,
                user_id=int(user.id),
                options=options,
            )
        state_payload = serialize_card_state(state)
        state_hash = study_artifact_service.canonical_digest(state_payload)
        context = study_artifact_service.build_effective_study_card(
            card=card,
            clone_scope=clone_scope,
            clone_added_note_ids=clone_added_note_ids,
            note_override_rows_by_note_id=note_override_rows_by_note_id,
            template_overrides=template_overrides,
        )
        if input_bindings is not None:
            # Session bindings replace application defaults only in this
            # detached render source; storage and existing leases stay intact.
            source_values = {key: value for key, value in vars(context.template).items()
                             if not key.startswith("_")}
            for name in ("id", "name", "front_html", "back_html", "shared_css", "input_schema", "updated_at"):
                source_values[name] = getattr(context.template, name, None)
            source_values["input_schema"] = study_template_preset_service.effective_input_schema(
                context.template, getattr(context.field_defs, "source_fields", context.field_defs),
            )
            source_values["input_bindings"] = deepcopy(input_bindings)
            context = apply_binding_projection(replace(context, template=SimpleNamespace(**source_values)))
        # template_version covers raw sources, CSS, renderer ABI and effective
        # field definitions, so an overlay rename/schema change cannot reuse
        # the wrong sanitized artifact. The cache lives only in this issuance.
        artifact_version = study_artifact_service.template_version(context)
        if artifact_version not in template_artifacts:
            template_artifacts[artifact_version] = study_artifact_service.build_template_artifact(context)
        template = template_artifacts[artifact_version]
        content = study_artifact_service.build_content_artifact(context)
        template_key = f"{template['id']}:{template['version']}"
        content_key = f"{content['id']}:{content['version']}"
        templates.setdefault(template_key, template)
        contents.setdefault(content_key, content)
        composition = resolve_compatibility_composition_for_card(card, clone_scope)
        if composition.composition_id != composition_selection.composition.composition_id:
            raise StudySessionError(
                "COMPOSITION_RESOLUTION_CONFLICT",
                "A selected session card resolved to a different composition.",
                status=409,
            )
        compositions.setdefault(composition.composition_id, composition.to_dict())
        binding_material = {
            "schema_version": "study-composition-binding.v1",
            "composition_id": composition.composition_id,
            "definition_id": composition.definition_id,
            "definition_version": template["version"],
            "application_id": composition.application_id,
            "application_occurrence_id": composition.application_id,
            "binding_kind": "legacy-fielddef-direct",
            "field_bindings": [
                {
                    "input_id": f"legacy-field:{field_def['id']}",
                    "field_def_id": field_def["id"],
                    "field_name": field_def["name"],
                    "field_type": field_def["field_type"],
                    "required": field_def["required"],
                }
                for field_def in template.get("field_defs", [])
            ],
        }
        binding_material["binding_fingerprint"] = (
            study_artifact_service.canonical_digest(binding_material)
        )
        if frozen_binding is None:
            frozen_binding = binding_material
        elif frozen_binding != binding_material:
            raise StudySessionError(
                "COMPOSITION_BINDING_CONFLICT",
                "Cards in the selected composition resolved different bindings.",
                status=409,
            )
        base_revision = int(getattr(progress, "revision", 0) or 0)
        created_at = getattr(card, "created_at", None) or opened_at

        card_payload = {
                "card_id": str(card.id),
                "note_id": str(note.id),
                "template_id": str(card.template_id),
                "composition_id": composition.composition_id,
                "source_deck_id": (
                    int(note.deck_id) if note.deck_id is not None else None
                ),
                "local_deck_id": local_deck_id,
                "note_type_id": str(note.note_type_id),
                "created_at": _utc_iso(created_at),
                "policy_key": policy_key,
                "template_key": template_key,
                "content_key": content_key,
                "base_revision": base_revision,
                "base_state_hash": state_hash,
                "state": state_payload,
                "can_edit_card": bool(note.user_id == user.id),
            }
        if authority_subjects is not None:
            locked = authority_subjects.locked_by_logical_note_key[str(note.id)]
            authority_identity = build_note_authority_wire_identity(
                enrollment_epoch=authority_route.epoch,
                logical_note_key=bytes(locked.subject.logical_note_key),
                subject_generation=locked.subject.subject_generation,
                base_authority_revision=locked.token.authority_revision,
                base_authority_state_hash=locked.state.semantic_state_hash,
            )
            card_payload["authority_pin"] = (
                serialize_study_note_authority_identity(authority_identity)
            )
        card_payloads.append(card_payload)
        session_card_values.append(
            {
                "session_id": session_id,
                "card_id": str(card.id),
                "source_deck_id": (
                    int(note.deck_id) if note.deck_id is not None else None
                ),
                "local_deck_id": local_deck_id,
                "note_type_id": str(note.note_type_id),
                "scheduler_preset_id": (
                    int(local_deck.scheduler_preset_id)
                    if local_deck is not None
                    and local_deck.scheduler_preset_id is not None
                    else None
                ),
                "base_progress_revision": base_revision,
                "base_state_hash": state_hash,
                "scheduler_config_hash": policy_key,
                "initial_state_json": _json_dumps(state_payload),
                "ordinal": ordinal,
            }
        )

    scope_deck = (
        db.session.get(Deck, int(scope_id))
        if scope_type == "deck" and str(scope_id).isdigit()
        else None
    )
    if frozen_binding is None:
        raise StudySessionError(
            "COMPOSITION_BINDING_UNAVAILABLE",
            "The selected composition has no executable binding material.",
            status=409,
        )
    selected_composition_payload = composition_selection.composition.to_dict()
    storage_profile = (
        study_service.NOTE_STORAGE_PROFILE
        if authority_subjects is not None
        and isinstance(accepted_note_storage_profiles, list)
        and study_service.NOTE_STORAGE_PROFILE in accepted_note_storage_profiles
        else None
    )
    snapshot_material = {
        "schema_version": wire_contract.session_schema,
        "session_id": session_id,
        "user_id": int(user.id),
        "scope": {
            "type": scope_type,
            "id": str(scope_id),
            "name": str(scope_deck.name) if scope_deck is not None else "",
        },
        "server_now_utc": _utc_iso(opened_at),
        "timezone": timezone_name,
        "day_boundary_hour_local": int(runtime.day_boundary_hour_local),
        "learn_ahead_seconds": int(runtime.learn_ahead_seconds),
        "scheduler_algorithm": SCHEDULER_ALGORITHM,
        "algorithm_version": ALGORITHM_VERSION,
        "queue_contract_version": "flama-queue.v1",
        "composition_contract_version": COMPOSITION_CONTRACT_VERSION,
        "selected_composition_id": composition_selection.composition.composition_id,
        "selected_composition": selected_composition_payload,
        "composition_selection_resolution": composition_selection.resolution,
        "composition_binding": frozen_binding,
        "policies": policies,
        "cards": card_payloads,
        "templates": templates,
        "contents": contents,
        "compositions": compositions,
    }
    if authority_subjects is not None:
        snapshot_material.update(
            {
                "authority_mode": "NOTE",
                "enrollment_epoch": str(authority_route.epoch),
            }
        )
        if offer_note_batches:
            snapshot_material["batch_transport"] = "study-note-batch-transport.v1"
        if storage_profile is not None:
            snapshot_material["storage_profile"] = storage_profile
    snapshot_hash = study_artifact_service.canonical_digest(snapshot_material)
    expires_at = opened_at + SESSION_TTL
    session = StudySession(
        id=session_id,
        user_id=int(user.id),
        scope_type=scope_type,
        scope_id=str(scope_id),
        local_deck_id=(
            int(scope_deck.id) if scope_deck is not None else None
        ),
        clone_install_id=(
            str(clone_scope.install.id) if clone_scope is not None else None
        ),
        status="open",
        scheduler_algorithm=SCHEDULER_ALGORITHM,
        algorithm_version=ALGORITHM_VERSION,
        wire_schema_version=wire_contract.session_schema,
        timezone=timezone_name,
        day_boundary_hour_local=int(runtime.day_boundary_hour_local),
        learn_ahead_seconds=int(runtime.learn_ahead_seconds),
        snapshot_hash=snapshot_hash,
        token_hash=_token_hash(token),
        config_snapshot_json=encode_study_session_config(
            policies=policies,
            selected_composition=selected_composition_payload,
            composition_binding=frozen_binding,
            storage_profile=storage_profile,
        ),
        opened_at=opened_at,
        expires_at=expires_at,
    )
    db.session.add(session)
    db.session.flush()
    from app.services.study_retirement_telemetry_service import record_legacy_usage

    record_legacy_usage("session.issue", wire=session.wire_schema_version)
    # One multi-row INSERT instead of one INSERT per Card (MySQL has no
    # RETURNING, so ORM objects would be inserted one by one for their IDs).
    db.session.execute(insert(StudySessionCard), session_card_values)
    if authority_subjects is not None:
        try:
            session_card_rows = tuple(
                db.session.execute(
                    select(StudySessionCard)
                    .where(StudySessionCard.session_id == session_id)
                    .order_by(StudySessionCard.ordinal.asc())
                ).scalars()
            )
            if [row.card_id for row in session_card_rows] != [
                payload["card_id"] for payload in card_payloads
            ]:
                raise StudySessionAuthorityPinError(
                    "SESSION_AUTHORITY_PIN_DIVERGED",
                    "Persisted Study Session membership differs from its snapshot.",
                )
            for session_card, card_payload in zip(
                session_card_rows,
                card_payloads,
                strict=True,
            ):
                pin = stage_study_session_authority_pin(
                    db.session,
                    study_session=session,
                    session_card=session_card,
                    route=authority_route,
                    locked=authority_subjects.locked_by_logical_note_key[
                        str(card_payload["note_id"])
                    ],
                    now_utc=opened_at,
                    membership_created_in_transaction=True,
                )
                if serialize_study_session_authority_pin(pin) != card_payload.get(
                    "authority_pin"
                ):
                    raise StudySessionAuthorityPinError(
                        "SESSION_AUTHORITY_PIN_DIVERGED",
                        "Persisted Study Session authority pin differs from its snapshot.",
                    )
        except StudySessionAuthorityPinError as exc:
            db.session.rollback()
            raise StudySessionError(exc.code, str(exc), status=409) from exc
    flush_review_analytics_deltas(db.session)
    db.session.commit()
    return {
        **snapshot_material,
        "session_token": token,
        "snapshot_hash": snapshot_hash,
        "expires_at": _utc_iso(expires_at),
    }


def get_study_session_status(
    *, user: Any, session_id: str, now: datetime | None = None,
) -> dict[str, Any]:
    """Own a read transaction so status never retains locks or writes state."""
    try:
        with db.session.no_autoflush:
            return _get_study_session_status(user=user, session_id=session_id, now=now)
    finally:
        db.session.rollback()


def _get_study_session_status(
    *,
    user: Any,
    session_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    route = lock_study_authority_route(
        db.session, learner_user_id=int(user.id), allow_note_authority=True,
    )
    session = StudySession.query.filter_by(
        id=session_id,
        user_id=int(user.id),
    ).populate_existing().with_for_update().first()
    if session is None:
        raise StudySessionError(
            "SESSION_NOT_FOUND",
            "Study session was not found.",
            status=404,
        )

    status = str(session.status or "open")
    from app.services.study_retirement_telemetry_service import record_legacy_usage

    record_legacy_usage("session.restore", wire=session.wire_schema_version)
    if status == "open" and (now or datetime.utcnow()) > session.expires_at:
        status = "expired"
    if status == "open":
        _require_session_algorithm(
            key=session.scheduler_algorithm,
            version=session.algorithm_version,
            purpose=AlgorithmResolutionPurpose.EXISTING_LEASE,
        )

    is_stale = False
    extra = {}
    if session.wire_schema_version == SESSION_SCHEMA_V4:
        from app.services.study_note_session_status_service import inspect_note_session_continuation

        try:
            stream, stale_reason = inspect_note_session_continuation(
                user=user, study_session=session, route=route,
                check_current=status == "open", now=now,
            )
            extra["batch_stream"] = stream
            if stale_reason:
                is_stale = True
                extra["stale_reason"] = stale_reason
        except Exception as exc:
            code = domain_error_code(exc)
            if not code:
                raise
            is_stale = True
            extra["stale_reason"] = code

    threshold = (
        max(session.created_at, session.opened_at)
        if session.created_at and session.opened_at
        else (session.created_at or session.opened_at)
    )
    if status == "open" and threshold:
        # The dealt Cards are named by presentation keys (or pre-P11 IDs).
        dealt = load_cards(db.session, [
            row[0] for row in db.session.query(StudySessionCard.card_id)
            .filter(StudySessionCard.session_id == session.id).all()
        ]).values()
        template_ids = sorted({str(card.template_id) for card in dealt})
        note_ids = sorted({str(card.note_id) for card in dealt})
        has_updated_template = bool(template_ids) and (
            db.session.query(Template.id)
            .filter(Template.id.in_(template_ids), Template.updated_at > threshold)
            .with_for_update(read=True)
            .first()
            is not None
        )
        if has_updated_template:
            is_stale = True
        elif note_ids:
            has_updated_note = (
                db.session.query(Note.id)
                .filter(Note.id.in_(note_ids), Note.updated_at > threshold)
                .with_for_update(read=True)
                .first()
                is not None
            )
            if has_updated_note:
                is_stale = True

    return {
        "schema_version": "study-session-status.v1",
        "session_id": session.id,
        "status": status,
        "stale": is_stale,
        "expires_at": _utc_iso(session.expires_at),
        "committed_at": _utc_iso(session.committed_at),
        **extra,
    }


def _validate_session_token(session: StudySession, raw_token: Any) -> None:
    candidate = str(raw_token or "")
    if not candidate or not hmac.compare_digest(
        session.token_hash,
        _token_hash(candidate),
    ):
        raise StudySessionError(
            "INVALID_SESSION_TOKEN",
            "Study session token is invalid.",
            status=403,
        )


def _idempotent_response(
    *,
    session_id: str,
    idempotency_key: str,
    request_hash: str,
) -> dict[str, Any] | None:
    row = StudySessionCommit.query.filter_by(
        session_id=session_id,
        idempotency_key=idempotency_key,
    ).first()
    if row is None:
        return None
    if row.request_hash != request_hash:
        # A commit row exists only once the lease committed under this id. A
        # retry that changed the payload (a browser that lost the receipt and
        # resent with another commit reason) cannot commit again; answer with
        # the stored receipt so the client can settle, never re-apply it.
        raise StudySessionError(
            "SESSION_ALREADY_COMMITTED",
            "Study session was already committed.",
            status=409,
            details=json.loads(row.response_json),
        )
    return json.loads(row.response_json)


def _decode_and_validate_session_config(
    session: StudySession,
    payload: dict[str, Any],
):
    try:
        config = decode_study_session_config(session.config_snapshot_json)
        if config.storage_profile is not None and session.wire_schema_version != SESSION_SCHEMA_V4:
            raise StudySessionConfigError("NOTE storage profile requires a v4 lease.")
    except StudySessionConfigError as exc:
        raise StudySessionError(
            "INVALID_CONFIG_SNAPSHOT",
            "Stored study session config is invalid.",
            status=500,
        ) from exc
    try:
        validate_payload_composition(config, payload)
    except StudySessionConfigError as exc:
        raise StudySessionError(
            "COMPOSITION_SNAPSHOT_MISMATCH",
            str(exc),
            status=409,
        ) from exc
    return config


def study_batch_job_from_admission(
    batch: StudySessionBatch,
    session: StudySession,
) -> dict[str, Any]:
    """Rebuild a queued job from the committed admission row, never Redis state."""

    if (
        batch.status != "enqueued"
        or str(batch.session_id) != str(session.id)
        or int(batch.user_id) != int(session.user_id)
        or not batch.payload_json
    ):
        raise StudySessionError(
            "BATCH_OUTBOX_INVALID",
            "Batch admission is not a recoverable queued job.",
            status=409,
        )
    try:
        payload = json.loads(batch.payload_json)
    except (TypeError, ValueError) as exc:
        raise StudySessionError(
            "BATCH_OUTBOX_INVALID", "Batch admission payload is corrupt.", status=409
        ) from exc
    if not isinstance(payload, dict) or _request_hash(payload) != batch.request_hash:
        raise StudySessionError(
            "BATCH_OUTBOX_INVALID",
            "Batch admission payload differs from its durable hash.",
            status=409,
        )
    requested_batch_id = str(
        payload.get("batch_id") or payload.get("commit_id") or ""
    ).strip()
    if requested_batch_id and requested_batch_id != str(batch.batch_id):
        raise StudySessionError(
            "BATCH_OUTBOX_INVALID", "Batch admission ID differs from its payload.", status=409
        )
    wire_contract = _wire_contract_or_session_error(session.wire_schema_version)
    if wire_contract.requires_note_authority_identity:
        from app.services.study_note_batch_transport_service import note_batch_job_from_admission

        try:
            return note_batch_job_from_admission(batch, session)
        except Exception as exc:
            code = domain_error_code(exc)
            if code:
                raise StudySessionError(code, str(exc), status=409) from exc
            raise
    source_schema = str(payload.get("schema_version") or "")
    if source_schema not in {wire_contract.batch_schema, wire_contract.commit_schema}:
        raise StudySessionError(
            "BATCH_OUTBOX_INVALID",
            "Batch admission wire schema differs from its session.",
            status=409,
        )
    raw_events = payload.get("events")
    if not isinstance(raw_events, list) or len(raw_events) != int(batch.event_count):
        raise StudySessionError(
            "BATCH_OUTBOX_INVALID",
            "Batch admission event count differs from its payload.",
            status=409,
        )
    commit_reason = str(payload.get("commit_reason") or "rollover").strip().lower()
    is_final = bool(payload.get("is_final", False)) or commit_reason in {
        "auto_finish", "manual_exit", "page_exit",
    }
    if (
        commit_reason != batch.commit_reason
        or is_final != bool(batch.is_final)
        or int(payload.get("batch_sequence", 1) or 1) != int(batch.batch_sequence)
    ):
        raise StudySessionError(
            "BATCH_OUTBOX_INVALID",
            "Batch admission metadata differs from its payload.",
            status=409,
        )
    _validate_session_token(session, payload.get("session_token"))
    snapshot_hash = str(payload.get("snapshot_hash") or "").strip()
    if snapshot_hash and snapshot_hash != session.snapshot_hash:
        raise StudySessionError(
            "BATCH_OUTBOX_INVALID",
            "Batch admission snapshot differs from its session.",
            status=409,
        )
    session_config = _decode_and_validate_session_config(session, payload)
    attempt_count = int(batch.attempt_count)
    if attempt_count < 0:
        raise StudySessionError(
            "BATCH_OUTBOX_INVALID",
            "Batch admission has a negative retry count.",
            status=409,
        )
    return {
        "schema_version": "study-batch-job.v1",
        "source_schema_version": source_schema,
        "session_wire_schema_version": wire_contract.session_schema,
        "batch_id": str(batch.batch_id),
        "batch_sequence": int(batch.batch_sequence),
        "session_id": str(session.id),
        "user_id": int(batch.user_id),
        "session_token": payload.get("session_token"),
        "snapshot_hash": session.snapshot_hash,
        "composition_id": session_config.selected_composition_id,
        "commit_reason": commit_reason,
        "is_final": is_final,
        "events": raw_events,
        "final_states": payload.get("final_states"),
        "enqueued_at": _utc_iso(batch.enqueued_at),
        "request_hash": batch.request_hash,
        "attempts": attempt_count,
        "max_retries": 3,
    }


def enqueue_study_session_batch(
    *,
    user: Any,
    session_id: str,
    payload: Any,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate and enqueue a study review batch into Redis for asynchronous processing."""
    if not _has_async_study_worker():
        # Check before learner/session locks, independently of snapshot-time
        # negotiation. A later process/network crash is handled by DB recovery.
        raise StudySessionError(
            "ASYNC_BATCH_WORKER_UNAVAILABLE",
            "No compatible Study batch consumer is ready; retain pending work and retry later.",
            status=503,
        )
    if not isinstance(payload, dict):
        raise StudySessionError(
            "INVALID_BATCH",
            "Batch payload must be an object.",
            status=400,
        )
    batch_id = str(payload.get("batch_id") or payload.get("commit_id") or uuid4()).strip()
    if not batch_id or len(batch_id) > 64:
        raise StudySessionError(
            "INVALID_BATCH_ID",
            "batch_id is required.",
            status=400,
        )
    commit_reason = str(
        payload.get("commit_reason") or "rollover"
    ).strip().lower()
    if commit_reason not in VALID_COMMIT_REASONS:
        raise StudySessionError(
            "INVALID_COMMIT_REASON",
            "commit_reason must be auto_finish, manual_exit, page_exit, or rollover.",
            status=422,
        )
    try:
        authority_route = lock_study_authority_route(
            db.session,
            learner_user_id=int(user.id),
            allow_note_authority=True,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise StudySessionError(exc.code, str(exc), status=409) from exc
    session = (
        StudySession.query.filter_by(id=session_id, user_id=int(user.id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if session is None:
        raise StudySessionError(
            "SESSION_NOT_FOUND",
            "Study session was not found.",
            status=404,
        )
    _validate_session_token(session, payload.get("session_token"))
    if authority_route.mode_code == "NOTE" and session.wire_schema_version == SESSION_SCHEMA_V4:
        from app.services.study_note_batch_transport_service import enqueue_note_study_session_batch

        return enqueue_note_study_session_batch(
            user=user, session=session, route=authority_route, payload=payload, now=now,
        )
    if authority_route.mode_code == "NOTE" or session.wire_schema_version == SESSION_SCHEMA_V4:
        db.session.rollback()
        raise StudySessionError(
            "ASYNC_BATCH_NOTE_UNSUPPORTED",
            "Study Session v4 cannot enter the legacy asynchronous Card worker.",
            status=409,
        )
    wire_contract = _wire_contract_or_session_error(session.wire_schema_version)
    schema_version = str(payload.get("schema_version") or "")
    accepted_envelopes = {
        wire_contract.batch_schema,
        wire_contract.commit_schema,
    }
    if schema_version not in accepted_envelopes:
        expected = " or ".join(sorted(accepted_envelopes))
        raise StudySessionError(
            "UNSUPPORTED_BATCH_SCHEMA",
            f"schema_version must be {expected} for this session.",
            status=422,
        )
    snapshot_hash = str(payload.get("snapshot_hash") or "").strip()
    if snapshot_hash and snapshot_hash != session.snapshot_hash:
        raise StudySessionError(
            "SNAPSHOT_MISMATCH",
            "Study snapshot no longer matches this session.",
            status=409,
        )
    session_config = _decode_and_validate_session_config(session, payload)

    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raise StudySessionError(
            "INVALID_EVENTS",
            "events must be an array.",
            status=400,
        )

    from app.services.study_queue_service import (
        enqueue_study_batch,
    )

    payload_hash = _request_hash(payload)
    enqueued_at = now or datetime.utcnow()

    # Idempotency check: if batch was already completed, return receipt immediately
    existing_batch = (
        StudySessionBatch.query.filter_by(session_id=session.id, batch_id=batch_id)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if existing_batch and existing_batch.request_hash != payload_hash:
        db.session.rollback()
        raise StudySessionError(
            "BATCH_IDEMPOTENCY_CONFLICT",
            "This batch ID was already admitted with a different payload.",
            status=409,
        )
    if existing_batch and existing_batch.status == "completed":
        receipt = {
            "schema_version": "study-batch-receipt.v1",
            "status": "already_processed",
            "session_id": session.id,
            "batch_id": batch_id,
            "event_count": existing_batch.event_count,
            "enqueued_at": _utc_iso(existing_batch.enqueued_at),
        }
        db.session.rollback()
        return receipt
    if existing_batch and existing_batch.status == "failed":
        db.session.rollback()
        raise StudySessionError(
            "BATCH_FAILED",
            "This batch ID has already failed and cannot be re-admitted.",
            status=409,
        )
    if session.status != "open" and session.status != "expired":
        db.session.rollback()
        raise StudySessionError(
            "SESSION_NOT_OPEN", "Study session is not open.", status=409
        )
    # An already-admitted job retains its lease even if its Redis delivery was
    # lost. Expiry prevents new admission, not recovery of an accepted request.
    # Retention marks a session ``expired`` only when it has no admitted batch.
    if session.status == "expired" or (existing_batch is None and enqueued_at > session.expires_at):
        db.session.rollback()
        raise StudySessionError(
            "SESSION_EXPIRED", "Study session has expired.", status=410
        )
    if existing_batch is None:
        pending_final = (
            StudySessionBatch.query.filter_by(
                session_id=session.id, status="enqueued", is_final=True
            )
            .with_for_update()
            .first()
        )
        if pending_final is not None:
            db.session.rollback()
            raise StudySessionError(
                "BATCH_AFTER_FINAL",
                "A final batch is already admitted for this session.",
                status=409,
            )

    is_final = bool(payload.get("is_final", False)) or commit_reason in {
        "auto_finish",
        "manual_exit",
        "page_exit",
    }

    if existing_batch is None:
        batch_row = StudySessionBatch(
            session_id=session.id,
            user_id=int(user.id),
            batch_id=batch_id,
            batch_sequence=int(payload.get("batch_sequence", 1) or 1),
            event_count=len(raw_events),
            status="enqueued",
            commit_reason=commit_reason,
            is_final=is_final,
            request_hash=payload_hash,
            payload_json=_json_dumps(payload),
            enqueued_at=enqueued_at,
        )
        db.session.add(batch_row)
        try:
            flush_review_analytics_deltas(db.session)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # A concurrent admission may have won the unique (session, batch)
            # key after our first read. Never enqueue a different job body for
            # the winner's durable row.
            existing_batch = StudySessionBatch.query.filter_by(
                session_id=session.id,
                batch_id=batch_id,
            ).first()
            if existing_batch is None:
                db.session.rollback()
                raise StudySessionError(
                    "BATCH_ADMISSION_CONFLICT",
                    "Batch admission failed without a durable matching row.",
                    status=409,
                )
            if existing_batch.request_hash != payload_hash:
                db.session.rollback()
                raise StudySessionError(
                    "BATCH_IDEMPOTENCY_CONFLICT",
                    "This batch ID was already admitted with a different payload.",
                    status=409,
                )
            if existing_batch.status == "completed":
                receipt = {
                    "schema_version": "study-batch-receipt.v1",
                    "status": "already_processed",
                    "session_id": session.id,
                    "batch_id": batch_id,
                    "event_count": existing_batch.event_count,
                    "enqueued_at": _utc_iso(existing_batch.enqueued_at),
                }
                db.session.rollback()
                return receipt
            if existing_batch.status == "failed":
                db.session.rollback()
                raise StudySessionError(
                    "BATCH_FAILED",
                    "This batch ID has already failed and cannot be re-admitted.",
                    status=409,
                )

    admitted_batch = existing_batch if existing_batch is not None else batch_row
    job_payload = study_batch_job_from_admission(admitted_batch, session)

    # No DB mutation remains after the durable admission row is committed.
    # Release the learner fence before the external queue push can block.
    db.session.rollback()
    enqueue_study_batch(job_payload)

    return {
        "schema_version": "study-batch-receipt.v1",
        "status": "enqueued",
        "session_id": session_id,
        "batch_id": batch_id,
        "event_count": len(raw_events),
        "enqueued_at": _utc_iso(enqueued_at),
    }


def _replay_session_events(
    *, session, payload, session_cards, raw_events, note_authority_pins, committed_at,
):
    """Pure verification from the frozen lease/action log, never ReviewEvent state."""
    membership = {row.card_id: row for row in session_cards}
    session_config = _decode_and_validate_session_config(session, payload)
    policies = session_config.policies
    states = {
        row.card_id: deserialize_card_state(json.loads(row.initial_state_json))
        for row in session_cards
    }
    replayed_events: list[
        tuple[
            dict[str, Any],
            StudySessionCard,
            CardState,
            CardState,
            datetime,
            DeckOptions,
            ReviewTransitionResult,
        ]
    ] = []
    last_offset = -1
    touched_ids: set[str] = set()
    event_ids: set[str] = set()
    siblings_by_note: dict[str, list[StudySessionCard]] = {}
    if note_authority_pins is not None:
        for member in session_cards:
            identity = note_authority_pins.identity_by_session_card_id[int(member.id)]
            siblings_by_note.setdefault(identity.logical_note_key, []).append(member)

    for index, raw_event in enumerate(raw_events, start=1):
        if not isinstance(raw_event, dict):
            raise StudySessionError(
                "INVALID_EVENT",
                f"Event {index} must be an object.",
                status=422,
            )
        try:
            raw_event = validate_session_event_payload(raw_event)
        except ReviewEventPayloadError as exc:
            raise StudySessionError(
                exc.code,
                str(exc),
                status=exc.status,
                details={"event_index": index, "field": exc.field},
            ) from exc
        sequence = int(raw_event.get("sequence") or 0)
        if sequence != index:
            raise StudySessionError(
                "INVALID_EVENT_SEQUENCE",
                "Event sequence must be contiguous and start at 1.",
                status=422,
            )
        event_id = str(raw_event.get("event_id") or "").strip()
        try:
            UUID(event_id)
        except (TypeError, ValueError, AttributeError):
            raise StudySessionError(
                "INVALID_EVENT_ID",
                f"Event {index} has an invalid event_id.",
                status=422,
            )
        if event_id in event_ids:
            raise StudySessionError(
                "DUPLICATE_EVENT_ID",
                f"Event {index} reuses an event_id.",
                status=422,
            )
        event_ids.add(event_id)
        card_id = str(raw_event.get("card_id") or "").strip()
        session_card = membership.get(card_id)
        if session_card is None:
            raise StudySessionError(
                "CARD_OUTSIDE_SESSION",
                f"Card {card_id} is not part of this session.",
                status=422,
            )
        rating = str(raw_event.get("rating") or "").strip().lower()
        if rating not in VALID_RATINGS:
            raise StudySessionError(
                "INVALID_RATING",
                f"Event {index} has an invalid rating.",
                status=422,
            )
        try:
            offset_ms = int(raw_event.get("scheduler_offset_ms") or 0)
        except (TypeError, ValueError) as exc:
            raise StudySessionError(
                "INVALID_EVENT_TIME",
                f"Event {index} has an invalid scheduler offset.",
                status=422,
            ) from exc
        elapsed_commit_ms = max(
            0,
            int((committed_at - session.opened_at).total_seconds() * 1000),
        )
        max_offset = min(
            int(SESSION_TTL.total_seconds() * 1000),
            elapsed_commit_ms + 5 * 60 * 1000,
        )
        if offset_ms < last_offset or offset_ms < 0 or offset_ms > max_offset:
            raise StudySessionError(
                "INVALID_EVENT_TIME",
                "Scheduler offsets must be monotonic and within the session lease.",
                status=422,
            )
        last_offset = offset_ms
        policy_key = str(
            raw_event.get("policy_key")
            or session_card.scheduler_config_hash
        )
        if policy_key != session_card.scheduler_config_hash:
            raise StudySessionError(
                "CONFIG_MISMATCH",
                f"Event {index} uses the wrong scheduler config.",
                status=409,
            )
        policy = policies.get(policy_key)
        if not isinstance(policy, dict):
            raise StudySessionError(
                "CONFIG_MISMATCH",
                "Scheduler config snapshot is missing.",
                status=409,
            )
        try:
            action_contract = validate_review_event_wire_contract(
                raw_event,
                session_schema=session.wire_schema_version,
                session_id=session.id,
                algorithm_key=session.scheduler_algorithm,
                algorithm_version=session.algorithm_version,
                policy=policy,
                event_index=index,
                note_authority=(
                    note_authority_pins.identity_by_session_card_id[
                        int(session_card.id)
                    ]
                    if note_authority_pins is not None
                    else None
                ),
            )
        except StudyWireContractError as exc:
            raise StudySessionError(
                exc.code,
                str(exc),
                status=exc.status,
                details={"event_index": index},
            ) from exc
        options = deserialize_deck_options(policy.get("config"))
        answer_at = session.opened_at + timedelta(milliseconds=offset_ms)
        if note_authority_pins is not None:
            # NOTE native reviews use the legacy DATETIME(0) clock while the
            # lossless rollback projection is required. Quantize BEFORE the
            # scheduler transition, just like direct NOTE reviews; never drop
            # precision from an already calculated canonical state. Keep the
            # original offset in the admitted event/idempotency fingerprint.
            answer_at = answer_at.replace(microsecond=0)
        before = states[card_id]
        requested_before_hash = str(
            raw_event.get("before_state_hash") or ""
        ).strip()
        actual_before_hash = study_artifact_service.canonical_digest(
            serialize_card_state(before)
        )
        if requested_before_hash and requested_before_hash != actual_before_hash:
            raise StudySessionError(
                "SCHEDULER_REPLAY_MISMATCH",
                f"Event {index} before-state does not match server replay.",
                status=422,
            )
        try:
            transition = study_service.execute_native_review_transition(
                study_service.NativeReviewTransitionInput(
                    state=before,
                    deck_options=options,
                    reviewed_at=answer_at,
                    action=action_contract.rating,
                    timezone_name=session.timezone,
                    algorithm_key=session.scheduler_algorithm,
                    algorithm_version=session.algorithm_version,
                    trigger_key=action_contract.trigger_key,
                    trigger_contract_version=(
                        action_contract.trigger_contract_version
                    ),
                    storage_profile=(
                        session_config.storage_profile
                        if note_authority_pins is not None else None
                    ),
                )
            )
        except study_service.StudyReviewError as exc:
            raise StudySessionError(exc.code, str(exc), status=exc.status) from exc
        except StudyAlgorithmNotFoundError as exc:
            raise StudySessionError(
                "ALGORITHM_UNAVAILABLE",
                str(exc),
                status=409,
            ) from exc
        after = transition.state
        requested_after_hash = str(
            raw_event.get("after_state_hash") or ""
        ).strip()
        actual_after_hash = study_artifact_service.canonical_digest(
            serialize_card_state(after)
        )
        if requested_after_hash and requested_after_hash != actual_after_hash:
            raise StudySessionError(
                "SCHEDULER_REPLAY_MISMATCH",
                f"Event {index} after-state does not match server replay.",
                status=422,
            )
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
        if note_authority_pins is None:
            states[card_id] = after
            touched_ids.add(card_id)
        else:
            note_identity = note_authority_pins.identity_by_session_card_id[
                int(session_card.id)
            ]
            for sibling in siblings_by_note[note_identity.logical_note_key]:
                states[sibling.card_id] = after
                touched_ids.add(sibling.card_id)

    return states, replayed_events, touched_ids, event_ids


def _note_session_review_command(
    *, user, session, session_card, card, raw_event, before, transition,
    answer_at, options, route, locked, siblings, compatibility, expected, committed_at,
):
    """Build the same canonical fingerprint for apply and read-only verification."""
    mutation = study_service.NativeReviewMutationInput(
        user_id=int(user.id),
        card=card,
        current_state=before,
        transition=transition,
        reviewed_at=answer_at,
        duration_ms=study_service.normalize_review_duration(
            raw_event.get("duration_ms")
        ),
        payload=None,
        local_deck_id=session_card.local_deck_id,
        scheduler_preset_id=session_card.scheduler_preset_id,
        scheduler_config_hash=session_card.scheduler_config_hash,
        timezone_name=session.timezone,
        deck_options=options,
        note_type_id=session_card.note_type_id,
        provenance=study_service.NativeReviewProvenance(
            source_path="native.session.commit",
            study_session_id=session.id,
            client_event_id=str(raw_event["event_id"]),
            sequence_no=int(raw_event["sequence"]),
            request_id=str(raw_event["event_id"]),
            wire_schema_version=session.wire_schema_version,
        ),
        progress_input=None,
    )
    return mutation, IdempotentExistingStateNoteReviewCommand(
        operation_key=str(raw_event["operation_key"]),
        command=ExistingStateNoteReviewCommand(
            route=route,
            locked=locked,
            expected=expected,
            siblings=siblings,
            compatibility=compatibility,
            review=mutation,
            now_utc=committed_at,
        ),
    )


def _lock_note_session_context(
    *, user, session, session_cards, route, pins, event_card_ids, committed_at,
    create_token_if_missing=True,
):
    # The scope checks below read every Card's Note: load them in one query.
    # Keyed by the IDs the session dealt, legacy pre-P11 IDs included.
    card_rows = load_cards(
        db.session,
        event_card_ids,
        query=Card.query.options(selectinload(Card.note))
        .order_by(Card.note_id.asc(), Card.application_id.asc())
        .populate_existing()
        .with_for_update(read=True),
    ) if event_card_ids else {}
    if set(card_rows) != set(event_card_ids):
        raise StudySessionError(
            "CARD_OUTSIDE_SESSION",
            "One or more NOTE authority Cards no longer exist.",
            status=409,
        )

    membership_by_card_id = {row.card_id: row for row in session_cards}
    note_keys: set[str] = set()
    for card_id, card in card_rows.items():
        membership = membership_by_card_id[card_id]
        identity = pins.identity_by_session_card_id[int(membership.id)]
        if str(card.note_id) != identity.logical_note_key:
            raise StudySessionError(
                "SESSION_AUTHORITY_SUBJECT_CONFLICT",
                "A Study Session Card moved to another authority Note.",
                status=409,
            )
        note_keys.add(identity.logical_note_key)

    if session.clone_install_id is not None:
        install = db.session.get(DeckInstall, session.clone_install_id)
        if (
            install is None
            or int(install.user_id) != int(user.id)
            or str(install.clone_mode or "") != "logical_overlay"
        ):
            raise StudySessionError(
                "SESSION_SCOPE_CHANGED",
                "The installed deck scope changed during this session.",
                status=409,
            )
        current_map = {
            int(row.source_deck_id): int(row.local_deck_id)
            for row in DeckCloneDeckMap.query.filter_by(
                deck_install_id=install.id
            ).all()
        }
        local_added_note_ids = frozenset(db.session.execute(
            select(DeckCloneAddedNote.note_id).where(
                DeckCloneAddedNote.deck_install_id == install.id,
                DeckCloneAddedNote.note_id.in_(sorted({card.note_id for card in card_rows.values()})),
            )
        ).scalars()) if card_rows else frozenset()
        for card_id, card in card_rows.items():
            membership = membership_by_card_id[card_id]
            is_local_added = str(card.note_id) in local_added_note_ids
            if is_local_added:
                valid = (
                    int(card.note.user_id) == int(user.id)
                    and card.note.deck_id == membership.source_deck_id
                    and card.note.deck_id == membership.local_deck_id
                )
            else:
                valid = (
                    membership.source_deck_id is not None
                    and membership.local_deck_id is not None
                    and current_map.get(int(membership.source_deck_id))
                    == int(membership.local_deck_id)
                )
            if not valid:
                raise StudySessionError(
                    "SESSION_SCOPE_CHANGED",
                    "A NOTE authority Card moved outside the installed session scope.",
                    status=409,
                )
    else:
        for card_id, card in card_rows.items():
            membership = membership_by_card_id[card_id]
            if (
                int(card.note.user_id) != int(user.id)
                or card.note.deck_id != membership.source_deck_id
            ):
                raise StudySessionError(
                    "SESSION_SCOPE_CHANGED",
                    "A NOTE authority Card moved outside the session scope.",
                    status=409,
                )

    locked_subjects = None
    locked_vectors: dict[str, tuple[Any, Any]] = {}
    if note_keys:
        try:
            locked_subjects = lock_study_session_authority_subjects(
                db.session,
                route=route,
                logical_note_keys=sorted(note_keys),
                now_utc=committed_at,
                create_token_if_missing=create_token_if_missing,
            )
            siblings_by_note = lock_study_authority_siblings_many(
                db.session, route=route,
                locked_by_logical_note_key=locked_subjects.locked_by_logical_note_key,
            )
            for note_key in sorted(note_keys, key=lambda value: value.encode("utf-8")):
                locked = locked_subjects.locked_by_logical_note_key[note_key]
                siblings = siblings_by_note[note_key]
                compatibility = lock_study_authority_compatibility(
                    db.session,
                    route=route,
                    locked=locked,
                    siblings=siblings,
                )
                locked_vectors[note_key] = (siblings, compatibility)
        except Exception as exc:
            code = domain_error_code(exc)
            if code is None:
                raise
            db.session.rollback()
            raise StudySessionError(code, str(exc), status=409) from exc

    return card_rows, note_keys, locked_subjects, locked_vectors


def _commit_note_authority_session(
    *,
    user: Any,
    session: StudySession,
    session_cards: list[StudySessionCard],
    route: Any,
    pins: LockedStudySessionAuthorityPins,
    replayed_events: list[
        tuple[
            dict[str, Any],
            StudySessionCard,
            CardState,
            CardState,
            datetime,
            DeckOptions,
            ReviewTransitionResult,
        ]
    ],
    states: dict[str, CardState],
    commit_key: str,
    payload_hash: str,
    commit_reason: str,
    committed_at: datetime,
    note_batch: NoteBatchContinuation | None = None,
) -> dict[str, Any]:
    """Commit a replayed v4 log through the canonical NOTE receipt command."""

    event_card_ids = sorted(
        {session_card.card_id for _, session_card, *_rest in replayed_events}
    )
    card_rows, note_keys, locked_subjects, locked_vectors = _lock_note_session_context(
        user=user, session=session, session_cards=session_cards, route=route,
        pins=pins, event_card_ids=event_card_ids, committed_at=committed_at,
    )

    rating_counts = {rating: 0 for rating in sorted(VALID_RATINGS)}
    projected_revisions: dict[str, int] = {}
    seen_note_events: dict[str, int] = {}
    usage = study_service.ReviewUsageTouches()
    membership_identity_by_note = {
        identity.logical_note_key: identity
        for identity in pins.identity_by_session_card_id.values()
    }
    try:
        if note_batch is not None:
            note_batch = verify_note_batch_continuation(
                study_session=session, context=note_batch, route=route,
                memberships=session_cards, pins=pins,
            )
        for note_key in sorted(note_keys):
            locked = locked_subjects.locked_by_logical_note_key[note_key]
            membership_identity = (
                note_batch.expected_by_note[note_key]
                if note_batch is not None else membership_identity_by_note[note_key]
            )
            current_identity = build_note_authority_wire_identity(
                enrollment_epoch=route.epoch,
                logical_note_key=bytes(locked.subject.logical_note_key),
                subject_generation=locked.subject.subject_generation,
                base_authority_revision=locked.token.authority_revision,
                base_authority_state_hash=locked.state.semantic_state_hash,
            )
            if current_identity != membership_identity:
                raise StudySessionAuthorityPinError(
                    "AUTHORITY_STATE_CONFLICT",
                    "Study Session NOTE authority lease is stale.",
                )
        for replay_index, (
            raw_event,
            session_card,
            before,
            _after,
            answer_at,
            options,
            transition,
        ) in enumerate(replayed_events):
            card = card_rows[session_card.card_id]
            identity = pins.identity_by_session_card_id[int(session_card.id)]
            note_key = identity.logical_note_key
            locked = locked_subjects.locked_by_logical_note_key[note_key]
            siblings, compatibility = locked_vectors[note_key]
            if seen_note_events.get(note_key, 0):
                compatibility = lock_study_authority_compatibility(
                    db.session,
                    route=route,
                    locked=locked,
                    siblings=siblings,
                )
                locked_vectors[note_key] = (siblings, compatibility)
            expected = StudyAuthorityCASExpectation(
                enrollment_epoch=int(route.epoch),
                subject_generation=int(locked.subject.subject_generation),
                authority_revision=int(locked.token.authority_revision),
                semantic_state_hash=bytes(locked.token.semantic_state_hash),
            )
            prior_receipt = (
                note_batch.receipt_by_event[str(raw_event["event_id"])]
                if note_batch is not None and replay_index < note_batch.previous_event_count
                else None
            )
            if prior_receipt is not None:
                expected = StudyAuthorityCASExpectation(
                    enrollment_epoch=int(prior_receipt.enrollment_epoch),
                    subject_generation=int(prior_receipt.subject_generation),
                    authority_revision=int(prior_receipt.authority_revision_before),
                    semantic_state_hash=bytes(prior_receipt.before_state_hash),
                )
            mutation, command = _note_session_review_command(
                user=user, session=session, session_card=session_card, card=card,
                raw_event=raw_event, before=before, transition=transition,
                answer_at=answer_at, options=options, route=route, locked=locked,
                siblings=siblings, compatibility=compatibility, expected=expected,
                committed_at=committed_at,
            )
            if prior_receipt is not None:
                verified = require_existing_note_review_receipt(db.session, command=command)
                if verified.id != prior_receipt.id:
                    raise StudySessionError("AUTHORITY_RECEIPT_MISMATCH", "Batch receipt changed.", status=409)
                continue
            result = apply_idempotent_existing_state_note_review(db.session, command=command)
            if result.replayed:
                raise StudySessionError(
                    "CLIENT_EVENT_REUSED",
                    "A NOTE authority event was already committed.",
                    status=409,
                )
            study_service.stage_native_review_side_effects(mutation, usage=usage)
            for card_id, revision in dict(
                result.response_payload["projected_card_revisions"]
            ).items():
                projected_revisions[str(card_id)] = int(revision)
            rating = str(raw_event["rating"]).lower()
            rating_counts[rating] += 1
            seen_note_events[note_key] = seen_note_events.get(note_key, 0) + 1
        # Install locks follow every subject lock, as on the per-answer path.
        usage.apply()

        updated_cards = [
            {
                "card_id": card_id,
                "revision": revision,
                "state": serialize_card_state(states[card_id]),
            }
            for card_id, revision in sorted(projected_revisions.items())
            if card_id in states
        ]
        response = {
            "schema_version": "study-commit-receipt.v2",
            "authority_mode": "NOTE",
            "enrollment_epoch": str(route.epoch),
            "success": True,
            "session_id": session.id,
            "commit_id": commit_key,
            "commit_reason": commit_reason,
            "applied_event_count": len(replayed_events) - (
                note_batch.previous_event_count if note_batch is not None else 0
            ),
            "updated_cards": updated_cards,
            "rating_counts": rating_counts,
            "committed_at": _utc_iso(committed_at),
        }
        is_final = note_batch is None or bool(note_batch.batch.is_final)
        if note_batch is not None:
            batch = note_batch.batch
            response.update({
                "batch_receipt_schema_version": NOTE_BATCH_RECEIPT_SCHEMA,
                "batch_id": batch.batch_id,
                "batch_sequence": batch.batch_sequence,
                "request_hash": batch.request_hash,
                "is_final": is_final,
                "cumulative_event_count": len(replayed_events),
            })
            response["receipt_hash"] = _request_hash(response)
            batch.status = "completed"
            batch.processed_at = committed_at
            batch.response_json = _json_dumps(response)
        if is_final:
            session.status = "committed"
            session.committed_at = committed_at
            db.session.add(StudySessionCommit(
                session_id=session.id,
                user_id=int(user.id),
                idempotency_key=commit_key,
                request_hash=payload_hash,
                response_json=_json_dumps(response),
            ))
        db.session.add(
            AuditLog(
                user_id=int(user.id),
                action="study.session.batch.note" if note_batch is not None else "study.session.commit.note",
                payload={
                    "session_id": session.id,
                    "scope_type": session.scope_type,
                    "scope_id": session.scope_id,
                    "event_count": response["applied_event_count"],
                    "note_count": len(note_keys),
                    "commit_reason": commit_reason,
                    "enrollment_epoch": int(route.epoch),
                },
            )
        )
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        return response
    except IntegrityError:
        db.session.rollback()
        if note_batch is not None:
            # The batch entry point resolves retries from its own durable row,
            # never from a synchronous commit key which happens to collide.
            raise
        replayed = _idempotent_response(
            session_id=session.id,
            idempotency_key=commit_key,
            request_hash=payload_hash,
        )
        if replayed is not None:
            return replayed
        raise
    except StudySessionError:
        db.session.rollback()
        raise
    except Exception as exc:
        db.session.rollback()
        code = domain_error_code(exc)
        if code is not None:
            raise StudySessionError(code, str(exc), status=409) from exc
        raise


def commit_study_session(
    *,
    user: Any,
    session_id: str,
    payload: Any,
    now: datetime | None = None,
    _note_batch: NoteBatchContinuation | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StudySessionError(
            "INVALID_COMMIT",
            "Commit payload must be an object.",
            status=400,
        )
    commit_key = str(payload.get("commit_id") or "").strip()
    if not commit_key or len(commit_key) > 64:
        raise StudySessionError(
            "INVALID_COMMIT_ID",
            "commit_id is required.",
            status=400,
        )
    commit_reason = str(
        payload.get("commit_reason") or "manual_exit"
    ).strip().lower()
    if commit_reason not in VALID_COMMIT_REASONS:
        raise StudySessionError(
            "INVALID_COMMIT_REASON",
            "commit_reason must be auto_finish, manual_exit, page_exit, or rollover.",
            status=422,
        )
    payload_hash = _request_hash(payload)
    # Authority compatibility projects into legacy MySQL DATETIME(0) columns.
    committed_at = (now or datetime.utcnow()).replace(microsecond=0)
    try:
        authority_route = lock_study_authority_route(
            db.session,
            learner_user_id=int(user.id),
            allow_note_authority=True,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise StudySessionError(exc.code, str(exc), status=409) from exc
    session = (
        StudySession.query.filter_by(id=session_id, user_id=int(user.id))
        .populate_existing()
        .with_for_update()
        .first()
    )
    if session is None:
        raise StudySessionError(
            "SESSION_NOT_FOUND",
            "Study session was not found.",
            status=404,
        )
    if _note_batch is not None and (
        not isinstance(_note_batch, NoteBatchContinuation)
        or _note_batch.batch is None
        or _note_batch.batch.session_id != session_id
        or _note_batch.batch.user_id != int(user.id)
        or _note_batch.batch.status != "enqueued"
        or session.wire_schema_version != SESSION_SCHEMA_V4
    ):
        raise StudySessionError("INVALID_NOTE_BATCH_CONTEXT", "Invalid internal NOTE batch context.", status=409)
    _validate_session_token(session, payload.get("session_token"))
    wire_contract = _wire_contract_or_session_error(session.wire_schema_version)
    if str(payload.get("schema_version") or "") != wire_contract.commit_schema:
        raise StudySessionError(
            "UNSUPPORTED_COMMIT_SCHEMA",
            (
                "schema_version must be "
                f"{wire_contract.commit_schema} for this session."
            ),
            status=422,
        )
    if _note_batch is None:
        from app.services.study_retirement_telemetry_service import record_legacy_usage

        record_legacy_usage("session.commit", wire=session.wire_schema_version)
        replayed = _idempotent_response(
            session_id=session_id,
            idempotency_key=commit_key,
            request_hash=payload_hash,
        )
        if replayed is not None:
            return replayed
    if session.status == "committed":
        canonical = StudySessionCommit.query.filter_by(
            session_id=session.id,
        ).first()
        if canonical is not None:
            raise StudySessionError(
                "SESSION_ALREADY_COMMITTED",
                "Study session was already committed.",
                status=409,
                details=json.loads(canonical.response_json),
            )
    if session.status != "open" and session.status != "expired":
        raise StudySessionError(
            "SESSION_NOT_OPEN",
            "Study session is not open.",
            status=409,
        )
    # Retention marks long-expired leases ``expired``; answer as before it did.
    if session.status == "expired" or (_note_batch is None and committed_at > session.expires_at):
        raise StudySessionError(
            "SESSION_EXPIRED",
            "Study session has expired.",
            status=410,
        )
    # Only a commit that would write needs the lease's authority contract. A
    # replay, an already-committed lease and an expired lease are answered
    # first, exactly as before the learner's authority changed: a browser that
    # lost the acknowledgement of a pre-cutover legacy commit gets its receipt.
    if wire_contract.requires_note_authority_identity:
        if authority_route.mode_code != "NOTE":
            raise StudySessionError(
                "AUTHORITY_MODE_CONFLICT",
                "Study Session v4 requires active NOTE authority.",
                status=409,
            )
    elif authority_route.mode_code == "NOTE":
        raise StudySessionError(
            "WIRE_CONTRACT_MISMATCH",
            "NOTE authority cannot commit a legacy Study Session lease.",
            status=409,
        )
    if _note_batch is None and session.wire_schema_version == SESSION_SCHEMA_V4:
        admitted = StudySessionBatch.query.filter_by(session_id=session.id).with_for_update().first()
        if admitted is not None:
            raise StudySessionError(
                "SESSION_HAS_ASYNC_BATCHES",
                "This NOTE session must finish through its admitted batch stream.",
                status=409,
            )
    _require_session_algorithm(
        key=session.scheduler_algorithm,
        version=session.algorithm_version,
        purpose=(AlgorithmResolutionPurpose.ACCEPTED_JOB if _note_batch is not None
                 else AlgorithmResolutionPurpose.EXISTING_LEASE),
    )
    if str(payload.get("snapshot_hash") or "") != session.snapshot_hash:
        raise StudySessionError(
            "SNAPSHOT_MISMATCH",
            "Study snapshot no longer matches this session.",
            status=409,
        )

    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raise StudySessionError(
            "INVALID_EVENTS",
            "events must be an array.",
            status=400,
        )
    if len(raw_events) > MAX_COMMIT_EVENTS:
        raise StudySessionError(
            "COMMIT_TOO_LARGE",
            f"A commit is limited to {MAX_COMMIT_EVENTS} events.",
            status=413,
        )

    session_cards = (
        StudySessionCard.query.filter_by(session_id=session.id)
        .order_by(StudySessionCard.ordinal.asc())
        .all()
    )
    membership = {row.card_id: row for row in session_cards}
    note_authority_pins: LockedStudySessionAuthorityPins | None = None
    if wire_contract.requires_note_authority_identity:
        try:
            note_authority_pins = lock_study_session_authority_pins(
                db.session,
                study_session=session,
                session_cards=session_cards,
                route=authority_route,
            )
        except StudySessionAuthorityPinError as exc:
            db.session.rollback()
            raise StudySessionError(exc.code, str(exc), status=409) from exc
    states, replayed_events, touched_ids, event_ids = _replay_session_events(
        session=session, payload=payload, session_cards=session_cards,
        raw_events=raw_events, note_authority_pins=note_authority_pins,
        committed_at=committed_at,
    )

    previous_event_ids = (
        {str(event["event_id"]) for event in _note_batch.previous_events}
        if _note_batch is not None else set()
    )
    new_event_ids = event_ids - previous_event_ids
    if new_event_ids:
        reused_event = ReviewEvent.query.filter(
            ReviewEvent.user_id == int(user.id),
            ReviewEvent.client_event_id.in_(sorted(new_event_ids)),
        ).first()
        if reused_event is not None:
            raise StudySessionError(
                "CLIENT_EVENT_REUSED",
                "An event id was already committed in another batch.",
                status=409,
            )

    final_states_payload = payload.get("final_states")
    if final_states_payload is not None and not isinstance(
        final_states_payload,
        list,
    ):
        raise StudySessionError(
            "INVALID_FINAL_STATES",
            "final_states must be an array.",
            status=400,
        )
    if note_authority_pins is not None and final_states_payload:
        raise StudySessionError(
            "INVALID_FINAL_STATES",
            "Study Session v4 derives NOTE final state only from its event log.",
            status=422,
        )
    for raw_final in final_states_payload or []:
        if not isinstance(raw_final, dict):
            raise StudySessionError(
                "INVALID_FINAL_STATES",
                "Each final state must be an object.",
                status=422,
            )
        card_id = str(raw_final.get("card_id") or "")
        if card_id not in touched_ids or card_id not in states:
            raise StudySessionError(
                "INVALID_FINAL_STATES",
                f"Final state for card {card_id} is not part of the event log.",
                status=422,
            )
        if int(raw_final.get("base_revision") or 0) != int(
            membership[card_id].base_progress_revision
        ):
            raise StudySessionError(
                "CARD_PROGRESS_CONFLICT",
                f"Final state for card {card_id} has a stale base revision.",
                status=409,
            )
        submitted = raw_final.get("state")
        if submitted is not None:
            if not _states_match_for_commit(
                deserialize_card_state(submitted),
                states[card_id],
            ):
                raise StudySessionError(
                    "FINAL_STATE_MISMATCH",
                    f"Final state for card {card_id} does not match server replay.",
                    status=422,
                )

    if commit_reason == "auto_finish" and _has_actionable_session_card(
        states,
        now=committed_at,
        timezone_name=session.timezone,
        day_boundary_hour_local=session.day_boundary_hour_local,
        learn_ahead_seconds=session.learn_ahead_seconds,
    ):
        raise StudySessionError(
            "SESSION_NOT_COMPLETE",
            "Study session still contains cards eligible for review.",
            status=409,
        )

    if note_authority_pins is not None:
        return _commit_note_authority_session(
            user=user,
            session=session,
            session_cards=session_cards,
            route=authority_route,
            pins=note_authority_pins,
            replayed_events=replayed_events,
            states=states,
            commit_key=commit_key,
            payload_hash=payload_hash,
            commit_reason=commit_reason,
            committed_at=committed_at,
            note_batch=_note_batch,
        )

    raise StudySessionError("NOTE_AUTHORITY_REQUIRED", "This lease cannot execute the retired LEGACY scheduler.", status=409)
