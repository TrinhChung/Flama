// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  extractPathname,
  isBackendRoute,
  isSafeRedirectTarget,
  performRedirect,
  resolveRedirectTarget,
} from '../redirect'

describe('Auth Redirect Utilities', () => {
  const originalLocation = window.location

  beforeEach(() => {
    delete (window as any).location
    window.location = {
      ...originalLocation,
      origin: 'http://localhost:5173',
      pathname: '/login',
      search: '',
      href: 'http://localhost:5173/login',
      assign: vi.fn(),
      replace: vi.fn(),
    } as any
  })

  afterEach(() => {
    ;(window as any).location = originalLocation
  })

  describe('extractPathname', () => {
    it('extracts pathname from relative URL', () => {
      expect(extractPathname('/oauth/authorize?client_id=123')).toBe('/oauth/authorize')
      expect(extractPathname('/study')).toBe('/study')
    })

    it('extracts pathname from absolute URL', () => {
      expect(extractPathname('http://localhost:5173/settings/profile')).toBe('/settings/profile')
    })

    it('returns empty string for empty input or invalid URL', () => {
      expect(extractPathname('')).toBe('')
    })
  })

  describe('isSafeRedirectTarget', () => {
    it('accepts safe relative paths', () => {
      expect(isSafeRedirectTarget('/study')).toBe(true)
      expect(isSafeRedirectTarget('/marketplace/decks')).toBe(true)
      expect(isSafeRedirectTarget('/oauth/authorize?client_id=test&response_type=code')).toBe(true)
      expect(isSafeRedirectTarget('/oauth/consent?client_id=test')).toBe(true)
    })

    it('rejects protocol-relative and backslash bypass targets', () => {
      expect(isSafeRedirectTarget('//evil.com')).toBe(false)
      expect(isSafeRedirectTarget('//evil.com/oauth')).toBe(false)
      expect(isSafeRedirectTarget('/\\evil.com')).toBe(false)
      expect(isSafeRedirectTarget('\\\\evil.com')).toBe(false)
      expect(isSafeRedirectTarget('\\evil.com')).toBe(false)
    })

    it('rejects dangerous URI schemes', () => {
      expect(isSafeRedirectTarget('javascript:alert(1)')).toBe(false)
      expect(isSafeRedirectTarget('data:text/html,<h1>XSS</h1>')).toBe(false)
      expect(isSafeRedirectTarget('vbscript:msgbox(1)')).toBe(false)
      expect(isSafeRedirectTarget('ftp://evil.com/payload')).toBe(false)
    })

    it('rejects root and auth loop destinations', () => {
      expect(isSafeRedirectTarget('/')).toBe(false)
      expect(isSafeRedirectTarget('/login')).toBe(false)
      expect(isSafeRedirectTarget('/login?next=/study')).toBe(false)
      expect(isSafeRedirectTarget('/register')).toBe(false)
      expect(isSafeRedirectTarget('/register?ref=123')).toBe(false)
    })

    it('accepts absolute URLs matching current origin', () => {
      expect(isSafeRedirectTarget('http://localhost:5173/study')).toBe(true)
      expect(isSafeRedirectTarget('http://localhost:5173/oauth/authorize?client_id=123')).toBe(true)
    })

    it('rejects foreign absolute URLs', () => {
      expect(isSafeRedirectTarget('https://evil.com/oauth/authorize')).toBe(false)
      expect(isSafeRedirectTarget('http://attacker.com/study')).toBe(false)
    })

    it('rejects null, undefined, and empty string', () => {
      expect(isSafeRedirectTarget(null)).toBe(false)
      expect(isSafeRedirectTarget(undefined)).toBe(false)
      expect(isSafeRedirectTarget('')).toBe(false)
      expect(isSafeRedirectTarget('   ')).toBe(false)
    })
  })

  describe('isBackendRoute', () => {
    it('identifies backend OAuth endpoints as backend routes', () => {
      expect(isBackendRoute('/oauth/authorize')).toBe(true)
      expect(isBackendRoute('/oauth/authorize?client_id=chatgpt&scope=deck:read')).toBe(true)
      expect(isBackendRoute('/oauth/token')).toBe(true)
      expect(isBackendRoute('/oauth/revoke')).toBe(true)
      expect(isBackendRoute('/oauth/register')).toBe(true)
      expect(isBackendRoute('/oauth')).toBe(true)
    })

    it('identifies /oauth/consent as React SPA route (NOT backend route)', () => {
      expect(isBackendRoute('/oauth/consent')).toBe(false)
      expect(isBackendRoute('/oauth/consent?client_id=chatgpt')).toBe(false)
      expect(isBackendRoute('/oauth/consent/status')).toBe(false)
    })

    it('identifies auth endpoints as backend routes', () => {
      expect(isBackendRoute('/auth/google')).toBe(true)
      expect(isBackendRoute('/auth/google/callback')).toBe(true)
      expect(isBackendRoute('/auth/logout')).toBe(true)
      expect(isBackendRoute('/auth')).toBe(true)
    })

    it('identifies API and metadata endpoints as backend routes', () => {
      expect(isBackendRoute('/api/identity/login')).toBe(true)
      expect(isBackendRoute('/.well-known/oauth-authorization-server')).toBe(true)
      expect(isBackendRoute('/download/deck.zip')).toBe(true)
      expect(isBackendRoute('/media/images/avatar.png')).toBe(true)
    })

    it('identifies standard SPA routes as NOT backend routes', () => {
      expect(isBackendRoute('/dashboard')).toBe(false)
      expect(isBackendRoute('/decks')).toBe(false)
      expect(isBackendRoute('/study')).toBe(false)
      expect(isBackendRoute('/browse')).toBe(false)
      expect(isBackendRoute('/statistics')).toBe(false)
      expect(isBackendRoute('/marketplace/decks')).toBe(false)
      expect(isBackendRoute('/settings/study-goals')).toBe(false)
    })

    it('handles falsy input safely', () => {
      expect(isBackendRoute(null)).toBe(false)
      expect(isBackendRoute(undefined)).toBe(false)
      expect(isBackendRoute('')).toBe(false)
    })
  })

  describe('resolveRedirectTarget', () => {
    it('prioritizes valid next parameter', () => {
      expect(
        resolveRedirectTarget('/oauth/authorize?client_id=123', '/dashboard'),
      ).toBe('/oauth/authorize?client_id=123')
      expect(resolveRedirectTarget('/study', '/marketplace')).toBe('/study')
    })

    it('falls back to redirectTo when next is invalid or missing', () => {
      expect(resolveRedirectTarget(null, '/study')).toBe('/study')
      expect(resolveRedirectTarget('//evil.com', '/study')).toBe('/study')
      expect(resolveRedirectTarget('/login', '/marketplace')).toBe('/marketplace')
    })

    it('strips /app/ prefix from redirectTo', () => {
      expect(resolveRedirectTarget(null, '/app/study')).toBe('/study')
      expect(resolveRedirectTarget('', '/app/decks')).toBe('/decks')
    })

    it('falls back to default /dashboard when both candidates are unsafe', () => {
      expect(resolveRedirectTarget(null, null)).toBe('/dashboard')
      expect(resolveRedirectTarget('//evil.com', 'javascript:alert(1)')).toBe('/dashboard')
      expect(resolveRedirectTarget('/login', '/register', '/custom-fallback')).toBe('/custom-fallback')
    })
  })

  describe('performRedirect', () => {
    it('sets window.location.href for backend routes', () => {
      const navigateMock = vi.fn()
      performRedirect('/oauth/authorize?client_id=test', navigateMock)

      expect(window.location.href).toBe('/oauth/authorize?client_id=test')
      expect(navigateMock).not.toHaveBeenCalled()
    })

    it('calls navigate for React Router SPA routes', () => {
      const navigateMock = vi.fn()
      performRedirect('/study', navigateMock)

      expect(navigateMock).toHaveBeenCalledWith('/study', { replace: true })
      expect(window.location.href).toBe('http://localhost:5173/login')
    })

    it('calls navigate for /oauth/consent (SPA consent screen)', () => {
      const navigateMock = vi.fn()
      performRedirect('/oauth/consent?client_id=test', navigateMock)

      expect(navigateMock).toHaveBeenCalledWith('/oauth/consent?client_id=test', { replace: true })
    })
  })
})
