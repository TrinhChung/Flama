import { describe, expect, it } from 'vitest'
import type { DeckNode } from '../types'
import { flattenVisibleDecks } from './flattenDeckTree'

function deck(id: number, children: DeckNode[] = []): DeckNode {
  return {
    id,
    parent_id: null,
    name: `Deck ${id}`,
    depth: 0,
    study_url: `/study?deck_id=${id}`,
    counts: { new: 0, learning: 0, due: 0 },
    move_alias: `deck-${id}`,
    share_url: '',
    children,
  }
}

describe('flattenVisibleDecks', () => {
  const tree = [deck(1, [deck(2, [deck(3)]), deck(4)]), deck(5)]

  it('lists only roots when nothing is expanded', () => {
    expect(flattenVisibleDecks(tree, new Set()).map((node) => node.id)).toEqual([1, 5])
  })

  it('walks expanded branches depth-first and skips collapsed descendants', () => {
    expect(flattenVisibleDecks(tree, new Set([1])).map((node) => node.id)).toEqual([1, 2, 4, 5])
    expect(flattenVisibleDecks(tree, new Set([1, 2])).map((node) => node.id)).toEqual([1, 2, 3, 4, 5])
  })

  it('hides an expanded child whose parent is collapsed', () => {
    expect(flattenVisibleDecks(tree, new Set([2])).map((node) => node.id)).toEqual([1, 5])
  })
})
