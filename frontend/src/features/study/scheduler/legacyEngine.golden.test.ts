import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { resolveReviewAction } from '../interactions/reviewInteraction'
import type { Rating } from '../types'
import { computeDecision } from './legacyEngine'
import type {
  SchedulerCardState,
  SchedulerOptions,
  SchedulerPreview,
} from './types'

type GoldenExpected = {
  state_patch: Partial<SchedulerCardState>
  preview: SchedulerPreview
}

type GoldenCase = {
  id: string
  now: string
  timezone: string
  state: SchedulerCardState
  options_patch?: Partial<SchedulerOptions>
  expected: Record<Rating, GoldenExpected>
}

type GoldenFixture = {
  vector_schema_version: string
  algorithm: {
    key: string
    version: string
    state_schema_version: string
  }
  action_contract: {
    version: string
    ratings: Record<Rating, {
      action_key: string
      trigger_key: string
    }>
  }
  base_options: SchedulerOptions
  cases: GoldenCase[]
}

const fixturePath = fileURLToPath(
  new URL(
    '../../../../../tests/fixtures/study/legacy-anki-1.0.0-golden-vectors.json',
    import.meta.url,
  ),
)
const fixture = JSON.parse(
  readFileSync(fixturePath, 'utf8'),
) as GoldenFixture
const ratings: Rating[] = ['again', 'hard', 'good', 'easy']

describe('legacy-anki 1.0.0 frozen cross-language vectors', () => {
  it('pins the fixture and action contract identities', () => {
    expect(fixture.vector_schema_version).toBe(
      'study-algorithm-golden-vectors.v1',
    )
    expect(fixture.algorithm).toEqual({
      key: 'legacy-anki',
      version: '1.0.0',
      state_schema_version: 'anki-card-state.v1',
    })
    expect(fixture.cases).toHaveLength(10)
    expect(fixture.cases.reduce(
      (total, vector) => total + Object.keys(vector.expected).length,
      0,
    )).toBe(40)

    for (const rating of ratings) {
      const action = resolveReviewAction(rating)
      expect({
        action_key: action.actionKey,
        trigger_key: action.triggerKey,
        trigger_contract_version: action.triggerContractVersion,
      }).toEqual({
        ...fixture.action_contract.ratings[rating],
        trigger_contract_version: fixture.action_contract.version,
      })
    }
  })

  it.each(fixture.cases)('$id', (vector) => {
    const options: SchedulerOptions = {
      ...fixture.base_options,
      ...(vector.options_patch ?? {}),
    }
    const decision = computeDecision(
      vector.state,
      options,
      Date.parse(vector.now),
      vector.timezone,
    )

    for (const rating of ratings) {
      const expected = vector.expected[rating]
      expect(decision.outcomes[rating]).toEqual({
        ...vector.state,
        ...expected.state_patch,
      })
      expect(decision.previews[rating]).toEqual(expected.preview)
    }
  })
})
