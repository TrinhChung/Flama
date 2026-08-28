import { appApi } from '@/app/api'
import { apiRequest } from '@/shared/api/client'
import type {
  AppliedInstalledUpdate,
  ApplyInstalledUpdateInput,
  AutoPublishStatus,
  ChangeRequestInbox,
  ChangeRequestItem,
  ConflictResolutionInput,
  CreateDeckReleaseInput,
  CursorDiffPage,
  DeckChangeRequest,
  DeckRelease,
  DeckReleaseList,
  DiffChangeFilter,
  DiffFilters,
  DiffItem,
  DiffSummary,
  InstalledDeckSettings,
  InstalledDeckUpdatePage,
  InstalledDeckUpdates,
  InstalledUpdateConflictPage,
  LocalChangeItem,
  LocalChangesPreview,
  PreparedInstalledUpdate,
  ReleasePreviewPage,
} from './types'

type ReleaseStatus = DeckRelease['status']

type RawDiffSummary = {
  change_count?: number
  entity_count?: number
  note_count?: number
  field_count?: number
  added_count?: number
  modified_count?: number
  removed_count?: number
  conflict_count?: number
}

type RawDiffItem = {
  id?: string | number | null
  change_key: string
  entity_kind: string
  entity_id: string
  field_def_id?: string | null
  field_name?: string | null
  property_key?: string | null
  operation: 'add' | 'set' | 'remove'
  before_value?: unknown
  after_value?: unknown
  source_deck_id?: string | number | null
}

type RawRelease = {
  id: string
  deck_item_id?: string
  sequence_no?: number | null
  version_label: string
  parent_release_id?: string | null
  status?: string
  source_working_revision?: number | null
  manifest_hash?: string | null
  change_count?: number
  entity_count?: number
  added_count?: number
  modified_count?: number
  removed_count?: number
  changelog?: string | null
  created_by_user_id?: number | null
  created_at?: string | null
  published_at?: string | null
}

type RawReleasePreviewPage = {
  deck_item_id: string
  deck_title?: string | null
  base_release: RawRelease | null
  working_revision?: number | null
  snapshot_revision?: string | number | null
  summary: RawDiffSummary
  items: RawDiffItem[]
  next_cursor: string | null
}

type RawReleaseList = {
  items: RawRelease[]
  next_cursor?: string | null
}

type RawReleaseChanges = {
  snapshot_revision?: string | number | null
  summary: RawDiffSummary
  items: RawDiffItem[]
  next_cursor: string | null
}

type RawInstalledDeckUpdates = {
  install_id: string | number
  deck_item_id?: string | number | null
  version_mode?: string | null
  overlay_revision?: string | number | null
  auto_update_enabled?: boolean
  sync_mode?: string | null
  last_auto_updated_at?: string | null
  last_sync_status?: string | null
  pending_conflict_count?: number
  active_rebase_id?: string | number | null
  applied_release: RawRelease | null
  available_release: RawRelease | null
  update_available: boolean
  unread_update: boolean
  change_count?: number
}

type RawInstalledDeckUpdateDiff = {
  install_id: string | number
  from_release: RawRelease | null
  to_release: RawRelease
  items: RawDiffItem[]
  summary?: RawDiffSummary
  page: {
    limit: number
    has_more: boolean
    next_cursor: string | null
  }
}

type RawUpdateConflict = {
  id: string | number
  change_id?: string | number | null
  change_key?: string | null
  note_label?: string | null
  field_name?: string | null
  property_key?: string | null
  base_value?: unknown
  local_value?: unknown
  upstream_value?: unknown
  resolution_mode?: 'keep_mine' | 'keep_upstream' | 'manual' | null
  resolved_value?: unknown
  resolved_at?: string | null
}

type RawRebaseConflictPage = {
  limit: number
  has_more: boolean
  next_after_id: string | number | null
}

