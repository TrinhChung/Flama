// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n, { DEFAULT_LOCALE } from '@/shared/config/i18n'
import viMcp from '@/shared/config/i18n/locales/vi/mcp.json'
import enMcp from '@/shared/config/i18n/locales/en/mcp.json'
import { McpTokensPage } from '../../pages/McpTokensPage'
import { McpTokensManager } from '@/features/mcp/components/McpTokensManager'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

// Mock ResizeObserver for JSDOM
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

vi.mock('@/app/api', () => ({
  appApi: {
    get: vi.fn().mockImplementation((url: string) => {
      if (url === '/mcp-tokens' || url === '/api/mcp/tokens') {
        return Promise.resolve({
          items: [
            {
              id: 1,
              name: 'Claude Desktop Local',
              token_hint: 'flama_sec_claude_123',
              scopes: ['deck:read', 'note:read'],
              status: 'active',
              expires_at: '2026-12-31T23:59:59Z',
              last_used_at: '2026-10-01T12:00:00Z',
              created_at: '2026-01-01T00:00:00Z',
            },
          ],
          policy: {
            default_expiry_days: 180,
            allowed_expiry_days: [30, 90, 180, 365],
            allow_no_expiry: true,
            scopes: [],
          },
        })
      }
      if (url === '/api/oauth/endpoints-info') {
        return Promise.resolve({
          base_url: 'http://localhost:4789',
          auth_url: 'http://localhost:4789/oauth/authorize',
          token_url: 'http://localhost:4789/oauth/token',
          resource_url: 'http://localhost:4789/api/mcp',
          userinfo_url: 'http://localhost:4789/oauth/userinfo',
          openid_config_url: 'http://localhost:4789/.well-known/openid-configuration',
          scopes: ['deck:read', 'note:create'],
          scopes_string: 'deck:read note:create',
          default_client: {
            id: 1,
            client_id: 'chatgpt_flama',
            client_name: 'Flama Flashcard',
            client_secret: 'flama_sec_test_123',
            redirect_uris: ['https://chatgpt.com/api/actions/callback'],
            is_default: true,
          },
        })
      }
      return Promise.resolve({ items: [] })
    }),
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: {
      user: {
        id: 1,
        email: 'test@example.com',
        is_admin: true,
      },
    },
  }),
}))

describe('MCP Localization Suite (Vietnamese & Technical English)', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(async () => {
    localStorage.clear()
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    await act(async () => {
      await i18n.changeLanguage(DEFAULT_LOCALE)
    })
  })

  afterEach(async () => {
    await act(async () => {
      root.unmount()
      await i18n.changeLanguage(DEFAULT_LOCALE)
    })
    container.remove()
    localStorage.clear()
  })

  const waitForContent = async (text: string, maxAttempts = 30) => {
    for (let i = 0; i < maxAttempts; i++) {
      if (container.textContent?.includes(text)) return
      await act(async () => {
        await new Promise((r) => setTimeout(r, 20))
      })
    }
  }

  it('verifies that vi and en mcp locale files have identical key sets recursively', () => {
    function extractKeys(obj: Record<string, unknown>, prefix = ''): string[] {
      return Object.entries(obj).flatMap(([key, val]) => {
        const fullKey = prefix ? `${prefix}.${key}` : key
        if (val && typeof val === 'object' && !Array.isArray(val)) {
          return extractKeys(val as Record<string, unknown>, fullKey)
        }
        return [fullKey]
      })
    }

    const viKeys = extractKeys(viMcp).sort()
    const enKeys = extractKeys(enMcp).sort()

    expect(viKeys).toEqual(enKeys)
  })

  it('renders publication-grade technical English on McpTokensPage when language is en', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <McpTokensPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    await waitForContent('AI Integration via Model Context Protocol (MCP)')

    // Verify English titles & descriptions
    expect(container.textContent).toContain('AI Integration via Model Context Protocol (MCP)')
    expect(container.textContent).toContain('Connect ChatGPT, Cursor, and AI assistants')
    expect(container.textContent).toContain('Connect ChatGPT')
    expect(container.textContent).toContain('Recommended')
    expect(container.textContent).toContain('API Access Tokens & Permissions')
    expect(container.textContent).toContain('Setup Guide')
  })

  it('renders technical English tokens manager UI when language is en', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <McpTokensManager mode="user" />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    await waitForContent('Manage MCP Access Tokens')

    // Verify English stats & headers
    expect(container.textContent).toContain('Manage MCP Access Tokens')
    expect(container.textContent).toContain('Total Tokens')
    expect(container.textContent).toContain('Active Tokens')
    expect(container.textContent).toContain('Expired / Revoked')
    expect(container.textContent).toContain('Create New Token')
    expect(container.textContent).toContain('Token Name')
    expect(container.textContent).toContain('Permissions (Scopes)')
    expect(container.textContent).toContain('Actions')
  })

  it('dynamically re-renders UI between Vietnamese and English without layout corruption', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <McpTokensPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    await waitForContent('Kết nối AI qua Model Context Protocol (MCP)')
    expect(container.textContent).toContain('Kết nối AI qua Model Context Protocol (MCP)')
    expect(container.textContent).toContain('1. Kết nối ChatGPT')

    // Switch to English
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    await waitForContent('AI Integration via Model Context Protocol (MCP)')
    expect(container.textContent).toContain('AI Integration via Model Context Protocol (MCP)')
    expect(container.textContent).toContain('1. Connect ChatGPT')

    // Switch back to Vietnamese
    await act(async () => {
      await i18n.changeLanguage('vi')
    })

    await waitForContent('Kết nối AI qua Model Context Protocol (MCP)')
    expect(container.textContent).toContain('Kết nối AI qua Model Context Protocol (MCP)')
  })
})
