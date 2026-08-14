import { describe, expect, it } from 'vitest'
import {
  buildExactAnkiDeckQuery,
  buildExactAnkiModelQuery,
  classifyNoteSyncStatus,
  indexCardDecksByNote,
  indexImportCardResults,
  mapAnkiDeckPath,
} from './ankiSyncHelpers'
import {
  ankiProgressSnapshot,
  ankiReviewRecord,
  canonicalizeAnkiEndpoint,
  shouldQueueAnkiHistory,
} from './ankiSyncEngine'

describe('ankiSyncEngine helpers', () => {
  it('quotes deck and note type values for exact Anki searches', () => {
    expect(buildExactAnkiDeckQuery('Japanese::N3 "Core"')).toBe('deck:"Japanese::N3 \\"Core\\""')
    expect(buildExactAnkiModelQuery('Japanese::N3', 'Basic "JP"')).toBe(
      'deck:"Japanese::N3" note:"Basic \\"JP\\""'
    )
  })

  it('indexes per-card import outcomes without treating a missing result as success', () => {
    const indexed = indexImportCardResults([
      { ankiNoteId: 11, imported: true, noteId: 'flama-11' },
      { ankiNoteId: 12, imported: false, error: 'invalid field' },
    ])

    expect(indexed.get(11)).toMatchObject({ imported: true, noteId: 'flama-11' })
    expect(indexed.get(12)).toMatchObject({ imported: false, error: 'invalid field' })
    expect(indexed.get(13)).toBeUndefined()
  })

  it('preserves every relative child segment below the selected root', () => {
    expect(mapAnkiDeckPath('Japanese::N3', 'Japanese::N3', 'Imported::N3')).toBe('Imported::N3')
    expect(mapAnkiDeckPath('Japanese::N3', 'Japanese::N3::Grammar::Week 1', 'Imported::N3')).toBe(
      'Imported::N3::Grammar::Week 1'
    )
    expect(() => mapAnkiDeckPath('Japanese::N3', 'Japanese::N2', 'Imported::N3')).toThrow()
  })

  it('detects notes whose cards are assigned to more than one Anki deck', () => {
    const indexed = indexCardDecksByNote([
      { cardId: 1, note: 10, modelName: 'Basic', deckName: 'Root::A', fields: {}, ord: 0, type: 0, queue: 0, due: 1, interval: 0, factor: 0, reps: 0, lapses: 0 },
      { cardId: 2, note: 10, modelName: 'Basic', deckName: 'Root::B', fields: {}, ord: 1, type: 0, queue: 0, due: 2, interval: 0, factor: 0, reps: 0, lapses: 0 },
      { cardId: 3, note: 11, modelName: 'Basic', deckName: 'Root::A', fields: {}, ord: 0, type: 0, queue: 0, due: 3, interval: 0, factor: 0, reps: 0, lapses: 0 },
    ])
    expect([...indexed.get(10)!]).toEqual(['Root::A', 'Root::B'])
    expect([...indexed.get(11)!]).toEqual(['Root::A'])
  })

  it('retries a failed note even when its content hash is unchanged', () => {
    const failedState = {
      key: 'source-note',
      sourceKey: 'source',
      ankiNoteId: 10,
      ankiDeckName: 'Root',
      ankiNoteType: 'Basic',
      contentHash: 'same-hash',
      syncStatus: 'Error' as const,
      syncProfileId: 'profile',
    }

    expect(classifyNoteSyncStatus(failedState, 'profile', 'same-hash', 'new_and_changed')).toBe('New')
    expect(classifyNoteSyncStatus(failedState, 'profile', 'same-hash', 'only_new')).toBe('New')
    expect(classifyNoteSyncStatus({ ...failedState, syncStatus: 'Synced' }, 'profile', 'same-hash', 'new_and_changed')).toBe('Unchanged')
  })

  it('uses one source namespace for equivalent loopback endpoints', () => {
    expect(canonicalizeAnkiEndpoint()).toBe('http://127.0.0.1:8765')
    expect(canonicalizeAnkiEndpoint('http://localhost:8765/')).toBe('http://127.0.0.1:8765')
  })

  it('builds a stable raw scheduler snapshot without a time-relative due value', () => {
    const snapshot = ankiProgressSnapshot({
      cardId: 12,
      note: 8,
      modelName: 'Basic',
      deckName: 'Root',
      fields: {},
      ord: 0,
      type: 2,
      queue: 2,
      due: 50001,
      interval: 14,
      factor: 2500,
      reps: 3,
      lapses: 1,
      left: 0,
      mod: 123,
    })
    expect(snapshot).toMatchObject({ sourceCardId: 12, due: 50001, reps: 3, mod: 123 })
    expect(snapshot).not.toHaveProperty('relativeDue')
  })

  it('serializes every revlog field needed by historical analytics and dedupe', () => {
    expect(ankiReviewRecord(12, {
      id: 1_786_500_000_000,
      usn: 9,
      ease: 3,
      ivl: 10,
      lastIvl: 5,
      factor: 2500,
      time: 1800,
      type: 1,
    })).toEqual({
      sourceReviewId: 1_786_500_000_000,
      sourceCardId: 12,
      ease: 3,
      type: 1,
      ivl: 10,
      lastIvl: 5,
      factor: 2500,
      time: 1800,
    })
  })

  it('queues history only after the source card has an authoritative mapping', () => {
    const base = {
      reps: 10,
      syncMode: 'new_and_changed' as const,
      reviewCursor: null,
      progressUploadFailed: false,
      mappedDuringProgress: false,
    }

    expect(shouldQueueAnkiHistory({ ...base, progressState: 'new' })).toBe(false)
    expect(shouldQueueAnkiHistory({
      ...base,
      progressState: 'new',
      mappedDuringProgress: true,
    })).toBe(true)
    expect(shouldQueueAnkiHistory({
      ...base,
      progressState: 'unchanged',
    })).toBe(true)
    expect(shouldQueueAnkiHistory({
      ...base,
      progressState: 'unchanged',
      reviewCursor: '1786500000000',
    })).toBe(false)
    expect(shouldQueueAnkiHistory({
      ...base,
      progressState: 'changed',
      reviewCursor: '1786500000000',
      progressUploadFailed: true,
    })).toBe(false)
  })
})
