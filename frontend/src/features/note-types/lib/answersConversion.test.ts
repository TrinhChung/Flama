import { describe, expect, it } from 'vitest'
import {
  DEFAULT_SPLIT_PRESETS,
  buildAnswersBackup,
  parseAnswersBackup,
  splitToAnswers,
  type SplitPresetId,
} from './answersConversion'

const presets = (...ids: SplitPresetId[]) => new Set<SplitPresetId>(ids)

describe('splitToAnswers', () => {
  it('splits by the default separators: lines, commas and semicolons', () => {
    expect(splitToAnswers('Nghĩa 1, nghĩa 2; nghĩa 3\nnghĩa 4', DEFAULT_SPLIT_PRESETS)).toEqual({
      value: 'Nghĩa 1\nnghĩa 2\nnghĩa 3\nnghĩa 4',
      answers: ['Nghĩa 1', 'nghĩa 2', 'nghĩa 3', 'nghĩa 4'],
      flags: [],
    })
  })

  it('handles full-width and Japanese separators when chosen', () => {
    expect(splitToAnswers('たべる、くう', presets('jp_comma')).answers).toEqual(['たべる', 'くう'])
    expect(splitToAnswers('a，b；c', presets('comma', 'semicolon')).answers).toEqual(['a', 'b', 'c'])
    expect(splitToAnswers('a/b／c', presets('slash')).answers).toEqual(['a', 'b', 'c'])
  })

  it('splits numbered lists and keeps the middle dot unless chosen', () => {
    expect(splitToAnswers('1. ăn 2. uống', presets('numbered')).answers).toEqual(['ăn', 'uống'])
    expect(splitToAnswers('① ăn ② uống', presets('numbered')).answers).toEqual(['ăn', 'uống'])
    expect(splitToAnswers('ジョン・スミス', DEFAULT_SPLIT_PRESETS).answers).toEqual(['ジョン・スミス'])
    expect(splitToAnswers('ジョン・スミス', presets('middle_dot')).answers).toEqual(['ジョン', 'スミス'])
  })

  it('joins lines when the newline separator is off', () => {
    expect(splitToAnswers('dùng\nbữa', presets('comma')).answers).toEqual(['dùng bữa'])
  })

  it('flags markup, sound references, duplicates and long answers', () => {
    expect(splitToAnswers('<b>ăn</b>, ăn', DEFAULT_SPLIT_PRESETS)).toEqual({ value: 'ăn', answers: ['ăn'], flags: ['html', 'duplicates'] })
    expect(splitToAnswers('ăn[sound:a.mp3]', DEFAULT_SPLIT_PRESETS).flags).toEqual(['sound'])
    expect(splitToAnswers('x'.repeat(81), DEFAULT_SPLIT_PRESETS).flags).toEqual(['long'])
  })

  it('flags a non-empty value that leaves no answer and keeps empty values empty', () => {
    expect(splitToAnswers('<br>,;', DEFAULT_SPLIT_PRESETS)).toEqual({ value: '', answers: [], flags: ['html', 'empty'] })
    expect(splitToAnswers('', DEFAULT_SPLIT_PRESETS)).toEqual({ value: '', answers: [], flags: [] })
  })
})

describe('answers backup', () => {
  const backup = buildAnswersBackup({
    noteTypeId: 'nt-1', fieldId: 'f-1', fieldName: 'Meaning', originalType: 'text',
    notes: [{ note_id: 'n-1', value: 'a, b' }], now: new Date('2026-10-10T00:00:00Z'),
  })

  it('round-trips through JSON for the same field', () => {
    const parsed = parseAnswersBackup(JSON.parse(JSON.stringify(backup)), { noteTypeId: 'nt-1', fieldId: 'f-1' })
    expect(parsed).toEqual({ ok: true, backup })
  })

  it('refuses another field or a malformed file', () => {
    expect(parseAnswersBackup(backup, { noteTypeId: 'nt-1', fieldId: 'f-2' })).toEqual({ ok: false, error: 'other_field' })
    expect(parseAnswersBackup({ ...backup, original_type: 'image' }, { noteTypeId: 'nt-1', fieldId: 'f-1' })).toEqual({ ok: false, error: 'invalid' })
    expect(parseAnswersBackup({ ...backup, notes: [{ note_id: 1 }] }, { noteTypeId: 'nt-1', fieldId: 'f-1' })).toEqual({ ok: false, error: 'invalid' })
    expect(parseAnswersBackup('nope', { noteTypeId: 'nt-1', fieldId: 'f-1' })).toEqual({ ok: false, error: 'invalid' })
  })
})
