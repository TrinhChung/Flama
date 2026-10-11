export interface TemplateReleaseDto {
  id: string
  template_id: string
  version_id: string
  sequence_no: number
  version_label: string
  parent_release_id: string | null
  publish_mode: 'manual' | 'automatic'
  idempotency_key?: string | null
  change_note: string | null
  created_by_user_id: number | null
  published_at: string
}

export interface TemplatePublicationDto {
  template_id: string
  auto_publish_enabled: boolean
  current_release: TemplateReleaseDto | null
  current_version_id: string
  has_unpublished_changes: boolean
  last_auto_published_at: string | null
  last_auto_publish_error: string | null
}

export interface TemplateReleasesResponse {
  template_id: string
  source_template_id: string
  items: TemplateReleaseDto[]
  has_more: boolean
}

export interface PublishTemplateReleaseBody {
  version_label: string
  change_note?: string
  expected_current_release_id: string | null
  expected_current_version_id: string | null
}

export interface PublishReleaseResponse {
  release: TemplateReleaseDto
  replayed: boolean
}

export interface ConflictContent {
  base: string | unknown
  upstream: string | unknown
  local: string | unknown
}

export interface PendingUpdateDto {
  id: string
  from_release_id: string
  to_release_id: string
  expected_local_version_id: string
  status: 'ready' | 'has_conflict'
  conflicts: Record<string, ConflictContent>
  idempotency_key?: string | null
  mode: 'manual' | 'automatic'
}

export interface TemplateSubscriptionDto {
  id: string
  user_id: number
  source_template_id: string
  local_template_id: string
  template_id: string
  current_version_id: string
  applied_release_id: string
  applied_release: TemplateReleaseDto | null
  current_release: TemplateReleaseDto | null
  update_available: boolean
  auto_update_enabled: boolean
  pending_update_json: PendingUpdateDto | null
  last_sync_status: 'synced' | 'conflict' | 'ready' | string
  last_synced_at: string | null
  created_at: string
  updated_at: string
}

export type ConflictResolutionMode = 'keep_mine' | 'keep_upstream' | 'manual'

export interface ConflictResolution {
  mode: ConflictResolutionMode
  value?: string
}

export interface ApplyTemplateUpdateBody {
  preparation_id: string
  resolutions?: Record<string, ConflictResolution>
}
