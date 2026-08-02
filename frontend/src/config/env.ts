const ABSOLUTE_HTTP_URL = /^https?:\/\//i
const URL_SCHEME = /^[a-z][a-z\d+.-]*:/i

function normalizeApiBaseUrl(value: string | undefined): string {
  const configuredValue = String(value || '/api').trim() || '/api'
  const normalizedValue =
    ABSOLUTE_HTTP_URL.test(configuredValue) || configuredValue.startsWith('/')
      ? configuredValue
      : `/${configuredValue}`

  return normalizedValue.replace(/\/+$/, '') || '/'
}

function apiBaseOrigin(apiBaseUrl: string): string {
  if (!ABSOLUTE_HTTP_URL.test(apiBaseUrl)) return ''
  return new URL(apiBaseUrl).origin
}

export const API_BASE_URL = normalizeApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
)

export const BACKEND_ORIGIN = apiBaseOrigin(API_BASE_URL)

const DEFAULT_FLAMA_CONNECT_URL = import.meta.env.DEV
  ? 'http://127.0.0.1:4790/v1/flama-connect'
  : 'https://flama-connect.stmtp.com/v1/flama-connect'

export const FLAMA_CONNECT_URL = String(
  import.meta.env.VITE_FLAMA_CONNECT_URL || DEFAULT_FLAMA_CONNECT_URL,
).trim()

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
