// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setCsrfToken } from '@/shared/api/client'

const stageId = `stg_${'a'.repeat(32)}`
const staged = { stage_id: stageId, asset_id: 'b'.repeat(64), sha256: 'b'.repeat(64), size_bytes: 3, content_type: 'image/png' }
const json = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), {
  status, headers: { 'Content-Type': 'application/json' },
})
const ticket = (token = 'signed-ticket', expires = Date.now() / 1000 + 3600) => ({
  ticket: token, upload_url: 'https://media.example.test/media/upload',
  upload_zip_url: 'https://media.example.test/media/upload-zip', expires_at: expires,
  max_bytes: 10 * 1024 * 1024, staging_ttl_seconds: 86400,
})

describe('direct note media upload', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.resetModules()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-01T00:00:00Z'))
    setCsrfToken('media-test-session')
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('sends original bytes to Go without cookies or CSRF and leaves the note unchanged', async () => {
    fetchMock.mockResolvedValueOnce(json(ticket())).mockResolvedValue(json(staged))
    const { stageNoteMedia } = await import('./media')
    const blob = new Blob(['raw'], { type: 'image/png' })
    const result = await stageNoteMedia(blob, 'photo.png')
    expect(result.url).toBe(`https://media.example.test/media/staged/${stageId}`)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    const [url, request] = fetchMock.mock.calls[1]
    expect(url).toBe('https://media.example.test/media/upload')
    expect(request.credentials).toBe('omit')
    expect(request.headers).toEqual({ Authorization: 'Bearer signed-ticket', Accept: 'application/json' })
    expect(Array.from(request.body.keys())).toEqual(['file'])
    expect(request.body.get('file').size).toBe(blob.size)
    expect(fetchMock.mock.calls.some(([target]) => target.includes('/notes/'))).toBe(false)
  })

  it('reuses a current ticket for the same upload context', async () => {
    fetchMock.mockResolvedValueOnce(json(ticket())).mockImplementation(() => Promise.resolve(json(staged)))
    const { stageNoteMedia } = await import('./media')
    await stageNoteMedia(new Blob(['raw']))
    await stageNoteMedia(new Blob(['raw']))
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/media/upload-ticket')).toHaveLength(1)
  })

  it('obtains a fresh ticket after expiry or a session change', async () => {
    fetchMock.mockImplementation((url) => Promise.resolve(json(url === '/api/media/upload-ticket' ? ticket() : staged)))
    const { stageNoteMedia } = await import('./media')
    const client = await import('@/shared/api/client')
    await stageNoteMedia(new Blob(['raw']))
    vi.advanceTimersByTime(3600_000)
    await stageNoteMedia(new Blob(['raw']))
    client.setCsrfToken('another-user-session')
    await stageNoteMedia(new Blob(['raw']))
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/media/upload-ticket')).toHaveLength(3)
  })

  it('does not upload with a capability obtained during a different session', async () => {
    let finishFirstTicket: (response: Response) => void
    fetchMock.mockImplementationOnce(() => new Promise<Response>((resolve) => { finishFirstTicket = resolve }))
      .mockResolvedValueOnce(json(ticket('new-session-ticket')))
      .mockResolvedValueOnce(json(staged))
    const { stageNoteMedia } = await import('./media')
    const client = await import('@/shared/api/client')
    const upload = stageNoteMedia(new Blob(['raw']))
    client.setCsrfToken('changed-while-ticket-was-pending')
    finishFirstTicket!(json(ticket('old-session-ticket')))
    await upload
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer new-session-ticket')
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/media/upload-ticket')).toHaveLength(2)
  })

  it('refreshes a rejected ticket once and retries only the worker upload', async () => {
    fetchMock.mockResolvedValueOnce(json(ticket('old')))
      .mockResolvedValueOnce(json({ error: 'TOKEN_EXPIRED' }, 401))
      .mockResolvedValueOnce(json(ticket('renewed')))
      .mockResolvedValueOnce(json(staged))
    const { stageNoteMedia } = await import('./media')
    await stageNoteMedia(new Blob(['raw']))
    expect(fetchMock).toHaveBeenCalledTimes(4)
    expect(fetchMock.mock.calls[3][1].headers.Authorization).toBe('Bearer renewed')
  })

  it('checks the ticket size limit before sending the file', async () => {
    fetchMock.mockResolvedValueOnce(json({ ...ticket(), max_bytes: 2 }))
    const { stageNoteMedia } = await import('./media')
    await expect(stageNoteMedia(new Blob(['raw']))).rejects.toMatchObject({ code: 'MEDIA_TOO_LARGE' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('attaches an audio stage using JSON only after worker success', async () => {
    fetchMock.mockResolvedValueOnce(json(ticket()))
      .mockResolvedValueOnce(json(staged))
      .mockResolvedValueOnce(json({ asset_id: 'db-id', url: '/store/db-id' }))
    const { uploadNoteMediaBlob } = await import('./media')
    await uploadNoteMediaBlob('note-1', 'Audio', new Blob(['raw']), 'tts.wav')
    const [url, request] = fetchMock.mock.calls[2]
    expect(url).toBe('/api/notes/note-1/media')
    expect(JSON.parse(request.body)).toEqual({ field_name: 'Audio', stage_id: stageId, filename: 'tts.wav' })
    expect(request.body).not.toBeInstanceOf(FormData)
  })

  it('retains per-item upload failures while attaching successful batch stages', async () => {
    fetchMock.mockImplementation((url) => {
      if (url === '/api/media/upload-ticket') return Promise.resolve(json(ticket()))
      if (url === '/api/notes/media/batch') return Promise.resolve(json({ success: true, success_count: 1, failed_count: 0, items: [{ item_id: 'first', status: 'success' }] }))
      return Promise.resolve(json(staged))
    })
    const { uploadNoteMediaBatch } = await import('./media')
    const result = await uploadNoteMediaBatch([
      { itemId: 'first', noteId: 'note-1', fieldName: 'Audio', blob: new Blob(['raw']) },
      { itemId: 'second', noteId: 'note-2', fieldName: 'Audio', blob: new Blob([new ArrayBuffer(11 * 1024 * 1024)]) },
    ])
    expect(result.success_count).toBe(1)
    expect(result.failed_count).toBe(1)
    expect(result.items.find((item) => item.item_id === 'second')).toMatchObject({ status: 'failed', error: 'MEDIA_TOO_LARGE' })
    const request = fetchMock.mock.calls.find(([url]) => url === '/api/notes/media/batch')![1]
    const body = JSON.parse(request.body)
    expect(body.items).toHaveLength(1)
    expect(body.items[0].stage_id).toBe(stageId)
    expect(body.items[0]).not.toHaveProperty('blob')
  })

  it('attaches larger batches within the server receipt limit', async () => {
    fetchMock.mockImplementation((url, request) => {
      if (url === '/api/media/upload-ticket') return Promise.resolve(json(ticket()))
      if (url === '/api/notes/media/batch') {
        const items = JSON.parse(request.body).items
        return Promise.resolve(json({ success: true, success_count: items.length, failed_count: 0, items: items.map((item: any) => ({ ...item, status: 'success' })) }))
      }
      return Promise.resolve(json(staged))
    })
    const { uploadNoteMediaBatch } = await import('./media')
    const result = await uploadNoteMediaBatch(Array.from({ length: 101 }, (_, index) => ({
      itemId: String(index), noteId: 'note-1', fieldName: 'Audio', blob: new Blob(['raw']),
    })))
    const attachments = fetchMock.mock.calls.filter(([url]) => url === '/api/notes/media/batch')
    expect(attachments.map(([, request]) => JSON.parse(request.body).items.length)).toEqual([100, 1])
    expect(result.success_count).toBe(101)
    expect(result.items).toHaveLength(101)
  })
})
