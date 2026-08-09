/**
 * Flama Connect API client implementation with header authentication, timeout,
 * AbortSignal support, and error classification.
 */

import { FLAMA_CONNECT_URL } from '@/config/env'
import { redact_sensitive_text } from '@/lib/secureKeyStorage'

export interface FlamaAccountInfo {
  userId: number
  username: string
  displayName: string
  workspace: string
  importPermission: boolean
  uploadLimit: number
}

export type FlamaConnectErrorCategory =
  | 'INVALID_KEY'
  | 'EXPIRED_KEY'
  | 'REVOKED_KEY'
  | 'PERMISSION_DENIED'
  | 'ACCOUNT_DISABLED'
  | 'SERVER_UNAVAILABLE'
  | 'NETWORK_ERROR'
  | 'TIMEOUT'
  | 'RATE_LIMITED'
  | 'INVALID_SERVER_RESPONSE'
  | 'REQUEST_REJECTED'
  | 'UNSUPPORTED_VERSION'

export interface FlamaImportNoteTypePlan {
  sourceModelId: string
  sourceModelName: string
  targetNoteTypeId?: string
  fields: Array<{ name: string; fieldType: string }>
  templates: Array<{ name: string; frontHtml: string; backHtml: string; sharedCss: string }>
  fieldMapping: Record<string, string>
}

export interface FlamaImportSessionPayload {
  source?: string
  sourceKey: string
  sourceRootPath: string
  targetRootPath: string
  selectedDecks: string[]
  decks: Array<{ sourceDeckId: string; sourcePath: string; targetPath: string }>
  totalNotes: number
  totalMedia: number
  appVersion?: string
  mode: 'strict' | 'auto_sync_missing'
  noteTypes: FlamaImportNoteTypePlan[]
  planHash: string
}

export interface FlamaImportSessionResult {
  importSessionId: string
  status: string
  noteTypeBindings: Record<
    string,
    {
      sourceModelName: string
      targetNoteTypeId: string
      fieldMapping: Record<string, string>
      schemaHash: string
    }
  >
  blockers: Array<{ sourceModelId: string; sourceModelName: string; code: string; message: string }>
  selectedDecks: string[]
}

export interface FlamaImportCapabilities {
  formatVersion: number
  mediaPackageMaxBytes: number
  mediaPackageMaxEntries: number
  mediaPackageMaxUncompressedBytes: number
  mediaFileMaxBytes: number
  cardBatchMaxItems: number
  supportedMediaExtensions: string[]
}

export class FlamaConnectClientError extends Error {
  category: FlamaConnectErrorCategory
  status?: number

  constructor(message: string, category: FlamaConnectErrorCategory, status?: number) {
    super(redact_sensitive_text(message))
    this.name = 'FlamaConnectClientError'
    this.category = category
    this.status = status
  }
}

export interface IFlamaConnectClient {
  validateKeyAsync(key: string, options?: { signal?: AbortSignal }): Promise<FlamaAccountInfo>
  getCurrentUserAsync(key: string, options?: { signal?: AbortSignal }): Promise<FlamaAccountInfo>
  uploadMediaAsync(
    file: File,
    key: string,
    options?: { signal?: AbortSignal; importSessionId?: string }
  ): Promise<{ mediaId: string; url: string; contentHash: string; mimeType: string; size: number }>
  createImportSessionAsync(
    payload: FlamaImportSessionPayload,
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<FlamaImportSessionResult>
  importCardsAsync(
    payload: { importSessionId: string; cards: any[]; deckName?: string },
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ importSessionId: string; results: any[] }>
  getImportStatusAsync(
    sessionId: string,
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ importSessionId: string; status: string }>
  completeImportSessionAsync(
    sessionId: string,
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ importSessionId: string; status: string }>
  getImportCapabilitiesAsync(key: string, options?: { signal?: AbortSignal }): Promise<FlamaImportCapabilities>
  uploadMediaPackageAsync(
    sessionId: string,
    sequence: number,
    packageBlob: Blob,
    sha256: string,
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ packageId: string; sequence: number; sha256: string; itemCount: number; replayed: boolean }>
  uploadCardPackageAsync(
    sessionId: string,
    sequence: number,
    packageBlob: Blob,
    sha256: string,
    contentEncoding: 'gzip' | 'identity',
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ packageId: string; sequence: number; sha256: string; itemCount: number; replayed: boolean; results: any[] }>
}

export class FlamaConnectClient implements IFlamaConnectClient {
  private baseUrl: string
  private timeoutMs: number