type RawPreparedInstalledUpdate = {
  id: string | number
  status: string
  to_release?: RawRelease | null
  expected_overlay_revision?: string | number | null
  conflict_count?: number
  resolved_conflict_count?: number
  conflicts?: RawUpdateConflict[]
  conflict_page?: RawRebaseConflictPage
}

type RawPreparedInstalledUpdateEnvelope = {
  rebase: RawPreparedInstalledUpdate
}

type RawInstalledUpdateConflictPage = {
  rebase_id: string | number
  status: string
  conflict_count: number
  resolved_conflict_count: number
  items: RawUpdateConflict[]
  page: RawRebaseConflictPage
}

type DiffQuery = {
  cursor?: string | null
  limit?: number
  changeType?: DiffChangeFilter
  query?: string
}

function encodeSegment(value: string) {
  return encodeURIComponent(value)
}

function withDiffQuery(path: string, query: DiffQuery) {
  const search = new URLSearchParams()
  if (query.cursor) search.set('cursor', query.cursor)
  if (query.limit) search.set('limit', String(query.limit))
  if (query.changeType && query.changeType !== 'all') {
    search.set('type', query.changeType)
  }
  if (query.query?.trim()) search.set('q', query.query.trim())
  return search.size ? `${path}?${search.toString()}` : path
}

function normalizeSummary(summary: RawDiffSummary) {
  const total = summary.change_count || 0
  return {
    total,
    entities: summary.entity_count ?? 0,
    notes: summary.note_count,
    fields: summary.field_count,
    added: summary.added_count || 0,
    modified: summary.modified_count || 0,
    removed: summary.removed_count || 0,
    conflicts: summary.conflict_count || 0,
  }
}

function normalizeItem(item: RawDiffItem) {
  const changeType = item.operation === 'add'
    ? 'added'
    : item.operation === 'remove'
      ? 'removed'
      : 'modified'
  return {
    id: String(item.id ?? item.change_key),
    change_type: changeType,
    entity_kind: item.entity_kind,
    entity_id: item.entity_id,
    operation: item.operation,
    deck_id: item.source_deck_id,
    note_id: item.entity_kind === 'note_field' ? item.entity_id : null,
    field_def_id: item.field_def_id,
    field_name: item.field_name ?? item.property_key,
    before_value: item.before_value,
    after_value: item.after_value,
  } as const
}

function normalizeStatus(status?: string): ReleaseStatus {
  if (status === 'building' || status === 'failed') return status
  return 'published'
}

function normalizeRelease(release: RawRelease): DeckRelease {
  return {
    ...release,
    deck_item_id: String(release.deck_item_id || ''),
    status: normalizeStatus(release.status),
  }
}

export function getReleasePreview(
  itemId: string,
  query: DiffQuery,
  signal?: AbortSignal,
): Promise<ReleasePreviewPage> {
  const path = withDiffQuery(
    `/api/marketplace/decks/${encodeSegment(itemId)}/releases/preview`,
    query,
  )
  return apiRequest<RawReleasePreviewPage>(path, { signal }).then((payload) => ({
    deck_item_id: payload.deck_item_id,
    deck_title: payload.deck_title,
    base_release: payload.base_release ? normalizeRelease(payload.base_release) : null,
    working_revision: payload.working_revision,
    snapshot_revision: payload.snapshot_revision,
    summary: normalizeSummary(payload.summary),
    items: payload.items.map(normalizeItem),
    next_cursor: payload.next_cursor,
    has_changes: (payload.summary.change_count || 0) > 0,
  } satisfies ReleasePreviewPage))
}

export function listDeckReleases(
  itemId: string,
  cursor?: string | null,
  signal?: AbortSignal,
) {
  const path = withDiffQuery(
    `/api/marketplace/decks/${encodeSegment(itemId)}/releases`,
    { cursor, limit: 50, query: '' },
  )
  return apiRequest<RawReleaseList>(path, { signal }).then((payload) => ({
    items: payload.items.map(normalizeRelease),
    next_cursor: payload.next_cursor,
  } satisfies DeckReleaseList))
}

