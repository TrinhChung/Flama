export type NoteTypeItem = {
  id: string
  name: string
  description?: string | null
  publish_status?: string
  is_marketplace_install?: boolean
  field_count?: number
  template_count?: number
  version?: string | null
  created_at?: string | null
  updated_at?: string | null
  /** Older callers may still supply a full definition. The manager does not fetch it. */
  field_defs?: Array<{ id: string; name: string }>
  templates?: Array<{ id: string; name: string }>
}

export type NoteTypesResponse = { items: NoteTypeItem[] }
