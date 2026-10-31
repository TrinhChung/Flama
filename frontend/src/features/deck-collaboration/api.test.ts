import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiRequest, mutate } = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  mutate: vi.fn(),
}))

vi.mock('@/shared/api/client', () => ({ apiRequest, apiJson: mutate }))

import {
  approveDeckChangeRequest,
  buildDeckChangeRequestDraft,
  getActiveDeckChangeRequest,
  getDeckChangeRequest,
  getIncomingDeckChangeRequests,
  getLocalDeckChanges,
  resolveDeckChangeRequestConflict,
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

  it('sends the owner selection only when some changes are left out', async () => {
    mutate.mockResolvedValue({ id: 'request-1', status: 'merged' })
    await approveDeckChangeRequest('request-1', 'ok')
    expect(mutate).toHaveBeenLastCalledWith('/api/change-requests/request-1/approve', 'POST', { review_comment: 'ok' })
    const selection = { mode: 'all_except' as const, item_ids: ['item-2'] }
    await approveDeckChangeRequest('request-1', '', selection)
    expect(mutate).toHaveBeenLastCalledWith('/api/change-requests/request-1/approve', 'POST', {
      review_comment: '', selection,
    })
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

})