export function createDeckRelease(
  itemId: string,
  input: CreateDeckReleaseInput,
  idempotencyKey: string,
) {
  return apiRequest<{ release: RawRelease; replayed: boolean }>(
    `/api/marketplace/decks/${encodeSegment(itemId)}/releases`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(input),
    },
  ).then((payload) => normalizeRelease(payload.release))
}

export function getAutoPublishStatus(
  itemId: string,
  signal?: AbortSignal,
): Promise<AutoPublishStatus> {
  return apiRequest<AutoPublishStatus>(
    `/api/marketplace/decks/${encodeSegment(itemId)}/auto-publish`,
    { signal },
  )
}

export function updateAutoPublishSetting(
  itemId: string,
  autoPublishEnabled: boolean,
): Promise<AutoPublishStatus> {
  return appApi.mutate<AutoPublishStatus>(
    `/api/marketplace/decks/${encodeSegment(itemId)}/auto-publish`,
    'POST',
    { auto_publish_enabled: autoPublishEnabled },
  )
}

export function getReleaseChanges(
  itemId: string,
  releaseId: string,
  query: DiffQuery,
  signal?: AbortSignal,
) {
  const path = withDiffQuery(
    `/api/marketplace/decks/${encodeSegment(itemId)}/releases/${encodeSegment(releaseId)}/changes`,
    query,
  )
  return apiRequest<RawReleaseChanges>(path, { signal }).then((payload) => ({
    snapshot_revision: payload.snapshot_revision,
    summary: normalizeSummary(payload.summary),
    items: payload.items.map(normalizeItem),
    next_cursor: payload.next_cursor,
  } satisfies CursorDiffPage))
}

export function getInstalledDeckUpdates(
  installId: string,
  signal?: AbortSignal,
) {
  return apiRequest<RawInstalledDeckUpdates>(
    `/api/marketplace/installations/${encodeSegment(installId)}/updates`,
    { signal },
  ).then(normalizeInstalledDeckUpdates)
}

function normalizeUpdateConflict(conflict: RawUpdateConflict) {
  return {
    id: String(conflict.id),
    change_id: conflict.change_id === null || conflict.change_id === undefined
      ? conflict.change_key
      : String(conflict.change_id),
    note_label: conflict.note_label,
    field_name: conflict.field_name || conflict.property_key,
    base_value: conflict.base_value,
    local_value: conflict.local_value,
    upstream_value: conflict.upstream_value,
    resolution_mode: conflict.resolution_mode,
    resolved_value: conflict.resolved_value,
    resolved_at: conflict.resolved_at,
  }
}

function normalizeConflictPage(page: RawRebaseConflictPage) {
  return {
    limit: page.limit,
    has_more: page.has_more,
    next_after_id: page.next_after_id === null ? null : String(page.next_after_id),
  }
}

function normalizePreparedInstalledUpdate(
  payload: RawPreparedInstalledUpdate,
): PreparedInstalledUpdate {
  const conflicts = (payload.conflicts || []).map(normalizeUpdateConflict)
  const conflictCount = payload.conflict_count ?? conflicts.length
  const resolvedConflictCount = payload.resolved_conflict_count
    ?? conflicts.filter((conflict) => Boolean(conflict.resolved_at)).length
  return {
    rebase_id: String(payload.id),
    status: payload.status === 'applied'
      ? 'applied'
      : conflictCount > resolvedConflictCount
        ? 'conflicts'
        : 'ready',
    conflict_count: conflictCount,
    resolved_conflict_count: resolvedConflictCount,
    conflicts,
    conflict_page: payload.conflict_page
      ? normalizeConflictPage(payload.conflict_page)
      : undefined,
    expected_overlay_revision: payload.expected_overlay_revision,
  }
}

