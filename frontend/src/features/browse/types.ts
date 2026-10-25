/**
 * Browse API contract. Unions and limits mirror the backend validation in
 * app/services/browse_card_service.py and app/validators/flashcard_input.py,
 * so a value the backend rejects with 400 fails the type check instead.
 */

export const BROWSE_SORT_FIELDS = ['due', 'deck', 'word'] as const
export type BrowseSortBy = (typeof BROWSE_SORT_FIELDS)[number]
export type BrowseSortDir = 'asc' | 'desc'

export const BROWSE_STATUS_FILTERS = ['all', 'new', 'learn', 'due', 'review'] as const
export type BrowseStatusFilter = (typeof BROWSE_STATUS_FILTERS)[number]

export function isBrowseStatusFilter(value: string): value is BrowseStatusFilter {
  return (BROWSE_STATUS_FILTERS as readonly string[]).includes(value)
}

/** `q` is sanitized with max_length=120. */
export const BROWSE_SEARCH_MAX_LENGTH = 120

export type BrowseCardRow = {
  card_id: string
  note_id: string
  deck_id: number | null
  deck_name: string
  word: string
  reading: string
  meaning: string
  tags: string[]
  status: string
  due_label: string
}

export type BrowseCardsResponse = {
  items: BrowseCardRow[]
  page: number
  per_page?: number
  total: number
  pages: number
  has_next: boolean
}

export type BrowseDeck = {
  id: number
  name: string
  /** False on the lightweight tree until its subtree summary has arrived. */
  summary_loaded?: boolean
  parent_id?: number | null
  path?: string
  note_type_id?: string | null
  note_type_name?: string | null
  note_type_ids?: string[]
  note_type_names?: string[]
  has_mixed_note_types?: boolean
  counts?: {
    total?: number
    new?: number
    learn?: number
    due?: number
  }
}

export type NoteFieldType = 'text' | 'richtext' | 'markdown' | 'image' | 'audio' | 'diagram' | 'array'

export type CardDetailField = {
  name: string
  position: number
  required?: boolean
  field_type?: NoteFieldType
}

export type NoteTypeFieldDef = {
  name: string
  position: number
  required?: boolean
  field_type?: NoteFieldType
}

export type NoteTypeSummary = {
  id: string
  name: string
  title?: string
  field_defs?: NoteTypeFieldDef[]
}

export type CardDetailResponse = {
  card: BrowseCardRow
  note: {
    id: string
    note_type_id?: string | null
    note_type_name?: string | null
    deck_id: number
    deck_name: string
    field_values: Record<string, unknown>
    content_revision?: number
    field_schema_revision?: number
    overlay_revision?: number
    /** Present only for logical-overlay clones; the backend rejects deck moves and tag edits for them. */
    deck_install_id?: string
    tags: string[]
  }
  fields: CardDetailField[]
  media_assets?: Array<{
    id: string
    field_name: string
    filename: string
    mime_type: string
    url: string
  }>
  can_upload_media?: boolean
  media_disabled_reason?: string | null
}
