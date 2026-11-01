import { ApiError, apiRequest, getCsrfToken } from '@/shared/api/client'

export type StagedNoteMedia = {
  stage_id: string
  asset_id: string
  url: string
  sha256: string
  size_bytes: number
  content_type: string
  filename?: string
  width?: number
  height?: number
}

type UploadTicket = {
  ticket: string
  upload_url: string
  upload_zip_url: string
  expires_at: number
  max_bytes: number
  staging_ttl_seconds: number
}

type UploadContext = { noteId?: string; fieldName?: string }
type CachedTicket = { session: string; value: UploadTicket }
const tickets = new Map<string, CachedTicket>()
const pendingTickets = new Map<string, Promise<UploadTicket>>()

/** In-memory only: never reuse an upload capability across a CSRF/session change. */
async function getUploadTicket(context: UploadContext, refresh = false): Promise<UploadTicket> {
  const session = getCsrfToken()
  const key = JSON.stringify([session, context.noteId, context.fieldName])
  const cached = tickets.get(key)
  if (!refresh && cached?.session === session && cached.value.expires_at * 1000 > Date.now() + 30_000) {
    return cached.value
  }
  if (!refresh && pendingTickets.has(key)) return pendingTickets.get(key)!
  if (refresh) tickets.delete(key)

  const request = apiRequest<UploadTicket>('/api/media/upload-ticket', {
    method: 'POST',
    body: JSON.stringify({ note_id: context.noteId, field_name: context.fieldName }),
  }).then((ticket) => {
    if (!ticket.ticket || !ticket.upload_url || !Number.isFinite(ticket.expires_at) || ticket.max_bytes <= 0) {
      throw new ApiError('Máy chủ trả về vé tải lên không hợp lệ.', 502, 'INVALID_MEDIA_TICKET')
    }
    // A CSRF refresh or account switch can happen while this request is pending.
    // Obtain a new capability in that session instead of caching the previous one there.
    const currentSession = getCsrfToken()
    if (currentSession !== session) return getUploadTicket(context, true)
    for (const [cachedKey, entry] of tickets) {
      if (entry.session !== session) tickets.delete(cachedKey)
    }
    if (tickets.size >= 32) tickets.delete(tickets.keys().next().value!)
    tickets.set(JSON.stringify([currentSession, context.noteId, context.fieldName]), {
      session: currentSession, value: ticket,
    })
    return ticket
  }).finally(() => pendingTickets.delete(key))
  pendingTickets.set(key, request)
  return request
}

/** Upload bytes directly to the media worker. Saving the note commits this stage later. */
export async function stageNoteMedia(
  blob: Blob,
  filename = 'clipboard.png',
  context: UploadContext = {},
  signal?: AbortSignal,
): Promise<StagedNoteMedia> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const ticket = await getUploadTicket(context, attempt > 0)
    if (signal?.aborted) throw new DOMException('Upload cancelled', 'AbortError')
    if (blob.size > ticket.max_bytes) {
      throw new ApiError('Dung lượng tệp vượt quá giới hạn tải lên.', 413, 'MEDIA_TOO_LARGE')
    }
    const body = new FormData()
    body.append('file', blob, filename)
    let response: Response
    try {
      response = await fetch(ticket.upload_url, {
        method: 'POST',
        headers: { Authorization: `Bearer ${ticket.ticket}`, Accept: 'application/json' },
        body,
        credentials: 'omit',
        signal,
      })
    } catch (error) {
      if (signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) throw error
      throw new ApiError('Không thể tải tệp tới máy chủ media.', 0, 'MEDIA_UPLOAD_NETWORK_ERROR')
    }
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      if (attempt === 0 && (response.status === 401 || (response.status === 403 && payload?.error === 'TOKEN_EXPIRED'))) {
        continue
      }
      throw new ApiError(payload?.message || 'Tải media thất bại.', response.status, payload?.error || 'MEDIA_UPLOAD_FAILED')
    }
    if (!payload || !/^stg_[a-f0-9]{32}$/.test(payload.stage_id || '')) {
      throw new ApiError('Máy chủ trả về media tạm không hợp lệ.', 502, 'INVALID_MEDIA_STAGE')
    }
    // The preview must use the worker's origin, including in local development.
    const uploadUrl = new URL(ticket.upload_url, window.location.origin)
    return { ...payload, url: new URL(`/media/staged/${payload.stage_id}`, uploadUrl).href }
  }
  throw new ApiError('Vé tải lên đã hết hạn.', 401, 'TOKEN_EXPIRED')
}

export type UploadMediaResponse = {
  asset_id?: string
  field_name?: string
  filename?: string
  url?: string
}

/** Audio generation is an explicit save action, so attach its stage immediately. */
export async function uploadNoteMediaBlob(
  noteId: string,
  fieldName: string,
  blob: Blob,
  filename = 'voicevox_tts.wav',
): Promise<UploadMediaResponse> {
  const staged = await stageNoteMedia(blob, filename, { noteId, fieldName })
  return apiRequest<UploadMediaResponse>(`/api/notes/${encodeURIComponent(noteId)}/media`, {
    method: 'POST',
    body: JSON.stringify({ field_name: fieldName, stage_id: staged.stage_id, filename }),
  })
}

export type BatchMediaItemInput = {
  itemId?: string
  noteId: string
  fieldName: string
  blob: Blob
  filename?: string
}

export type BatchUploadMediaResponseItem = {
  item_id: string
  note_id: string
  field_name: string
  asset_id?: string
  url?: string
  filename?: string
  status: 'success' | 'failed'
  error?: string
  message?: string
}

export type BatchUploadMediaResponse = {
  success: boolean
  success_count: number
  failed_count: number
  items: BatchUploadMediaResponseItem[]
}

export async function uploadNoteMediaBatch(items: BatchMediaItemInput[]): Promise<BatchUploadMediaResponse> {
  if (!items.length) return { success: true, success_count: 0, failed_count: 0, items: [] }
  const stagedItems = []
  const failures: BatchUploadMediaResponseItem[] = []
  for (const [index, item] of items.entries()) {
    const itemId = item.itemId ?? String(index)
    const filename = item.filename || `tts_${item.noteId}.wav`
    try {
      const staged = await stageNoteMedia(item.blob, filename, { noteId: item.noteId, fieldName: item.fieldName })
      stagedItems.push({ item_id: itemId, note_id: item.noteId, field_name: item.fieldName, stage_id: staged.stage_id, filename })
    } catch (error) {
      failures.push({
        item_id: itemId, note_id: item.noteId, field_name: item.fieldName, status: 'failed',
        error: error instanceof ApiError ? error.code : 'MEDIA_UPLOAD_FAILED',
        message: error instanceof Error ? error.message : 'Tải media thất bại.',
      })
    }
  }
  const result: BatchUploadMediaResponse = { success: true, success_count: 0, failed_count: failures.length, items: [] }
  // The metadata attach endpoint accepts at most 100 receipts per request.
  for (let offset = 0; offset < stagedItems.length; offset += 100) {
    const batch = await apiRequest<BatchUploadMediaResponse>('/api/notes/media/batch', {
      method: 'POST', body: JSON.stringify({ items: stagedItems.slice(offset, offset + 100) }),
    })
    result.success &&= batch.success
    result.success_count += batch.success_count
    result.failed_count += batch.failed_count
    result.items.push(...batch.items)
  }
  result.items.push(...failures)
  return result
}