function normalizeInstalledDeckUpdates(payload: RawInstalledDeckUpdates) {
  const appliedRelease = payload.applied_release
    ? normalizeRelease(payload.applied_release)
    : null
  const availableRelease = payload.available_release
    ? normalizeRelease(payload.available_release)
    : null
  return {
    installation: {
      id: String(payload.install_id),
      deck_item_id: payload.deck_item_id === null || payload.deck_item_id === undefined
        ? null
        : String(payload.deck_item_id),
      version_mode: payload.version_mode,
      auto_update_enabled: payload.auto_update_enabled,
      sync_mode: payload.sync_mode,
      last_auto_updated_at: payload.last_auto_updated_at,
      pending_conflict_count: payload.pending_conflict_count,
      active_rebase_id: payload.active_rebase_id ? String(payload.active_rebase_id) : null,
      applied_release: appliedRelease,
      available_release: availableRelease,
      overlay_revision: payload.overlay_revision,
    },
    items: availableRelease ? [availableRelease] : [],
    update_available: payload.update_available,
    unread_update: payload.unread_update,
    change_count: payload.change_count || availableRelease?.change_count || 0,
    auto_update_enabled: payload.auto_update_enabled,
    sync_mode: payload.sync_mode,
    last_auto_updated_at: payload.last_auto_updated_at,
    pending_conflict_count: payload.pending_conflict_count,
    active_rebase_id: payload.active_rebase_id ? String(payload.active_rebase_id) : null,
  } satisfies InstalledDeckUpdates
}

export function markInstalledDeckUpdateSeen(
  installId: string,
  releaseId: string,
) {
  return appApi.mutate<RawInstalledDeckUpdates>(
    `/api/marketplace/installations/${encodeSegment(installId)}/updates/${encodeSegment(releaseId)}/mark-seen`,
    'POST',
    {},
  ).then(normalizeInstalledDeckUpdates)
}

export function getInstalledDeckUpdate(
  installId: string,
  releaseId: string,
  query: DiffQuery,
  signal?: AbortSignal,
) {
  const path = withDiffQuery(
    `/api/marketplace/installations/${encodeSegment(installId)}/updates/${encodeSegment(releaseId)}/diff`,
    query,
  )
  return apiRequest<RawInstalledDeckUpdateDiff>(path, { signal }).then((payload) => {
    const targetRelease = normalizeRelease(payload.to_release)
    return {
      installation: {
        id: String(payload.install_id),
        applied_release: payload.from_release
          ? normalizeRelease(payload.from_release)
          : null,
        available_release: targetRelease,
      },
      from_release: payload.from_release
        ? normalizeRelease(payload.from_release)
        : null,
      target_release: targetRelease,
      changelog: targetRelease.changelog,
      already_applied: payload.from_release?.id === payload.to_release.id,
      snapshot_revision: payload.to_release.id,
      summary: normalizeSummary(payload.summary || {
        change_count: targetRelease.change_count,
        entity_count: targetRelease.entity_count,
        added_count: targetRelease.added_count,
        modified_count: targetRelease.modified_count,
        removed_count: targetRelease.removed_count,
      }),
      items: payload.items.map(normalizeItem),
      next_cursor: payload.page.has_more ? payload.page.next_cursor : null,
    } satisfies InstalledDeckUpdatePage
  })
}

export function prepareInstalledDeckUpdate(
  installId: string,
  releaseId: string,
  body: {
    expected_applied_release_id?: string | null
    expected_overlay_revision?: string | number | null
    idempotency_key: string
  },
) {
  return appApi.mutate<RawPreparedInstalledUpdateEnvelope>(
    `/api/marketplace/installations/${encodeSegment(installId)}/updates/${encodeSegment(releaseId)}/prepare`,
    'POST',
    body,
  ).then(({ rebase }) => normalizePreparedInstalledUpdate(rebase))
}

