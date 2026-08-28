export type DiffChangeType =
  | 'added'
  | 'modified'
  | 'removed'
  | 'conflict'

export type DiffChangeFilter = 'all' | DiffChangeType

export type DiffFilters = {
  query: string
  changeType: DiffChangeFilter
}

export type DiffSummary = {
  total: number
  entities: number
  notes?: number
  fields?: number
  added: number
  modified: number
  removed: number
  conflicts: number
}

export type DiffValue = unknown

export type DiffItem = {
  id: string
  change_type: DiffChangeType
  entity_kind: string
  entity_id: string
  operation?: string | null
  deck_id?: string | number | null
  deck_path?: string | null
  note_id?: string | null
  note_label?: string | null
  field_def_id?: string | null
  field_name?: string | null
  before_preview?: DiffValue
  after_preview?: DiffValue
  before_value?: DiffValue
  after_value?: DiffValue
  is_truncated?: boolean
  conflict_id?: string | null
}

export type CursorDiffPage = {
  snapshot_revision?: string | number | null
  summary: DiffSummary
  items: DiffItem[]
  next_cursor: string | null
}

export type CursorPageMeta = {
  limit: number
  has_more: boolean
  next_cursor: string | null
  filtered_item_count?: number
  revision?: number
}

export type ReleaseRef = {
  id: string
  sequence_no?: number | null
  version_label: string
  changelog?: string | null
  published_at?: string | null
  change_count?: number
}

export type ReleasePreviewPage = CursorDiffPage & {
  deck_item_id: string
  deck_title?: string | null
  base_release: ReleaseRef | null
  suggested_version?: string | null
  working_revision?: number | null
  has_changes: boolean
}

export type DeckRelease = ReleaseRef & {
  deck_item_id: string
  status: 'building' | 'published' | 'failed'
  publish_mode?: 'manual' | 'automatic' | null
  parent_release_id?: string | null
  source_working_revision?: number | null
  manifest_hash?: string | null
  entity_count?: number
  added_count?: number
  modified_count?: number
  removed_count?: number
  created_by_user_id?: number | null
  created_at?: string | null
  summary?: DiffSummary
}

export type AutoPublishStatus = {
  deck_item_id: string
  auto_publish_enabled: boolean
  last_auto_published_at?: string | null
  last_auto_publish_error?: string | null
  current_release?: DeckRelease | null
  pending_changes_count: number
  working_revision: number
}

export type DeckReleaseList = {
  items: DeckRelease[]
  next_cursor?: string | null
}

export type CreateDeckReleaseInput = {
  version_label: string
  changelog: string
  expected_current_release_id?: string | null
  expected_working_revision?: number | null
}

export type InstalledDeckSettings = {
  install_id: string
  deck_item_id?: string | null
  auto_update_enabled: boolean
  sync_mode: string
  last_auto_updated_at?: string | null
  last_sync_status?: string | null
  pending_conflict_count: number
  version_mode?: string | null
}

export type InstalledDeckRef = {
  id: string
  deck_item_id?: string | null
  title?: string | null
  version_mode?: string | null
  auto_update_enabled?: boolean
  sync_mode?: string | null
  last_auto_updated_at?: string | null
  pending_conflict_count?: number
  active_rebase_id?: string | null
  applied_release: ReleaseRef | null
  available_release?: ReleaseRef | null
  overlay_revision?: string | number | null
}

export type InstalledDeckUpdates = {
  installation: InstalledDeckRef
  items: ReleaseRef[]
  update_available: boolean
  unread_update: boolean
  change_count: number
  auto_update_enabled?: boolean
  sync_mode?: string | null
  last_auto_updated_at?: string | null
  pending_conflict_count?: number
  active_rebase_id?: string | null
}

export type InstalledDeckUpdatePage = CursorDiffPage & {
  installation: InstalledDeckRef
  from_release: ReleaseRef | null
  target_release: ReleaseRef
  changelog?: string | null
  already_applied?: boolean
}

export type UpdateConflictResolution = 'keep_mine' | 'keep_upstream'

export type UpdateConflict = {
  id: string
  change_id?: string | null
  note_label?: string | null
  field_name?: string | null
  base_value?: DiffValue
  local_value?: DiffValue
  upstream_value?: DiffValue
  resolution_mode?: UpdateConflictResolution | 'manual' | null
  resolved_value?: DiffValue
  resolved_at?: string | null
}

