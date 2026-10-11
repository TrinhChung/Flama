// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { appApi } from '@/app/api'
import { toast } from 'sonner'
import { AsbplayerTokensPage } from '../../pages/AsbplayerTokensPage'
import { YomitanTokensTab } from '../YomitanTokensTab'
import { AsbplayerTokensTab } from '../AsbplayerTokensTab'
import { useYomitanTokenCRUD } from '../../hooks/useYomitanTokenCRUD'
import { useAsbplayerTokenCRUD } from '../../hooks/useAsbplayerTokenCRUD'
import { SiteFooter } from '@/components/site-footer'
import { AppSidebar } from '@/components/app-sidebar'
import { SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import type { FrontendBootstrap } from '@/shared/types/api'
import viSettings from '@/shared/config/i18n/locales/vi/settings.json'
import enSettings from '@/shared/config/i18n/locales/en/settings.json'
import viShell from '@/shared/config/i18n/locales/vi/shell.json'
import enShell from '@/shared/config/i18n/locales/en/shell.json'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('@/app/api', () => ({ appApi: { get: vi.fn(), mutate: vi.fn(), logout: vi.fn() } }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))
vi.mock('@/config/env', () => ({
  FLAMA_CONNECT_URL: 'https://connect.example/v1/flama-connect',
  FLAMA_ANKI_CONNECT_URL: 'https://connect.example/v1/anki-connect',
}))

const mockBootstrap: FrontendBootstrap = {
  user: {
    id: 1,
    username: 'challenger_user',
    account_name: 'Empirical Challenger',
    is_admin: true,
    role: 'admin',
    roles: ['admin'],
    permissions: [],
  },
  links: {
    dashboard: '/dashboard',
    study: '/study',
    browse: '/browse',
    installed_decks: '/installed-decks',
    note_types: '/note-types',
    shared_decks: '/marketplace/decks',
    shared_note_types: '/marketplace/note-types',
    terms: '/terms',
    privacy: '/privacy',
    cookies: '/cookies',
    support: '/support',
    admin_users: '/admin/users',
  },
  support_contact_email: 'support@flama.vn',
  messages: [],
} as unknown as FrontendBootstrap

async function waitFor(assertion: () => void, timeoutMs = 2500) {
  const start = Date.now()
  let lastError: unknown
  while (Date.now() - start < timeoutMs) {
    try {
      assertion()
      return
    } catch (err) {
      lastError = err
      await act(async () => {
        await new Promise((r) => setTimeout(r, 15))
      })
    }
  }
  if (lastError) throw lastError
}

describe('Adversarial & Empirical Challenger Suite for asbplayer & Yomitan Isolation', () => {
  let root: Root
  let host: HTMLDivElement
  let client: QueryClient

  beforeEach(async () => {
    vi.clearAllMocks()
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
    await i18n.changeLanguage('vi')
    host = document.createElement('div')
    document.body.append(host)
    root = createRoot(host)
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    client.clear()
    host.remove()
  })

  it('verifies strict token isolation between Yomitan and asbplayer', async () => {
    vi.mocked(appApi.get).mockResolvedValue({
      items: [
        { id: 101, name: 'Yomitan Token Alpha', status: 'active', scopes: [], preset: 'legacy', token_prefix: 'yt_alpha' },
        { id: 102, name: 'asbplayer Text Token', status: 'active', scopes: ['note:create'], preset: 'mining-text', token_prefix: 'asb_txt' },
        { id: 103, name: 'asbplayer Media Token', status: 'active', scopes: ['note:create', 'media:write'], preset: 'mining-media', token_prefix: 'asb_med' },
        { id: 104, name: 'Unknown Custom Token', status: 'active', scopes: [], preset: 'custom', token_prefix: 'cust' },
      ],
      policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true },
    })

    function IsolationHarness() {
      const yomitanCRUD = useYomitanTokenCRUD()
      const asbplayerCRUD = useAsbplayerTokenCRUD()
      return (
        <div>
          <div data-testid="yomitan-section">
            <YomitanTokensTab hookResult={yomitanCRUD} />
          </div>
          <div data-testid="asbplayer-section">
            <AsbplayerTokensTab hookResult={asbplayerCRUD} />
          </div>
        </div>
      )
    }

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <IsolationHarness />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    await waitFor(() => {
      const yomitanSection = host.querySelector('[data-testid="yomitan-section"]')!
      const asbplayerSection = host.querySelector('[data-testid="asbplayer-section"]')!

      // Yomitan section MUST have Yomitan Token Alpha and Unknown Custom Token (legacy/custom)
      expect(yomitanSection.textContent).toContain('Yomitan Token Alpha')
      expect(yomitanSection.textContent).toContain('Unknown Custom Token')
      // Yomitan section MUST NOT have asbplayer tokens
      expect(yomitanSection.textContent).not.toContain('asbplayer Text Token')
      expect(yomitanSection.textContent).not.toContain('asbplayer Media Token')

      // asbplayer section MUST have asbplayer tokens
      expect(asbplayerSection.textContent).toContain('asbplayer Text Token')
      expect(asbplayerSection.textContent).toContain('asbplayer Media Token')
      // asbplayer section MUST NOT have Yomitan or custom tokens
      expect(asbplayerSection.textContent).not.toContain('Yomitan Token Alpha')
      expect(asbplayerSection.textContent).not.toContain('Unknown Custom Token')
    })
  })

  it('verifies AsbplayerTokensPage renders guide links and context help button with correct targets', async () => {
    vi.mocked(appApi.get).mockResolvedValue({
      items: [],
      policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true },
    })

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <AsbplayerTokensPage />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    await waitFor(() => {
      // Check ContextHelpButton
      const helpLink = host.querySelector('a[href="/guide/integrations/asbplayer"]')
      expect(helpLink).not.toBeNull()

      // Check Quick Links
      const allLinks = Array.from(host.querySelectorAll('a')).map((a) => a.getAttribute('href'))
      expect(allLinks).toContain('/guide/integrations/asbplayer')
      expect(allLinks).toContain('/guide/integrations/asbplayer#mapping')
      expect(allLinks).toContain('/guide/integrations/asbplayer#shortcuts')
    })
  })

  it('verifies SiteFooter and AppSidebar integration links for asbplayer', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <TooltipProvider>
            <SidebarProvider>
              <MemoryRouter>
                <div data-testid="footer">
                  <SiteFooter bootstrap={mockBootstrap} />
                </div>
                <div data-testid="sidebar">
                  <AppSidebar bootstrap={mockBootstrap} onLogout={vi.fn()} logoutPending={false} />
                </div>
              </MemoryRouter>
            </SidebarProvider>
          </TooltipProvider>
        </QueryClientProvider>
      )
    })

    const footer = host.querySelector('[data-testid="footer"]')!
    const footerAsbLink = footer.querySelector('a[href="/settings/asbplayer"]')
    expect(footerAsbLink).not.toBeNull()
    expect(footerAsbLink?.textContent).toContain('asbplayer')

    const sidebar = host.querySelector('[data-testid="sidebar"]')!
    const sidebarAsbLink = sidebar.querySelector('a[href="/settings/asbplayer"]')
    expect(sidebarAsbLink).not.toBeNull()
  })

  it('stress tests error handling on failed sentence mining setup and token creation validation', async () => {
    vi.mocked(appApi.get).mockResolvedValue({
      items: [],
      policy: { default_expiry_days: 180, allowed_expiry_days: [30, 90, 180, 365], allow_no_expiry: true },
    })
    vi.mocked(appApi.mutate).mockRejectedValue(new Error('Network error: 500 Internal Server Error'))

    function Harness() {
      return <AsbplayerTokensTab hookResult={useAsbplayerTokenCRUD()} />
    }

    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <Harness />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    await waitFor(() => {
      expect(host.querySelector('button')).not.toBeNull()
    })

    const buttons = Array.from(host.querySelectorAll('button'))
    const prepareBtn = buttons.find((b) => b.textContent?.includes('Chuẩn bị') || b.textContent?.includes('Prepare'))
    expect(prepareBtn).toBeDefined()

    await act(async () => {
      prepareBtn?.click()
      await new Promise((r) => setTimeout(r, 20))
    })

    expect(toast.error).toHaveBeenCalledWith('Network error: 500 Internal Server Error')

    // Empty or whitespace token name disabled check using React input event
    const nameInput = host.querySelector('#asbplayer-token-name') as HTMLInputElement
    expect(nameInput).not.toBeNull()

    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set
    await act(async () => {
      nativeSetter!.call(nameInput, '   ')
      nameInput.dispatchEvent(new Event('input', { bubbles: true }))
    })

    const createBtn = buttons.find((b) => b.textContent?.includes('Tạo') || b.textContent?.includes('Generate'))
    expect(createBtn?.hasAttribute('disabled')).toBe(true)
  })

  it('validates 100% leaf-key parity and non-empty strings for asbplayer in i18n dictionaries', () => {
    // 1. Settings dictionary
    expect(viSettings.asbplayer).toBeDefined()
    expect(enSettings.asbplayer).toBeDefined()

    function getLeafKeys(obj: Record<string, any>, prefix = ''): Record<string, string> {
      let leaves: Record<string, string> = {}
      for (const key of Object.keys(obj)) {
        const fullKey = prefix ? `${prefix}.${key}` : key
        if (typeof obj[key] === 'object' && obj[key] !== null) {
          Object.assign(leaves, getLeafKeys(obj[key], fullKey))
        } else {
          leaves[fullKey] = String(obj[key])
        }
      }
      return leaves
    }

    const viLeaves = getLeafKeys(viSettings.asbplayer, 'asbplayer')
    const enLeaves = getLeafKeys(enSettings.asbplayer, 'asbplayer')

    const viKeys = Object.keys(viLeaves).sort()
    const enKeys = Object.keys(enLeaves).sort()

    expect(viKeys).toEqual(enKeys)

    for (const key of viKeys) {
      expect(viLeaves[key].trim().length).toBeGreaterThan(0)
      expect(enLeaves[key].trim().length).toBeGreaterThan(0)
    }

    // 2. Shell dictionary
    expect(viShell.sidebar.item.asbplayer).toBe('Kết nối asbplayer')
    expect(enShell.sidebar.item.asbplayer).toBe('Connect asbplayer')
    expect(viShell.footer.link_asbplayer).toBe('Tích hợp asbplayer')
    expect(enShell.footer.link_asbplayer).toBe('asbplayer Integration')
    expect(viShell.page_titles.settings_asbplayer).toBe('Cài đặt Kết nối asbplayer')
    expect(enShell.page_titles.settings_asbplayer).toBe('asbplayer Integration')
  })
})
