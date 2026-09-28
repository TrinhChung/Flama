import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { NOTE_STORAGE_PROFILE, legacyFloatRoundTrip, normalizeNoteTransitionState } from './noteStoragePrecision'
import type { SchedulerCardState } from './types'

const fixture = JSON.parse(readFileSync(fileURLToPath(new URL(
  '../../../../../tests/fixtures/study/note-storage-precision-v1.json', import.meta.url,
)), 'utf8')) as { profile: string; cases: { input: number; expected: number }[] }

describe('NOTE MySQL FLOAT text precision', () => {
  it('uses the same persistence profile as the server', () => {
    expect(fixture.profile).toBe(NOTE_STORAGE_PROFILE)
  })

  it.each(fixture.cases)('round-trips $input to $expected exactly and idempotently', ({ input, expected }) => {
    const actual = legacyFloatRoundTrip(input)
    expect(Object.is(actual, expected)).toBe(true)
    expect(Object.is(legacyFloatRoundTrip(actual), actual)).toBe(true)
  })

  it.each([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY, 1e100])('rejects %s', (value) => {
    expect(() => legacyFloatRoundTrip(value)).toThrow(/finite value/)
  })

  it('does not mutate the scheduler output or unrelated state', () => {
    const before: SchedulerCardState = {
      type: 'review', step_index: 0, due_at: '2026-09-27T00:00:00Z', due_day: 20723,
      interval_days: 1 / 3, ease: 2.0500000000000003, reps: 5, lapses: 1,
      last_review_at: null, review_kind: 'review', scheduler_mode: 'fsrs',
      suspended: false, suspension_reason: null, leeched: false,
      memory_state: { stability: 1.015625, difficulty: 1.046875 },
    }
    const after = normalizeNoteTransitionState(before)
    expect(after).toEqual({ ...before, interval_days: 0.333333, ease: 2.05,
      memory_state: { stability: 1.01562, difficulty: 1.04688 } })
    expect(before.memory_state?.stability).toBe(1.015625)
    expect(before.ease).toBe(2.0500000000000003)
  })
})
