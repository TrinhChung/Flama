"""Anki-like scheduler covering legacy SM-2-like behavior and FSRS hooks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Literal, Optional

Answer = Literal["again", "hard", "good", "easy"]
CardType = Literal["new", "learning", "review", "relearning"]
SchedulerMode = Literal["legacy", "fsrs"]


UTC = timezone.utc


@dataclass
class FsrsMemoryState:
    stability: float
    difficulty: float


@dataclass
class FsrsAnswerState:
    intervalDays: float
    memory: Optional[FsrsMemoryState] = None


@dataclass
class FsrsNextStates:
    again: FsrsAnswerState
    hard: FsrsAnswerState
    good: FsrsAnswerState
    easy: FsrsAnswerState


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
    reviewKind: str = "review"
    suspended: bool = False
    leeched: bool = False
    memoryState: Optional[FsrsMemoryState] = None


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
    learnAheadSeconds: int = 20 * 60
    leechThreshold: int = 8
    leechSuspend: bool = True
    schedulerMode: SchedulerMode = "legacy"
    fsrsNextStates: Optional[FsrsNextStates] = None
    reviewFuzzFactor: Optional[float] = None
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
        learnAheadSeconds=20 * 60,
        leechThreshold=8,
        leechSuspend=True,
        schedulerMode="legacy",
        fsrsNextStates=None,
        reviewFuzzFactor=None,
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
    scheduled_days = _round_review_interval(ivl, options)
    ease = float(state.ease or options.startingEase)
    current_day = _day_index(now, options.dayBoundaryHourLocal, timezone_name=timezone_name)
    scheduled_due_day = state.dueDay
    if scheduled_due_day is None:
        scheduled_due_day = _day_index(
            state.due or now,
            options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )
    days_late = current_day - scheduled_due_day
    state.reviewKind = "filtered" if days_late < 0 else "review"

    if answer == "again":
        state.lapses = max(0, int(state.lapses)) + 1
        state.leeched = _leech_threshold_met(state.lapses, options.leechThreshold)
        state.suspended = bool(state.leeched and options.leechSuspend)
        state.ease = max(options.minEase, ease - 0.20)
        lapse_interval = _failing_review_interval(scheduled_days, options)
        state.intervalDays = lapse_interval
        if _is_fsrs_mode(options):
            state.memoryState = _memory_state_for_answer(options, "again")
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

    if _is_fsrs_mode(options):
        next_intervals = _passing_fsrs_review_intervals(scheduled_days, options)
        raw_next = next_intervals[answer]
    elif days_late < 0:
        raw_next = _passing_early_review_interval(
            scheduled_days,
            days_late,
            ease,
            answer,
            options,
        )
    elif answer == "hard":
        raw_next = _legacy_nonearly_review_interval(
            float(scheduled_days) * float(options.hardFactor),
            0 if float(options.hardFactor) <= 1.0 else scheduled_days + 1,
            options,
        )
    elif answer == "good":
        hard_minimum = 0 if float(options.hardFactor) <= 1.0 else scheduled_days + 1
        hard_interval = _legacy_nonearly_review_interval(
            float(scheduled_days) * float(options.hardFactor),
            hard_minimum,
            options,
        )
        good_minimum = scheduled_days + 1 if float(options.hardFactor) <= 1.0 else hard_interval + 1
        base = float(scheduled_days) + (max(0, days_late) / 2.0)
        raw_next = _legacy_nonearly_review_interval(
            base * ease,
            int(good_minimum),
            options,
        )
    else:  # easy
        if float(options.hardFactor) <= 1.0:
            hard_interval = _legacy_nonearly_review_interval(
                float(scheduled_days) * float(options.hardFactor),
                0,
                options,
            )
            good_minimum = scheduled_days + 1
        else:
            hard_interval = _legacy_nonearly_review_interval(
                float(scheduled_days) * float(options.hardFactor),
                scheduled_days + 1,
                options,
            )
            good_minimum = hard_interval + 1
        good_interval = _legacy_nonearly_review_interval(
            (float(scheduled_days) + (max(0, days_late) / 2.0)) * ease,
            int(good_minimum),
            options,
        )
        base = float(scheduled_days) + float(max(0, days_late))
        raw_next = _legacy_nonearly_review_interval(
            base * ease * float(options.easyBonus),
            int(good_interval + 1),
            options,
        )

    if answer == "hard":
        state.ease = max(options.minEase, ease - 0.15)
    elif answer == "good":
        state.ease = ease
    else:
        state.ease = ease + 0.15

    if _is_fsrs_mode(options):
        state.memoryState = _memory_state_for_answer(options, answer)
    elif days_late < 0:
        raw_next = max(float(options.minimumIntervalDays), raw_next)
    else:
        raw_next = max(raw_next, float(options.minimumIntervalDays))
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
    if target_day == now_day:
        state.intervalDays = 0.0
        state.due = target_due
        state.dueDay = None
        return state

    state.intervalDays = float(max(1, target_day - now_day))
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

    if state.dueDay is not None:
        current_day = _day_index(now, options.dayBoundaryHourLocal, timezone_name=timezone_name)
        interval_days = max(1, int(state.dueDay - current_day))
        due = state.due or _day_index_to_datetime(
            state.dueDay,
            options.dayBoundaryHourLocal,
            timezone_name=timezone_name,
        )
        delta_seconds = max(0, int((due - now).total_seconds())) if due is not None else None
        return {
            "seconds": delta_seconds,
            "days": float(interval_days),
            "intervalDays": interval_days,
            "label": f"{interval_days}d",
        }

    due = state.due
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


def _failing_review_interval(scheduled_days: int, options: DeckOptions) -> float:
    if _is_fsrs_mode(options):
        states = options.fsrsNextStates
        if states is None:
            return float(options.minimumIntervalDays)
        return max(float(options.minimumIntervalDays), float(states.again.intervalDays))
    return float(
        _with_review_fuzz(
            max(1.0, float(scheduled_days)) * float(options.newIntervalFactor),
            options.minimumIntervalDays,
            options.maxIntervalDays,
            options,
        )
    )


def _passing_fsrs_review_intervals(scheduled_days: int, options: DeckOptions) -> Dict[Answer, float]:
    states = options.fsrsNextStates
    if states is None:
        raise ValueError("FSRS mode requires fsrsNextStates.")

    def greater_than_last(interval_days: float) -> int:
        rounded = int(interval_days + 0.5)
        if rounded > scheduled_days:
            return scheduled_days + 1
        return 0

    hard = _constrain_passing_interval(
        float(states.hard.intervalDays),
        max(1, greater_than_last(float(states.hard.intervalDays))),
        options,
        use_fuzz=True,
        apply_interval_modifier=False,
    )
    good = _constrain_passing_interval(
        float(states.good.intervalDays),
        max(hard + 1, greater_than_last(float(states.good.intervalDays))),
        options,
        use_fuzz=True,
        apply_interval_modifier=False,
    )
    easy = _constrain_passing_interval(
        float(states.easy.intervalDays),
        max(good + 1, greater_than_last(float(states.easy.intervalDays))),
        options,
        use_fuzz=True,
        apply_interval_modifier=False,
    )
    return {
        "hard": float(hard),
        "good": float(good),
        "easy": float(easy),
    }


def _passing_early_review_interval(
    scheduled_days: int,
    days_late: int,
    ease: float,
    answer: Answer,
    options: DeckOptions,
) -> float:
    elapsed_days = max(0.0, float(scheduled_days + days_late))
    scheduled = max(1.0, float(scheduled_days))

    if answer == "hard":
        half_usual = float(options.hardFactor) / 2.0
        base_interval = max(elapsed_days * float(options.hardFactor), scheduled * half_usual)
    elif answer == "good":
        base_interval = max(elapsed_days * ease, scheduled)
    else:
        reduced_bonus = float(options.easyBonus) - ((float(options.easyBonus) - 1.0) / 2.0)
        base_interval = max(elapsed_days * ease, scheduled) * reduced_bonus

    return float(
        _constrain_passing_interval(
            base_interval,
            0,
            options,
            use_fuzz=False,
            apply_interval_modifier=True,
        )
    )


def _legacy_nonearly_review_interval(
    raw_interval_days: float,
    minimum_days: int,
    options: DeckOptions,
) -> float:
    adjusted = float(raw_interval_days) * float(options.intervalModifier)
    minimum = max(float(options.minimumIntervalDays), float(minimum_days))
    if options.reviewFuzzFactor is not None:
        return float(
            _with_review_fuzz(
                adjusted,
                int(minimum),
                int(options.maxIntervalDays),
                options,
            )
        )
    return max(minimum, _clamp_review_interval(adjusted, options))


def _constrain_passing_interval(
    interval_days: float,
    minimum_days: int,
    options: DeckOptions,
    *,
    use_fuzz: bool,
    apply_interval_modifier: bool,
) -> int:
    interval = float(interval_days)
    if apply_interval_modifier:
        interval *= float(options.intervalModifier)

    minimum = max(1, min(int(minimum_days), int(options.maxIntervalDays)))
    maximum = max(1, int(options.maxIntervalDays))
    if use_fuzz:
        return _with_review_fuzz(interval, minimum, maximum, options)

    rounded = int(interval + 0.5)
    return max(minimum, min(maximum, rounded))


def _with_review_fuzz(interval_days: float, minimum_days: int, maximum_days: int, options: DeckOptions) -> int:
    fuzz_factor = options.reviewFuzzFactor
    clamped_interval = max(float(minimum_days), min(float(maximum_days), float(interval_days)))
    if fuzz_factor is None:
        rounded = int(clamped_interval + 0.5)
        return max(minimum_days, min(maximum_days, rounded))

    lower, upper = _constrained_fuzz_bounds(clamped_interval, minimum_days, maximum_days)
    span = 1 + upper - lower
    value = int((lower + (float(fuzz_factor) * span)) // 1)
    return max(lower, min(upper, value))


def _constrained_fuzz_bounds(interval_days: float, minimum_days: int, maximum_days: int) -> tuple[int, int]:
    minimum = min(int(minimum_days), int(maximum_days))
    interval = max(float(minimum), min(float(maximum_days), float(interval_days)))
    lower, upper = _fuzz_bounds(interval)
    lower = max(minimum, min(int(maximum_days), lower))
    upper = max(minimum, min(int(maximum_days), upper))
    if upper == lower and upper > 2 and upper < int(maximum_days):
        upper = lower + 1
    return lower, upper


def _fuzz_bounds(interval_days: float) -> tuple[int, int]:
    delta = _fuzz_delta(interval_days)
    return (int(interval_days - delta + 0.5), int(interval_days + delta + 0.5))


def _fuzz_delta(interval_days: float) -> float:
    if interval_days < 2.5:
        return 0.0
    delta = 1.0
    for start, end, factor in ((2.5, 7.0, 0.15), (7.0, 20.0, 0.1), (20.0, float("inf"), 0.05)):
        delta += factor * max(0.0, min(interval_days, end) - start)
    return delta


def _leech_threshold_met(lapses: int, threshold: int) -> bool:
    if int(threshold) <= 0:
        return False
    half_threshold = max(1, -(-int(threshold) // 2))
    return lapses >= threshold and (lapses - threshold) % half_threshold == 0


def _is_fsrs_mode(options: DeckOptions) -> bool:
    return str(options.schedulerMode or "legacy").strip().lower() == "fsrs" and options.fsrsNextStates is not None


def _memory_state_for_answer(options: DeckOptions, answer: Answer) -> Optional[FsrsMemoryState]:
    states = options.fsrsNextStates
    if states is None:
        return None
    state = getattr(states, answer, None)
    return state.memory if state is not None else None


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
        reviewKind=str(card.reviewKind or "review"),
        suspended=bool(card.suspended),
        leeched=bool(card.leeched),
        memoryState=card.memoryState,
    )
