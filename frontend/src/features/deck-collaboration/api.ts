import { apiJson, apiRequest } from '@/shared/api/client'
export { getAutoPublishStatus, updateAutoPublishSetting } from '@/entities/deck-publication'
import type {
  ChangeRequestInbox,
  ConflictResolutionInput,
  ContributionSendSelection,
  CreateDeckReleaseInput,
  CursorDiffPage,
  DeckChangeRequest,
  DeckRelease,
  DeckReleaseList,
  DiffChangeFilter,
  DiffFilters,
  DiffItem,
  DiffSummary,
  LocalChangesPreview,
  ReleasePreviewPage,
  ReviewSelection,
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
  content_model?: 'published_base'
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
    content_model: payload.content_model,
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
  return apiJson<DeckChangeRequest>(
    `/api/shared/decks/${encodeSegment(deckItemId)}/change-requests/draft`,
    'POST',
    body,
  )
}

export function sendDeckContribution(
  deckItemId: string,
  body: {
    title: string
    description: string
    expected_overlay_fingerprint: string
    /** Omit to keep a matching draft's own choice of notes. */
    selection?: ContributionSendSelection
  },
) {
  return apiJson<DeckChangeRequest>(
    `/api/shared/decks/${encodeSegment(deckItemId)}/change-requests/send`,
    'POST',
    body,
  )
}

export function syncDeckChangeRequest(deckItemId: string, requestId: string) {
  return apiJson<DeckChangeRequest>(
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
  return apiJson<DeckChangeRequest>(
    `/api/shared/decks/${encodeSegment(deckItemId)}/change-requests/${encodeSegment(requestId)}/conflicts/${encodeSegment(conflictId)}/resolve`,
    'POST',
    input,
  )
}

export function submitDeckChangeRequest(deckItemId: string, requestId: string) {
  return apiJson<DeckChangeRequest>(
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

export function approveDeckChangeRequest(
  requestId: string,
  reviewComment: string,
  selection?: ReviewSelection,
) {
  return apiJson<DeckChangeRequest>(
    `/api/change-requests/${encodeSegment(requestId)}/approve`,
    'POST',
    selection ? { review_comment: reviewComment, selection } : { review_comment: reviewComment },
  )
}

export function rejectDeckChangeRequest(requestId: string, reviewComment: string) {
  return apiJson<DeckChangeRequest>(
    `/api/change-requests/${encodeSegment(requestId)}/reject`,
    'POST',
    { review_comment: reviewComment },
  )
}
