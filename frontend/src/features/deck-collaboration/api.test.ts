import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiRequest, mutate } = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  mutate: vi.fn(),
}))

vi.mock('@/shared/api/client', () => ({ apiRequest, apiJson: mutate }))

import {
  buildDeckChangeRequestDraft,
  contributionItemToDiffItem,
  getActiveDeckChangeRequest,
  getDeckChangeRequest,
  getIncomingDeckChangeRequests,
  getInstalledUpdateConflicts,
  getLocalDeckChanges,
  markInstalledDeckUpdateSeen,
  prepareInstalledDeckUpdate,
  resolveDeckChangeRequestConflict,
  resolveInstalledUpdateConflict,
  sendDeckContribution,
} from './api'

describe('deck collaboration API contract', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    mutate.mockReset()
  })

  it('sends saved changes with the reviewed overlay fingerprint in one request', async () => {
    const result = { id: 'request-1', status: 'pending_review' }
    const body = { title: 'Sửa nghĩa', description: 'Mô tả', expected_overlay_fingerprint: 'a'.repeat(64) }
    mutate.mockResolvedValueOnce(result)
    await expect(sendDeckContribution('deck/item', body)).resolves.toBe(result)
    expect(mutate).toHaveBeenCalledWith('/api/shared/decks/deck%2Fitem/change-requests/send', 'POST', body)
  })

  it('uses the Flask contribution endpoints and keeps their raw response envelope', async () => {
    const activePayload = { request: null }
    apiRequest.mockResolvedValueOnce(activePayload)

    await expect(getActiveDeckChangeRequest('deck/item')).resolves.toBe(activePayload)
    expect(apiRequest).toHaveBeenCalledWith(
      '/api/shared/decks/deck%2Fitem/change-requests/active',
      { signal: undefined },
    )

    const draft = { id: 'request-1', status: 'needs_sync' }
    mutate.mockResolvedValueOnce(draft)
    await expect(buildDeckChangeRequestDraft('deck/item', {
      title: 'Sửa nghĩa',
      description: 'Mô tả',
    })).resolves.toBe(draft)
    expect(mutate).toHaveBeenCalledWith(
      '/api/shared/decks/deck%2Fitem/change-requests/draft',
      'POST',
      { title: 'Sửa nghĩa', description: 'Mô tả' },
    )
  })

  it('forwards owner filters and manual conflict resolutions exactly', async () => {
    apiRequest.mockResolvedValueOnce({ items: [] })
    await getIncomingDeckChangeRequests('deck 1')
    expect(apiRequest).toHaveBeenCalledWith(
      '/api/change-requests/incoming?deck_item_id=deck+1',
      { signal: undefined },
    )

    mutate.mockResolvedValueOnce({ id: 'request-1' })
    await resolveDeckChangeRequestConflict('deck/1', 'request/1', 'conflict/1', {
      resolution_mode: 'manual',
      resolved_value: { text: '犬' },
    })
    expect(mutate).toHaveBeenCalledWith(
      '/api/shared/decks/deck%2F1/change-requests/request%2F1/conflicts/conflict%2F1/resolve',
      'POST',
      { resolution_mode: 'manual', resolved_value: { text: '犬' } },
    )

    apiRequest.mockResolvedValueOnce({ items: [], page: { next_cursor: null } })
    await getDeckChangeRequest('request 1', {
      cursor: 'next/cursor',
      limit: 100,
      changeType: 'conflict',
      query: '犬',
    })
    expect(apiRequest).toHaveBeenLastCalledWith(
      '/api/change-requests/request%201?cursor=next%2Fcursor&limit=100&type=conflict&q=%E7%8A%AC',
      { signal: undefined },
    )
  })

  it('forwards cursor filters for local and active contribution pages', async () => {
    apiRequest.mockResolvedValueOnce({ items: [], page: { next_cursor: null } })
    await getLocalDeckChanges('deck 1', {
      cursor: 'local/cursor',
      limit: 100,
      changeType: 'modified',
      query: '  犬  ',
    })
    expect(apiRequest).toHaveBeenLastCalledWith(
      '/api/shared/decks/deck%201/change-requests/local-changes?cursor=local%2Fcursor&limit=100&type=modified&q=%E7%8A%AC',
      { signal: undefined },
    )

    apiRequest.mockResolvedValueOnce({ request: null })
    await getActiveDeckChangeRequest('deck 1', {
      cursor: 'active/cursor',
      limit: 100,
      changeType: 'conflict',
      query: 'Meaning',
    })
    expect(apiRequest).toHaveBeenLastCalledWith(
      '/api/shared/decks/deck%201/change-requests/active?cursor=active%2Fcursor&limit=100&type=conflict&q=Meaning',
      { signal: undefined },
    )
  })

  it('marks the opened release as seen through the installation endpoint', async () => {
    mutate.mockResolvedValueOnce({
      install_id: 'install-1',
      applied_release: null,
      available_release: null,
      update_available: false,
      unread_update: false,
    })

    await expect(markInstalledDeckUpdateSeen('install/1', 'release/1')).resolves.toMatchObject({
      unread_update: false,
    })
    expect(mutate).toHaveBeenCalledWith(
      '/api/marketplace/installations/install%2F1/updates/release%2F1/mark-seen',
      'POST',
      {},
    )
  })

  it('normalizes the bounded conflict page returned by prepare', async () => {
    mutate.mockResolvedValueOnce({
      rebase: {
        id: 42,
        status: 'has_conflict',
        expected_overlay_revision: 7,
        conflict_count: 101,
        resolved_conflict_count: 1,
        conflicts: [{
          id: 100,
          change_key: 'note-field-100',
          note_label: '犬',
          property_key: 'Meaning',
          local_value: 'hound',
          upstream_value: 'dog',
          resolution_mode: 'keep_mine',
          resolved_at: '2026-08-21T00:00:00Z',
        }],
        conflict_page: {
          limit: 100,
          has_more: true,
          next_after_id: 100,
        },
      },
    })

    await expect(prepareInstalledDeckUpdate('install/1', 'release/2', {
      expected_overlay_revision: 7,
      idempotency_key: 'prepare-key',
    })).resolves.toMatchObject({
      rebase_id: '42',
      status: 'conflicts',
      conflict_count: 101,
      resolved_conflict_count: 1,
      conflict_page: {
        limit: 100,
        has_more: true,
        next_after_id: '100',
      },
      conflicts: [{
        id: '100',
        change_id: 'note-field-100',
        field_name: 'Meaning',
        resolution_mode: 'keep_mine',
      }],
    })
    expect(mutate).toHaveBeenCalledWith(
      '/api/marketplace/installations/install%2F1/updates/release%2F2/prepare',
      'POST',
      {
        expected_overlay_revision: 7,
        idempotency_key: 'prepare-key',
      },
    )
  })

  it('loads the next rebase conflict page through after_id', async () => {
    const signal = new AbortController().signal
    apiRequest.mockResolvedValueOnce({
      rebase_id: 42,
      status: 'has_conflict',
      conflict_count: 101,
      resolved_conflict_count: 1,
      items: [{
        id: 101,
        change_id: 501,
        note_label: '猫',
        field_name: 'Meaning',
      }],
      page: {
        limit: 100,
        has_more: false,
        next_after_id: null,
      },
    })

    await expect(getInstalledUpdateConflicts('rebase/42', '100', 100, signal))
      .resolves.toMatchObject({
        rebase_id: '42',
        status: 'conflicts',
        items: [{ id: '101', change_id: '501' }],
        page: { has_more: false, next_after_id: null },
      })
    expect(apiRequest).toHaveBeenCalledWith(
      '/api/marketplace/rebases/rebase%2F42/conflicts?after_id=100&limit=100',
      { signal },
    )
  })

  it('normalizes a header-only response after resolving a conflict', async () => {
    mutate.mockResolvedValueOnce({
      rebase: {
        id: 42,
        status: 'ready',
        conflict_count: 101,
        resolved_conflict_count: 101,
      },
    })

    await expect(resolveInstalledUpdateConflict('42', '101', 'keep_upstream'))
      .resolves.toEqual({
        rebase_id: '42',
        status: 'ready',
        conflict_count: 101,
        resolved_conflict_count: 101,
        conflicts: [],
        conflict_page: undefined,
        expected_overlay_revision: undefined,
      })
    expect(mutate).toHaveBeenCalledWith(
      '/api/marketplace/rebases/42/conflicts/101/resolve',
      'POST',
      { resolution_mode: 'keep_upstream' },
    )
  })

  it('maps unresolved Flask conflicts to compact Git-style diff rows', () => {
    const row = contributionItemToDiffItem({
      id: 'item-1',
      change_type: 'note_field_set',
      source_ref_id: 'note-1',
      path_key: 'Meaning',
      path_label: 'Note 犬 / Meaning',
      before_value: 'dog',
      after_value: 'hound',
      effective_after_value: 'hound',
      metadata: {
        source_note_label: '犬',
        source_field_def_id: 'field-1',
        field_name: 'Meaning',
      },
      is_conflict: true,
      conflict: {
        id: 'conflict-1',
        conflict_type: 'value_changed',
        resolved_at: null,
      },
    })

    expect(row).toMatchObject({
      id: 'item-1',
      change_type: 'conflict',
      entity_kind: 'note_field',
      note_id: 'note-1',
      note_label: '犬',
      field_def_id: 'field-1',
      field_name: 'Meaning',
      conflict_id: 'conflict-1',
      before_value: 'dog',
      after_value: 'hound',
    })
  })
})
