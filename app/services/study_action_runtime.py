"""Semantic study Actions and compatibility Trigger execution.

The first contract deliberately models only the existing four review actions.
It provides one validated runtime seam for HTTP, MCP, and batch replay without
changing the current scheduler result or persistence authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from app.services.anki_scheduler import Answer, CardState, DeckOptions
from app.services.study_algorithm_registry import (
    DEFAULT_ALGORITHM_IDENTITY,
    AlgorithmIdentity,
    resolve_study_algorithm,
)


ReviewRating = Literal["again", "hard", "good", "easy"]
REVIEW_RATINGS: tuple[ReviewRating, ...] = ("again", "hard", "good", "easy")
REVIEW_ACTION_CONTRACT_VERSION = "1"
REVIEW_TRIGGER_CONTRACT_VERSION = "1"


@dataclass(frozen=True)
class ReviewActionContract:
    rating: ReviewRating
    action_key: str
    trigger_key: str
    action_contract_version: str = REVIEW_ACTION_CONTRACT_VERSION
    trigger_contract_version: str = REVIEW_TRIGGER_CONTRACT_VERSION


@dataclass(frozen=True)
class ReviewTransitionResult:
    action: ReviewActionContract
    algorithm: AlgorithmIdentity
    state: CardState
    storage_profile: str | None = None

    def metadata(self) -> dict[str, str]:
        return {
            "action_key": self.action.action_key,
            "action_contract_version": self.action.action_contract_version,
            "trigger_key": self.action.trigger_key,
            "trigger_contract_version": self.action.trigger_contract_version,
            "algorithm_key": self.algorithm.key,
            "algorithm_version": self.algorithm.version,
            "state_schema_version": self.algorithm.state_schema_version,
            **({"storage_profile": self.storage_profile} if self.storage_profile else {}),
        }


class StudyActionValidationError(ValueError):
    def __init__(self, value: Any) -> None:
        super().__init__("Review action must be one of: again, hard, good, easy.")
        self.value = value


class StudyTriggerValidationError(ValueError):
    def __init__(self, message: str, *, code: str = "TRIGGER_CONTRACT_MISMATCH") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BuiltInTriggerIdentity:
    key: str
    version: str


@dataclass(frozen=True)
class BuiltInReviewTriggerCommand:
    action: ReviewActionContract
    trigger: BuiltInTriggerIdentity
    algorithm_key: str
    algorithm_version: str


_REVIEW_ACTIONS: dict[str, ReviewActionContract] = {
    rating: ReviewActionContract(
        rating=rating,
        action_key=f"review.{rating}",
        trigger_key=f"scheduler.review.{rating}",
    )
    for rating in REVIEW_RATINGS
}

_BUILT_IN_REVIEW_TRIGGERS: dict[
    tuple[str, str], ReviewActionContract
] = {
    (action.trigger_key, action.trigger_contract_version): action
    for action in _REVIEW_ACTIONS.values()
}


def resolve_review_action(value: Any) -> ReviewActionContract:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("review."):
        normalized = normalized.removeprefix("review.")
    action = _REVIEW_ACTIONS.get(normalized)
    if action is None:
        raise StudyActionValidationError(value)
    return action


def verify_review_trigger(
    action: ReviewActionContract,
    trigger_key: str | None = None,
    trigger_contract_version: str | None = None,
) -> None:
    effective_key = trigger_key or action.trigger_key
    effective_version = trigger_contract_version or action.trigger_contract_version
    registered_action = _BUILT_IN_REVIEW_TRIGGERS.get(
        (effective_key, effective_version)
    )
    if registered_action is None:
        raise StudyTriggerValidationError(
            f"Trigger '{effective_key}' version '{effective_version}' is unavailable.",
            code="TRIGGER_UNAVAILABLE",
        )
    if registered_action != action:
        raise StudyTriggerValidationError(
            f"Trigger '{effective_key}' does not match action '{action.action_key}'."
        )


def list_builtin_review_triggers() -> tuple[BuiltInTriggerIdentity, ...]:
    """Return the exact built-in Trigger versions supported by this runtime."""

    return tuple(
        BuiltInTriggerIdentity(key=key, version=version)
        for key, version in sorted(_BUILT_IN_REVIEW_TRIGGERS)
    )


def dispatch_builtin_review_trigger(
    *,
    state: CardState,
    options: DeckOptions,
    now: datetime,
    command: BuiltInReviewTriggerCommand,
    timezone_name: str,
) -> ReviewTransitionResult:
    """Authorize one built-in Trigger and calculate its exact Algorithm transition.

    This boundary is intentionally pure: its caller owns idempotency, persistence,
    transaction commit/rollback and any post-commit follow-up work.
    """

    verify_review_trigger(
        command.action,
        trigger_key=command.trigger.key,
        trigger_contract_version=command.trigger.version,
    )
    adapter = resolve_study_algorithm(
        command.algorithm_key,
        command.algorithm_version,
    )
    updated_state = adapter.transition(
        state,
        options,
        now,
        command.action.rating,  # type: ignore[arg-type]
        timezone_name=timezone_name,
    )
    return ReviewTransitionResult(
        action=command.action,
        algorithm=adapter.identity,
        state=updated_state,
    )


def execute_review_action(
    *,
    state: CardState,
    options: DeckOptions,
    now: datetime,
    action: Any,
    timezone_name: str,
    algorithm_key: str = DEFAULT_ALGORITHM_IDENTITY.key,
    algorithm_version: str = DEFAULT_ALGORITHM_IDENTITY.version,
    trigger_key: str | None = None,
    trigger_contract_version: str | None = None,
) -> ReviewTransitionResult:
    verified_action = resolve_review_action(action)
    return dispatch_builtin_review_trigger(
        state=state,
        options=options,
        now=now,
        timezone_name=timezone_name,
        command=BuiltInReviewTriggerCommand(
            action=verified_action,
            trigger=BuiltInTriggerIdentity(
                key=trigger_key or verified_action.trigger_key,
                version=(
                    trigger_contract_version
                    or verified_action.trigger_contract_version
                ),
            ),
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
        ),
    )


def compute_review_previews(
    *,
    state: CardState,
    options: DeckOptions,
    now: datetime,
    timezone_name: str,
    algorithm_key: str = DEFAULT_ALGORITHM_IDENTITY.key,
    algorithm_version: str = DEFAULT_ALGORITHM_IDENTITY.version,
) -> dict[Answer, dict[str, float | int | str | None]]:
    adapter = resolve_study_algorithm(algorithm_key, algorithm_version)
    return adapter.previews(
        state,
        options,
        now,
        timezone_name=timezone_name,
    )

