import { BACKEND_ORIGIN, resolveBackendUrl } from '@/config/env'

const URL_SCHEME = /^[a-z][a-z\d+.-]*:/i

/**
 * Extracts pathname safely from a relative or absolute URL string.
 */
export function extractPathname(url: string): string {
  if (!url) return ''
  try {
    const base =
      typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin
        : 'http://localhost'
    const parsed = new URL(url, base)
    return parsed.pathname
  } catch {
    return ''
  }
}

/**
 * Validates that a redirection candidate is safe from open redirect attacks
 * and avoids circular loops.
 */
export function isSafeRedirectTarget(target: string | null | undefined): boolean {
  if (!target) return false
  const trimmed = target.trim()
  if (!trimmed) return false

  // Disallow protocol-relative or backslash bypasses
  if (trimmed.startsWith('//') || trimmed.startsWith('/\\') || trimmed.startsWith('\\')) {
    return false
  }

  // Handle absolute HTTP(S) URLs
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    try {
      const currentOrigin =
        typeof window !== 'undefined' && window.location?.origin
          ? window.location.origin
          : ''
      const parsed = new URL(trimmed, currentOrigin || 'http://localhost')
      const isAllowedOrigin =
        (currentOrigin && parsed.origin === currentOrigin) ||
        (BACKEND_ORIGIN && parsed.origin === BACKEND_ORIGIN)

      if (!isAllowedOrigin) return false

      const pathname = parsed.pathname
      return pathname !== '/' && pathname !== '/login' && pathname !== '/register'
    } catch {
      return false
    }
  }

  // Disallow non-http schemes (e.g. javascript:, data:, vbscript:)
  if (URL_SCHEME.test(trimmed)) {
    return false
  }

  // Relative path must start with '/'
  if (!trimmed.startsWith('/')) {
    return false
  }

  const pathname = extractPathname(trimmed)
  return pathname !== '/' && pathname !== '/login' && pathname !== '/register'
}

/**
 * Checks if the target path is handled by Flask backend rather than React Router SPA.
 */
export function isBackendRoute(target: string | null | undefined): boolean {
  if (!target) return false
  const pathname = extractPathname(target.trim())

  // /oauth/consent is handled by the React SPA
  if (pathname === '/oauth/consent' || pathname.startsWith('/oauth/consent/')) {
    return false
  }

  // All other /oauth/* routes are Flask backend endpoints
  if (pathname === '/oauth' || pathname.startsWith('/oauth/')) {
    return true
  }

  // Backend authentication routes
  if (pathname === '/auth' || pathname.startsWith('/auth/')) {
    return true
  }

  // Backend API and system endpoints
  if (
    pathname === '/api' ||
    pathname.startsWith('/api/') ||
    pathname.startsWith('/.well-known/') ||
    pathname.startsWith('/download/') ||
    pathname.startsWith('/media/')
  ) {
    return true
  }

  return false
}

/**
 * Resolves the primary redirection target, prioritizing query param 'next',
 * then backend response 'redirect_to', falling back to '/dashboard'.
 */
export function resolveRedirectTarget(
  nextCandidate?: string | null,
  redirectToCandidate?: string | null,
  fallback = '/dashboard',
): string {
  if (nextCandidate && isSafeRedirectTarget(nextCandidate)) {
    return nextCandidate.trim()
  }

  if (redirectToCandidate) {
    let candidate = redirectToCandidate.trim()
    if (candidate.startsWith('/app/')) {
      candidate = candidate.slice('/app'.length)
    }
    if (isSafeRedirectTarget(candidate)) {
      return candidate
    }
  }

  return fallback
}

/**
 * Dispatches the redirection: window.location.href for backend routes,
 * navigate() for React Router SPA routes.
 */
export function performRedirect(
  target: string,
  navigate: (to: string, options?: { replace?: boolean }) => void,
): void {
  if (isBackendRoute(target)) {
    window.location.href = resolveBackendUrl(target)
  } else {
    navigate(target, { replace: true })
  }
}
