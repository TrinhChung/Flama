"""Anki-like legacy SM-2 scheduler (non-FSRS)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Literal, Optional

Answer = Literal["again", "hard", "good", "easy"]
CardType = Literal["new", "learning", "review", "relearning"]


UTC = timezone.utc


@dataclass
class CardState:
    type: CardType
    stepIndex: int = 0
    due: Optional[datetime] = None
    dueDay: Optional[int] = None
    intervalDays: float = 0.0
    ease: float = 2.5
    reps: int = 0
    lapses: int = 0
    lastReviewAt: Optional[datetime] = None


@dataclass
class DeckOptions:
    learningSteps: list[timedelta]
    graduatingIntervalDays: int
    easyIntervalDays: int
    relearningSteps: list[timedelta]
    minimumIntervalDays: int
    startingEase: float
    easyBonus: float
    intervalModifier: float
    hardFactor: float
    newIntervalFactor: float
    minEase: float = 1.30
    maxIntervalDays: int = 36500
    dayBoundaryHourLocal: int = 4
    fuzz: bool = False


def default_deck_options() -> DeckOptions:
    return DeckOptions(
        learningSteps=[timedelta(minutes=1), timedelta(minutes=10)],
        graduatingIntervalDays=1,
        easyIntervalDays=5,
        relearningSteps=[timedelta(minutes=10)],
        minimumIntervalDays=1,
        startingEase=2.50,
        easyBonus=1.30,
        intervalModifier=1.00,
        hardFactor=1.20,
        newIntervalFactor=0.00,
        minEase=1.30,
        maxIntervalDays=36500,
        dayBoundaryHourLocal=4,
        fuzz=False,
    )


def computeAnswerPreview(
    card: CardState, options: DeckOptions, now: datetime, *, timezone_name: str = "UTC"
) -> Dict[Answer, Dict[str, float | int | str | None]]:
    previews: Dict[Answer, Dict[str, float | int | str | None]] = {}
    for answer in ("again", "hard", "good", "easy"):
        simulated = applyAnswer(  # type: ignore[arg-type]
            _clone_card(card),
            options,
            now,
            answer,
            timezone_name=timezone_name,
        )
        previews[answer] = _preview_from_state(simulated, options, now, timezone_name=timezone_name)
    return previews


def applyAnswer(
    card: CardState,
    options: DeckOptions,
    now: datetime,
    answer: Answer,
    *,
    timezone_name: str = "UTC",
) -> CardState:
    state = _clone_card(card)
    normalized_type = _normalize_card_type(state.type)
    state.type = normalized_type
    state.reps = max(0, int(state.reps)) + 1
    state.lastReviewAt = now

    if normalized_type in {"new", "learning"}:
        return _apply_learning(
            state,
            options,
            now,
            answer,
            relearning=False,
            timezone_name=timezone_name,
        )
    if normalized_type == "relearning":
        return _apply_learning(
            state,
            options,
            now,
            answer,
            relearning=True,
            timezone_name=timezone_name,
        )
    return _apply_review(state, options, now, answer, timezone_name=timezone_name)


def _apply_learning(
    state: CardState,
    options: DeckOptions,
    now: datetime,
    answer: Answer,
    *,
    relearning: bool,
    timezone_name: str,
) -> CardState:
    steps = options.relearningSteps if relearning else options.learningSteps
    current_idx = max(0, int(state.stepIndex))

    if answer == "again":
        state.stepIndex = 0
        delay = steps[0] if steps else timedelta(minutes=1)
        return _set_learning_due(
            state,
            now,
            delay,
            options.dayBoundaryHourLocal,
            relearning,
            timezone_name=timezone_name,
        )

    if answer == "hard":
        if current_idx <= 0:
            if len(steps) >= 2:
                delay = (steps[0] + steps[1]) / 2
            elif len(steps) == 1:
                delay = min(steps[0] * 1.5, steps[0] + timedelta(days=1))
            else:
                delay = timedelta(minutes=1)
            state.stepIndex = 0
        else:
            step_pos = min(current_idx, len(steps) - 1) if steps else 0
            delay = steps[step_pos] if steps else timedelta(minutes=10)
            state.stepIndex = current_idx
        return _set_learning_due(
            state,
            now,
            delay,
            options.dayBoundaryHourLocal,
            relearning,
            timezone_name=timezone_name,
        )

    if answer == "easy":
        if relearning:
            return _graduate_relearning(state, options, now, timezone_name=timezone_name)
        return _graduate_new_learning(
            state,
            options,
            now,
            max(options.minimumIntervalDays, options.easyIntervalDays),
            reset_ease=True,
            timezone_name=timezone_name,
        )

    # good
    next_idx = current_idx + 1
    if steps and next_idx < len(steps):
        state.stepIndex = next_idx
        delay = steps[next_idx]
        return _set_learning_due(
            state,
            now,
            delay,
            options.dayBoundaryHourLocal,
            relearning,
            timezone_name=timezone_name,
        )

    if relearning:
        return _graduate_relearning(state, options, now, timezone_name=timezone_name)

    return _graduate_new_learning(
        state,
        options,
        now,
        max(options.minimumIntervalDays, options.graduatingIntervalDays),
        reset_ease=True,
        timezone_name=timezone_name,
    )


def _apply_review(
    state: CardState,
    options: DeckOptions,
    now: datetime,
    answer: Answer,
    *,
    timezone_name: str,
) -> CardState:
    ivl = max(float(options.minimumIntervalDays), float(state.intervalDays or 0))
    ease = float(state.ease or options.startingEase)
    current_day = _day_index(now, options.dayBoundaryHourLocal, timezone_name=timezone_name)
    scheduled_due_day = state.dueDay
    if scheduled_due_day is None:
        scheduled_due_day = _day_index(
            state.due or now,
            options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )
    days_late = max(0, current_day - scheduled_due_day)

    if answer == "again":
        state.lapses = max(0, int(state.lapses)) + 1
        state.ease = max(options.minEase, ease - 0.20)
        lapse_interval = max(float(options.minimumIntervalDays), ivl * float(options.newIntervalFactor))
        state.intervalDays = lapse_interval
        if options.relearningSteps:
            state.type = "relearning"
            state.stepIndex = 0
            return _set_learning_due(
                state,
                now,
                options.relearningSteps[0],
                options.dayBoundaryHourLocal,
                relearning=True,
                timezone_name=timezone_name,
            )
        # no relearning steps: immediately stay review at minimum/lapse interval
        return _set_review_due(state, now, lapse_interval, options, timezone_name=timezone_name)

    if answer == "hard":
        state.ease = max(options.minEase, ease - 0.15)
        raw_next = ivl * float(options.hardFactor) * float(options.intervalModifier)
    elif answer == "good":
        base = ivl + (days_late / 2.0)
        raw_next = base * ease * float(options.intervalModifier)
        state.ease = ease
    else:  # easy
        state.ease = ease + 0.15
        base = ivl + float(days_late)
        raw_next = base * ease * float(options.easyBonus) * float(options.intervalModifier)

    raw_next = max(raw_next, ivl + 1.0)
    return _set_review_due(state, now, raw_next, options, timezone_name=timezone_name)


def _graduate_relearning(
    state: CardState, options: DeckOptions, now: datetime, *, timezone_name: str
) -> CardState:
    exit_interval = max(float(options.minimumIntervalDays), float(state.intervalDays or 0))
    return _set_review_due(state, now, exit_interval, options, timezone_name=timezone_name)


def _graduate_new_learning(
    state: CardState,
    options: DeckOptions,
    now: datetime,
    interval_days: int,
    *,
    reset_ease: bool,
    timezone_name: str,
) -> CardState:
    if reset_ease:
        state.ease = float(options.startingEase)
    return _set_review_due(state, now, float(interval_days), options, timezone_name=timezone_name)


def _set_learning_due(
    state: CardState,
    now: datetime,
    delay: timedelta,
    boundary_hour: int,
    relearning: bool,
    *,
    timezone_name: str,
) -> CardState:
    target_due = now + delay
    now_day = _day_index(now, boundary_hour, timezone_name=timezone_name)
    target_day = _day_index(target_due, boundary_hour, timezone_name=timezone_name)
    state.type = "relearning" if relearning else "learning"
    state.intervalDays = float(state.intervalDays or 0)
    if target_day == now_day:
        state.due = target_due
        state.dueDay = None
        return state

    state.dueDay = target_day
    state.due = _day_index_to_datetime(target_day, boundary_hour, timezone_name=timezone_name)
    return state


def _set_review_due(
    state: CardState,
    now: datetime,
    interval_days: float,
    options: DeckOptions,
    *,
    timezone_name: str,
) -> CardState:
    clamped_days = _clamp_review_interval(interval_days, options)
    rounded_days = _round_review_interval(clamped_days, options)
    state.type = "review"
    state.stepIndex = 0
    state.intervalDays = float(clamped_days)
    current_day = _day_index(now, options.dayBoundaryHourLocal, timezone_name=timezone_name)
    due_day = current_day + max(1, int(rounded_days))
    state.dueDay = due_day
    state.due = _day_index_to_datetime(
        due_day,
        options.dayBoundaryHourLocal,
        timezone_name=timezone_name,
    )
    return state


def _preview_from_state(
    state: CardState,
    options: DeckOptions,
    now: datetime,
    *,
    timezone_name: str,
) -> Dict[str, float | int | str | None]:
    if state.type in {"review"}:
        raw_days = float(state.intervalDays)
        rounded_days = max(1, int(raw_days + 0.5))
        return {
            "seconds": None,
            "days": raw_days,
            "intervalDays": rounded_days,
            "label": f"{rounded_days}d",
        }

    due = state.due
    if state.dueDay is not None:
        due = _day_index_to_datetime(
            state.dueDay,
            options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )
    if due is None:
        return {"seconds": None, "days": None, "intervalDays": None, "label": "n/a"}

    delta_seconds = max(0, int((due - now).total_seconds()))
    if delta_seconds < 86400:
        if delta_seconds < 3600:
            minutes = max(1, int(round(delta_seconds / 60)))
            return {
                "seconds": delta_seconds,
                "days": delta_seconds / 86400,
                "intervalDays": 0,
                "label": f"<{minutes}m",
            }
        hours = max(1, int(round(delta_seconds / 3600)))
        return {
            "seconds": delta_seconds,
            "days": delta_seconds / 86400,
            "intervalDays": 0,
            "label": f"<{hours}h",
        }

    days = max(1, int((delta_seconds / 86400) + 0.5))
    return {
        "seconds": delta_seconds,
        "days": delta_seconds / 86400,
        "intervalDays": days,
        "label": f"{days}d",
    }


def _round_review_interval(raw_days: float, options: DeckOptions) -> int:
    capped = _clamp_review_interval(raw_days, options)
    rounded = int(capped + 0.5)
    return max(options.minimumIntervalDays, min(options.maxIntervalDays, rounded))


def _clamp_review_interval(raw_days: float, options: DeckOptions) -> float:
    return min(float(options.maxIntervalDays), max(float(options.minimumIntervalDays), raw_days))


def _day_index(moment: datetime, boundary_hour: int, *, timezone_name: str = "UTC") -> int:
    local_moment = _to_local_naive(moment, timezone_name)
    shifted = local_moment - timedelta(hours=boundary_hour)
    return shifted.date().toordinal()


def _day_index_to_datetime(day_index: int, boundary_hour: int, *, timezone_name: str = "UTC") -> datetime:
    day_date = date.fromordinal(day_index)
    local_due = datetime.combine(day_date, time(hour=boundary_hour))
    return _local_naive_to_utc(local_due, timezone_name)


def _build_timezone(timezone_name: str):
    from app.services.stats_overview import _build_timezone_obj

    candidate = str(timezone_name or "UTC").strip() or "UTC"
    return _build_timezone_obj(candidate)


def _ensure_utc_naive(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment
    return moment.astimezone(UTC).replace(tzinfo=None)


def _to_local_naive(moment: datetime, timezone_name: str) -> datetime:
    utc_moment = _ensure_utc_naive(moment).replace(tzinfo=UTC)
    return utc_moment.astimezone(_build_timezone(timezone_name)).replace(tzinfo=None)


def _local_naive_to_utc(moment: datetime, timezone_name: str) -> datetime:
    local_aware = moment.replace(tzinfo=_build_timezone(timezone_name))
    return local_aware.astimezone(UTC).replace(tzinfo=None)


def _normalize_card_type(card_type: str | CardType) -> CardType:
    normalized = str(card_type or "new").strip().lower()
    if normalized in {"review"}:
        return "review"
    if normalized in {"relearn", "relearning"}:
        return "relearning"
    if normalized in {"learn", "learning"}:
        return "learning"
    return "new"


def _clone_card(card: CardState) -> CardState:
    return CardState(
        type=_normalize_card_type(card.type),
        stepIndex=int(card.stepIndex or 0),
        due=card.due,
        dueDay=card.dueDay,
        intervalDays=float(card.intervalDays or 0),
        ease=float(card.ease or 0),
        reps=int(card.reps or 0),
        lapses=int(card.lapses or 0),
        lastReviewAt=card.lastReviewAt,
    )
