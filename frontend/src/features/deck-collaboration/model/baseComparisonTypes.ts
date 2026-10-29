export type BaseOverrideComparison = {
  id: string
  note_id: string
  field_identity: string
  field_name: string
  operation: 'set' | 'remove'
  personal_value: unknown
  base_value: unknown
  base_exists: boolean
  base_changed: boolean
  current_base_hash: string
  note_deleted: boolean
  field_deleted: boolean
}

export type BaseOverrideComparisonPage = {
  content_model: 'published_base'
  install_id: string
  deck_title: string
  overlay_revision: number
  content_revision: number
  items: BaseOverrideComparison[]
  next_cursor: string | null
}
