import type {
  SchedulerCardState,
  SchedulerOptions,
} from './scheduler/types'
import type { ReviewRating } from './interactions/reviewInteraction'

export type Rating = ReviewRating

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

export type StudyIntervalsRef = {
  state_version: string
  url: string
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
  intervals_ref?: StudyIntervalsRef
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

export type StudySessionPolicy = {
  algorithm_key: string
  algorithm_version: string
  config_schema_version: string
  config_hash: string
  timezone: string
  config: SchedulerOptions
  preset_id: number | null
}

export type AppliedComposition = {
  composition_id: string
  mode_key: string
  note_type_id: string
  template_id: string
  template_name: string
  is_default: boolean
  interaction_key: string
  trigger_key: string
  trigger_contract_version: string
  algorithm_key: string
  algorithm_version: string
}

export type StudySessionCard = {
  card_id: string
  note_id: string
  template_id: string
  source_deck_id: number | null
  local_deck_id: number | null
  note_type_id: string
  created_at: string
  policy_key: string
  template_key: string
  content_key: string
  composition_id?: string | null
  base_revision: number
  base_state_hash: string
  state: SchedulerCardState
  can_edit_card: boolean
}

export type StudySessionSnapshot = {
  schema_version: 'study-session.v2'
  session_id: string
  user_id: number
  session_token: string
  snapshot_hash: string
  scope: { type: 'deck' | 'note_type'; id: string; name: string }
  server_now_utc: string
  expires_at: string
  timezone: string
  day_boundary_hour_local: number
  learn_ahead_seconds: number
  scheduler_algorithm: string
  algorithm_version: string
  queue_contract_version: string
  policies: Record<string, StudySessionPolicy>
  cards: StudySessionCard[]
  templates: Record<string, StudyTemplateArtifact>
  contents: Record<string, StudyContentArtifact>
  compositions?: Record<string, AppliedComposition>
}

export type StudySessionEvent = {
  event_id: string
  sequence: number
  card_id: string
  rating: Rating
  action_key: `review.${Rating}`
  trigger_key: `scheduler.review.${Rating}`
  trigger_contract_version: '1'
  policy_key: string
  scheduler_offset_ms: number
  duration_ms: number
}

export type StudySessionCommitReceipt = {
  schema_version: 'study-commit-receipt.v1'
  success: boolean
  session_id: string
  commit_id: string
  commit_reason: 'auto_finish' | 'manual_exit' | 'page_exit' | 'rollover'
  applied_event_count: number
  updated_cards: Array<{
    card_id: string
    revision: number
    state: SchedulerCardState
  }>
  rating_counts: Record<Rating, number>
  committed_at: string
}

export type StudySessionStatus = {
  schema_version: 'study-session-status.v1'
  session_id: string
  status: 'open' | 'committed' | 'expired'
  expires_at: string
  committed_at: string | null
}

export type StudyCardEditResponse = {
  success: boolean
  card_id: string
  note_id: string
  deck_id?: number | null
  tags?: string[]
  field_values: Record<string, string>
  content_ref?: StudyArtifactRef
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
