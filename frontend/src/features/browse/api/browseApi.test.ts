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
    expect(url.pathname).toBe('/api/browse/notes')
    expect(Object.fromEntries(url.searchParams)).toEqual({ view: 'rows', q: 'a & b', status: 'review', sort_by: 'word', sort_dir: 'desc', page: '2', per_page: '100' })
  })

  it('keeps native lists and optimistic revision preconditions in update requests', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ detail: { row: { note_id: 'note-id' }, note: { id: 'note-id' }, fields: [] } }))
    const body = { field_values: { Answers: ['one', ['two']] }, expected_content_revision: 3, expected_field_schema_revision: 7 }
    await browseApi.updateCard('card/id', body)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/browse/notes/card%2Fid?view=editor')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body)).toEqual(body)
  })

  it('passes aborts through without retrying a canceled request', async () => {
    const aborted = new DOMException('Canceled', 'AbortError')
    fetchMock.mockRejectedValueOnce(aborted)
    await expect(browseApi.fetchNoteTypes(new AbortController().signal)).rejects.toBe(aborted)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('uses the Note identity for rows and detail even without a presentation', async () => {
    const row = { note_id: 'note-only', deck_id: 1, deck_name: 'Deck', word: 'word', reading: '', meaning: '', tags: [], status: 'new', due_label: '' }
    fetchMock.mockResolvedValueOnce(Response.json({ items: [row], total: 1, page: 1, pages: 1, has_next: false }))
    const list = await browseApi.fetchCards({ q: '', deck_id: 1, status: 'all', sort_by: 'due', sort_dir: 'asc', page: 1, per_page: 100 })
    expect(list.items[0]).toMatchObject({ note_id: 'note-only', card_id: 'note-only' })
    fetchMock.mockResolvedValueOnce(Response.json({ row, note: { id: 'note-only', field_values: { Answers: ['one', ['two']] } }, fields: [] }))
    const detail = await browseApi.fetchCardDetail('note-only')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/browse/notes/note-only?view=editor')
    expect(detail.card.card_id).toBe('note-only')
    expect(detail.note.field_values.Answers).toEqual(['one', ['two']])
  })

  it('requests Note counters and sends explicit Note selectors to VoiceVox', async () => {
    fetchMock.mockResolvedValueOnce(Response.json({ decks: [] }))
    await browseApi.fetchDecks()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/browse/decks?view=notes')
    fetchMock.mockResolvedValueOnce(Response.json({ success: true }))
    await browseApi.generateVoiceVox({ card_ids: ['note-only'], source_field: 'Word', destination_field: 'Audio' })
    const body = JSON.parse(fetchMock.mock.calls[1][1].body)
    expect(body.note_ids).toEqual(['note-only'])
    expect(body).not.toHaveProperty('card_ids')
  })
})
