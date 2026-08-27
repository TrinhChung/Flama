import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Rating, StudySessionSnapshot } from '../types'
import {
  ClientAlgorithmContractError,
  ClientAlgorithmUnavailableError,
} from '../scheduler/algorithmRegistry'
import {
  applyLocalAnswer,
  automaticCommitMode,
  buildSessionView,
  createPersistedSession,
  decisionForCard,
  isBackgroundRolloverCommit,
  prepareCommit,
  undoLocalAnswer,
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
        composition_id: 'standard',
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
    compositions: {},
  }
}

function snapshotWithCards(cardCount: number): StudySessionSnapshot {
  const base = snapshot()
  const baseCard = base.cards[0]
  const baseContent = base.contents.content
  const cards = Array.from({ length: cardCount }, (_, index) => {
    const ordinal = index + 1
    return {
      ...baseCard,
      card_id: `card-${ordinal}`,
      note_id: `note-${ordinal}`,
      created_at: `2026-02-${ordinal.toString().padStart(2, '0')}T00:00:00.000Z`,
      content_key: `content-${ordinal}`,
      state: { ...baseCard.state },
    }
  })
  return {
    ...base,
    cards,
    contents: Object.fromEntries(cards.map((card) => [
      card.content_key,
      {
        ...baseContent,
        id: card.note_id,
        note_id: card.note_id,
        field_values: { Word: card.card_id },
        render_context: { Word: card.card_id },
      },
    ])),
  }
}

