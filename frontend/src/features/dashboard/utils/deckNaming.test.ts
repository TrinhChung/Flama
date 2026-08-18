import { describe, expect, it } from 'vitest'
import { suggestNextDeckName } from './deckNaming'

describe('suggestNextDeckName', () => {
  it('increments trailing lesson numbers like N1:Bài 1 -> N1:Bài 2', () => {
    expect(suggestNextDeckName('N1:Bài 1')).toBe('N1:Bài 2')
    expect(suggestNextDeckName('N1::Bài 1')).toBe('N1::Bài 2')
    expect(suggestNextDeckName('N1: Bài 1')).toBe('N1: Bài 2')
    expect(suggestNextDeckName('Bài 1')).toBe('Bài 2')
  })

  it('preserves zero-padding when incrementing', () => {
    expect(suggestNextDeckName('Bài 01')).toBe('Bài 02')
    expect(suggestNextDeckName('Bài 09')).toBe('Bài 10')
    expect(suggestNextDeckName('Lesson 009')).toBe('Lesson 010')
  })

  it('increments the last number sequence when multiple numbers are present', () => {
    expect(suggestNextDeckName('JLPT N3 - Bài 5')).toBe('JLPT N3 - Bài 6')
    expect(suggestNextDeckName('N2 - Part 1')).toBe('N2 - Part 2')
    expect(suggestNextDeckName('Minna no Nihongo 24')).toBe('Minna no Nihongo 25')
  })

  it('appends 2 when no numbers are in the deck name', () => {
    expect(suggestNextDeckName('Kanji')).toBe('Kanji 2')
    expect(suggestNextDeckName('Từ vựng IT')).toBe('Từ vựng IT 2')
  })

  it('skips existing sibling deck names to find the next available number', () => {
    const existing = ['N1:Bài 1', 'N1:Bài 2', 'N1:Bài 3']
    expect(suggestNextDeckName('N1:Bài 1', existing)).toBe('N1:Bài 4')
    expect(suggestNextDeckName('N1:Bài 2', existing)).toBe('N1:Bài 4')
    expect(suggestNextDeckName('N1:Bài 3', existing)).toBe('N1:Bài 4')
  })

  it('fills gaps in existing sibling numbers if a gap exists after the reference deck', () => {
    const existingWithGap = ['N1:Bài 1', 'N1:Bài 3']
    expect(suggestNextDeckName('N1:Bài 1', existingWithGap)).toBe('N1:Bài 2')
  })

  it('avoids collisions when no initial numbers were present', () => {
    const existing = ['Kanji', 'Kanji 2']
    expect(suggestNextDeckName('Kanji', existing)).toBe('Kanji 3')
  })

  it('returns empty string for null, undefined or whitespace-only names', () => {
    expect(suggestNextDeckName(null)).toBe('')
    expect(suggestNextDeckName(undefined)).toBe('')
    expect(suggestNextDeckName('')).toBe('')
    expect(suggestNextDeckName('   ')).toBe('')
  })
})
