export type CardTemplateItem = {
  id: string
  note_type_id: string
  name: string
  front_html: string
  back_html: string
  shared_css: string
  position: number
  is_default: boolean
  updated_at: string | null
  current_version_id?: string | null
}

export type TemplateVersionOrigin = 'backfill' | 'create' | 'edit' | 'reset' | 'restore' | 'apply' | 'fork'

export type TemplateVersionSummary = {
  id: string
  template_id: string
  version_no: number
  content_hash: string
  change_note: string
  origin: TemplateVersionOrigin
  created_at: string
  created_by: { id: number; username: string } | null
  is_current: boolean
}

export type TemplateVersionDetail = TemplateVersionSummary & {
  front_html: string
  back_html: string
  shared_css: string
  input_schema: unknown[]
}

export type TemplateVersionList = {
  schema_version: 'template-versions.v2'
  template_id: string
  current_version_id: string | null
  items: TemplateVersionSummary[]
}

export type CardTemplateWithNoteCount = CardTemplateItem & { note_count: number }

export type NoteTypeTemplatesResponse = { items: CardTemplateWithNoteCount[] }

export type CardTypeContextKind = 'owned' | 'installed_source' | 'installed_local'

export type DeckCardType = {
  composition_id: string
  note_type_id: string
  note_type_name?: string
  template_id: string
  template_name: string
  is_default: boolean
  context_kind?: CardTypeContextKind
  install_id?: string | null
}

export type DeckCardTypeGroup = {
  note_type_id: string
  note_type_name: string
  compositions: DeckCardType[]
}

export type DeckCardTypesResponse = {
  schema_version: 'study-scope-compositions.v2'
  scope_type: 'deck'
  scope_id: string
  cardinality: 'zero' | 'one' | 'many'
  default_composition_id: string | null
  groups: DeckCardTypeGroup[]
  compositions: DeckCardType[]
  note_counts: Record<string, number>
}
