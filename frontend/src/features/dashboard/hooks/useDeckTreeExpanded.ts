import { useState, useCallback, useEffect } from 'react'
import type { DeckNode } from '../types'

export const DASHBOARD_EXPANDED_DECKS_STORAGE_KEY = 'flama_dashboard_expanded_deck_ids'

export function getInitialExpandedDeckIds(): Set<number> {
  try {
    const raw = typeof window !== 'undefined' ? localStorage.getItem(DASHBOARD_EXPANDED_DECKS_STORAGE_KEY) : null
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        return new Set(parsed.filter((id): id is number => typeof id === 'number'))
      }
    }
  } catch {
    // Ignore JSON parse or storage access errors
  }
  return new Set<number>()
}

export function persistExpandedDeckIds(ids: Set<number>): void {
  try {
    if (typeof window !== 'undefined') {
      localStorage.setItem(
        DASHBOARD_EXPANDED_DECKS_STORAGE_KEY,
        JSON.stringify(Array.from(ids)),
      )
    }
  } catch {
    // Ignore storage quota / access errors
  }
}

export function useDeckTreeExpanded(nodes?: DeckNode[], selectedDeckId?: number | null) {
  const [expandedDeckIds, setExpandedDeckIds] = useState<Set<number>>(getInitialExpandedDeckIds)

  const isExpanded = useCallback(
    (deckId: number) => expandedDeckIds.has(deckId),
    [expandedDeckIds],
  )

  const toggleExpand = useCallback((deckId: number) => {
    setExpandedDeckIds((prev) => {
      const next = new Set(prev)
      if (next.has(deckId)) {
        next.delete(deckId)
      } else {
        next.add(deckId)
      }
      persistExpandedDeckIds(next)
      return next
    })
  }, [])

  // Auto-expand ancestor path of selectedDeckId if provided
  useEffect(() => {
    if (!selectedDeckId || !nodes || nodes.length === 0) return

    const findAncestors = (
      tree: DeckNode[],
      targetId: number,
      ancestors: number[] = [],
    ): number[] | null => {
      for (const node of tree) {
        if (node.id === targetId) return ancestors
        if (node.children.length > 0) {
          const found = findAncestors(node.children, targetId, [...ancestors, node.id])
          if (found) return found
        }
      }
      return null
    }

    const ancestorIds = findAncestors(nodes, selectedDeckId)
    if (ancestorIds && ancestorIds.length > 0) {
      setExpandedDeckIds((prev) => {
        let changed = false
        const next = new Set(prev)
        for (const aid of ancestorIds) {
          if (!next.has(aid)) {
            next.add(aid)
            changed = true
          }
        }
        if (changed) {
          persistExpandedDeckIds(next)
          return next
        }
        return prev
      })
    }
  }, [nodes, selectedDeckId])

  return {
    isExpanded,
    toggleExpand,
    expandedDeckIds,
  }
}