export function getInstalledUpdateConflicts(
  rebaseId: string,
  afterId?: string | null,
  limit = 100,
  signal?: AbortSignal,
) {
  const search = new URLSearchParams()
  if (afterId) search.set('after_id', afterId)
  search.set('limit', String(limit))
  return apiRequest<RawInstalledUpdateConflictPage>(
    `/api/marketplace/rebases/${encodeSegment(rebaseId)}/conflicts?${search.toString()}`,
    { signal },
  ).then((payload) => ({
    rebase_id: String(payload.rebase_id),
    status: payload.status === 'applied'
      ? 'applied'
      : payload.conflict_count > payload.resolved_conflict_count
        ? 'conflicts'
        : 'ready',
    conflict_count: payload.conflict_count,
    resolved_conflict_count: payload.resolved_conflict_count,
    items: payload.items.map(normalizeUpdateConflict),
    page: normalizeConflictPage(payload.page),
  } satisfies InstalledUpdateConflictPage))
}

export function applyInstalledDeckUpdate(
  installId: string,
  releaseId: string,
  body: ApplyInstalledUpdateInput,
) {
  return appApi.mutate<RawPreparedInstalledUpdateEnvelope>(
    `/api/marketplace/installations/${encodeSegment(installId)}/updates/${encodeSegment(releaseId)}/apply`,
    'POST',
    body,
  ).then(({ rebase }) => ({
    status: 'applied' as const,
    applied_release: rebase.to_release
      ? normalizeRelease(rebase.to_release)
      : { id: releaseId, version_label: releaseId },
  } satisfies AppliedInstalledUpdate))
}

export function resolveInstalledUpdateConflict(
  rebaseId: string,
  conflictId: string,
  resolutionMode: 'keep_mine' | 'keep_upstream',
) {
  return appApi.mutate<RawPreparedInstalledUpdateEnvelope>(
    `/api/marketplace/rebases/${encodeSegment(rebaseId)}/conflicts/${encodeSegment(conflictId)}/resolve`,
    'POST',
    { resolution_mode: resolutionMode },
  ).then(({ rebase }) => normalizePreparedInstalledUpdate(rebase))
}

export function applyPreparedInstalledUpdate(rebaseId: string) {
  return appApi.mutate<RawPreparedInstalledUpdateEnvelope>(
    `/api/marketplace/rebases/${encodeSegment(rebaseId)}/apply`,
    'POST',
    {},
  ).then(({ rebase }) => {
    if (!rebase.to_release) {
      throw new Error('Máy chủ không trả về release vừa áp dụng.')
    }
    return {
      status: 'applied' as const,
      applied_release: normalizeRelease(rebase.to_release),
    } satisfies AppliedInstalledUpdate
  })
}

export function getInstalledDeckSettings(
  installId: string,
  signal?: AbortSignal,
): Promise<InstalledDeckSettings> {
  return apiRequest<InstalledDeckSettings>(
    `/api/marketplace/installations/${encodeSegment(installId)}/settings`,
    { signal },
  )
}

export function updateInstalledDeckSettings(
  installId: string,
  autoUpdateEnabled: boolean,
): Promise<InstalledDeckUpdates> {
  return appApi.mutate<RawInstalledDeckUpdates>(
    `/api/marketplace/installations/${encodeSegment(installId)}/settings`,
    'POST',
    { auto_update_enabled: autoUpdateEnabled },
  ).then(normalizeInstalledDeckUpdates)
}

export function detachInstalledDeck(
  installId: string,
): Promise<{ install_id: string; version_mode: string; status: string }> {
  return appApi.mutate<{ install_id: string; version_mode: string; status: string }>(
    `/api/marketplace/installations/${encodeSegment(installId)}/detach`,
    'POST',
    {},
  )
}

export function resolveAllInstalledUpdateConflicts(
  rebaseId: string,
  resolutionMode: 'keep_mine' | 'keep_upstream',
) {
  return appApi.mutate<RawPreparedInstalledUpdateEnvelope>(
    `/api/marketplace/rebases/${encodeSegment(rebaseId)}/conflicts/resolve-all`,
    'POST',
    { resolution_mode: resolutionMode },
  ).then(({ rebase }) => normalizePreparedInstalledUpdate(rebase))
}

