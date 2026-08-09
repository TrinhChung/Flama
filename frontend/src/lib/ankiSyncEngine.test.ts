import { describe, expect, it } from 'vitest'
import {
  buildExactAnkiDeckQuery,
  buildExactAnkiModelQuery,
  classifyNoteSyncStatus,
  indexCardDecksByNote,
  indexImportCardResults,
  mapAnkiDeckPath,
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
      { cardId: 1, note: 10, modelName: 'Basic', deckName: 'Root::A', fields: {} },
      { cardId: 2, note: 10, modelName: 'Basic', deckName: 'Root::B', fields: {} },
      { cardId: 3, note: 11, modelName: 'Basic', deckName: 'Root::A', fields: {} },
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
})
