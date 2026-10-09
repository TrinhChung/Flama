import { describe, expect, it } from 'vitest'
import { applyLocalAnswer, createPersistedSession, decisionForCard, extractPendingBatch, undoLocalAnswer } from './studySessionEngine'
import { studySnapshotFixture } from './studySessionTestFixture'
import { applyCardContentPatch } from './contentPatchAdapter'
import { normalizePersistedStudySession } from './sessionRestore'
import { artifactsForRestoredSession, hydrateStoredCheckpoint, splitSessionCheckpoint } from './sessionStorageCodec'

describe('split study checkpoints', () => {
  it('reuses immutable artifacts for checkpoints and keeps a full validated restore', () => {
    const session = createPersistedSession(studySnapshotFixture())
    const first = splitSessionCheckpoint(session)
    const next = { ...session, snapshot: { ...session.snapshot, cards: [...session.snapshot.cards] }, updated_at_ms: session.updated_at_ms + 1 }
    const second = splitSessionCheckpoint(next, first.artifacts)
    expect(second.artifacts).toBe(first.artifacts)
    expect(second.checkpoint.snapshot).not.toHaveProperty('contents')
    expect(second.checkpoint.snapshot).not.toHaveProperty('templates')
    expect(second.checkpoint.snapshot).not.toHaveProperty('cards')
    expect(second.checkpoint.card_overrides).toEqual([])
    const restored = hydrateStoredCheckpoint(second.checkpoint, second.artifacts)
    expect(normalizePersistedStudySession(restored, session.scope_key)).toMatchObject({
      status: 'restored', session: { snapshot: next.snapshot, updated_at_ms: next.updated_at_ms },
    })
  })

  it('allocates new artifacts after a content patch without changing scheduler state', () => {
    const session = createPersistedSession(studySnapshotFixture())
    const first = splitSessionCheckpoint(session)
    const patch = applyCardContentPatch(session, session.snapshot.cards[0].card_id, { Word: 'dog' })
    const second = splitSessionCheckpoint(patch.nextSession, first.artifacts)
    expect(second.artifacts.id).not.toBe(first.artifacts.id)
    const raw = hydrateStoredCheckpoint(second.checkpoint, second.artifacts)
    const restored = normalizePersistedStudySession(raw, session.scope_key)
    expect(restored.status).toBe('restored')
    if (restored.status !== 'restored') throw new Error('Patch failed restore')
    const card = restored.session.snapshot.cards[0]
    expect(restored.session.snapshot.contents[card.content_key].field_values.Word).toBe('dog')
    expect(card.state).toEqual(session.snapshot.cards[0].state)
    expect(restored.session.events).toEqual(session.events)
  })

  it.each(['missing', 'foreign_scope', 'foreign_session', 'wrong_key', 'malformed_maps'])('quarantines %s artifacts instead of accepting a partial snapshot', (failure) => {
    const session = createPersistedSession(studySnapshotFixture())
    const { checkpoint, artifacts } = splitSessionCheckpoint(session)
    const damaged = failure === 'missing' ? undefined
      : { ...artifacts,
          ...(failure === 'foreign_scope' ? { scope_key: 'user:999:deck:1' } : {}),
          ...(failure === 'foreign_session' ? { session_id: crypto.randomUUID() } : {}),
          ...(failure === 'wrong_key' ? { id: crypto.randomUUID() } : {}),
          ...(failure === 'malformed_maps' ? { contents: [] } : {}),
        }
    expect(normalizePersistedStudySession(hydrateStoredCheckpoint(checkpoint, damaged), session.scope_key).status).toBe('quarantine')
  })

  it('continues to read old inline rows', () => {
    const session = createPersistedSession(studySnapshotFixture())
    expect(hydrateStoredCheckpoint(session, undefined)).toBe(session)
    expect(normalizePersistedStudySession(session, session.scope_key).status).toBe('restored')
  })

  it('retains answers, undo and in-flight batch identity after reloading and saving again', () => {
    const initial = createPersistedSession(studySnapshotFixture())
    const first = splitSessionCheckpoint(initial)
    const id = initial.snapshot.cards[0].card_id
    const answered = applyLocalAnswer(initial, id, 'good', decisionForCard(initial, id, Date.parse(initial.snapshot.server_now_utc) + 1000), 500)
    const second = splitSessionCheckpoint(answered, first.artifacts)
    expect(second.artifacts).toBe(first.artifacts)
    expect(second.checkpoint.card_overrides).toHaveLength(1)
    const restored = normalizePersistedStudySession(hydrateStoredCheckpoint(second.checkpoint, first.artifacts), initial.scope_key)
    if (restored.status !== 'restored') throw new Error('Answer failed restore')
    const cached = artifactsForRestoredSession(restored.session, first.artifacts.id, first.artifacts.cards)
    const next = splitSessionCheckpoint({ ...restored.session, updated_at_ms: restored.session.updated_at_ms + 1 }, cached)
    expect(next.checkpoint.card_overrides).toHaveLength(1)
    expect(hydrateStoredCheckpoint(next.checkpoint, cached)).toMatchObject({
      events: answered.events, undo_history: answered.undo_history, snapshot: { cards: answered.snapshot.cards },
    })
    const batch = extractPendingBatch(restored.session)!
    const batched = splitSessionCheckpoint(batch.session, cached)
    expect(hydrateStoredCheckpoint(batched.checkpoint, cached)).toMatchObject({
      in_flight_batches: [batch.batch], batch_sequence: 1, events: [],
    })
    const undone = undoLocalAnswer(restored.session)!.session
    const undoCheckpoint = splitSessionCheckpoint(undone, cached)
    expect(hydrateStoredCheckpoint(undoCheckpoint.checkpoint, cached)).toMatchObject({
      events: [], snapshot: { cards: initial.snapshot.cards },
    })
  })

  it.each(['negative', 'outside', 'duplicate', 'wrong_card'])('quarantines a %s card override', (failure) => {
    const session = createPersistedSession(studySnapshotFixture())
    const { checkpoint, artifacts } = splitSessionCheckpoint(session)
    const card = session.snapshot.cards[0]
    const overrides = failure === 'negative' ? [[-1, card]]
      : failure === 'outside' ? [[artifacts.cards.length, card]]
      : failure === 'duplicate' ? [[0, card], [0, card]]
      : [[0, { ...card, card_id: 'another-card' }]]
    const damaged = { ...checkpoint, card_overrides: overrides }
    expect(normalizePersistedStudySession(hydrateStoredCheckpoint(damaged, artifacts), session.scope_key).status).toBe('quarantine')
  })
})
