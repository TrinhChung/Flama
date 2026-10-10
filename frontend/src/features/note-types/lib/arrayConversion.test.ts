import { describe, expect, it } from 'vitest'
import {
  DEFAULT_SPLIT_PRESETS,
  buildArrayBackup,
  parseArrayBackup,
  splitToArray,
  type SplitPresetId,
} from './arrayConversion'

const presets = (...ids: SplitPresetId[]) => new Set<SplitPresetId>(ids)

describe('splitToArray', () => {
  it('splits by the default separators: lines, commas and semicolons', () => {
    expect(splitToArray('Nghĩa 1, nghĩa 2; nghĩa 3\nnghĩa 4', DEFAULT_SPLIT_PRESETS)).toEqual({
      value: 'Nghĩa 1\nnghĩa 2\nnghĩa 3\nnghĩa 4',
      items: ['Nghĩa 1', 'nghĩa 2', 'nghĩa 3', 'nghĩa 4'],
      flags: [],
    })
  })

  it('handles full-width and Japanese separators when chosen', () => {
    expect(splitToArray('たべる、くう', presets('jp_comma')).items).toEqual(['たべる', 'くう'])
    expect(splitToArray('a，b；c', presets('comma', 'semicolon')).items).toEqual(['a', 'b', 'c'])
    expect(splitToArray('a/b／c', presets('slash')).items).toEqual(['a', 'b', 'c'])
  })

  it('splits numbered lists and keeps the middle dot unless chosen', () => {
    expect(splitToArray('1. ăn 2. uống', presets('numbered')).items).toEqual(['ăn', 'uống'])
    expect(splitToArray('① ăn ② uống', presets('numbered')).items).toEqual(['ăn', 'uống'])
    expect(splitToArray('ジョン・スミス', DEFAULT_SPLIT_PRESETS).items).toEqual(['ジョン・スミス'])
    expect(splitToArray('ジョン・スミス', presets('middle_dot')).items).toEqual(['ジョン', 'スミス'])
  })

  it('never splits inside brackets and flags bracketed items', () => {
    expect(splitToArray('Số tờ, số tấm (giấy, ảnh, vé)', DEFAULT_SPLIT_PRESETS)).toEqual({
      value: 'Số tờ\nsố tấm (giấy, ảnh, vé)',
      items: ['Số tờ', 'số tấm (giấy, ảnh, vé)'],
      flags: ['brackets'],
    })
    expect(splitToArray('たべる（食べる、喰べる）、くう', presets('jp_comma')).items).toEqual(['たべる（食べる、喰べる）', 'くう'])
    expect(splitToArray('a [b; c]; d「e, f」, g', DEFAULT_SPLIT_PRESETS).items).toEqual(['a [b; c]', 'd「e, f」', 'g'])
  })

  it('survives unbalanced brackets and numbered markers with a closing parenthesis', () => {
    expect(splitToArray('a), b, (c', DEFAULT_SPLIT_PRESETS).items).toEqual(['a)', 'b', '(c'])
    expect(splitToArray('1) ăn 2) uống', presets('numbered')).items).toEqual(['ăn', 'uống'])
  })

  it('joins lines when the newline separator is off', () => {
    expect(splitToArray('dùng\nbữa', presets('comma')).items).toEqual(['dùng bữa'])
  })

  it('flags markup, sound references, duplicates and long items', () => {
    expect(splitToArray('<b>ăn</b>, ăn', DEFAULT_SPLIT_PRESETS)).toEqual({ value: 'ăn', items: ['ăn'], flags: ['html', 'duplicates'] })
    expect(splitToArray('ăn[sound:a.mp3]', DEFAULT_SPLIT_PRESETS).flags).toEqual(['sound'])
    expect(splitToArray('x'.repeat(81), DEFAULT_SPLIT_PRESETS).flags).toEqual(['long'])
  })

  it('flags a non-empty value that leaves no item and keeps empty values empty', () => {
    expect(splitToArray('<br>,;', DEFAULT_SPLIT_PRESETS)).toEqual({ value: '', items: [], flags: ['html', 'empty'] })
    expect(splitToArray('', DEFAULT_SPLIT_PRESETS)).toEqual({ value: '', items: [], flags: [] })
  })
})

describe('array backup', () => {
  const backup = buildArrayBackup({
    noteTypeId: 'nt-1', fieldId: 'f-1', fieldName: 'Meaning', originalType: 'text',
    notes: [{ note_id: 'n-1', value: 'a, b' }], now: new Date('2026-10-10T00:00:00Z'),
  })

  it('round-trips through JSON for the same field', () => {
    const parsed = parseArrayBackup(JSON.parse(JSON.stringify(backup)), { noteTypeId: 'nt-1', fieldId: 'f-1' })
    expect(parsed).toEqual({ ok: true, backup })
  })

  it('refuses another field or a malformed file', () => {
    expect(parseArrayBackup(backup, { noteTypeId: 'nt-1', fieldId: 'f-2' })).toEqual({ ok: false, error: 'other_field' })
    expect(parseArrayBackup({ ...backup, original_type: 'image' }, { noteTypeId: 'nt-1', fieldId: 'f-1' })).toEqual({ ok: false, error: 'invalid' })
    expect(parseArrayBackup({ ...backup, notes: [{ note_id: 1 }] }, { noteTypeId: 'nt-1', fieldId: 'f-1' })).toEqual({ ok: false, error: 'invalid' })
    expect(parseArrayBackup('nope', { noteTypeId: 'nt-1', fieldId: 'f-1' })).toEqual({ ok: false, error: 'invalid' })
  })
})
