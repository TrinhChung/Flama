import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setCsrfToken } from '@/shared/api/client'
import { browseApi, browseQueryKeys } from './browseApi'

describe('Browse transport', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    fetchMock.mockReset()
    setCsrfToken('')
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('requests compact NoteTypes with native-array definitions and an independent cache identity', async () => {
    const payload = { items: [{ id: 'nt', name: 'Vocabulary', field_defs: [{ name: 'Answers', position: 0, field_type: 'array', required: true }] }] }
    fetchMock.mockResolvedValueOnce(Response.json(payload))
    const controller = new AbortController()
    expect(await browseApi.fetchNoteTypes(controller.signal)).toEqual(payload)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/note-types?compact=1')
    expect(init.credentials).toBe('include')
    expect(init.signal).toBe(controller.signal)
    expect(browseQueryKeys.noteTypes).not.toEqual(['note-types'])
    expect(browseQueryKeys.noteTypes[0]).toBe('note-types')
  })

  it('keeps list filters before pagination and omits an empty deck filter', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ items: [], total: 0, pages: 0, page: 2 }))
    await browseApi.fetchCards({ q: 'a & b', deck_id: '', status: 'review', sort_by: 'word', sort_dir: 'desc', page: 2, per_page: 100 })
    const url = new URL(fetchMock.mock.calls[0][0], 'http://localhost')
    expect(url.pathname).toBe('/api/browse/cards')
    expect(Object.fromEntries(url.searchParams)).toEqual({ q: 'a & b', status: 'review', sort_by: 'word', sort_dir: 'desc', page: '2', per_page: '100' })
  })

  it('keeps native lists and optimistic revision preconditions in update requests', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ detail: {} }))
    const body = { field_values: { Answers: ['one', ['two']] }, expected_content_revision: 3, expected_field_schema_revision: 7 }
    await browseApi.updateCard('card/id', body)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/browse/cards/card%2Fid')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body)).toEqual(body)
  })

  it('passes aborts through without retrying a canceled request', async () => {
    const aborted = new DOMException('Canceled', 'AbortError')
    fetchMock.mockRejectedValueOnce(aborted)
    await expect(browseApi.fetchNoteTypes(new AbortController().signal)).rejects.toBe(aborted)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
