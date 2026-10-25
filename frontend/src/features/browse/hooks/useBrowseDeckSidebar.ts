import { useState, useMemo, useCallback, useEffect } from 'react'
import type { BrowseDeck } from '../types'

export interface BrowseDeckTreeNode {
  deck: BrowseDeck
  children: BrowseDeckTreeNode[]
}

const EMPTY_DECKS: BrowseDeck[] = []

export function useBrowseDeckSidebar(
  decks: BrowseDeck[] = EMPTY_DECKS,
  selectedDeckId: number | null,
  deckSearch: string,
  setVisibleDeckIds: (ids: number[]) => void,
) {
  const [expandedNodes, setExpandedNodes] = useState<Record<number, boolean>>({})
  const toggleExpand = useCallback((id: number) => setExpandedNodes((previous) => ({ ...previous, [id]: !previous[id] })), [])
  const byId = useMemo(() => new Map(decks.map((deck) => [deck.id, deck])), [decks])

  useEffect(() => {
    const ancestors: number[] = []
    const seen = new Set<number>()
    let parent = selectedDeckId === null ? null : byId.get(selectedDeckId)?.parent_id
    while (parent != null && !seen.has(parent)) {
      seen.add(parent)
      ancestors.push(parent)
      parent = byId.get(parent)?.parent_id
    }
    setExpandedNodes((previous) => ancestors.every((id) => previous[id])
      ? previous : { ...previous, ...Object.fromEntries(ancestors.map((id) => [id, true])) })
  }, [selectedDeckId, byId])

  const searching = Boolean(deckSearch.trim())
  const treeRoots = useMemo(() => {
    const allowed = new Set<number>()
    const query = deckSearch.trim().toLowerCase()
    decks.forEach((deck) => {
      if (!query) { allowed.add(deck.id); return }
      if (!deck.name.toLowerCase().includes(query)) return
      let current: number | null | undefined = deck.id
      const seen = new Set<number>()
      while (current != null && !seen.has(current)) {
        seen.add(current)
        allowed.add(current)
        current = byId.get(current)?.parent_id
      }
    })
    const nodes = new Map(decks.filter((deck) => allowed.has(deck.id)).map((deck) => [deck.id, { deck, children: [] } as BrowseDeckTreeNode]))
    const roots: BrowseDeckTreeNode[] = []
    nodes.forEach((node) => {
      const parent = node.deck.parent_id == null ? null : nodes.get(node.deck.parent_id)
      if (parent) parent.children.push(node)
      else roots.push(node)
    })
    const sort = (items: BrowseDeckTreeNode[]) => {
      items.sort((a, b) => a.deck.name.localeCompare(b.deck.name, 'vi'))
      items.forEach((node) => sort(node.children))
    }
    sort(roots)
    return roots
  }, [decks, byId, deckSearch])

  const visibleKey = useMemo(() => {
    const ids: number[] = []
    const visit = (nodes: BrowseDeckTreeNode[]) => nodes.forEach((node) => {
      ids.push(node.deck.id)
      if (searching || expandedNodes[node.deck.id]) visit(node.children)
    })
    visit(treeRoots)
    return ids.sort((a, b) => a - b).join(',')
  }, [treeRoots, searching, expandedNodes])
  useEffect(() => {
    setVisibleDeckIds(visibleKey ? visibleKey.split(',').map(Number) : [])
  }, [visibleKey, setVisibleDeckIds])
  useEffect(() => () => setVisibleDeckIds([]), [setVisibleDeckIds])

  return { treeRoots, expandedNodes, toggleExpand, searching }
}
