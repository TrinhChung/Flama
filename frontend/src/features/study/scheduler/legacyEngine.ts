import type { Rating } from '../types'
import {
  dayIndex,
  dayIndexToUtcMs,
  epochMsFromIso,
  isoFromEpochMs,
} from './time'
import type {
  FsrsAnswerState,
  SchedulerCardState,
  SchedulerDecision,
  SchedulerOptions,
  SchedulerPreview,
} from './types'

const RATINGS: Rating[] = ['again', 'hard', 'good', 'easy']

function pythonRoundPositive(value: number) {
  const floor = Math.floor(value)
  const fraction = value - floor
  if (Math.abs(fraction - 0.5) < Number.EPSILON * 4) {
    return floor % 2 === 0 ? floor : floor + 1
  }
  return Math.round(value)
}

function cloneState(state: SchedulerCardState): SchedulerCardState {
  return {
    ...state,
    memory_state: state.memory_state ? { ...state.memory_state } : null,
  }
}

function normalizeType(value: string): SchedulerCardState['type'] {
  const normalized = String(value || 'new').toLowerCase()
  if (normalized === 'review') return 'review'
  if (normalized === 'relearn' || normalized === 'relearning') {
    return 'relearning'
  }
  if (normalized === 'learn' || normalized === 'learning') return 'learning'
  return 'new'
}

function clampReviewInterval(rawDays: number, options: SchedulerOptions) {
  return Math.min(
    options.max_interval_days,
    Math.max(options.minimum_interval_days, rawDays),
  )
}

function roundReviewInterval(rawDays: number, options: SchedulerOptions) {
  const capped = clampReviewInterval(rawDays, options)
  return Math.max(
    options.minimum_interval_days,
    Math.min(options.max_interval_days, Math.floor(capped + 0.5)),
  )
}

function fuzzDelta(intervalDays: number) {
  if (intervalDays < 2.5) return 0
  let delta = 1
  const ranges: Array<[number, number, number]> = [
    [2.5, 7, 0.15],
    [7, 20, 0.1],
    [20, Number.POSITIVE_INFINITY, 0.05],
  ]
  for (const [start, end, factor] of ranges) {
    delta += factor * Math.max(0, Math.min(intervalDays, end) - start)
  }
  return delta
}

function constrainedFuzzBounds(
  intervalDays: number,
  minimumDays: number,
  maximumDays: number,
) {
  const minimum = Math.min(Math.trunc(minimumDays), Math.trunc(maximumDays))
  const interval = Math.max(minimum, Math.min(maximumDays, intervalDays))
  const delta = fuzzDelta(interval)
  let lower = Math.floor(interval - delta + 0.5)
  let upper = Math.floor(interval + delta + 0.5)
  lower = Math.max(minimum, Math.min(maximumDays, lower))
  upper = Math.max(minimum, Math.min(maximumDays, upper))
  if (upper === lower && upper > 2 && upper < maximumDays) upper = lower + 1
  return [lower, upper] as const
}

function withReviewFuzz(
  intervalDays: number,
  minimumDays: number,
  maximumDays: number,
  options: SchedulerOptions,
) {
  const clamped = Math.max(
    minimumDays,
    Math.min(maximumDays, intervalDays),
  )
  const factor = options.review_fuzz_factor
  if (factor === null) {
    return Math.max(
      minimumDays,
      Math.min(maximumDays, Math.floor(clamped + 0.5)),
    )
  }
  const [lower, upper] = constrainedFuzzBounds(
    clamped,
    minimumDays,
    maximumDays,
  )
  const span = 1 + upper - lower
  const value = Math.floor(lower + factor * span)
  return Math.max(lower, Math.min(upper, value))
}

function legacyNonEarlyInterval(
  rawDays: number,
  minimumDays: number,
  options: SchedulerOptions,
) {
  const adjusted = rawDays * options.interval_modifier
  const minimum = Math.max(options.minimum_interval_days, minimumDays)
  if (options.review_fuzz_factor !== null) {
    return withReviewFuzz(
      adjusted,
      minimum,
      options.max_interval_days,
      options,
    )
  }
  return Math.max(minimum, clampReviewInterval(adjusted, options))
}

