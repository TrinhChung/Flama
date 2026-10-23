import type { DeckListItem, DeckOption } from '../model/types'

/** Builds `Parent::Child` paths for decks whose API row has no `path`. */
export function toDeckOptions(decks: DeckListItem[]): DeckOption[] {
  const deckMap = new Map<number, DeckListItem>()
  decks.forEach((deck) => deckMap.set(deck.id, deck))

  const buildPath = (deck: DeckListItem): string => {
    const parts = [deck.name]
    let current = deck
    const seen = new Set<number>()
    while (current.parent_id != null && deckMap.has(current.parent_id) && !seen.has(current.parent_id)) {
      seen.add(current.parent_id)
      current = deckMap.get(current.parent_id)!
      parts.unshift(current.name)
    }
    return parts.join('::')
  }

  return decks.map((deck) => ({
    id: deck.id,
    name: deck.name,
    path: deck.path || buildPath(deck),
    parent_id: deck.parent_id,
    notes_count: deck.counts?.total ?? deck.counts?.due ?? 0,
  }))
}
