import { describe, expect, it, vi } from 'vitest'
import type { StudySessionSnapshot } from '../types'
import {
  applyLocalAnswer,
  automaticCommitMode,
  buildSessionView,
  createPersistedSession,
  decisionForCard,
  prepareCommit,
} from './studySessionEngine'

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
    cards: [
      {
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
      },
    ],
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

describe('local study session engine', () => {
  it('answers locally and builds a delta batch', () => {
    vi.stubGlobal('crypto', {
      randomUUID: () => '00000000-0000-4000-8000-000000000001',
    })
    const local = createPersistedSession(snapshot())
    const now = Date.parse(local.snapshot.server_now_utc)
    const view = buildSessionView(local, now)
    expect(view.card?.card_id).toBe('card-1')

    const decision = decisionForCard(local, 'card-1', now + 1000)
    const answered = applyLocalAnswer(
      local,
      'card-1',
      'good',
      decision,
      500,
    )
    expect(answered.events).toHaveLength(1)
    expect(answered.snapshot.cards[0].state.type).toBe('learning')

    const prepared = prepareCommit(answered, {
      resumeAfterCommit: true,
    })
    expect(prepared.payload.events).toHaveLength(1)
    expect(prepared.payload.final_states).toHaveLength(1)
    expect(prepared.payload.final_states[0].card_id).toBe('card-1')
    expect(prepared.session.resume_after_commit).toBe(true)

    expect(automaticCommitMode(
      answered,
      { ...view, session_state: 'complete' },
    )).toBe('finish')

    const thresholdSession = {
      ...answered,
      events: Array.from({ length: 50 }, (_, index) => ({
        ...answered.events[0],
        event_id: `event-${index}`,
        sequence: index + 1,
      })),
    }
    expect(automaticCommitMode(
      thresholdSession,
      { ...view, session_state: 'active' },
    )).toBe('rollover')
    expect(automaticCommitMode(
      { ...thresholdSession, status: 'pending_commit' },
      { ...view, session_state: 'active' },
    )).toBeNull()
    vi.unstubAllGlobals()
  })
})
