import { describe, expect, it } from 'vitest'
import {
  getDeckFullPath,
  getDeckPathTokens,
  suggestNextDeckName,
  suggestNextDeckPath,
} from './deckNaming'
import type { DeckNode } from '../types'

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

const createTestNode = (
  id: number,
  name: string,
  parentId: number | null = null,
  children: DeckNode[] = [],
): DeckNode => ({
  id,
  parent_id: parentId,
  name,
  depth: 0,
  study_url: `/study?deck_id=${id}`,
  counts: { new: 0, learning: 0, due: 0 },
  move: { alias: `alias-${id}`, token: 't', parent_alias: null, parent_token: null },
  actions: {
    rename: '',
    move: '',
    delete: '',
    reset: '',
    share: '',
  },
  children,
})

describe('getDeckPathTokens and getDeckFullPath', () => {
  const tree: DeckNode[] = [
    createTestNode(1, 'SAA', null, [
      createTestNode(2, 'deck9', 1, [
        createTestNode(3, 'Part 1', 2),
      ]),
    ]),
    createTestNode(4, 'JLPT N2', null),
  ]

  it('returns tokens for root and nested nodes', () => {
    expect(getDeckPathTokens(tree, 1)).toEqual(['SAA'])
    expect(getDeckPathTokens(tree, 2)).toEqual(['SAA', 'deck9'])
    expect(getDeckPathTokens(tree, 3)).toEqual(['SAA', 'deck9', 'Part 1'])
    expect(getDeckPathTokens(tree, 4)).toEqual(['JLPT N2'])
    expect(getDeckPathTokens(tree, 999)).toEqual([])
    expect(getDeckPathTokens(tree, null)).toEqual([])
  })

  it('returns full path joined with ::', () => {
    expect(getDeckFullPath(tree, 1)).toBe('SAA')
    expect(getDeckFullPath(tree, 2)).toBe('SAA::deck9')
    expect(getDeckFullPath(tree, 3)).toBe('SAA::deck9::Part 1')
    expect(getDeckFullPath(tree, null)).toBe('')
  })
})

describe('suggestNextDeckPath', () => {
  const deck1 = createTestNode(11, 'deck1', 1)
  const deck9 = createTestNode(19, 'deck9', 1)
  const saaNode = createTestNode(1, 'SAA', null, [deck1, deck9])
  const emptyRoot = createTestNode(2, 'Kanji', null, [])
  const dashboardDecks = [saaNode, emptyRoot]

  it('returns empty string when no deck is selected', () => {
    expect(suggestNextDeckPath(null, dashboardDecks)).toBe('')
    expect(suggestNextDeckPath(undefined, dashboardDecks)).toBe('')
  })

  it('suggests sibling hierarchical path SAA::deck10 when child deck9 is selected', () => {
    expect(suggestNextDeckPath(deck9, dashboardDecks)).toBe('SAA::deck10')
  })

  it('suggests next child SAA::deck10 when parent deck SAA with children is selected', () => {
    expect(suggestNextDeckPath(saaNode, dashboardDecks)).toBe('SAA::deck10')
  })

  it('suggests next sibling root deck Kanji 2 when empty root deck is selected', () => {
    expect(suggestNextDeckPath(emptyRoot, dashboardDecks)).toBe('Kanji 2')
  })
})

