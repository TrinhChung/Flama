import type { DeckNode } from '../types'

/** Depth-first list of the decks currently visible: roots plus children of expanded decks. */
export function flattenVisibleDecks(nodes: DeckNode[], expandedDeckIds: ReadonlySet<number>): DeckNode[] {
  const rows: DeckNode[] = []
  const visit = (list: DeckNode[]) => {
    for (const node of list) {
      rows.push(node)
      if (node.children.length > 0 && expandedDeckIds.has(node.id)) visit(node.children)
    }
  }
  visit(nodes)
  return rows
}
