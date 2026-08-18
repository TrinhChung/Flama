import type { DeckNode } from '../types'

/**
 * Utility for intelligent deck name suggestion and auto-incrementing.
 */

/**
 * Generates the next sequential deck name based on a reference deck name.
 * - If the reference deck has numbers (e.g. "N1:Bài 1", "Lesson 01", "Day 9"), it increments the last number sequence.
 * - Preserves zero-padding if present (e.g. "Bài 09" -> "Bài 10", "Day 01" -> "Day 02").
 * - If no numbers exist (e.g. "Kanji"), it appends " 2".
 * - If existingNames are provided, it avoids collisions with sibling decks by finding the next available number.
 */
export function suggestNextDeckName(
  baseName: string | null | undefined,
  existingNames: string[] = [],
): string {
  if (!baseName || !baseName.trim()) {
    return ''
  }

  const trimmed = baseName.trim()
  const existingSet = new Set(
    existingNames.map((name) => name.trim().toLowerCase()).filter(Boolean),
  )

  const numberMatches = Array.from(trimmed.matchAll(/\d+/g))

  const generateCandidate = (step: number): string => {
    if (numberMatches.length > 0) {
      const lastMatch = numberMatches[numberMatches.length - 1]
      const digitsStr = lastMatch[0]
      const matchIndex = lastMatch.index ?? 0
      const currentNum = parseInt(digitsStr, 10)
      const nextNum = currentNum + step

      const isPadded = digitsStr.length > 1 && digitsStr.startsWith('0')
      const formattedNum = isPadded
        ? String(nextNum).padStart(digitsStr.length, '0')
        : String(nextNum)

      return (
        trimmed.slice(0, matchIndex) +
        formattedNum +
        trimmed.slice(matchIndex + digitsStr.length)
      )
    }

    return step === 1 ? `${trimmed} 2` : `${trimmed} ${step + 1}`
  }

  // Find the first candidate that doesn't collide with existing siblings
  for (let step = 1; step <= 1000; step++) {
    const candidate = generateCandidate(step)
    if (!existingSet.has(candidate.toLowerCase())) {
      return candidate
    }
  }

  return generateCandidate(1)
}

/**
 * Recursively find the path tokens of deck names leading to the given target deck ID.
 */
export function getDeckPathTokens(decks: DeckNode[], targetId: number | null): string[] {
  if (targetId === null) return []
  for (const node of decks) {
    if (node.id === targetId) {
      return [node.name]
    }
    const childPath = getDeckPathTokens(node.children, targetId)
    if (childPath.length > 0) {
      return [node.name, ...childPath]
    }
  }
  return []
}

/**
 * Returns the full hierarchical path string (e.g. "SAA::deck10") for a deck ID.
 */
export function getDeckFullPath(decks: DeckNode[], targetId: number | null): string {
  return getDeckPathTokens(decks, targetId).join('::')
}

/**
 * Intelligent path suggestion for creating a new deck:
 * - If selectedDeck is a child deck (parent_id != null): suggests a sibling within the same parent (e.g. SAA::deck9 -> SAA::deck10).
 * - If selectedDeck is a root deck with children: suggests the next child inside that deck (e.g. SAA [with deck1..9] -> SAA::deck10).
 * - If selectedDeck is a root deck without children: suggests the next root deck (e.g. SAA -> SAA 2).
 * - If selectedDeck is null/undefined: returns empty string.
 */
export function suggestNextDeckPath(
  selectedDeck: DeckNode | null | undefined,
  dashboardDecks: DeckNode[],
): string {
  if (!selectedDeck) {
    return ''
  }

  // Case 1: selectedDeck is a child deck (has a parent)
  if (selectedDeck.parent_id !== null) {
    const parentTokens = getDeckPathTokens(dashboardDecks, selectedDeck.parent_id)
    const parentDeck = dashboardDecks
      .flatMap(function flatten(d): DeckNode[] {
        return [d, ...d.children.flatMap(flatten)]
      })
      .find((d) => d.id === selectedDeck.parent_id)

    const siblingNames = (parentDeck?.children ?? []).map((d) => d.name)
    const nextLeafName = suggestNextDeckName(selectedDeck.name, siblingNames)
    return [...parentTokens, nextLeafName].join('::')
  }

  // Case 2: selectedDeck is a root deck with children -> suggest next child inside this deck
  if (selectedDeck.children && selectedDeck.children.length > 0) {
    const lastChild = selectedDeck.children[selectedDeck.children.length - 1]
    const childrenNames = selectedDeck.children.map((d) => d.name)
    const nextChildName = suggestNextDeckName(lastChild.name, childrenNames)
    return [selectedDeck.name, nextChildName].join('::')
  }

  // Case 3: selectedDeck is a root deck without children -> suggest next sibling root deck
  const rootNames = dashboardDecks.map((d) => d.name)
  return suggestNextDeckName(selectedDeck.name, rootNames)
}
