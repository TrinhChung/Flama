export type CardTemplateItem = {
  id: string
  note_type_id: string | null
  name: string
  front_html: string
  back_html: string
  shared_css: string
  position: number
  is_default: boolean
  updated_at: string | null
  current_version_id?: string | null
}

export type TemplateVersionOrigin =
  | 'backfill'
  | 'create'
  | 'edit'
  | 'reset'
  | 'restore'
  | 'apply'
  | 'fork'
  | 'market_copy'
  | 'update'

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
  application_id?: string
  study_application_id?: string | null
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

export type TemplateInputType = 'text' | 'richtext' | 'markdown' | 'image' | 'audio' | 'diagram' | 'answers'

/** Display options of a typing-answer input (only on `answers` inputs). */
export type TemplateTypingOptions = {
  show_length: boolean
  hints: boolean
}

export type TemplateInputSpec = {
  key: string
  label: string
  type: TemplateInputType
  required: boolean
  typing?: TemplateTypingOptions
}

export type TemplateBindings = Record<string, string | null>

export type TemplateLibraryGroup = 'all' | 'mine' | 'market' | 'standalone' | 'in_use'

export type TemplateLibraryParams = {
  q?: string
  group?: TemplateLibraryGroup
  category?: string
  include_archived?: boolean
  compact?: boolean
  page?: number
  page_size?: number
}

export type TemplateLibraryTemplate = {
  id: string
  owner_user_id: number | null
  name: string
  description: string
  primary_category: string | null
  origin: 'authored' | 'market_copy'
  source_template_id: string | null
  source_version_id: string | null
  current_version_id: string | null
  front_html: string
  back_html: string
  shared_css: string
  input_schema: TemplateInputSpec[]
  archived_at: string | null
  created_at: string | null
  updated_at: string | null
}

export type TemplateApplicationUsage = {
  id: string
  application_id: string
  note_type_id: string
  note_type_name: string
  occurrence_key: string
  display_name: string | null
  position: number
  is_default: boolean
}

export type TemplateLibraryItem = TemplateLibraryTemplate & {
  application_count: number
  note_type_count: number
}

export type TemplateLibraryDetail = TemplateLibraryItem & {
  applications: TemplateApplicationUsage[]
}

export type TemplateLibrarySummary = Omit<TemplateLibraryItem, 'front_html' | 'back_html' | 'shared_css'>

export type TemplateLibraryResponse = {
  schema_version: 'template-library.v2'
  items: TemplateLibrarySummary[]
  pagination?: { page: number; page_size: number; total: number; has_more: boolean }
}

export type TemplateWriteBody = {
  name?: string
  description?: string
  primary_category?: string | null
  front_html?: string
  back_html?: string
  shared_css?: string
  input_schema?: TemplateInputSpec[]
  change_note?: string
  expected_current_version_id?: string | null
}

export type TemplateUpdateResponse = TemplateLibraryTemplate & {
  affected_applications: string[]
}

export type TemplatePreviewBody = {
  front_html?: string
  back_html?: string
  shared_css?: string
  input_schema?: TemplateInputSpec[]
  sample_values?: Record<string, string>
}

export type TemplateLibraryPreview = {
  front_html: string
  back_html: string
  front_renderer_payload: unknown
  back_renderer_payload: unknown
}

export type TemplateBindingWarning = {
  input_key: string
  code: 'INPUT_UNBOUND' | 'INPUT_TYPE_MISMATCH'
  required: boolean
}

export type TemplateApplication = {
  id: string
  application_id: string
  note_type_id: string
  template_id: string
  occurrence_key: string
  status_code: 'ACTIVE' | 'RETIRED'
  display_name: string | null
  position: number
  is_default: boolean
  input_bindings: TemplateBindings
  input_schema: TemplateInputSpec[]
  warnings: TemplateBindingWarning[]
  template: TemplateLibraryTemplate
}

export type TemplateApplicationsResponse = {
  schema_version: 'template-applications.v2'
  items: TemplateApplication[]
}

export type TemplateApplicationPatch = {
  input_bindings?: TemplateBindings
  display_name?: string | null
  position?: number
  is_default?: boolean
}

export type TemplateAttachmentBody = TemplateApplicationPatch & {
  template_id: string
  occurrence_key?: string
}

export type StudyTemplateFieldDef = {
  id: string
  name: string
  field_type: string
  required?: boolean
  position?: number
}

export type StudyTemplateComposition = DeckCardType & {
  mode_key: string
  interaction_key: string
  trigger_key: string
  trigger_contract_version: string
  algorithm_key: string
  algorithm_version: string
}

export type StudyTemplatePreparationEntry = {
  input_schema: TemplateInputSpec[]
  field_defs: StudyTemplateFieldDef[]
  input_bindings: TemplateBindings
  warnings: Array<{ input_key: string; code: string; required: boolean }>
}

export type StudyTemplateInputsResponse = {
  schema_version: 'study-scope-compositions.v2'
  scope_type: 'deck'
  scope_id: string
  cardinality: 'zero' | 'one' | 'many'
  default_composition_id: string | null
  groups: Array<{ note_type_id: string; note_type_name: string; compositions: StudyTemplateComposition[] }>
  compositions: StudyTemplateComposition[]
  note_counts: Record<string, number>
  template_inputs: Record<string, StudyTemplatePreparationEntry>
}

export type StudyTemplatePresetWrite = {
  selected_compositions: string[]
  input_bindings: Record<string, TemplateBindings>
  ask_before_study: boolean
}

export type StudyTemplatePreset = StudyTemplatePresetWrite & {
  preset_id?: string
  deck_id?: string
  stale_compositions: string[]
}
