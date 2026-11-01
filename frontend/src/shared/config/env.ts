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
  : 'https://connect.flama.vn/v1/flama-connect'

export const FLAMA_CONNECT_URL = String(
  import.meta.env.VITE_FLAMA_CONNECT_URL || DEFAULT_FLAMA_CONNECT_URL,
).trim()

export const FLAMA_ANKI_CONNECT_URL = String(
  import.meta.env.VITE_FLAMA_ANKI_CONNECT_URL || FLAMA_CONNECT_URL.replace(/\/v1\/flama-connect\/?$/, '/v1/anki-connect'),
).trim()

const DEFAULT_FLAMA_MCP_URL = import.meta.env.DEV
  ? 'http://127.0.0.1:4790/v1/mcp'
  : 'https://connect.flama.vn/v1/mcp'

export const FLAMA_MCP_URL = String(
  import.meta.env.VITE_FLAMA_MCP_URL || DEFAULT_FLAMA_MCP_URL,
).trim()

// Media is served straight from the flama-media gateway; development keeps the backend.
const DEFAULT_MEDIA_BASE_URL = import.meta.env.DEV ? '' : 'https://media.flama.vn'

export const MEDIA_BASE_URL = String(
  import.meta.env.VITE_MEDIA_BASE_URL ?? DEFAULT_MEDIA_BASE_URL,
).trim().replace(/\/+$/, '')

export const MEDIA_ORIGIN = apiBaseOrigin(MEDIA_BASE_URL)

const MEDIA_PATH_RE = /^\/?(?:media\/)?(?:store|proxy|library)\/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/
const BARE_HASH_OR_UUID_RE = /^(?:[0-9a-f]{64}|[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/i
const BARE_STROKE_KEY_RE = /^stroke_[a-zA-Z0-9_-]+(?:\.svg)?$/
const AVATAR_PATH_RE = /^\/?(?:static\/uploads\/avatars\/|uploads\/avatars\/|avatars\/)([A-Za-z0-9_.-]+)$/

/** Absolute URL for a stored media path; other values resolve like backend URLs. */
export function resolveMediaUrl(value: string | null | undefined): string {
  const url = String(value || '').trim()
  if (!url) return ''

  if (
    URL_SCHEME.test(url) ||
    url.startsWith('//') ||
    url.startsWith('#')
  ) {
    return url
  }

  // 1. Bare SHA-256 or UUID -> /store/<id>
  if (BARE_HASH_OR_UUID_RE.test(url)) {
    const targetPath = `/store/${url}`
    if (MEDIA_ORIGIN) return `${MEDIA_ORIGIN}${targetPath}`
    return resolveBackendUrl(targetPath)
  }

  // 2. Bare Kanji / Hanzi stroke SVG key -> /store/<key>
  if (BARE_STROKE_KEY_RE.test(url)) {
    const targetPath = `/store/${url}`
    if (MEDIA_ORIGIN) return `${MEDIA_ORIGIN}${targetPath}`
    return resolveBackendUrl(targetPath)
  }

  // 3. Stored media paths (/store/..., store/..., /media/proxy/..., media/proxy/..., /media/library/..., media/library/...)
  if (MEDIA_PATH_RE.test(url)) {
    const targetPath = url.startsWith('/') ? url : `/${url}`
    if (MEDIA_ORIGIN) return `${MEDIA_ORIGIN}${targetPath}`
    return resolveBackendUrl(targetPath)
  }

  // 4. User avatars (/static/uploads/avatars/..., uploads/avatars/..., avatars/...)
  const avatarMatch = url.match(AVATAR_PATH_RE)
  if (avatarMatch) {
    const targetPath = `/static/uploads/avatars/${avatarMatch[1]}`
    const staticBase = BACKEND_ORIGIN || MEDIA_ORIGIN || ''
    return staticBase ? `${staticBase}${targetPath}` : targetPath
  }

  // 5. Fallback for other paths (e.g. /media/staged/..., /static/images/...)
  return resolveBackendUrl(url.startsWith('/') ? url : `/${url}`)
}

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
