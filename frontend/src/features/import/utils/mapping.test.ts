import { describe, it, expect } from 'vitest'
import { buildSuggestedMapping, normalizeFieldName } from './mapping'
import type { NoteField, ParsedColumn } from '../hooks/useFileImportWizard'

describe('normalizeFieldName', () => {
  it('normalizes strings properly', () => {
    expect(normalizeFieldName('Front')).toBe('front')
    expect(normalizeFieldName('  Front_Text  ')).toBe('fronttext')
    expect(normalizeFieldName('reading-furigana')).toBe('readingfurigana')
    expect(normalizeFieldName('Từ vựng')).toBe('từvựng')
    expect(normalizeFieldName('')).toBe('')
    expect(normalizeFieldName(null)).toBe('')
  })
})

describe('buildSuggestedMapping', () => {
  const sampleColumns: ParsedColumn[] = [
    { index: 0, name: 'Word', display: 'Word' },
    { index: 1, name: 'Reading', display: 'Reading' },
    { index: 2, name: 'Meaning', display: 'Meaning' },
  ]

  it('matches exactly by column name when header exists', () => {
    const fields: NoteField[] = [
      { id: '1', name: 'Word', position: 0, required: true, field_type: 'text' },
      { id: '2', name: 'Reading', position: 1, required: true, field_type: 'text' },
      { id: '3', name: 'Meaning', position: 2, required: false, field_type: 'text' },
    ]

    const mapping = buildSuggestedMapping(fields, sampleColumns, true)

    expect(mapping['Word']).toEqual({ source_type: 'column', column_index: 0, constant_value: '' })
    expect(mapping['Reading']).toEqual({ source_type: 'column', column_index: 1, constant_value: '' })
    expect(mapping['Meaning']).toEqual({ source_type: 'column', column_index: 2, constant_value: '' })
  })

  it('matches fuzzy normalized names (casing, spaces, underscores)', () => {
    const fields: NoteField[] = [
      { id: '1', name: 'word_term', position: 0, required: true, field_type: 'text' },
    ]
    const columns: ParsedColumn[] = [
      { index: 0, name: 'Word Term', display: 'Word Term' },
    ]

    const mapping = buildSuggestedMapping(fields, columns, true)
    expect(mapping['word_term']).toEqual({ source_type: 'column', column_index: 0, constant_value: '' })
  })

  it('falls back to sequential arrangement ("xếp lần lượt") when names do not match', () => {
    const fields: NoteField[] = [
      { id: '1', name: 'Front', position: 0, required: true, field_type: 'text' },
      { id: '2', name: 'Back', position: 1, required: true, field_type: 'text' },
    ]
    const columns: ParsedColumn[] = [
      { index: 0, name: 'Cột 1', display: 'Cột 1' },
      { index: 1, name: 'Cột 2', display: 'Cột 2' },
      { index: 2, name: 'Cột 3', display: 'Cột 3' },
    ]

    const mapping = buildSuggestedMapping(fields, columns, true)

    // Should map sequentially: Front -> Col 0, Back -> Col 1
    expect(mapping['Front']).toEqual({ source_type: 'column', column_index: 0, constant_value: '' })
    expect(mapping['Back']).toEqual({ source_type: 'column', column_index: 1, constant_value: '' })
  })

  it('arranges sequentially when hasHeader is false', () => {
    const fields: NoteField[] = [
      { id: '1', name: 'FieldA', position: 0, required: true, field_type: 'text' },
      { id: '2', name: 'FieldB', position: 1, required: true, field_type: 'text' },
    ]
    const columns: ParsedColumn[] = [
      { index: 0, name: '', display: 'Cột 1' },
      { index: 1, name: '', display: 'Cột 2' },
    ]

    const mapping = buildSuggestedMapping(fields, columns, false)
    expect(mapping['FieldA']).toEqual({ source_type: 'column', column_index: 0, constant_value: '' })
    expect(mapping['FieldB']).toEqual({ source_type: 'column', column_index: 1, constant_value: '' })
  })

  it('handles mixed matching: maps matching fields first, then arranges remaining fields into unused columns without collision', () => {
    const fields: NoteField[] = [
      { id: '1', name: 'Audio', position: 0, required: false, field_type: 'audio' },
      { id: '2', name: 'Word', position: 1, required: true, field_type: 'text' },
      { id: '3', name: 'Meaning', position: 2, required: false, field_type: 'text' },
    ]
    const columns: ParsedColumn[] = [
      { index: 0, name: 'Word', display: 'Word' },
      { index: 1, name: 'Sound', display: 'Sound' },
      { index: 2, name: 'Meaning', display: 'Meaning' },
    ]

    const mapping = buildSuggestedMapping(fields, columns, true)

    // Word -> Col 0 (exact match)
    // Meaning -> Col 2 (exact match)
    // Audio (at position 0, but Col 0 is used) -> falls back to first unused column Col 1 ("Sound")
    expect(mapping['Word']).toEqual({ source_type: 'column', column_index: 0, constant_value: '' })
    expect(mapping['Meaning']).toEqual({ source_type: 'column', column_index: 2, constant_value: '' })
    expect(mapping['Audio']).toEqual({ source_type: 'column', column_index: 1, constant_value: '' })
  })

  it('marks excess fields as ignore when there are more fields than columns', () => {
    const fields: NoteField[] = [
      { id: '1', name: 'F1', position: 0, required: true, field_type: 'text' },
      { id: '2', name: 'F2', position: 1, required: true, field_type: 'text' },
      { id: '3', name: 'F3', position: 2, required: false, field_type: 'text' },
    ]
    const columns: ParsedColumn[] = [
      { index: 0, name: 'A', display: 'A' },
    ]

    const mapping = buildSuggestedMapping(fields, columns, true)
    expect(mapping['F1']).toEqual({ source_type: 'column', column_index: 0, constant_value: '' })
    expect(mapping['F2']).toEqual({ source_type: 'ignore', column_index: null, constant_value: '' })
    expect(mapping['F3']).toEqual({ source_type: 'ignore', column_index: null, constant_value: '' })
  })

  it('returns empty object when fields or columns are empty', () => {
    expect(buildSuggestedMapping([], sampleColumns)).toEqual({})
    expect(buildSuggestedMapping([{ id: '1', name: 'F', position: 0, required: true, field_type: 'text' }], [])).toEqual({})
  })
})
