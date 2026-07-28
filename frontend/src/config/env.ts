const ABSOLUTE_HTTP_URL = /^https?:\/\//i
const URL_SCHEME = /^[a-z][a-z\d+.-]*:/i

function normalizeApiBaseUrl(value: string | undefined): string {
  const configuredValue = String(value || '/api/v1').trim() || '/api/v1'
  const normalizedValue =
    ABSOLUTE_HTTP_URL.test(configuredValue) || configuredValue.startsWith('/')
      ? configuredValue
      : `/${configuredValue}`

  return normalizedValue.replace(/\/+$/, '') || '/'
}

function normalizeBackendOrigin(value: string | undefined): string {
  const configuredValue = String(value || '').trim()
  if (!configuredValue) return ''

  let parsed: URL
  try {
    parsed = new URL(configuredValue)
  } catch {
    throw new Error('VITE_BACKEND_ORIGIN must be an absolute HTTP(S) origin.')
  }

  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('VITE_BACKEND_ORIGIN must use HTTP or HTTPS.')
  }

  return parsed.origin
}

function apiBaseOrigin(apiBaseUrl: string): string {
  if (!ABSOLUTE_HTTP_URL.test(apiBaseUrl)) return ''
  return new URL(apiBaseUrl).origin
}

export const API_BASE_URL = normalizeApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
)

export const BACKEND_ORIGIN =
  normalizeBackendOrigin(import.meta.env.VITE_BACKEND_ORIGIN) ||
  apiBaseOrigin(API_BASE_URL)

export function resolveBackendUrl(value: string): string {
  const url = String(value || '').trim()
  if (
    !url ||
    !BACKEND_ORIGIN ||
    URL_SCHEME.test(url) ||
    url.startsWith('//') ||
    url.startsWith('#')
  ) {
    return url
  }
  if (!url.startsWith('/')) return url

  return `${BACKEND_ORIGIN}${url}`
}