  constructor(baseUrl: string = FLAMA_CONNECT_URL, timeoutMs = 15000) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.timeoutMs = timeoutMs
  }

  private importApiUrl(path: string): string {
    const root = this.baseUrl.replace(/\/v1\/flama-connect(?:\/.*)?$/, '')
    return `${root}${path}`
  }

  private async importApiFetch<T>(
    path: string,
    key: string,
    init: RequestInit,
    options?: { signal?: AbortSignal }
  ): Promise<T> {
    const sanitizedKey = this.sanitizeKey(key)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), Math.max(this.timeoutMs, 60_000))
    if (options?.signal) options.signal.addEventListener('abort', () => controller.abort())
    try {
      const response = await fetch(this.importApiUrl(path), {
        ...init,
        headers: { Authorization: `Bearer ${sanitizedKey}`, ...(init.headers || {}) },
        signal: controller.signal,
      })
      const payload = await response.json().catch(() => null)
      if (!response.ok) {
        throw new FlamaConnectClientError(
          String(payload?.message || payload?.error || `HTTP ${response.status}`),
          response.status === 429 ? 'RATE_LIMITED' : 'REQUEST_REJECTED',
          response.status
        )
      }
      return payload as T
    } catch (error: any) {
      if (error instanceof FlamaConnectClientError) throw error
      if (error?.name === 'AbortError') throw new FlamaConnectClientError('Upload package bị quá thời gian.', 'TIMEOUT')
      throw new FlamaConnectClientError('Không thể upload package lên Flama Connect.', 'NETWORK_ERROR')
    } finally {
      clearTimeout(timeoutId)
    }
  }

  private sanitizeKey(rawKey: string): string {
    const trimmed = String(rawKey || '').trim()
    if (!trimmed) {
      throw new FlamaConnectClientError('Flama Connect Key không được để trống.', 'INVALID_KEY')
    }
    return trimmed
  }

  private async postAction<T>(
    action: string,
    params: Record<string, any>,
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<T> {
    const sanitizedKey = this.sanitizeKey(key)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs)

    if (options?.signal) {
      options.signal.addEventListener('abort', () => controller.abort())
    }

    try {
      const res = await fetch(this.baseUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${sanitizedKey}`,
        },
        body: JSON.stringify({
          action,
          version: 6,
          params,
        }),
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (res.status === 429) {
        throw new FlamaConnectClientError('Tốc độ gửi request vượt giới hạn cho phép. Vui lòng thử lại sau.', 'RATE_LIMITED', 429)
      }

      if (res.status >= 500) {
        throw new FlamaConnectClientError('Máy chủ Flama Connect hiện không phản hồi. Vui lòng thử lại sau.', 'SERVER_UNAVAILABLE', res.status)
      }

      let payload: any
      try {
        payload = await res.json()
      } catch {
        throw new FlamaConnectClientError('Phản hồi từ máy chủ không đúng định dạng JSON.', 'INVALID_SERVER_RESPONSE', res.status)
      }

      if (payload && typeof payload === 'object' && payload.error) {
        const errorMsg = String(payload.error).toLowerCase()
        if (errorMsg.includes('revoked')) {
          throw new FlamaConnectClientError('Flama Connect Key đã bị thu hồi.', 'REVOKED_KEY', res.status)
        }
        if (errorMsg.includes('expired')) {
          throw new FlamaConnectClientError('Flama Connect Key đã hết hạn.', 'EXPIRED_KEY', res.status)
        }
        if (errorMsg.includes('disabled')) {
          throw new FlamaConnectClientError('Tài khoản Flama của bạn đã bị khóa hoặc vô hiệu hóa.', 'ACCOUNT_DISABLED', res.status)
        }
        if (errorMsg.includes('permission')) {
          throw new FlamaConnectClientError('Tài khoản không có quyền thực hiện thao tác này.', 'PERMISSION_DENIED', res.status)
        }
        if (errorMsg.includes('version')) {
          throw new FlamaConnectClientError('Phiên bản API Flama Connect không còn được hỗ trợ.', 'UNSUPPORTED_VERSION', res.status)
        }
        throw new FlamaConnectClientError(String(payload.error), 'REQUEST_REJECTED', res.status)
      }

      return (payload?.result !== undefined ? payload.result : payload) as T
    } catch (err: any) {
      clearTimeout(timeoutId)
      if (err instanceof FlamaConnectClientError) {
        throw err
      }
      if (err?.name === 'AbortError') {
        throw new FlamaConnectClientError('Yêu cầu kết nối bị quá thời gian (Timeout).', 'TIMEOUT')
      }
      throw new FlamaConnectClientError('Không thể kết nối đến Flama Connect. Vui lòng kiểm tra lại mạng.', 'NETWORK_ERROR')
    }
  }

  async validateKeyAsync(key: string, options?: { signal?: AbortSignal }): Promise<FlamaAccountInfo> {
    return this.getCurrentUserAsync(key, options)
  }

  async getCurrentUserAsync(key: string, options?: { signal?: AbortSignal }): Promise<FlamaAccountInfo> {
    const rawInfo = await this.postAction<any>('userInfo', {}, key, options)
    return {
      userId: rawInfo.userId ?? 0,
      username: rawInfo.username ?? 'user',
      displayName: rawInfo.displayName ?? rawInfo.username ?? 'Flama User',
      workspace: rawInfo.workspace ?? 'default',
      importPermission: Boolean(rawInfo.importPermission ?? true),
      uploadLimit: rawInfo.uploadLimit ?? 1048576,
    }
  }

  async uploadMediaAsync(
    file: File,
    key: string,
    options?: { signal?: AbortSignal; importSessionId?: string }
  ): Promise<{ mediaId: string; url: string; contentHash: string; mimeType: string; size: number }> {
    const arrayBuffer = await file.arrayBuffer()
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    const contentHash = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')

    const bytes = new Uint8Array(arrayBuffer)
    const chunks: string[] = []
    for (let offset = 0; offset < bytes.length; offset += 0x8000) {
      chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 0x8000)))
    }
    const base64Data = btoa(chunks.join(''))
    const stored = await this.postAction<string | { filename: string; sha256: string; mimeType: string; size: number }>(
      'storeMediaFile',
      {
        filename: file.name,
        data: base64Data,
        importSessionId: options?.importSessionId,
        mediaKind: file.type.startsWith('image/') ? 'image' : 'audio',
      },
      key,
      options
    )

    return {
      mediaId: typeof stored === 'string' ? stored : stored.filename,
      url: '',
      contentHash: typeof stored === 'string' ? contentHash : stored.sha256,
      mimeType: typeof stored === 'string' ? file.type || 'audio/mpeg' : stored.mimeType,
      size: typeof stored === 'string' ? file.size : stored.size,
    }
  }

  async createImportSessionAsync(
    payload: FlamaImportSessionPayload,
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<FlamaImportSessionResult> {
    return this.postAction<FlamaImportSessionResult>('createImportSession', payload, key, options)
  }

  async importCardsAsync(
    payload: { importSessionId: string; cards: any[]; deckName?: string },
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ importSessionId: string; results: any[] }> {
    return this.postAction<{ importSessionId: string; results: any[] }>('importCards', payload, key, options)
  }

  async getImportStatusAsync(
    sessionId: string,
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ importSessionId: string; status: string }> {
    return this.postAction<{ importSessionId: string; status: string }>('getImportStatus', { importSessionId: sessionId }, key, options)
  }

  async completeImportSessionAsync(
    sessionId: string,
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ importSessionId: string; status: string }> {
    return this.postAction<{ importSessionId: string; status: string }>('completeImportSession', { importSessionId: sessionId }, key, options)
  }

  async getImportCapabilitiesAsync(
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<FlamaImportCapabilities> {
    return this.importApiFetch<FlamaImportCapabilities>(
      '/v1/import-sessions/capabilities',
      key,
      { method: 'GET' },
      options
    )
  }

  async uploadMediaPackageAsync(
    sessionId: string,
    sequence: number,
    packageBlob: Blob,
    sha256: string,
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ packageId: string; sequence: number; sha256: string; itemCount: number; replayed: boolean }> {
    return this.importApiFetch(
      `/v1/import-sessions/${encodeURIComponent(sessionId)}/packages/media/${sequence}`,
      key,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/zip', 'X-Package-SHA256': sha256 },
        body: packageBlob,
      },
      options
    )
  }

  async uploadCardPackageAsync(
    sessionId: string,
    sequence: number,
    packageBlob: Blob,
    sha256: string,
    contentEncoding: 'gzip' | 'identity',
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ packageId: string; sequence: number; sha256: string; itemCount: number; replayed: boolean; results: any[] }> {
    return this.importApiFetch(
      `/v1/import-sessions/${encodeURIComponent(sessionId)}/packages/cards/${sequence}`,
      key,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/x-ndjson',
          'Content-Encoding': contentEncoding,
          'X-Package-SHA256': sha256,
        },
        body: packageBlob,
      },
      options
    )
  }
}

export const flamaConnectClient = new FlamaConnectClient()