function constrainPassingInterval(
  intervalDays: number,
  minimumDays: number,
  options: SchedulerOptions,
  useFuzz: boolean,
  applyModifier: boolean,
) {
  let interval = intervalDays
  if (applyModifier) interval *= options.interval_modifier
  const minimum = Math.max(
    1,
    Math.min(Math.trunc(minimumDays), options.max_interval_days),
  )
  if (useFuzz) {
    return withReviewFuzz(
      interval,
      minimum,
      options.max_interval_days,
      options,
    )
  }
  return Math.max(
    minimum,
    Math.min(options.max_interval_days, Math.floor(interval + 0.5)),
  )
}

function isFsrs(options: SchedulerOptions) {
  return options.scheduler_mode.toLowerCase() === 'fsrs'
    && options.fsrs_next_states !== null
}

function memoryFor(
  options: SchedulerOptions,
  rating: Rating,
) {
  const memory = options.fsrs_next_states?.[rating]?.memory
  return memory ? { ...memory } : null
}

function failingReviewInterval(
  scheduledDays: number,
  options: SchedulerOptions,
) {
  if (isFsrs(options)) {
    return Math.max(
      options.minimum_interval_days,
      options.fsrs_next_states?.again.interval_days
        ?? options.minimum_interval_days,
    )
  }
  return withReviewFuzz(
    Math.max(1, scheduledDays) * options.new_interval_factor,
    options.minimum_interval_days,
    options.max_interval_days,
    options,
  )
}

function fsrsPassingIntervals(
  scheduledDays: number,
  options: SchedulerOptions,
) {
  const states = options.fsrs_next_states
  if (!states) throw new Error('FSRS mode requires next states.')
  const greaterThanLast = (state: FsrsAnswerState) => (
    Math.floor(state.interval_days + 0.5) > scheduledDays
      ? scheduledDays + 1
      : 0
  )
  const hard = constrainPassingInterval(
    states.hard.interval_days,
    Math.max(1, greaterThanLast(states.hard)),
    options,
    true,
    false,
  )
  const good = constrainPassingInterval(
    states.good.interval_days,
    Math.max(hard + 1, greaterThanLast(states.good)),
    options,
    true,
    false,
  )
  const easy = constrainPassingInterval(
    states.easy.interval_days,
    Math.max(good + 1, greaterThanLast(states.easy)),
    options,
    true,
    false,
  )
  return { hard, good, easy }
}

function earlyReviewInterval(
  scheduledDays: number,
  daysLate: number,
  ease: number,
  rating: Rating,
  options: SchedulerOptions,
) {
  const elapsedDays = Math.max(0, scheduledDays + daysLate)
  const scheduled = Math.max(1, scheduledDays)
  let baseInterval: number
  if (rating === 'hard') {
    baseInterval = Math.max(
      elapsedDays * options.hard_factor,
      scheduled * (options.hard_factor / 2),
    )
  } else if (rating === 'good') {
    baseInterval = Math.max(elapsedDays * ease, scheduled)
  } else {
    const reducedBonus = options.easy_bonus
      - ((options.easy_bonus - 1) / 2)
    baseInterval = Math.max(elapsedDays * ease, scheduled) * reducedBonus
  }
  return constrainPassingInterval(
    baseInterval,
    0,
    options,
    false,
    true,
  )
}

function leechThresholdMet(lapses: number, threshold: number) {
  if (threshold <= 0) return false
  const half = Math.max(1, Math.ceil(threshold / 2))
  return lapses >= threshold && (lapses - threshold) % half === 0
}

