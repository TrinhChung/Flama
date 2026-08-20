import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiRequest, mutate } = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  mutate: vi.fn(),
}))

vi.mock('@/shared/api/client', () => ({ apiRequest }))
vi.mock('@/app/api', () => ({ appApi: { mutate } }))

import {
  buildDeckChangeRequestDraft,
  contributionItemToDiffItem,
  getActiveDeckChangeRequest,
  getIncomingDeckChangeRequests,
  resolveDeckChangeRequestConflict,
} from './api'

describe('deck collaboration API contract', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    mutate.mockReset()
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
