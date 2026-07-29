export type Rating = 'again' | 'hard' | 'good' | 'easy'

export type FieldDef = {
  id?: string
  name: string
  field_type: string
  required?: boolean
  position?: number
}

export type StudyArtifactRef = {
  id: string
  version: string
  url: string
  visibility: 'public' | 'private'
}

export type StudyManifest = {
  schema_version: 'study-manifest.v1'
  render_contract: 'client_v1'
  renderer_abi?: string
  selection_id?: string | null
  card_id: string | null
  note_id?: string | null
  template_id?: string | null
  template_ref?: StudyArtifactRef
  content_ref?: StudyArtifactRef
  intervals_ref?: { url: string }
  review_state_version?: string
  new_count?: number
  learn_count?: number
  due_count?: number
  session_state?: string
  next_due_at?: string | null
  message?: string
  can_edit_card?: boolean
  save_card_url?: string | null
  load_note_url?: string | null
  deck_id?: number | null
  tags?: string[]
  note_type_name?: string
}

export type StudyTemplateArtifact = {
  schema_version: 'study-template.v1'
  renderer_abi: string
  id: string
  version: string
  front_source: string
  back_source: string
  front_inline_scripts: string[]
  back_inline_scripts: string[]
  shared_css: string
  field_defs: FieldDef[]
}

export type StudyMediaArtifact = {
  id: string
  field_name: string
  filename: string
  mime_type: string
  sha256: string
  proxy_url: string
}

export type StudyContentArtifact = {
  schema_version: 'study-content.v1'
  renderer_abi: string
  id: string
  note_id: string
  version: string
  field_values: Record<string, string>
  render_context: Record<string, unknown>
  media: StudyMediaArtifact[]
}

export type IntervalsPreview = Record<Rating, { label?: string }>

export type StudyIntervalsResponse = {
  schema_version: 'study-intervals.v1'
  selection_id: string
  card_id: string
  review_state_version: string
  intervals_preview: IntervalsPreview
}

export type StudyAnswerResponse = {
  success: boolean
  next_manifest: StudyManifest
}

export type RendererSidePayload = {
  html: string
  allowed_media_urls: string[]
  allowed_audio_urls: string[]
  allowed_audio_asset_ids: string[]
  template_key: string
  shell_key: string
  has_inline_script: boolean
  supports_live_patch: boolean
}
