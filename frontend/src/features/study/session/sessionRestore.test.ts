import { describe, expect, it } from 'vitest'
import {
  ClientAlgorithmContractError,
  ClientAlgorithmUnavailableError,
  resolveClientAlgorithm,
  validateSnapshotAlgorithmContract,
} from '../scheduler/algorithmRegistry'
import type { StudySessionSnapshot } from '../types'
import { normalizePersistedStudySession } from './sessionRestore'

function snapshot(): StudySessionSnapshot {
  return {
    schema_version: 'study-session.v2',
    session_id: 'session-1',
    user_id: 7,
    session_token: 'token',
    snapshot_hash: 'snapshot-hash',
    scope: { type: 'deck', id: '12', name: 'Deck' },
    server_now_utc: '2026-02-22T09:00:00.000Z',
    expires_at: '2026-02-23T09:00:00.000Z',
    timezone: 'UTC',
    day_boundary_hour_local: 4,
    learn_ahead_seconds: 1200,
    scheduler_algorithm: 'legacy-anki',
    algorithm_version: '1.0.0',
    queue_contract_version: 'flama-queue.v1',
    policies: {
      policy: {
        algorithm_key: 'legacy-anki',
        algorithm_version: '1.0.0',
        config_schema_version: 'scheduler-config.v1',
        config_hash: 'policy',
        timezone: 'UTC',
        preset_id: null,
        config: {
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
        },
      },
    },
    cards: [{
      card_id: 'card-1',
      note_id: 'note-1',
      template_id: 'template-1',
      source_deck_id: 12,
      local_deck_id: 12,
      note_type_id: 'type-1',
      created_at: '2026-02-01T00:00:00.000Z',
      policy_key: 'policy',
      template_key: 'template',
      content_key: 'content',
      base_revision: 0,
      base_state_hash: 'base',
      can_edit_card: true,
      state: {
        type: 'new',
        step_index: 0,
        due_at: '2026-02-22T09:00:00.000Z',
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
      },
    }],
    templates: {
      template: {
        schema_version: 'study-template.v1',
        renderer_abi: 'test',
        id: 'template-1',
        version: 'v1',
        front_source: '{{Word}}',
        back_source: '{{Word}}',
        front_inline_scripts: [],
        back_inline_scripts: [],
        shared_css: '',
        field_defs: [],
      },
    },
    contents: {
      content: {
        schema_version: 'study-content.v1',
        renderer_abi: 'test',
        id: 'note-1',
        note_id: 'note-1',
        version: 'v1',
        field_values: { Word: '猫' },
        render_context: { Word: '猫' },
        media: [],
      },
    },
  }
}

type StoredEventFixture = {
  event_id: string
  sequence: number
  card_id: string
  rating: string
  policy_key: string
  scheduler_offset_ms: number
  duration_ms: number
  action_key?: string
  trigger_key?: string
  trigger_contract_version?: string
}

function persistedSession() {
  const events: StoredEventFixture[] = [{
    event_id: 'event-1',
    sequence: 1,
    card_id: 'card-1',
    rating: 'good',
    policy_key: 'policy',
    scheduler_offset_ms: 1000,
    duration_ms: 500,
  }]
  return {
    scope_key: 'user:7:deck:12',
    snapshot: snapshot(),
    events,
    touched_card_ids: [],
    opened_client_at_ms: Date.parse('2026-02-22T09:00:00.000Z'),
    status: 'active',
    commit_id: null,
    updated_at_ms: Date.parse('2026-02-22T09:00:01.000Z'),
  }
}

describe('client Algorithm registry', () => {
  it('resolves only the exact retained Algorithm version', () => {
    expect(resolveClientAlgorithm('legacy-anki', '1.0.0')).toMatchObject({
      key: 'legacy-anki',
      version: '1.0.0',
    })
    expect(() => resolveClientAlgorithm('legacy-anki', '2.0.0'))
      .toThrow(ClientAlgorithmUnavailableError)
  })

  it('rejects policy identity that disagrees with the session', () => {
    const invalid = snapshot()
    invalid.policies.policy.algorithm_version = '2.0.0'
    expect(() => validateSnapshotAlgorithmContract(invalid))
      .toThrow(ClientAlgorithmContractError)
  })
})

describe('persisted study session normalization', () => {
  it('upgrades valid legacy v2 events to canonical Action metadata', () => {
    const result = normalizePersistedStudySession(persistedSession())

    expect(result.status).toBe('restored')
    if (result.status !== 'restored') return
    expect(result.migrated).toBe(true)
    expect(result.session.events[0]).toMatchObject({
      rating: 'good',
      action_key: 'review.good',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
    })
    expect(result.session.touched_card_ids).toEqual(['card-1'])
  })

  it('quarantines event metadata that disagrees with its rating', () => {
    const stored = persistedSession()
    stored.events[0] = {
      ...stored.events[0],
      action_key: 'review.easy',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
    }

    const result = normalizePersistedStudySession(stored)

    expect(result).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'EVENT_CONTRACT_MISMATCH' },
    })
  })

  it('quarantines sessions requiring an unavailable Algorithm version', () => {
    const stored = persistedSession()
    stored.snapshot.algorithm_version = '2.0.0'
    stored.snapshot.policies.policy.algorithm_version = '2.0.0'

    const result = normalizePersistedStudySession(stored)

    expect(result).toMatchObject({
      status: 'quarantine',
      quarantine: { reason: 'ALGORITHM_UNAVAILABLE' },
    })
  })
})
