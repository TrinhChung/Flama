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
REVIEW_TRIGGER_CONTRACT_VERSION = "1"


@dataclass(frozen=True)
class ReviewActionContract:
    rating: ReviewRating
    action_key: str
    trigger_key: str
    trigger_contract_version: str = REVIEW_TRIGGER_CONTRACT_VERSION


@dataclass(frozen=True)
class ReviewTransitionResult:
    action: ReviewActionContract
    algorithm: AlgorithmIdentity
    state: CardState

    def metadata(self) -> dict[str, str]:
        return {
            "action_key": self.action.action_key,
            "trigger_key": self.action.trigger_key,
            "trigger_contract_version": self.action.trigger_contract_version,
            "algorithm_key": self.algorithm.key,
            "algorithm_version": self.algorithm.version,
            "state_schema_version": self.algorithm.state_schema_version,
        }


class StudyActionValidationError(ValueError):
    def __init__(self, value: Any) -> None:
        super().__init__("Review action must be one of: again, hard, good, easy.")
        self.value = value


_REVIEW_ACTIONS: dict[str, ReviewActionContract] = {
    rating: ReviewActionContract(
        rating=rating,
        action_key=f"review.{rating}",
        trigger_key=f"scheduler.review.{rating}",
    )
    for rating in REVIEW_RATINGS
}


def resolve_review_action(value: Any) -> ReviewActionContract:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("review."):
        normalized = normalized.removeprefix("review.")
    action = _REVIEW_ACTIONS.get(normalized)
    if action is None:
        raise StudyActionValidationError(value)
    return action


def execute_review_action(
    *,
    state: CardState,
    options: DeckOptions,
    now: datetime,
    action: Any,
    timezone_name: str,
    algorithm_key: str = DEFAULT_ALGORITHM_IDENTITY.key,
    algorithm_version: str = DEFAULT_ALGORITHM_IDENTITY.version,
) -> ReviewTransitionResult:
    verified_action = resolve_review_action(action)
    adapter = resolve_study_algorithm(algorithm_key, algorithm_version)
    updated_state = adapter.transition(
        state,
        options,
        now,
        verified_action.rating,  # type: ignore[arg-type]
        timezone_name=timezone_name,
    )
    return ReviewTransitionResult(
        action=verified_action,
        algorithm=adapter.identity,
        state=updated_state,
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

