import { describe, expect, it } from 'vitest'
import { applyAnswer, computeDecision, formatIntervalDays } from './legacyEngine'
import { dayIndex } from './time'
import type { SchedulerCardState, SchedulerOptions } from './types'

function defaultOptions(): SchedulerOptions {
  return {
    learning_steps_ms: [60_000, 600_000],
    graduating_interval_days: 1,
    easy_interval_days: 5,
    relearning_steps_ms: [600_000],
    minimum_interval_days: 1,
    starting_ease: 2.5,
    easy_bonus: 1.3,
    interval_modifier: 1,
    hard_factor: 1.2,
    new_interval_factor: 0,
    min_ease: 1.3,
    max_interval_days: 36_500,
    day_boundary_hour_local: 4,
    learn_ahead_seconds: 1200,
    leech_threshold: 8,
    leech_suspend: true,
    scheduler_mode: 'legacy',
    review_fuzz_factor: null,
    fsrs_next_states: null,
  }
}

function state(
  overrides: Partial<SchedulerCardState> = {},
): SchedulerCardState {
  return {
    type: 'new',
    step_index: 0,
    due_at: null,
    due_day: null,
    interval_days: 0,
    ease: 2.5,
    reps: 0,
    lapses: 0,
    last_review_at: null,
    review_kind: 'review',
    scheduler_mode: 'legacy',
    suspended: false,
    suspension_reason: null,
    leeched: false,
    memory_state: null,
    ...overrides,
  }
}

describe('legacy frontend scheduler parity', () => {
  const options = defaultOptions()
  const now = Date.parse('2026-02-22T09:00:00.000Z')

  it('previews the first learning hard step as six minutes', () => {
    const decision = computeDecision(
      state({
        type: 'learning',
        due_at: new Date(now).toISOString(),
      }),
      options,
      now,
      'UTC',
    )
    expect(decision.previews.hard.label).toBe('<6m')
  })

  it('matches legacy review intervals', () => {
    const review = state({
      type: 'review',
      interval_days: 10,
      due_day: dayIndex(now, 4, 'UTC'),
      due_at: new Date(now).toISOString(),
    })
    const hard = applyAnswer(review, options, now, 'hard', 'UTC')
    const good = applyAnswer(review, options, now, 'good', 'UTC')
    const easy = applyAnswer(review, options, now, 'easy', 'UTC')
    expect(hard.interval_days).toBeCloseTo(12)
    expect(hard.ease).toBeCloseTo(2.35)
    expect(good.interval_days).toBeCloseTo(25)
    expect(easy.interval_days).toBeCloseTo(32.5)
    expect(easy.ease).toBeCloseTo(2.65)
  })

  it('moves an interday learning step to the Tokyo day boundary', () => {
    const boundaryNow = Date.parse('2026-02-22T18:55:00.000Z')
    const updated = applyAnswer(
      state({
        type: 'new',
        due_at: new Date(boundaryNow).toISOString(),
      }),
      options,
      boundaryNow,
      'good',
      'Asia/Tokyo',
    )
    expect(updated.type).toBe('learning')
    expect(updated.interval_days).toBe(1)
    expect(updated.due_at).toBe('2026-02-22T19:00:00.000Z')
    expect(updated.due_day).toBe(
      dayIndex(Date.parse('2026-02-22T19:00:00.000Z'), 4, 'Asia/Tokyo'),
    )
  })

  it('suspends a leech at the configured threshold', () => {
    const leechOptions = { ...options, leech_threshold: 2 }
    const updated = applyAnswer(
      state({
        type: 'review',
        interval_days: 5,
        due_day: dayIndex(now, 4, 'UTC'),
        due_at: new Date(now).toISOString(),
        lapses: 1,
      }),
      leechOptions,
      now,
      'again',
      'UTC',
    )
    expect(updated.lapses).toBe(2)
    expect(updated.leeched).toBe(true)
    expect(updated.suspended).toBe(true)
  })

  it('formats interval days into days, months, and years', () => {
    expect(formatIntervalDays(1)).toBe('1d')
    expect(formatIntervalDays(15)).toBe('15d')
    expect(formatIntervalDays(29)).toBe('29d')
    expect(formatIntervalDays(30)).toBe('1m')
    expect(formatIntervalDays(45)).toBe('1.5m')
    expect(formatIntervalDays(50)).toBe('1.7m')
    expect(formatIntervalDays(60)).toBe('2m')
    expect(formatIntervalDays(90)).toBe('3m')
    expect(formatIntervalDays(180)).toBe('6m')
    expect(formatIntervalDays(360)).toBe('12m')
    expect(formatIntervalDays(365)).toBe('1y')
    expect(formatIntervalDays(500)).toBe('1.4y')
    expect(formatIntervalDays(600)).toBe('1.6y')
    expect(formatIntervalDays(730)).toBe('2y')
    expect(formatIntervalDays(36500)).toBe('100y')
  })

  it('previews long review intervals using months or years labels', () => {
    const monthCard = state({
      type: 'review',
      interval_days: 50,
      due_day: dayIndex(now, 4, 'UTC'),
      due_at: new Date(now).toISOString(),
    })
    const monthDecision = computeDecision(monthCard, options, now, 'UTC')
    expect(monthDecision.previews.hard.label).toBe('2m') // 50 * 1.2 = 60d -> 2m

    const yearCard = state({
      type: 'review',
      interval_days: 300,
      due_day: dayIndex(now, 4, 'UTC'),
      due_at: new Date(now).toISOString(),
    })
    const yearDecision = computeDecision(yearCard, options, now, 'UTC')
    // 300 * 2.5 = 750d -> 750 / 365 = 2.05 -> 2.1y
    expect(yearDecision.previews.good.label).toBe('2.1y')
  })
})
