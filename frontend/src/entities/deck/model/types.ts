/** Deck row returned by `GET /api/browse/decks`. */
export interface DeckListItem {
  id: number
  name: string
  parent_id?: number | null
  path?: string
  counts?: { total?: number; new?: number; learn?: number; due?: number }
}

/** Flattened deck entry consumed by deck pickers such as `DeckSelectionTreeView`. */
export type DeckOption = {
  id: number
  name: string
  path: string
  note_type_id?: string | null
  parent_id?: number | null
  notes_count?: number
}
