import { API_BASE_URL, resolveBackendUrl } from '@/config/env'
import {
  isBackendUnavailableStatus,
  reportBackendUnavailable,
} from './backendAvailability'

type ErrorPayload = {
  error?: string
  message?: string
  field?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly field?: string

  constructor(message: string, status: number, code = 'REQUEST_FAILED', field?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.field = field
  }
}

let csrfToken = ''
let csrfRefreshRequest: Promise<void> | null = null

export function setCsrfToken(token: string) {
  csrfToken = token
  const meta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
  meta?.setAttribute('content', token)
}

export function getCsrfToken(): string {
  if (csrfToken) return csrfToken
  const meta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
  return meta?.getAttribute('content') || ''
}

function isUnsafeMethod(method: string) {
  return !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method.toUpperCase())
}

async function refreshCsrfToken(): Promise<void> {
  if (csrfRefreshRequest) return csrfRefreshRequest

  csrfRefreshRequest = (async () => {
    const response = await fetch(resolveBackendUrl(`${API_BASE_URL}/session`), {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'include',
    })
    const contentType = response.headers.get('content-type') || ''
    const payload = contentType.includes('application/json')
      ? ((await response.json()) as { csrf_token?: unknown; message?: string })
      : null
    const token = typeof payload?.csrf_token === 'string'
      ? payload.csrf_token.trim()
      : ''
    if (!response.ok || !token) {
      throw new ApiError(
        payload?.message || 'Không thể làm mới CSRF token.',
        response.status,
        'CSRF_REFRESH_FAILED',
      )
    }
    setCsrfToken(token)
  })().finally(() => {
    csrfRefreshRequest = null
  })

  return csrfRefreshRequest
}

async function apiFetch(
  url: string,
  init: RequestInit = {},
  accept = 'application/json',
  retryCsrf = true,
): Promise<Response> {
  const method = String(init.method || 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', accept)

  const effectiveCsrfToken = getCsrfToken()
  if (isUnsafeMethod(method) && effectiveCsrfToken) {
    headers.set('X-CSRF-Token', effectiveCsrfToken)
    headers.set('X-CSRFToken', effectiveCsrfToken)
  }
  if (
    init.body &&
    !headers.has('Content-Type') &&
    !(init.body instanceof FormData) &&
    !(init.body instanceof URLSearchParams)
  ) {
    headers.set('Content-Type', 'application/json')
  }
  if (init.body instanceof FormData && effectiveCsrfToken) {
    if (!init.body.has('_csrf_token') && !init.body.has('csrf_token')) {
      init.body.append('csrf_token', effectiveCsrfToken)
    }
  }

  let response: Response
  try {
    response = await fetch(resolveBackendUrl(url), {
      ...init,
      method,
      headers,
      credentials: 'include',
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }

    if (error instanceof TypeError) {
      reportBackendUnavailable()
      throw new ApiError(
        'Không thể kết nối tới máy chủ.',
        0,
        'BACKEND_UNAVAILABLE',
      )
    }

    throw error
  }

  if (isBackendUnavailableStatus(response.status)) {
    reportBackendUnavailable()
    throw new ApiError(
      'Máy chủ đang tạm thời không sẵn sàng.',
      response.status,
      'BACKEND_UNAVAILABLE',
    )
  }

  if (response.redirected && new URL(response.url).pathname === '/login') {
    throw new ApiError('Phiên đăng nhập đã hết hạn.', 401, 'AUTH_REQUIRED')
  }

  if (retryCsrf && isUnsafeMethod(method) && response.status === 400) {
    const contentType = response.headers.get('content-type') || ''
    const payload = contentType.includes('application/json')
      ? ((await response.clone().json()) as ErrorPayload)
      : null
    if (payload?.error === 'CSRF_FAILED') {
      await refreshCsrfToken()
      return apiFetch(url, init, accept, false)
    }
  }

  if (!response.ok) {
    const contentType = response.headers.get('content-type') || ''
    const payload = contentType.includes('application/json')
      ? ((await response.json()) as ErrorPayload)
      : null
    throw new ApiError(
      payload?.message ||
        payload?.error ||
        `Request failed with status ${response.status}.`,
      response.status,
      payload?.error,
      payload?.field,
    )
  }

  return response
}

export async function apiRequest<T>(
  url: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await apiFetch(url, init)
  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json')
    ? ((await response.json()) as T)
    : null

  return payload as T
}

export async function apiBlob(
  url: string,
  init: RequestInit = {},
): Promise<Blob> {
  const response = await apiFetch(url, init, 'audio/*, application/json')
  return response.blob()
}

export async function apiJson<T>(
  url: string,
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  body?: unknown,
) {
  return apiRequest<T>(url, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export async function apiJsonKeepalive<T>(
  url: string,
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  body?: unknown,
) {
  return apiRequest<T>(url, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
    keepalive: true,
  })
}

export async function submitLegacyForm(
  url: string,
  values: Record<string, string>,
) {
  const body = new URLSearchParams(values)
  const headers = new Headers({ Accept: 'text/html' })
  if (csrfToken) {
    headers.set('X-CSRF-Token', csrfToken)
  }
  await apiFetch(
    url,
    {
      method: 'POST',
      body,
      headers,
      redirect: 'follow',
    },
    'text/html',
  )
}
