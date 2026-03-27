"""Resolve scheduler runtime settings and deck options from persisted models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app.services.anki_scheduler import DeckOptions, default_deck_options
from models.deck import Deck
from models.scheduler_preset import SchedulerPreset
from models.user_scheduler_settings import UserSchedulerSettings


@dataclass(frozen=True)
class SchedulerRuntimeSettings:
    scheduler_mode: str
    day_boundary_hour_local: int
    learn_ahead_seconds: int
    fsrs_allow_short_term: bool


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_scheduler_mode(value: Any, default: str) -> str:
    mode = str(value or "").strip().lower()
    if mode == "fsrs":
        return "fsrs"
    if mode == "legacy":
        return "legacy"
    return default


def _clamp_int(value: Any, *, minimum: int, maximum: int, default: int) -> int:
    normalized = _safe_int(value, default)
    if normalized < minimum:
        return minimum
    if normalized > maximum:
        return maximum
    return normalized


def _load_step_durations(raw_json: Any, fallback: list[timedelta]) -> list[timedelta]:
    if raw_json is None:
        return list(fallback)
    try:
        parsed = json.loads(raw_json)
    except (TypeError, ValueError, json.JSONDecodeError):
        return list(fallback)
    if not isinstance(parsed, list):
        return list(fallback)
    if not parsed:
        return []

    steps: list[timedelta] = []
    for item in parsed:
        try:
            seconds = float(item)
        except (TypeError, ValueError):
            continue
        if seconds < 0:
            continue
        steps.append(timedelta(seconds=seconds))
    return steps if steps else list(fallback)


def get_user_scheduler_settings(user_id: int | None) -> UserSchedulerSettings | None:
    if user_id is None:
        return None
    return UserSchedulerSettings.query.filter_by(user_id=user_id).first()


def resolve_scheduler_runtime_settings(
    *,
    user_id: int | None = None,
    settings_row: UserSchedulerSettings | None = None,
) -> SchedulerRuntimeSettings:
    defaults = default_deck_options()
    row = settings_row if settings_row is not None else get_user_scheduler_settings(user_id)
    if row is None:
        return SchedulerRuntimeSettings(
            scheduler_mode=str(defaults.schedulerMode or "legacy"),
            day_boundary_hour_local=int(defaults.dayBoundaryHourLocal),
            learn_ahead_seconds=int(defaults.learnAheadSeconds),
            fsrs_allow_short_term=False,
        )

    return SchedulerRuntimeSettings(
        scheduler_mode=_normalize_scheduler_mode(
            getattr(row, "scheduler_mode", None),
            str(defaults.schedulerMode or "legacy"),
        ),
        day_boundary_hour_local=_clamp_int(
            getattr(row, "day_boundary_hour_local", None),
            minimum=0,
            maximum=23,
            default=int(defaults.dayBoundaryHourLocal),
        ),
        learn_ahead_seconds=max(
            0,
            _safe_int(getattr(row, "learn_ahead_seconds", None), int(defaults.learnAheadSeconds)),
        ),
        fsrs_allow_short_term=_safe_bool(getattr(row, "fsrs_allow_short_term", None), False),
    )


def resolve_day_boundary_hour_local(*, user_id: int | None = None) -> int:
    return resolve_scheduler_runtime_settings(user_id=user_id).day_boundary_hour_local


def resolve_learn_ahead_seconds(*, user_id: int | None = None) -> int:
    return resolve_scheduler_runtime_settings(user_id=user_id).learn_ahead_seconds


def resolve_scheduler_preset_for_deck(
    *,
    deck_id: int | None = None,
    deck_obj: Deck | None = None,
) -> SchedulerPreset | None:
    deck = deck_obj
    if deck is None and deck_id is not None:
        deck = Deck.query.filter_by(id=deck_id).first()
    if deck is None:
        return None
    return getattr(deck, "scheduler_preset", None)


def resolve_deck_options(
    *,
    user_id: int | None = None,
    deck_id: int | None = None,
    deck_obj: Deck | None = None,
    settings_row: UserSchedulerSettings | None = None,
    preset_row: SchedulerPreset | None = None,
) -> DeckOptions:
    defaults = default_deck_options()
    runtime = resolve_scheduler_runtime_settings(user_id=user_id, settings_row=settings_row)
    preset = preset_row if preset_row is not None else resolve_scheduler_preset_for_deck(
        deck_id=deck_id,
        deck_obj=deck_obj,
    )

    options = DeckOptions(
        learningSteps=list(defaults.learningSteps),
        graduatingIntervalDays=int(defaults.graduatingIntervalDays),
        easyIntervalDays=int(defaults.easyIntervalDays),
        relearningSteps=list(defaults.relearningSteps),
        minimumIntervalDays=int(defaults.minimumIntervalDays),
        startingEase=float(defaults.startingEase),
        easyBonus=float(defaults.easyBonus),
        intervalModifier=float(defaults.intervalModifier),
        hardFactor=float(defaults.hardFactor),
        newIntervalFactor=float(defaults.newIntervalFactor),
        minEase=float(defaults.minEase),
        maxIntervalDays=int(defaults.maxIntervalDays),
        dayBoundaryHourLocal=int(runtime.day_boundary_hour_local),
        learnAheadSeconds=int(runtime.learn_ahead_seconds),
        leechThreshold=int(defaults.leechThreshold),
        leechSuspend=bool(defaults.leechSuspend),
        schedulerMode=_normalize_scheduler_mode(runtime.scheduler_mode, str(defaults.schedulerMode or "legacy")),
        fsrsNextStates=None,
        reviewFuzzFactor=defaults.reviewFuzzFactor,
        fuzz=bool(defaults.fuzz),
    )

    if preset is None:
        return options

    options.learningSteps = _load_step_durations(
        getattr(preset, "learning_steps_json", None),
        options.learningSteps,
    )
    options.relearningSteps = _load_step_durations(
        getattr(preset, "relearning_steps_json", None),
        options.relearningSteps,
    )
    options.graduatingIntervalDays = max(
        1,
        _safe_int(getattr(preset, "graduating_interval_days", None), options.graduatingIntervalDays),
    )
    options.easyIntervalDays = max(
        1,
        _safe_int(getattr(preset, "easy_interval_days", None), options.easyIntervalDays),
    )
    options.minimumIntervalDays = max(
        1,
        _safe_int(getattr(preset, "minimum_lapse_interval_days", None), options.minimumIntervalDays),
    )
    options.easyBonus = max(
        1.0,
        _safe_float(getattr(preset, "easy_multiplier", None), options.easyBonus),
    )
    options.intervalModifier = max(
        0.0,
        _safe_float(getattr(preset, "interval_modifier", None), options.intervalModifier),
    )
    options.hardFactor = max(
        0.0,
        _safe_float(getattr(preset, "hard_multiplier", None), options.hardFactor),
    )
    options.newIntervalFactor = max(
        0.0,
        _safe_float(getattr(preset, "lapse_multiplier", None), options.newIntervalFactor),
    )
    options.maxIntervalDays = max(
        1,
        _safe_int(getattr(preset, "maximum_interval_days", None), options.maxIntervalDays),
    )
    options.leechThreshold = max(
        0,
        _safe_int(getattr(preset, "leech_threshold", None), options.leechThreshold),
    )
    leech_action = str(getattr(preset, "leech_action", "") or "").strip().lower().replace("-", "_")
    options.leechSuspend = leech_action != "tag_only"
    return options