function setLearningDue(
  state: SchedulerCardState,
  nowMs: number,
  delayMs: number,
  options: SchedulerOptions,
  relearning: boolean,
  timezone: string,
) {
  const targetMs = nowMs + delayMs
  const currentDay = dayIndex(
    nowMs,
    options.day_boundary_hour_local,
    timezone,
  )
  const targetDay = dayIndex(
    targetMs,
    options.day_boundary_hour_local,
    timezone,
  )
  state.type = relearning ? 'relearning' : 'learning'
  if (targetDay === currentDay) {
    state.interval_days = 0
    state.due_at = isoFromEpochMs(targetMs)
    state.due_day = null
    return state
  }
  state.interval_days = Math.max(1, targetDay - currentDay)
  state.due_day = targetDay
  state.due_at = isoFromEpochMs(
    dayIndexToUtcMs(
      targetDay,
      options.day_boundary_hour_local,
      timezone,
    ),
  )
  return state
}

function setReviewDue(
  state: SchedulerCardState,
  nowMs: number,
  intervalDays: number,
  options: SchedulerOptions,
  timezone: string,
) {
  const clamped = clampReviewInterval(intervalDays, options)
  const rounded = roundReviewInterval(clamped, options)
  state.type = 'review'
  state.step_index = 0
  state.interval_days = clamped
  const currentDay = dayIndex(
    nowMs,
    options.day_boundary_hour_local,
    timezone,
  )
  const dueDay = currentDay + Math.max(1, rounded)
  state.due_day = dueDay
  state.due_at = isoFromEpochMs(
    dayIndexToUtcMs(
      dueDay,
      options.day_boundary_hour_local,
      timezone,
    ),
  )
  return state
}

function graduateLearning(
  state: SchedulerCardState,
  nowMs: number,
  intervalDays: number,
  options: SchedulerOptions,
  timezone: string,
) {
  state.ease = options.starting_ease
  return setReviewDue(state, nowMs, intervalDays, options, timezone)
}

function applyLearning(
  state: SchedulerCardState,
  options: SchedulerOptions,
  nowMs: number,
  rating: Rating,
  relearning: boolean,
  timezone: string,
) {
  const steps = relearning
    ? options.relearning_steps_ms
    : options.learning_steps_ms
  const currentIndex = Math.max(0, Math.trunc(state.step_index))
  if (rating === 'again') {
    state.step_index = 0
    return setLearningDue(
      state,
      nowMs,
      steps[0] ?? 60_000,
      options,
      relearning,
      timezone,
    )
  }
  if (rating === 'hard') {
    let delay: number
    if (currentIndex <= 0) {
      if (steps.length >= 2) delay = (steps[0] + steps[1]) / 2
      else if (steps.length === 1) {
        delay = Math.min(steps[0] * 1.5, steps[0] + 86_400_000)
      } else delay = 60_000
      state.step_index = 0
    } else {
      delay = steps.length
        ? steps[Math.min(currentIndex, steps.length - 1)]
        : 600_000
      state.step_index = currentIndex
    }
    return setLearningDue(
      state,
      nowMs,
      delay,
      options,
      relearning,
      timezone,
    )
  }
  if (rating === 'easy') {
    if (relearning) {
      return setReviewDue(
        state,
        nowMs,
        Math.max(options.minimum_interval_days, state.interval_days),
        options,
        timezone,
      )
    }
    return graduateLearning(
      state,
      nowMs,
      Math.max(options.minimum_interval_days, options.easy_interval_days),
      options,
      timezone,
    )
  }
  const nextIndex = currentIndex + 1
  if (steps.length && nextIndex < steps.length) {
    state.step_index = nextIndex
    return setLearningDue(
      state,
      nowMs,
      steps[nextIndex],
      options,
      relearning,
      timezone,
    )
  }
  if (relearning) {
    return setReviewDue(
      state,
      nowMs,
      Math.max(options.minimum_interval_days, state.interval_days),
      options,
      timezone,
    )
  }
  return graduateLearning(
    state,
    nowMs,
    Math.max(
      options.minimum_interval_days,
      options.graduating_interval_days,
    ),
    options,
    timezone,
  )
}

