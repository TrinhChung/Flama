export type GenerateStrokesPayload = {
  text: string
  locale?: string
  format?: 'html' | 'urls' | 'raw'
  deduplicate?: boolean
  max_characters?: number
}

export type StrokeItem = {
  char: string
  hex: string
  url: string
  available: boolean
}

export type GenerateStrokesResponse = {
  locale: string
  characters: string[]
  items: StrokeItem[]
  output: string
  missing_count: number
  missing_characters: string[]
}

export type EstimateBatchStrokesPayload = {
  source_field: string
  target_field: string
  locale?: string
  deck_id?: number | null
  note_ids?: string[]
  card_ids?: string[]
  overwrite?: boolean
  max_characters?: number
}

export type EstimateBatchStrokesResponse = {
  total_notes: number
  notes_to_update: number
  notes_skipped: number
  unique_characters: number
  cached_characters: number
  new_characters: number
  estimated_seconds: number
  estimated_human: string
  is_heavy_task: boolean
  friendly_summary: string
  has_mixed_note_types?: boolean
  error?: string
  code?: string
  note_types?: string[]
}

export type BatchGenerateStrokesPayload = {
  source_field: string
  target_field: string
  locale?: string
  deck_id?: number | null
  note_ids?: string[]
  card_ids?: string[]
  format?: 'html' | 'urls' | 'raw'
  overwrite?: boolean
  max_characters?: number
}

export type BatchGenerateStrokesResponse = {
  total_processed: number
  updated: number
  skipped: number
  missing_characters: string[]
}
