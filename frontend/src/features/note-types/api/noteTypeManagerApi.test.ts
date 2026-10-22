import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createNoteType, fetchNoteTypeSummaries, noteTypeManagerQueryKey } from './noteTypeManagerApi'

const { apiRequest, apiJson } = vi.hoisted(() => ({ apiRequest: vi.fn(), apiJson: vi.fn() }))
vi.mock('@/shared/api/client', () => ({ apiRequest, apiJson }))
beforeEach(() => vi.clearAllMocks())

describe('note type manager API', () => {
  it('uses a lightweight endpoint, separate cache key, and abort signal', async () => {
    const signal = new AbortController().signal
    const response = { items: [{ id: 'nt-1', name: 'Vocabulary', field_count: 4, template_count: 2 }] }
    apiRequest.mockResolvedValue(response)
    expect(await fetchNoteTypeSummaries(signal)).toBe(response)
    expect(apiRequest).toHaveBeenCalledWith('/api/note-types?summary=1', { signal })
    expect(noteTypeManagerQueryKey).toEqual(['note-types', 'manager-summary'])
  })

  it('keeps creation on the canonical API with the original payload', async () => {
    apiJson.mockResolvedValue({ id: 'nt-new' })
    expect(await createNoteType('New type')).toEqual({ id: 'nt-new' })
    expect(apiJson).toHaveBeenCalledWith('/api/note-types', 'POST', { name: 'New type' })
  })
})
