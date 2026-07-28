type ErrorPayload = {
  error?: string
  message?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(message: string, status: number, code = 'REQUEST_FAILED') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

let csrfToken = ''

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

async function apiFetch(
  url: string,
  init: RequestInit = {},
  accept = 'application/json',
): Promise<Response> {
  const method = String(init.method || 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', accept)

  const effectiveCsrfToken = getCsrfToken()
  if (isUnsafeMethod(method) && effectiveCsrfToken) {
    headers.set('X-CSRF-Token', effectiveCsrfToken)
    headers.set('X-CSRFToken', effectiveCsrfToken)
  }
  if (init.body && !(init.body instanceof FormData) && !(init.body instanceof URLSearchParams)) {
    headers.set('Content-Type', 'application/json')
  }
  if (init.body instanceof FormData && effectiveCsrfToken) {
    if (!init.body.has('_csrf_token') && !init.body.has('csrf_token')) {
      init.body.append('csrf_token', effectiveCsrfToken)
    }
  }


  const response = await fetch(url, {
    ...init,
    method,
    headers,
    credentials: 'same-origin',
  })

  if (response.redirected && new URL(response.url).pathname === '/login') {
    throw new ApiError('Phiên đăng nhập đã hết hạn.', 401, 'AUTH_REQUIRED')
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

export async function submitLegacyForm(
  url: string,
  values: Record<string, string>,
) {
  const body = new URLSearchParams(values)
  const headers = new Headers({ Accept: 'text/html' })
  if (csrfToken) {
    headers.set('X-CSRF-Token', csrfToken)
  }
  const response = await fetch(url, {
    method: 'POST',
    body,
    headers,
    credentials: 'same-origin',
    redirect: 'follow',
  })
  if (!response.ok) {
    throw new ApiError(
      `Không thể hoàn tất thao tác (${response.status}).`,
      response.status,
    )
  }
}