function contributionChangeType(changeType: string) {
  if (changeType === 'field_def_add') return 'added' as const
  if (changeType === 'note_field_remove' || changeType === 'field_def_disable') {
    return 'removed' as const
  }
  return 'modified' as const
}

function contributionMetadata(item: ChangeRequestItem | LocalChangeItem) {
  return 'metadata' in item ? item.metadata : (item.metadata_json || {})
}

function metadataText(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function contributionItemToDiffItem(
  item: ChangeRequestItem | LocalChangeItem,
  index = 0,
): DiffItem {
  const metadata = contributionMetadata(item)
  const conflict = 'conflict' in item ? item.conflict : null
  const unresolvedConflict = Boolean(
    'is_conflict' in item
    && item.is_conflict
    && (!conflict || !conflict.resolved_at),
  )
  const sourceRef = String(item.source_ref_id || item.local_ref_id || '')
  const entityKind = item.change_type.startsWith('note_field')
    ? 'note_field'
    : 'field_def'
  const fieldName = metadataText(metadata, 'field_name') || item.path_key || item.path_label
  const noteLabel = metadataText(metadata, 'source_note_label')
  const itemId = 'id' in item && item.id
    ? item.id
    : `${item.change_type}:${sourceRef}:${item.path_key || index}`

  return {
    id: String(itemId),
    change_type: unresolvedConflict
      ? 'conflict'
      : contributionChangeType(item.change_type),
    entity_kind: entityKind,
    entity_id: sourceRef || String(itemId),
    operation: item.change_type,
    note_id: entityKind === 'note_field' ? sourceRef : null,
    note_label: noteLabel || item.path_label,
    field_def_id: metadataText(metadata, 'source_field_def_id'),
    field_name: fieldName,
    before_value: item.before_value,
    after_value: 'effective_after_value' in item
      ? item.effective_after_value
      : item.after_value,
    conflict_id: conflict?.id || null,
  }
}

export function summarizeDiffItems(items: DiffItem[]): DiffSummary {
  const entities = new Set<string>()
  const notes = new Set<string>()
  const fields = new Set<string>()
  let added = 0
  let modified = 0
  let removed = 0
  let conflicts = 0

  items.forEach((item) => {
    entities.add(`${item.entity_kind}:${item.entity_id}`)
    if (item.note_id) notes.add(item.note_id)
    if (item.field_def_id || item.field_name) {
      fields.add(String(item.field_def_id || item.field_name))
    }
    if (item.change_type === 'added') added += 1
    else if (item.change_type === 'removed') removed += 1
    else if (item.change_type === 'conflict') conflicts += 1
    else modified += 1
  })

  return {
    total: items.length,
    entities: entities.size,
    notes: notes.size,
    fields: fields.size,
    added,
    modified,
    removed,
    conflicts,
  }
}

export function summarizeChangeRequest(request: DeckChangeRequest): DiffSummary {
  return summarizeContributionCounts(
    request.item_count,
    request.unresolved_conflict_count,
    request.change_counts,
  )
}

export function summarizeLocalChanges(preview: LocalChangesPreview): DiffSummary {
  return summarizeContributionCounts(preview.item_count, 0, preview.change_counts)
}

function summarizeContributionCounts(
  itemCount: number,
  unresolvedConflictCount: number,
  changeCounts: Record<string, number>,
): DiffSummary {
  const count = (changeType: string) => Number(changeCounts[changeType] || 0)
  return {
    total: itemCount,
    entities: itemCount,
    added: count('field_def_add'),
    modified: count('note_field_set')
      + count('field_def_update')
      + count('field_order_update'),
    removed: count('note_field_remove') + count('field_def_disable'),
    conflicts: unresolvedConflictCount,
  }
}

export function filterDiffItems(items: DiffItem[], filters: DiffFilters) {
  const query = filters.query.trim().toLocaleLowerCase('vi-VN')
  return items.filter((item) => {
    if (filters.changeType !== 'all' && item.change_type !== filters.changeType) {
      return false
    }
    if (!query) return true
    const searchable = [
      item.deck_path,
      item.note_label,
      item.note_id,
      item.field_name,
      item.field_def_id,
      item.entity_id,
      item.before_value,
      item.after_value,
    ]
      .map((value) => typeof value === 'string' ? value : JSON.stringify(value) || '')
      .join(' ')
      .toLocaleLowerCase('vi-VN')
    return searchable.includes(query)
  })
}

export function getLocalDeckChanges(
  deckItemId: string,
  query: DiffQuery = {},
  signal?: AbortSignal,
) {
  const path = withDiffQuery(
    `/api/shared/decks/${encodeSegment(deckItemId)}/change-requests/local-changes`,
    query,
  )
  return apiRequest<LocalChangesPreview>(
    path,
    { signal },
  )
}

export function getActiveDeckChangeRequest(
  deckItemId: string,
  query: DiffQuery = {},
  signal?: AbortSignal,
) {
  const path = withDiffQuery(
    `/api/shared/decks/${encodeSegment(deckItemId)}/change-requests/active`,
    query,
  )
  return apiRequest<{ request: DeckChangeRequest | null }>(
    path,
    { signal },
  )
}

export function buildDeckChangeRequestDraft(
  deckItemId: string,
  body: { title: string; description: string },
) {
  return appApi.mutate<DeckChangeRequest>(
    `/api/shared/decks/${encodeSegment(deckItemId)}/change-requests/draft`,
    'POST',
    body,
  )
}

export function syncDeckChangeRequest(deckItemId: string, requestId: string) {
  return appApi.mutate<DeckChangeRequest>(
    `/api/shared/decks/${encodeSegment(deckItemId)}/change-requests/${encodeSegment(requestId)}/sync`,
    'POST',
    {},
  )
}

export function resolveDeckChangeRequestConflict(
  deckItemId: string,
  requestId: string,
  conflictId: string,
  input: ConflictResolutionInput,
) {
  return appApi.mutate<DeckChangeRequest>(
    `/api/shared/decks/${encodeSegment(deckItemId)}/change-requests/${encodeSegment(requestId)}/conflicts/${encodeSegment(conflictId)}/resolve`,
    'POST',
    input,
  )
}

export function submitDeckChangeRequest(deckItemId: string, requestId: string) {
  return appApi.mutate<DeckChangeRequest>(
    `/api/shared/decks/${encodeSegment(deckItemId)}/change-requests/${encodeSegment(requestId)}/submit`,
    'POST',
    {},
  )
}

export function getIncomingDeckChangeRequests(
  deckItemId?: string | null,
  query: { cursor?: string | null; limit?: number } = {},
  signal?: AbortSignal,
) {
  const search = new URLSearchParams()
  if (deckItemId?.trim()) search.set('deck_item_id', deckItemId.trim())
  if (query.cursor) search.set('cursor', query.cursor)
  if (query.limit) search.set('limit', String(query.limit))
  const suffix = search.size ? `?${search.toString()}` : ''
  return apiRequest<ChangeRequestInbox>(
    `/api/change-requests/incoming${suffix}`,
    { signal },
  )
}

export function getDeckChangeRequest(
  requestId: string,
  query: DiffQuery = {},
  signal?: AbortSignal,
) {
  const path = withDiffQuery(
    `/api/change-requests/${encodeSegment(requestId)}`,
    query,
  )
  return apiRequest<DeckChangeRequest>(
    path,
    { signal },
  )
}

export function approveDeckChangeRequest(requestId: string, reviewComment: string) {
  return appApi.mutate<DeckChangeRequest>(
    `/api/change-requests/${encodeSegment(requestId)}/approve`,
    'POST',
    { review_comment: reviewComment },
  )
}

export function rejectDeckChangeRequest(requestId: string, reviewComment: string) {
  return appApi.mutate<DeckChangeRequest>(
    `/api/change-requests/${encodeSegment(requestId)}/reject`,
    'POST',
    { review_comment: reviewComment },
  )
}
