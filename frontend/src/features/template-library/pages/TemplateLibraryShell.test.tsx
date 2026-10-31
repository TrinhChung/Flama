// @vitest-environment jsdom
import '@/shared/config/i18n'
import { act, type ComponentType } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type { FrontendBootstrap } from '@/shared/types/api'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const mocks = vi.hoisted(() => ({
  bootstrap: { data: null as FrontendBootstrap | null, isPending: false },
  router: null as ReturnType<typeof import('react-router-dom')['createBrowserRouter']> | null,
}))

// Retain the actual browser router and route matching, and capture it only for
// navigation/cleanup; App's router remains private in production.
vi.mock('react-router-dom', async (original) => {
  const actual = await original<typeof import('react-router-dom')>()
  return { ...actual, createBrowserRouter: (...args: Parameters<typeof actual.createBrowserRouter>) => {
    const router = actual.createBrowserRouter(...args)
    mocks.router = router
    return router
  } }
})
vi.mock('@/shared/api/bootstrap', () => ({ useBootstrap: () => mocks.bootstrap }))
vi.mock('@/app/layouts/AppLayout', async () => {
  const { Outlet } = await import('react-router-dom')
  const { AppSidebar } = await import('@/components/app-sidebar')
  const { SidebarProvider } = await import('@/components/ui/sidebar')
  const { TooltipProvider } = await import('@/components/ui/tooltip')
  return { AppLayout: () => <TooltipProvider><SidebarProvider><AppSidebar bootstrap={mocks.bootstrap.data!} onLogout={() => {}} logoutPending={false} /><main><Outlet /></main></SidebarProvider></TooltipProvider> }
})
// Keep the real feature barrel: App's named lazy imports must resolve through
// the shipped index.ts. Only page internals are replaced to avoid API traffic.
vi.mock('../pages/TemplateLibraryPage', () => ({ TemplateLibraryPage: () => <h1>Template library route</h1> }))
vi.mock('../pages/TemplateDetailPage', async () => {
  const { useParams } = await import('react-router-dom')
  return { TemplateDetailPage: () => <h1>Template detail {useParams().id}</h1> }
})
vi.mock('@/pages/installed-deck-templates', async () => {
  const { useParams } = await import('react-router-dom')
  return { InstallTemplatesPage: () => <h1>Install templates {useParams().installId}</h1> }
})
vi.mock('@/pages/note-types', () => ({ NoteTypeManagerPage: () => <h1>Note types route</h1> }))
vi.mock('@/features/note-types/pages/NoteTypeDetailPage', async () => {
  const { useParams } = await import('react-router-dom')
  return { NoteTypeDetailPage: () => <h1>Note type detail {useParams().id}</h1> }
})
vi.mock('@/features/auth/pages/LoginPage', () => ({ LoginPage: () => <h1>Login route</h1> }))
vi.mock('@/pages/LandingPage', () => ({ LandingPage: () => <h1>Landing route</h1> }))

let App: ComponentType
let root: Root
let host: HTMLDivElement
const fetchMock = vi.fn()
function bootstrap(): FrontendBootstrap {
  return { api_version: '1', csrf_token: '', messages: [], support_contact_email: '',
    user: { id: 7, username: 'reviewer', email: 'reviewer@example.test', timezone: 'UTC', is_admin: false, role: null },
    links: { react_root: '/', dashboard: '/dashboard', statistics: '/statistics', legacy_dashboard: '/dashboard', browse: '/browse', study: '/study', note_types: '/flashcards/note-types', installed_decks: '/installed-decks', shared_decks: '/marketplace/decks', shared_note_types: '/marketplace/note-types', orders: '/orders', support: '/support', terms: '/terms', privacy: '/privacy', cookies: '/cookies', admin_users: null, admin_payments: null, admin_tts: null },
  }
}
async function expectRoute(text: string) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (host.querySelector('main h1')?.textContent === text) return
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 25)) })
  }
  expect(host.querySelector('main h1')?.textContent).toBe(text)
}
async function navigate(path: string, expected: string) {
  await act(async () => { await mocks.router!.navigate(path) })
  await expectRoute(expected)
}
beforeAll(async () => {
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn(), addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: vi.fn() })))
  window.history.replaceState(null, '', '/card-templates')
  App = (await import('@/App')).default
}, 30000)
beforeEach(async () => {
  mocks.bootstrap = { data: bootstrap(), isPending: false }
  fetchMock.mockClear()
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
  await act(async () => root.render(<App />))
})
afterEach(async () => { await act(async () => root.unmount()); host.remove() })
afterAll(() => { mocks.router?.dispose(); vi.unstubAllGlobals() })

describe('template routes in the application shell', { timeout: 15000 }, () => {
  it('renders named library/detail/install pages and keeps NoteType routes and sidebar links', async () => {
    await navigate('/card-templates', 'Template library route')
    const templateLink = host.querySelector<HTMLAnchorElement>('a[href="/card-templates"]')
    expect(templateLink).not.toBeNull()
    expect(templateLink?.textContent?.trim()).toBeTruthy()
    expect(templateLink?.getAttribute('aria-current')).toBe('page')
    expect(host.querySelector('a[href="/flashcards/note-types"]')).not.toBeNull()
    expect(host.querySelector('a[href="/installed-decks"]')).not.toBeNull()
    await navigate('/card-templates/tpl-1', 'Template detail tpl-1')
    await navigate('/installed-decks/install-1/templates', 'Install templates install-1')
    await navigate('/note-types', 'Note types route')
    await navigate('/flashcards/note-types/nt-1', 'Note type detail nt-1')
    // The real sidebar link returns to the standalone library rather than
    // the existing NoteType manager or the installed-deck listing.
    await act(async () => host.querySelector<HTMLAnchorElement>('a[href="/card-templates"]')!.click())
    await expectRoute('Template library route')
    expect(window.location.pathname).toBe('/card-templates')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('keeps all new routes behind the real authentication guard', async () => {
    mocks.bootstrap = { data: { ...bootstrap(), user: null }, isPending: false }
    for (const path of ['/card-templates', '/card-templates/tpl-private', '/installed-decks/install-private/templates']) {
      await navigate(path, 'Login route')
      expect(mocks.router!.state.location.pathname).toBe('/login')
      expect(new URLSearchParams(mocks.router!.state.location.search).get('next')).toBe(path)
      expect(host.textContent).not.toContain('Template detail tpl-private')
      expect(host.textContent).not.toContain('Install templates install-private')
    }
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