describe('local study session engine', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('fails before opening a session whose Algorithm is unavailable', () => {
    const unsupported = snapshot()
    unsupported.algorithm_version = '2.0.0'
    unsupported.policies.policy.algorithm_version = '2.0.0'

    expect(() => createPersistedSession(unsupported))
      .toThrow(ClientAlgorithmUnavailableError)
  })

  it('fails before answering when a restored policy identity drifts', () => {
    const local = createPersistedSession(snapshot())
    local.snapshot.policies.policy.algorithm_version = '2.0.0'

    expect(() => decisionForCard(
      local,
      'card-1',
      Date.parse(local.snapshot.server_now_utc),
    )).toThrow(ClientAlgorithmContractError)
  })

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
    expect(answered.events[0]).toMatchObject({
      rating: 'good',
      action_key: 'review.good',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
    })
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
      { ...view, session_state: 'complete_today' },
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

    const rolloverCommit = prepareCommit(thresholdSession, {
      reason: 'rollover',
      resumeAfterCommit: true,
    }).session
    expect(isBackgroundRolloverCommit(rolloverCommit)).toBe(true)
    expect(rolloverCommit.commit_reason).toBe('rollover')
    expect(isBackgroundRolloverCommit({
      ...rolloverCommit,
      resume_after_commit: false,
    })).toBe(false)
  })

  it.each<Rating>(['again', 'hard', 'good'])(
    'keeps repeating %s learning cards inside the learn-ahead window',
    (rating) => {
      vi.stubGlobal('crypto', {
        randomUUID: () => '00000000-0000-4000-8000-000000000001',
      })
      let local = createPersistedSession(snapshotWithCards(3))
      const now = Date.parse(local.snapshot.server_now_utc)

      for (let index = 1; index <= 3; index += 1) {
        const cardId = `card-${index}`
        const answerAt = now + index * 1000
        local = applyLocalAnswer(
          local,
          cardId,
          rating,
          decisionForCard(local, cardId, answerAt),
          250,
        )
      }

      const view = buildSessionView(local, now + 4000)
      expect(view.session_state).toBe('active')
      expect(view.card?.card_id).toBe('card-1')
      expect(view.counts).toEqual({ new: 0, learning: 3, due: 0 })
      expect(automaticCommitMode(local, view)).toBeNull()
    },
  )

  it('waits only until a learning card enters learn-ahead, then resumes', () => {
    vi.stubGlobal('crypto', {
      randomUUID: () => '00000000-0000-4000-8000-000000000001',
    })
    const waitingSnapshot = snapshot()
    waitingSnapshot.learn_ahead_seconds = 300
    let local = createPersistedSession(waitingSnapshot)
    const now = Date.parse(local.snapshot.server_now_utc)
    local = applyLocalAnswer(
      local,
      'card-1',
      'good',
      decisionForCard(local, 'card-1', now),
      250,
    )

    const waiting = buildSessionView(local, now + 1000)
    expect(waiting.session_state).toBe('waiting')
    expect(waiting.pending_learning_count).toBe(1)
    expect(waiting.next_due_at_ms).toBe(now + 600_000)
    expect(waiting.next_eligible_at_ms).toBe(now + 300_000)
    expect(automaticCommitMode(local, waiting)).toBeNull()

    const resumed = buildSessionView(local, now + 300_000)
    expect(resumed.session_state).toBe('active')
    expect(resumed.card?.card_id).toBe('card-1')
  })

  it('finishes only after the final learning step graduates to review', () => {
    vi.stubGlobal('crypto', {
      randomUUID: () => '00000000-0000-4000-8000-000000000001',
    })
    let local = createPersistedSession(snapshot())
    const now = Date.parse(local.snapshot.server_now_utc)
    local = applyLocalAnswer(
      local,
      'card-1',
      'good',
      decisionForCard(local, 'card-1', now),
      250,
    )
    expect(buildSessionView(local, now + 500).session_state).toBe('active')

    local = applyLocalAnswer(
      local,
      'card-1',
      'good',
      decisionForCard(local, 'card-1', now + 1000),
      250,
    )
    const completed = buildSessionView(local, now + 1500)
    expect(local.snapshot.cards[0].state.type).toBe('review')
    expect(completed.session_state).toBe('complete_today')
    expect(automaticCommitMode(local, completed)).toBe('finish')
  })

  it('uses the Anki default learn-ahead for a malformed restored value', () => {
    const malformed = snapshot()
    malformed.learn_ahead_seconds = Number.NaN
    const local = createPersistedSession(malformed)
    const now = Date.parse(local.snapshot.server_now_utc)
    const decision = decisionForCard(local, 'card-1', now)
    const answered = applyLocalAnswer(local, 'card-1', 'good', decision, 250)

    expect(buildSessionView(answered, now + 1000).session_state).toBe('active')
  })

  it('undoes a local answer and restores previous card state and events', () => {
    vi.stubGlobal('crypto', {
      randomUUID: () => '00000000-0000-4000-8000-000000000001',
    })
    const initial = createPersistedSession(snapshot())
    const now = Date.parse(initial.snapshot.server_now_utc)
    const originalState = { ...initial.snapshot.cards[0].state }

    const decision = decisionForCard(initial, 'card-1', now + 1000)
    const answered = applyLocalAnswer(
      initial,
      'card-1',
      'good',
      decision,
      500,
    )
    expect(answered.events).toHaveLength(1)
    expect(answered.snapshot.cards[0].state.type).toBe('learning')
    expect(answered.touched_card_ids).toEqual(['card-1'])

    const undone = undoLocalAnswer(answered)
    expect(undone).not.toBeNull()
    expect(undone?.undoneCardId).toBe('card-1')
    expect(undone?.session.events).toHaveLength(0)
    expect(undone?.session.touched_card_ids).toHaveLength(0)
    expect(undone?.session.snapshot.cards[0].state).toEqual(originalState)

    const view = buildSessionView(undone!.session, now)
    expect(view.card?.card_id).toBe('card-1')
  })

  it('handles multiple sequential undos correctly across different cards', () => {
    vi.stubGlobal('crypto', {
      randomUUID: () => '00000000-0000-4000-8000-000000000001',
    })
    let current = createPersistedSession(snapshotWithCards(3))
    const now = Date.parse(current.snapshot.server_now_utc)
    const initialStates = current.snapshot.cards.map((c) => ({ ...c.state }))

    // Answer card-1, card-2, card-3
    for (let i = 1; i <= 3; i++) {
      const cardId = `card-${i}`
      const decision = decisionForCard(current, cardId, now + i * 1000)
      current = applyLocalAnswer(current, cardId, 'easy', decision, 200)
    }
    expect(current.events).toHaveLength(3)
    expect(current.touched_card_ids).toEqual(['card-1', 'card-2', 'card-3'])

    // Undo card-3
    const undo3 = undoLocalAnswer(current)
    expect(undo3?.undoneCardId).toBe('card-3')
    expect(undo3?.session.events).toHaveLength(2)
    expect(undo3?.session.touched_card_ids).toEqual(['card-1', 'card-2'])
    expect(undo3?.session.snapshot.cards[2].state).toEqual(initialStates[2])

    // Undo card-2
    const undo2 = undoLocalAnswer(undo3!.session)
    expect(undo2?.undoneCardId).toBe('card-2')
    expect(undo2?.session.events).toHaveLength(1)
    expect(undo2?.session.touched_card_ids).toEqual(['card-1'])
    expect(undo2?.session.snapshot.cards[1].state).toEqual(initialStates[1])

    // Undo card-1
    const undo1 = undoLocalAnswer(undo2!.session)
    expect(undo1?.undoneCardId).toBe('card-1')
    expect(undo1?.session.events).toHaveLength(0)
    expect(undo1?.session.touched_card_ids).toHaveLength(0)
    expect(undo1?.session.snapshot.cards[0].state).toEqual(initialStates[0])

    // Undoing when empty returns null
    expect(undoLocalAnswer(undo1!.session)).toBeNull()
  })

  it('locks the active card and does not auto-switch when another learning card becomes due on tick', () => {
    vi.stubGlobal('crypto', {
      randomUUID: () => '00000000-0000-4000-8000-000000000001',
    })
    const snap = snapshotWithCards(2)
    const now = Date.parse(snap.server_now_utc)

    // Card 1: Review card due today
    snap.cards[0].state = {
      ...snap.cards[0].state,
      type: 'review',
      due_day: 0,
      due_at: null,
    }
    // Card 2: Learning card due in 60s
    snap.cards[1].state = {
      ...snap.cards[1].state,
      type: 'learning',
      due_day: null,
      due_at: new Date(now + 60_000).toISOString(),
    }

    const session = createPersistedSession(snap)
    expect(session.active_card_id).toBe('card-1')

    // At t = now, card-1 is on screen
    const viewAtStart = buildSessionView(session, now)
    expect(viewAtStart.card?.card_id).toBe('card-1')

    // At t = now + 70s, card-2 becomes due in learning queue (normally higher priority than review)
    // But card-1 is locked as active_card_id, so buildSessionView must NOT switch to card-2
    const viewAfterTick = buildSessionView(session, now + 70_000)
    expect(viewAfterTick.card?.card_id).toBe('card-1')
    expect(viewAfterTick.counts.learning).toBe(1)
    expect(viewAfterTick.counts.due).toBe(1)

    // Only after answering card-1 does the session transition to card-2
    const decision = decisionForCard(session, 'card-1', now + 70_000)
    const answered = applyLocalAnswer(session, 'card-1', 'good', decision, 1000)
    expect(answered.active_card_id).toBe('card-2')

    const viewAfterAnswer = buildSessionView(answered, now + 70_000)
    expect(viewAfterAnswer.card?.card_id).toBe('card-2')
  })
})