export type RebaseConflictPageMeta = {
  limit: number
  has_more: boolean
  next_after_id: string | null
}

export type InstalledUpdateConflictPage = {
  rebase_id: string
  status: PreparedInstalledUpdate['status']
  conflict_count: number
  resolved_conflict_count: number
  items: UpdateConflict[]
  page: RebaseConflictPageMeta
}

export type PreparedInstalledUpdate = {
  rebase_id: string
  status: 'ready' | 'conflicts' | 'applied'
  mode?: 'manual' | 'automatic' | null
  conflict_count: number
  resolved_conflict_count: number
  conflicts: UpdateConflict[]
  conflict_page?: RebaseConflictPageMeta
  expected_overlay_revision?: string | number | null
}

export type ApplyInstalledUpdateInput = {
  expected_applied_release_id?: string | null
  expected_overlay_revision?: string | number | null
  idempotency_key: string
}

export type AppliedInstalledUpdate = {
  status: 'applied'
  applied_release: ReleaseRef
  kept_local_count?: number
  accepted_upstream_count?: number
}

export type ChangeRequestStatus =
  | 'needs_sync'
  | 'draft'
  | 'has_conflict'
  | 'pending_review'
  | 'rejected'
  | 'merged'

export type ChangeRequestActor = {
  id: number
  username: string
}

export type ChangeRequestConflict = {
  id: string
  item_id?: string | null
  conflict_type: string
  source_ref_id?: string | null
  upstream_value?: unknown
  local_value?: unknown
  base_value?: unknown
  resolution_mode?: 'keep_mine' | 'keep_upstream' | 'manual' | null
  resolved_value?: unknown
  resolved_at?: string | null
}

export type ChangeRequestItem = {
  id: string
  change_type: string
  source_ref_id?: string | null
  local_ref_id?: string | null
  path_key?: string | null
  path_label?: string | null
  before_value?: unknown
  after_value?: unknown
  effective_after_value?: unknown
  metadata: Record<string, unknown>
  is_conflict: boolean
  conflict?: ChangeRequestConflict | null
}

export type LocalChangeItem = Omit<
  ChangeRequestItem,
  'id' | 'metadata' | 'is_conflict' | 'conflict' | 'effective_after_value'
> & {
  id?: string
  metadata_json?: Record<string, unknown>
}

export type DeckChangeRequest = {
  id: string
  deck_install_id?: string | null
  deck_item_id: string
  local_deck_id?: number | null
  source_deck_id?: number | null
  source_note_type_id?: string | null
  status: ChangeRequestStatus
  base_release_id?: string | null
  revision: number
  title: string
  description?: string | null
  overlay_fingerprint?: string | null
  last_sync_status?: string | null
  last_synced_at?: string | null
  submitted_at?: string | null
  reviewed_at?: string | null
  merged_at?: string | null
  review_comment?: string | null
  created_at?: string | null
  updated_at?: string | null
  requester: ChangeRequestActor
  owner: ChangeRequestActor
  reviewed_by?: ChangeRequestActor | null
  deck_item?: { id: string; title: string } | null
  item_count: number
  unresolved_conflict_count: number
  change_counts: Record<string, number>
  can_submit: boolean
  can_resolve: boolean
  can_review: boolean
  items: ChangeRequestItem[]
  conflicts: ChangeRequestConflict[]
  page?: CursorPageMeta
}

export type ChangeRequestSummary = Pick<
  DeckChangeRequest,
  | 'id'
  | 'deck_item_id'
  | 'title'
  | 'status'
  | 'base_release_id'
  | 'revision'
  | 'requester'
  | 'deck_item'
  | 'item_count'
  | 'unresolved_conflict_count'
  | 'submitted_at'
  | 'updated_at'
>

export type LocalChangesPreview = {
  deck_install_id: string
  deck_item_id: string
  overlay_fingerprint: string
  item_count: number
  change_counts: Record<string, number>
  items: LocalChangeItem[]
  page?: CursorPageMeta
}

export type ChangeRequestInbox = {
  items: ChangeRequestSummary[]
  page?: CursorPageMeta
}

export type ConflictResolutionInput = {
  resolution_mode: 'keep_mine' | 'keep_upstream' | 'manual'
  resolved_value?: unknown
}