function applyReview(
  state: SchedulerCardState,
  options: SchedulerOptions,
  nowMs: number,
  rating: Rating,
  timezone: string,
) {
  const interval = Math.max(
    options.minimum_interval_days,
    state.interval_days || 0,
  )
  const scheduledDays = roundReviewInterval(interval, options)
  const ease = state.ease || options.starting_ease
  const currentDay = dayIndex(
    nowMs,
    options.day_boundary_hour_local,
    timezone,
  )
  const scheduledDueDay = state.due_day ?? dayIndex(
    epochMsFromIso(state.due_at) ?? nowMs,
    options.day_boundary_hour_local,
    timezone,
  )
  const daysLate = currentDay - scheduledDueDay
  state.review_kind = daysLate < 0 ? 'filtered' : 'review'

  if (rating === 'again') {
    state.lapses = Math.max(0, state.lapses) + 1
    state.leeched = leechThresholdMet(
      state.lapses,
      options.leech_threshold,
    )
    state.suspended = state.leeched && options.leech_suspend
    state.suspension_reason = state.suspended ? 'leech' : null
    state.ease = Math.max(options.min_ease, ease - 0.2)
    const lapseInterval = failingReviewInterval(scheduledDays, options)
    state.interval_days = lapseInterval
    if (isFsrs(options)) state.memory_state = memoryFor(options, rating)
    if (options.relearning_steps_ms.length) {
      state.type = 'relearning'
      state.step_index = 0
      return setLearningDue(
        state,
        nowMs,
        options.relearning_steps_ms[0],
        options,
        true,
        timezone,
      )
    }
    return setReviewDue(
      state,
      nowMs,
      lapseInterval,
      options,
      timezone,
    )
  }

  let rawNext: number
  if (isFsrs(options)) {
    rawNext = fsrsPassingIntervals(scheduledDays, options)[rating]
  } else if (daysLate < 0) {
    rawNext = earlyReviewInterval(
      scheduledDays,
      daysLate,
      ease,
      rating,
      options,
    )
  } else if (rating === 'hard') {
    rawNext = legacyNonEarlyInterval(
      scheduledDays * options.hard_factor,
      options.hard_factor <= 1 ? 0 : scheduledDays + 1,
      options,
    )
  } else if (rating === 'good') {
    const hardMinimum = options.hard_factor <= 1
      ? 0
      : scheduledDays + 1
    const hardInterval = legacyNonEarlyInterval(
      scheduledDays * options.hard_factor,
      hardMinimum,
      options,
    )
    const goodMinimum = options.hard_factor <= 1
      ? scheduledDays + 1
      : hardInterval + 1
    rawNext = legacyNonEarlyInterval(
      (scheduledDays + Math.max(0, daysLate) / 2) * ease,
      Math.trunc(goodMinimum),
      options,
    )
  } else {
    let goodMinimum: number
    if (options.hard_factor <= 1) {
      goodMinimum = scheduledDays + 1
    } else {
      const hardInterval = legacyNonEarlyInterval(
        scheduledDays * options.hard_factor,
        scheduledDays + 1,
        options,
      )
      goodMinimum = hardInterval + 1
    }
    const goodInterval = legacyNonEarlyInterval(
      (scheduledDays + Math.max(0, daysLate) / 2) * ease,
      Math.trunc(goodMinimum),
      options,
    )
    rawNext = legacyNonEarlyInterval(
      (scheduledDays + Math.max(0, daysLate))
        * ease
        * options.easy_bonus,
      Math.trunc(goodInterval + 1),
      options,
    )
  }

  if (rating === 'hard') state.ease = Math.max(options.min_ease, ease - 0.15)
  else if (rating === 'good') state.ease = ease
  else state.ease = ease + 0.15

  if (isFsrs(options)) state.memory_state = memoryFor(options, rating)
  rawNext = Math.max(options.minimum_interval_days, rawNext)
  return setReviewDue(state, nowMs, rawNext, options, timezone)
}

