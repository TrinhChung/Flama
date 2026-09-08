import { afterEach, describe, expect, it, vi } from 'vitest'
import type { StudySessionSnapshot } from '../types'
import { createPersistedSession } from './studySessionEngine'
import {
  acknowledgeStudySessionQuarantine,
  loadStudySessionWithDurability,
  saveStudySession,
} from './sessionStore'

function snapshot(): StudySessionSnapshot {
  return {
    schema_version: 'study-session.v2',
    session_id: '33333333-3333-4333-8333-333333333333',
    user_id: 901,
    session_token: 'token',
    snapshot_hash: 'snapshot-hash',
    scope: { type: 'deck', id: '77', name: 'Deck' },
    server_now_utc: '2026-09-08T00:00:00.000Z',
    expires_at: '2026-09-09T00:00:00.000Z',
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
      source_deck_id: 77,
      local_deck_id: 77,
      composition_id: 'standard',
      note_type_id: 'type-1',
      created_at: '2026-09-01T00:00:00.000Z',
      policy_key: 'policy',
      template_key: 'template',
      content_key: 'content',
      base_revision: 0,
      base_state_hash: 'base',
      can_edit_card: true,
      state: {
        type: 'new',
        step_index: 0,
        due_at: '2026-09-08T00:00:00.000Z',
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
        field_values: { Word: 'cat' },
        render_context: { Word: 'cat' },
        media: [],
      },
    },
    compositions: {},
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('study session quarantine fallback', () => {
  it('keeps a stable quarantine marker across repeated loads when IndexedDB fails', async () => {
    vi.stubGlobal('indexedDB', undefined)
    const session = createPersistedSession(snapshot())
    expect(await saveStudySession(session)).toBe(false)

    // Corrupt the same object held by the memory fallback to simulate a bad
    // persisted row discovered while durable storage is unavailable.
    session.snapshot.scope.id = 'outside-requested-scope'

    const first = await loadStudySessionWithDurability(session.scope_key)
    const repeated = await loadStudySessionWithDurability(session.scope_key)

    expect(first).toMatchObject({
      session: null,
      durable: false,
      quarantine: { reason: 'SCOPE_MISMATCH' },
    })
    expect(repeated).toEqual(first)
  })

  it('allows explicit recovery while retaining fail-closed default behavior', async () => {
    vi.stubGlobal('indexedDB', undefined)
    const sourceSnapshot = snapshot()
    sourceSnapshot.user_id = 902
    const session = createPersistedSession(sourceSnapshot)
    expect(await saveStudySession(session)).toBe(false)
    session.snapshot.scope.id = 'outside-requested-scope'

    expect(await loadStudySessionWithDurability(session.scope_key)).toMatchObject({
      session: null,
      quarantine: { reason: 'SCOPE_MISMATCH' },
    })

    await acknowledgeStudySessionQuarantine(session.scope_key)
    const replacementSnapshot = snapshot()
    replacementSnapshot.user_id = 902
    const replacement = createPersistedSession(replacementSnapshot)
    expect(await saveStudySession(replacement)).toBe(false)
    expect(await loadStudySessionWithDurability(session.scope_key)).toMatchObject({
      session: { scope_key: session.scope_key },
      durable: false,
    })
  })
})
