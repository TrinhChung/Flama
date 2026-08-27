"""Canonical scheduler policy serialization and identity.

The same policy material is used by direct reviews, MCP reviews, and durable
study sessions. A configuration hash therefore identifies executable inputs,
not the transport that happened to submit an answer.
"""

from __future__ import annotations

from typing import Any

from app.services import study_artifact_service
from app.services.anki_scheduler import DeckOptions, FsrsAnswerState
from app.services.study_algorithm_registry import (
    DEFAULT_ALGORITHM_IDENTITY,
    AlgorithmIdentity,
)


SCHEDULER_CONFIG_SCHEMA_VERSION = "scheduler-config.v1"


def serialize_deck_options(options: DeckOptions) -> dict[str, Any]:
    fsrs_states = options.fsrsNextStates

    def serialize_fsrs_state(state: FsrsAnswerState | None):
        if state is None:
            return None
        return {
            "interval_days": float(state.intervalDays),
            "memory": (
                {
                    "stability": float(state.memory.stability),
                    "difficulty": float(state.memory.difficulty),
                }
                if state.memory is not None
                else None
            ),
        }

    return {
        "learning_steps_ms": [
            int(step.total_seconds() * 1000) for step in options.learningSteps
        ],
        "graduating_interval_days": int(options.graduatingIntervalDays),
        "easy_interval_days": int(options.easyIntervalDays),
        "relearning_steps_ms": [
            int(step.total_seconds() * 1000) for step in options.relearningSteps
        ],
        "minimum_interval_days": int(options.minimumIntervalDays),
        "starting_ease": float(options.startingEase),
        "easy_bonus": float(options.easyBonus),
        "interval_modifier": float(options.intervalModifier),
        "hard_factor": float(options.hardFactor),
        "new_interval_factor": float(options.newIntervalFactor),
        "min_ease": float(options.minEase),
        "max_interval_days": int(options.maxIntervalDays),
        "day_boundary_hour_local": int(options.dayBoundaryHourLocal),
        "learn_ahead_seconds": int(options.learnAheadSeconds),
        "leech_threshold": int(options.leechThreshold),
        "leech_suspend": bool(options.leechSuspend),
        "scheduler_mode": str(options.schedulerMode or "legacy"),
        "review_fuzz_factor": (
            float(options.reviewFuzzFactor)
            if options.reviewFuzzFactor is not None
            else None
        ),
        "fsrs_next_states": (
            {
                "again": serialize_fsrs_state(fsrs_states.again),
                "hard": serialize_fsrs_state(fsrs_states.hard),
                "good": serialize_fsrs_state(fsrs_states.good),
                "easy": serialize_fsrs_state(fsrs_states.easy),
            }
            if fsrs_states is not None
            else None
        ),
    }


def build_scheduler_policy(
    *,
    options: DeckOptions,
    timezone_name: str,
    algorithm: AlgorithmIdentity = DEFAULT_ALGORITHM_IDENTITY,
) -> dict[str, Any]:
    material = {
        "algorithm_key": algorithm.key,
        "algorithm_version": algorithm.version,
        "config_schema_version": SCHEDULER_CONFIG_SCHEMA_VERSION,
        "timezone": str(timezone_name),
        "config": serialize_deck_options(options),
    }
    return {
        **material,
        "config_hash": study_artifact_service.canonical_digest(material),
    }
