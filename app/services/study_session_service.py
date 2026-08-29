"""Frontend-driven study session snapshot and atomic batch commit."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.repositories.study_repository import (
    card_state_from_progress,
    is_progress_suspended,
    load_card_progress_map,
)
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
from app.services.study_action_runtime import (
    REVIEW_RATINGS,
    ReviewTransitionResult,
    resolve_review_action,
)
from app.services.study_algorithm_registry import (
    DEFAULT_ALGORITHM_IDENTITY,
    StudyAlgorithmNotFoundError,
)
from app.services.study_composition_service import build_compatibility_composition
from app.services.scheduler_config_service import (
    resolve_deck_options,
    resolve_scheduler_runtime_settings,
)
from app.services.study_policy_service import build_scheduler_policy
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.study_session_commit import StudySessionCommit


WIRE_SCHEMA_VERSION = "study-session.v2"
COMMIT_SCHEMA_VERSION = "study-commit.v1"
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


def open_study_session(
    *,
    user: Any,
    query: Any,
    clone_scope: flashcards_share_service.CloneDeckScope | None,
    scope_type: str,
    scope_id: str,
    timezone_name: str,
    now: datetime | None = None,
    composition_ids: list[str] | None = None,
) -> dict[str, Any]:
    # MySQL DATETIME (without an explicit fsp) truncates sub-second precision.
    # Use the same durable anchor in the snapshot and during commit replay.
    opened_at = (now or datetime.utcnow()).replace(microsecond=0)
    cards = (
        query.order_by(Card.created_at.asc(), Card.id.asc())
        .limit(MAX_SESSION_CARDS + 1)
        .all()
    )
    if len(cards) > MAX_SESSION_CARDS:
        raise StudySessionError(
            "SESSION_TOO_LARGE",
            f"A study session is limited to {MAX_SESSION_CARDS} cards.",
            status=413,
        )

    if composition_ids is not None:
        allowed = set(composition_ids)
        cards = [
            card for card in cards
            if build_compatibility_composition(card.template).composition_id in allowed
        ]

    progress_map = load_card_progress_map(
        user_id=int(user.id),
        card_ids=[str(card.id) for card in cards],
    )
    runtime = resolve_scheduler_runtime_settings(user_id=int(user.id))
    session_id = str(uuid4())
    token = secrets.token_urlsafe(32)
    policies: dict[str, Any] = {}
    templates: dict[str, Any] = {}
    contents: dict[str, Any] = {}
    compositions: dict[str, Any] = {}
    card_payloads: list[dict[str, Any]] = []
    session_card_rows: list[StudySessionCard] = []

    for ordinal, card in enumerate(cards):
        note = card.note
        local_deck_id = study_service.resolve_effective_study_deck_id(
            card=card,
            clone_scope=clone_scope,
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
        policy = build_scheduler_policy(
            options=options,
            timezone_name=timezone_name,
        )
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
        )
        template = study_artifact_service.build_template_artifact(context)
        content = study_artifact_service.build_content_artifact(context)
        template_key = f"{template['id']}:{template['version']}"
        content_key = f"{content['id']}:{content['version']}"
        templates.setdefault(template_key, template)
        contents.setdefault(content_key, content)
        composition = build_compatibility_composition(card.template)
        compositions.setdefault(composition.composition_id, composition.to_dict())
        base_revision = int(getattr(progress, "revision", 0) or 0)
        created_at = getattr(card, "created_at", None) or opened_at

        card_payloads.append(
            {
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
        )
        session_card_rows.append(
            StudySessionCard(
                session_id=session_id,
                card_id=str(card.id),
                source_deck_id=(
                    int(note.deck_id) if note.deck_id is not None else None
                ),
                local_deck_id=local_deck_id,
                note_type_id=str(note.note_type_id),
                scheduler_preset_id=(
                    int(local_deck.scheduler_preset_id)
                    if local_deck is not None
                    and local_deck.scheduler_preset_id is not None
                    else None
                ),
                base_progress_revision=base_revision,
                base_state_hash=state_hash,
                scheduler_config_hash=policy_key,
                initial_state_json=_json_dumps(state_payload),
                ordinal=ordinal,
            )
        )

    scope_deck = (
        db.session.get(Deck, int(scope_id))
        if scope_type == "deck" and str(scope_id).isdigit()
        else None
    )
    snapshot_material = {
        "schema_version": WIRE_SCHEMA_VERSION,
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
        "policies": policies,
        "cards": card_payloads,
        "templates": templates,
        "contents": contents,
        "compositions": compositions,
    }
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
        wire_schema_version=WIRE_SCHEMA_VERSION,
        timezone=timezone_name,
        day_boundary_hour_local=int(runtime.day_boundary_hour_local),
        learn_ahead_seconds=int(runtime.learn_ahead_seconds),
        snapshot_hash=snapshot_hash,
        token_hash=_token_hash(token),
        config_snapshot_json=_json_dumps(policies),
        opened_at=opened_at,
        expires_at=expires_at,
    )
    db.session.add(session)
    db.session.add_all(session_card_rows)
    db.session.commit()
    return {
        **snapshot_material,
        "session_token": token,
        "snapshot_hash": snapshot_hash,
        "expires_at": _utc_iso(expires_at),
    }


def get_study_session_status(
    *,
    user: Any,
    session_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    session = StudySession.query.filter_by(
        id=session_id,
        user_id=int(user.id),
    ).first()
    if session is None:
        raise StudySessionError(
            "SESSION_NOT_FOUND",
            "Study session was not found.",
            status=404,
        )

    status = str(session.status or "open")
    if status == "open" and (now or datetime.utcnow()) > session.expires_at:
        status = "expired"
    return {
        "schema_version": "study-session-status.v1",
        "session_id": session.id,
        "status": status,
        "expires_at": _utc_iso(session.expires_at),
        "committed_at": _utc_iso(session.committed_at),
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
        raise StudySessionError(
            "IDEMPOTENCY_KEY_REUSED",
            "The commit id was already used with a different payload.",
            status=409,
        )
    return json.loads(row.response_json)


def commit_study_session(
    *,
    user: Any,
    session_id: str,
    payload: Any,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StudySessionError(
            "INVALID_COMMIT",
            "Commit payload must be an object.",
            status=400,
        )
    if str(payload.get("schema_version") or "") != COMMIT_SCHEMA_VERSION:
        raise StudySessionError(
            "UNSUPPORTED_COMMIT_SCHEMA",
            f"schema_version must be {COMMIT_SCHEMA_VERSION}.",
            status=422,
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
    committed_at = now or datetime.utcnow()
    session = (
        StudySession.query.filter_by(id=session_id, user_id=int(user.id))
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
    if session.status != "open":
        raise StudySessionError(
            "SESSION_NOT_OPEN",
            "Study session is not open.",
            status=409,
        )
    if committed_at > session.expires_at:
        raise StudySessionError(
            "SESSION_EXPIRED",
            "Study session has expired.",
            status=410,
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
    try:
        policies = json.loads(session.config_snapshot_json or "{}")
    except json.JSONDecodeError as exc:
        raise StudySessionError(
            "INVALID_CONFIG_SNAPSHOT",
            "Stored scheduler config is invalid.",
            status=500,
        ) from exc
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

    for index, raw_event in enumerate(raw_events, start=1):
        if not isinstance(raw_event, dict):
            raise StudySessionError(
                "INVALID_EVENT",
                f"Event {index} must be an object.",
                status=422,
            )
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
        action_contract = resolve_review_action(rating)
        supplied_contract = {
            "action_key": action_contract.action_key,
            "trigger_key": action_contract.trigger_key,
            "trigger_contract_version": (
                action_contract.trigger_contract_version
            ),
        }
        for contract_key, expected_value in supplied_contract.items():
            if (
                contract_key in raw_event
                and str(raw_event.get(contract_key) or "").strip()
                != expected_value
            ):
                raise StudySessionError(
                    "ACTION_CONTRACT_MISMATCH",
                    f"Event {index} has inconsistent {contract_key}.",
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
        options = deserialize_deck_options(policy.get("config"))
        answer_at = session.opened_at + timedelta(milliseconds=offset_ms)
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
                    action=rating,
                    timezone_name=session.timezone,
                    algorithm_key=session.scheduler_algorithm,
                    algorithm_version=session.algorithm_version,
                )
            )
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
        states[card_id] = after
        touched_ids.add(card_id)

    if event_ids:
        reused_event = ReviewEvent.query.filter(
            ReviewEvent.user_id == int(user.id),
            ReviewEvent.client_event_id.in_(sorted(event_ids)),
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

    progress_rows = []
    if touched_ids:
        progress_rows = (
            CardProgress.query.filter(
                CardProgress.user_id == int(user.id),
                CardProgress.card_id.in_(sorted(touched_ids)),
            )
            .order_by(CardProgress.card_id.asc())
            .with_for_update()
            .all()
        )
    progress_map = {
        str(row.card_id): row
        for row in progress_rows
        if row.card_id is not None
    }
    conflicts = []
    for card_id in sorted(touched_ids):
        row = progress_map.get(card_id)
        actual_revision = int(getattr(row, "revision", 0) or 0)
        expected_revision = int(membership[card_id].base_progress_revision or 0)
        if row is None:
            actual_revision = 0
        if actual_revision != expected_revision:
            conflicts.append(
                {
                    "card_id": card_id,
                    "expected_revision": expected_revision,
                    "actual_revision": actual_revision,
                }
            )
    if conflicts:
        raise StudySessionError(
            "CARD_PROGRESS_CONFLICT",
            "One or more cards changed in another study session.",
            status=409,
            details=conflicts,
        )

    card_rows = {
        str(card.id): card
        for card in Card.query.filter(Card.id.in_(sorted(touched_ids))).all()
    } if touched_ids else {}
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
        map_rows = DeckCloneDeckMap.query.filter_by(
            deck_install_id=install.id
        ).all()
        current_map = {
            int(row.source_deck_id): int(row.local_deck_id)
            for row in map_rows
        }
        for card_id in touched_ids:
            session_card = membership[card_id]
            card = card_rows.get(card_id)
            is_local_added = bool(
                card is not None
                and DeckCloneAddedNote.query.filter_by(
                    deck_install_id=install.id,
                    note_id=card.note_id,
                ).first()
            )
            if is_local_added:
                if (
                    card.note.user_id != int(user.id)
                    or card.note.deck_id != session_card.source_deck_id
                    or card.note.deck_id != session_card.local_deck_id
                ):
                    raise StudySessionError(
                        "SESSION_SCOPE_CHANGED",
                        "A locally-added clone card moved outside the session scope.",
                        status=409,
                    )
                continue
            if (
                session_card.source_deck_id is None
                or session_card.local_deck_id is None
                or current_map.get(int(session_card.source_deck_id))
                != int(session_card.local_deck_id)
            ):
                raise StudySessionError(
                    "SESSION_SCOPE_CHANGED",
                    "The installed deck mapping changed during this session.",
                    status=409,
                )
    else:
        for card_id, card in card_rows.items():
            session_card = membership[card_id]
            if (
                int(card.note.user_id) != int(user.id)
                or card.note.deck_id != session_card.source_deck_id
            ):
                raise StudySessionError(
                    "SESSION_SCOPE_CHANGED",
                    "A card moved outside the session scope.",
                    status=409,
                )
    try:
        created_progress_ids: list[str] = []
        for card_id in sorted(touched_ids):
            if card_id not in card_rows:
                raise StudySessionError(
                    "CARD_OUTSIDE_SESSION",
                    f"Card {card_id} no longer exists.",
                    status=409,
                )
            progress = progress_map.get(card_id)
            if progress is not None and is_progress_suspended(progress):
                raise StudySessionError(
                    "CARD_SUSPENDED",
                    f"Card {card_id} is suspended.",
                    status=409,
                )
            if progress is None:
                progress = CardProgress(
                    user_id=int(user.id),
                    card_id=card_id,
                    revision=0,
                )
                db.session.add(progress)
                progress_map[card_id] = progress
                created_progress_ids.append(card_id)

        if created_progress_ids:
            try:
                db.session.flush()
            except IntegrityError as exc:
                raise StudySessionError(
                    "CARD_PROGRESS_CONFLICT",
                    "Card progress changed while this study session was committing.",
                    status=409,
                    details=[
                        {"card_id": card_id}
                        for card_id in created_progress_ids
                    ],
                ) from exc

        last_review_event_by_card: dict[str, Any] = {}
        last_replay_index_by_card = {
            session_card.card_id: index
            for index, (_, session_card, *_rest) in enumerate(replayed_events)
        }
        rating_counts = {rating: 0 for rating in sorted(VALID_RATINGS)}
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
            rating = str(raw_event["rating"]).lower()
            rating_counts[rating] += 1
            progress_input = None
            if last_replay_index_by_card[session_card.card_id] == replay_index:
                final_state = states[session_card.card_id]
                progress_input = study_service.NativeReviewProgressInput(
                    progress=progress_map[session_card.card_id],
                    state=final_state,
                    last_reviewed_at=final_state.lastReviewAt or committed_at,
                    revision=(
                        int(session_card.base_progress_revision or 0) + 1
                    ),
                )
            mutation_result = study_service.apply_native_review_mutation(
                study_service.NativeReviewMutationInput(
                    user_id=int(user.id),
                    card=card,
                    current_state=before,
                    transition=transition,
                    reviewed_at=answer_at,
                    duration_ms=study_service.normalize_review_duration(
                        raw_event.get("duration_ms")
                    ),
                    payload=dict(raw_event),
                    local_deck_id=session_card.local_deck_id,
                    scheduler_preset_id=session_card.scheduler_preset_id,
                    scheduler_config_hash=session_card.scheduler_config_hash,
                    timezone_name=session.timezone,
                    deck_options=options,
                    note_type_id=session_card.note_type_id,
                    provenance=study_service.NativeReviewProvenance(
                        study_session_id=session.id,
                        client_event_id=str(raw_event["event_id"]),
                        sequence_no=int(raw_event["sequence"]),
                    ),
                    progress_input=progress_input,
                )
            )
            review_event = mutation_result.review_event
            last_review_event_by_card[session_card.card_id] = review_event

        db.session.flush()
        updated_cards = []
        for card_id in sorted(touched_ids):
            progress = progress_map[card_id]
            last_event = last_review_event_by_card.get(card_id)
            if last_event is not None and last_event.id is not None:
                progress.last_review_event_id = int(last_event.id)
            updated_cards.append(
                {
                    "card_id": card_id,
                    "revision": int(progress.revision),
                    "state": serialize_card_state(states[card_id]),
                }
            )

        response = {
            "schema_version": "study-commit-receipt.v1",
            "success": True,
            "session_id": session.id,
            "commit_id": commit_key,
            "commit_reason": commit_reason,
            "applied_event_count": len(replayed_events),
            "updated_cards": updated_cards,
            "rating_counts": rating_counts,
            "committed_at": _utc_iso(committed_at),
        }
        session.status = "committed"
        session.committed_at = committed_at
        commit_row = StudySessionCommit(
            session_id=session.id,
            user_id=int(user.id),
            idempotency_key=commit_key,
            request_hash=payload_hash,
            response_json=_json_dumps(response),
        )
        db.session.add(commit_row)
        db.session.add(
            AuditLog(
                user_id=int(user.id),
                action="study.session.commit",
                payload={
                    "session_id": session.id,
                    "scope_type": session.scope_type,
                    "scope_id": session.scope_id,
                    "event_count": len(replayed_events),
                    "card_count": len(touched_ids),
                    "commit_reason": commit_reason,
                },
            )
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        replayed = _idempotent_response(
            session_id=session_id,
            idempotency_key=commit_key,
            request_hash=payload_hash,
        )
        if replayed is not None:
            return replayed
        raise
    except Exception:
        db.session.rollback()
        raise
    return response
