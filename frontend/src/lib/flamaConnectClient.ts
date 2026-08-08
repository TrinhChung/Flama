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
  | 'UNSUPPORTED_VERSION'

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
    options?: { signal?: AbortSignal }
  ): Promise<{ mediaId: string; url: string; contentHash: string; mimeType: string; size: number }>
  createImportSessionAsync(
    payload: { source?: string; selectedDecks?: string[]; totalNotes?: number; totalMedia?: number; appVersion?: string },
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ importSessionId: string }>
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
}

export class FlamaConnectClient implements IFlamaConnectClient {
  private baseUrl: string
  private timeoutMs: number

  constructor(baseUrl: string = FLAMA_CONNECT_URL, timeoutMs = 15000) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.timeoutMs = timeoutMs
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
      } catch (e) {
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
        throw new FlamaConnectClientError('Flama Connect Key không hợp lệ hoặc xác thực thất bại.', 'INVALID_KEY', res.status)
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
    options?: { signal?: AbortSignal }
  ): Promise<{ mediaId: string; url: string; contentHash: string; mimeType: string; size: number }> {
    const arrayBuffer = await file.arrayBuffer()
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    const contentHash = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')

    const base64Data = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)))
    const resFilename = await this.postAction<string>(
      'storeMediaFile',
      {
        filename: file.name,
        data: base64Data,
      },
      key,
      options
    )

    return {
      mediaId: resFilename,
      url: `${this.baseUrl}/media/${resFilename}`,
      contentHash,
      mimeType: file.type || 'audio/mpeg',
      size: file.size,
    }
  }

  async createImportSessionAsync(
    payload: { source?: string; selectedDecks?: string[]; totalNotes?: number; totalMedia?: number; appVersion?: string },
    key: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ importSessionId: string }> {
    return this.postAction<{ importSessionId: string }>('createImportSession', payload, key, options)
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
}

export const flamaConnectClient = new FlamaConnectClient()
