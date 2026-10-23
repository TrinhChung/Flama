import { describe, expect, it } from 'vitest'
import {
  answerMask,
  fieldValueToText,
  matchTypedAnswer,
  maxHintCount,
  normalizeTypedAnswer,
  parseAnswerLines,
  splitGraphemes,
} from './typingAnswer'

describe('parseAnswerLines', () => {
  it('reads one accepted answer per line', () => {
    expect(parseAnswerLines('ăn\ndùng bữa')).toEqual(['ăn', 'dùng bữa'])
  })

  it('treats <br> and closing blocks as line breaks and drops other markup', () => {
    expect(parseAnswerLines('<b>ăn</b><br>dùng bữa<div>xơi</div>')).toEqual(['ăn', 'dùng bữa', 'xơi'])
  })

  it('drops sound references and decodes entities after removing tags', () => {
    expect(parseAnswerLines('食べる[sound:taberu.mp3]')).toEqual(['食べる'])
    expect(parseAnswerLines('a &amp; b<br>&lt;b&gt;')).toEqual(['a & b', '<b>'])
  })

  it('trims, collapses whitespace and removes empty or duplicate lines', () => {
    expect(parseAnswerLines('  ăn  \n\n  dùng   bữa \nĂN')).toEqual(['ăn', 'dùng bữa'])
  })

  it('supports native array field values with markup or plain text', () => {
    expect(parseAnswerLines(['ăn', 'dùng bữa'])).toEqual(['ăn', 'dùng bữa'])
    expect(parseAnswerLines(['<b>ăn</b>', 'dùng bữa[sound:test.mp3]'])).toEqual(['ăn', 'dùng bữa'])
    expect(parseAnswerLines([['ăn'], 'dùng bữa'])).toEqual(['ăn', 'dùng bữa'])
  })

  it('returns nothing for empty or non-string values', () => {
    expect(parseAnswerLines('')).toEqual([])
    expect(parseAnswerLines([])).toEqual([])
    expect(parseAnswerLines(['', ' '])).toEqual([])
    expect(parseAnswerLines(undefined)).toEqual([])
    expect(parseAnswerLines('<br>')).toEqual([])
  })
})

describe('matchTypedAnswer', () => {
  const answers = ['ăn', 'dùng bữa', '食べる']

  it('matches any accepted answer and reports its index', () => {
    expect(matchTypedAnswer('dùng bữa', answers)).toBe(1)
    expect(matchTypedAnswer('食べる', answers)).toBe(2)
  })

  it('ignores letter case, surrounding and repeated whitespace', () => {
    expect(matchTypedAnswer('  Dùng   Bữa ', answers)).toBe(1)
    expect(matchTypedAnswer('　食べる　', answers)).toBe(2)
  })

  it('treats composed and decomposed diacritics as the same text', () => {
    const decomposed = 'ăn'
    expect(decomposed).not.toBe('ăn')
    expect(matchTypedAnswer(decomposed, answers)).toBe(0)
  })

  it('requires exact Vietnamese diacritics', () => {
    expect(matchTypedAnswer('an', answers)).toBe(-1)
    expect(matchTypedAnswer('dung bua', answers)).toBe(-1)
  })

  it('keeps katakana, hiragana and kanji distinct', () => {
    expect(matchTypedAnswer('たべる', answers)).toBe(-1)
    expect(matchTypedAnswer('タベル', ['たべる'])).toBe(-1)
  })

  it('keeps punctuation exact and never matches empty input', () => {
    expect(matchTypedAnswer('ăn.', answers)).toBe(-1)
    expect(matchTypedAnswer('   ', answers)).toBe(-1)
    expect(matchTypedAnswer('ăn', [])).toBe(-1)
  })

  it('normalizes the same way for answers and typed text', () => {
    expect(normalizeTypedAnswer(' Ă  N ')).toBe('ă n')
  })
})

describe('answer mask and hints', () => {
  it('counts user-perceived characters', () => {
    expect(splitGraphemes('食べる')).toEqual(['食', 'べ', 'る'])
    expect(splitGraphemes('ăn')).toEqual(['ă', 'n'])
  })

  it('shows spaces as gaps and reveals characters from the left', () => {
    expect(answerMask('dùng bữa', 2)).toEqual([
      { kind: 'char', char: 'd', revealed: true },
      { kind: 'char', char: 'ù', revealed: true },
      { kind: 'char', char: 'n', revealed: false },
      { kind: 'char', char: 'g', revealed: false },
      { kind: 'space' },
      { kind: 'char', char: 'b', revealed: false },
      { kind: 'char', char: 'ữ', revealed: false },
      { kind: 'char', char: 'a', revealed: false },
    ])
  })

  it('stops hints one character short of the answer', () => {
    expect(maxHintCount('食べる')).toBe(2)
    expect(maxHintCount('dùng bữa')).toBe(6)
    expect(maxHintCount('木')).toBe(0)
    expect(maxHintCount('')).toBe(0)
  })
})

describe('fieldValueToText', () => {
  it('keeps line structure for display', () => {
    expect(fieldValueToText('a<br/>b\r\nc')).toBe('a\nb\nc')
  })
})
