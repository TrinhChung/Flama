import { describe, expect, it } from 'vitest'
import {
  buildExactAnkiDeckQuery,
  buildExactAnkiModelQuery,
  indexImportCardResults,
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
})