export function applyAnswer(
  original: SchedulerCardState,
  options: SchedulerOptions,
  nowMs: number,
  rating: Rating,
  timezone: string,
) {
  const state = cloneState(original)
  state.type = normalizeType(state.type)
  state.reps = Math.max(0, state.reps) + 1
  state.last_review_at = isoFromEpochMs(nowMs)
  state.scheduler_mode = options.scheduler_mode || 'legacy'
  if (
    state.type === 'new'
    || state.type === 'learning'
    || state.type === 'relearning'
  ) {
    state.review_kind = 'learning'
  }
  if (state.type === 'new' || state.type === 'learning') {
    return applyLearning(
      state,
      options,
      nowMs,
      rating,
      false,
      timezone,
    )
  }
  if (state.type === 'relearning') {
    return applyLearning(
      state,
      options,
      nowMs,
      rating,
      true,
      timezone,
    )
  }
  return applyReview(state, options, nowMs, rating, timezone)
}

export function formatIntervalDays(days: number): string {
  const clampedDays = Math.max(1, Math.floor(days + 0.5))
  if (clampedDays < 30) {
    return `${clampedDays}d`
  }
  if (clampedDays < 365) {
    const months = Number((clampedDays / 30).toFixed(1))
    return `${months}m`
  }
  const years = Number((clampedDays / 365).toFixed(1))
  return `${years}y`
}

function previewFromState(
  state: SchedulerCardState,
  options: SchedulerOptions,
  nowMs: number,
  timezone: string,
): SchedulerPreview {
  if (state.type === 'review') {
    const rawDays = state.interval_days
    const rounded = Math.max(1, Math.floor(rawDays + 0.5))
    return {
      seconds: null,
      days: rawDays,
      intervalDays: rounded,
      label: formatIntervalDays(rounded),
    }
  }
  if (state.due_day !== null) {
    const currentDay = dayIndex(
      nowMs,
      options.day_boundary_hour_local,
      timezone,
    )
    const intervalDays = Math.max(1, state.due_day - currentDay)
    const dueMs = epochMsFromIso(state.due_at) ?? dayIndexToUtcMs(
      state.due_day,
      options.day_boundary_hour_local,
      timezone,
    )
    return {
      seconds: Math.max(0, Math.floor((dueMs - nowMs) / 1000)),
      days: intervalDays,
      intervalDays,
      label: formatIntervalDays(intervalDays),
    }
  }
  const dueMs = epochMsFromIso(state.due_at)
  if (dueMs === null) {
    return {
      seconds: null,
      days: null,
      intervalDays: null,
      label: 'n/a',
    }
  }
  const seconds = Math.max(0, Math.floor((dueMs - nowMs) / 1000))
  if (seconds < 86_400) {
    if (seconds < 3600) {
      const minutes = Math.max(1, pythonRoundPositive(seconds / 60))
      return {
        seconds,
        days: seconds / 86_400,
        intervalDays: 0,
        label: `<${minutes}m`,
      }
    }
    const hours = Math.max(1, pythonRoundPositive(seconds / 3600))
    return {
      seconds,
      days: seconds / 86_400,
      intervalDays: 0,
      label: `<${hours}h`,
    }
  }
  const days = Math.max(1, Math.floor(seconds / 86_400 + 0.5))
  return {
    seconds,
    days: seconds / 86_400,
    intervalDays: days,
    label: formatIntervalDays(days),
  }
}

export function computeDecision(
  state: SchedulerCardState,
  options: SchedulerOptions,
  nowMs: number,
  timezone: string,
): SchedulerDecision {
  const outcomes = {} as Record<Rating, SchedulerCardState>
  const previews = {} as Record<Rating, SchedulerPreview>
  for (const rating of RATINGS) {
    const outcome = applyAnswer(state, options, nowMs, rating, timezone)
    outcomes[rating] = outcome
    previews[rating] = previewFromState(
      outcome,
      options,
      nowMs,
      timezone,
    )
  }
  return {
    scheduler_at: isoFromEpochMs(nowMs),
    scheduler_at_ms: nowMs,
    outcomes,
    previews,
  }
}
