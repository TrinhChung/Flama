// @vitest-environment jsdom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n, { DEFAULT_LOCALE } from '@/shared/config/i18n'
import { fetchConsentInfo, submitConsentDecision } from '../../api/oauthConsent'
import { OAuthConsentPage, sanitizeScopeKey } from '../OAuthConsentPage'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

// Mock ResizeObserver for JSDOM
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

vi.mock('../../api/oauthConsent', () => ({
  fetchConsentInfo: vi.fn(),
  submitConsentDecision: vi.fn(),
}))

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: {
      user: {
        id: 1,
        username: 'flama_tester',
        email: 'tester@flama.vn',
      },
    },
    isLoading: false,
  }),
}))

vi.mock('@/components/ambient-background', () => ({
  AmbientBackground: () => createElement('div', { 'data-testid': 'ambient-bg' }),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('OAuthConsentPage Localization & Behavior', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  const originalLocation = window.location

  const mockConsentData = {
    client: {
      id: 1,
      client_id: 'chatgpt_flama',
      client_name: 'ChatGPT Assistant',
      client_uri: 'https://chatgpt.com',
      logo_uri: null,
      is_trusted: true,
    },
    scopes: [
      {
        id: 'deck:read',
        title: 'Xem danh mục & cấu trúc bộ thẻ',
        desc: 'Đọc danh sách các bộ thẻ flashcard, cấu trúc thư mục phân cấp và số lượng thẻ.',
      },
      {
        id: 'note:create',
        title: 'Tạo thẻ ghi nhớ flashcard mới',
        desc: 'Thêm từ vựng và thẻ mới vào bộ bài của bạn kèm các trường thông tin tự động.',
      },
    ],
    user: {
      id: 1,
      username: 'flama_tester',
      email: 'tester@flama.vn',
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    void i18n.changeLanguage(DEFAULT_LOCALE)

    delete (window as any).location
    window.location = {
      ...originalLocation,
      origin: 'http://localhost:5173',
      pathname: '/oauth/consent',
      search: '',
      href: 'http://localhost:5173/oauth/consent',
      assign: vi.fn(),
      replace: vi.fn(),
    } as any

    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    ;(window as any).location = originalLocation
  })

  async function renderPage(search = '?client_id=chatgpt_flama&scope=deck:read+note:create') {
    await act(async () => {
      root.render(
        createElement(
          QueryClientProvider,
          { client: queryClient },
          createElement(
            MemoryRouter,
            { initialEntries: [`/oauth/consent${search}`] },
            createElement(OAuthConsentPage),
          ),
        ),
      )
    })
    // Give react-query time to resolve
    await act(async () => {
      await new Promise((r) => setTimeout(r, 20))
    })
  }

  describe('sanitizeScopeKey utility', () => {
    it('normalizes scope ids by replacing hyphens and colons with underscores', () => {
      expect(sanitizeScopeKey('deck:read')).toBe('deck_read')
      expect(sanitizeScopeKey('deck-share:read')).toBe('deck_share_read')
      expect(sanitizeScopeKey('note-type:write')).toBe('note_type_write')
      expect(sanitizeScopeKey('openid')).toBe('openid')
      expect(sanitizeScopeKey('*')).toBe('wildcard')
    })
  })

  it('renders default Vietnamese content accurately', async () => {
    vi.mocked(fetchConsentInfo).mockResolvedValueOnce(mockConsentData as any)

    await renderPage()

    // Title and client
    expect(container.textContent).toContain('Cấp quyền cho')
    expect(container.textContent).toContain('ChatGPT Assistant')

    // Account badge and counts
    expect(container.textContent).toContain('Tài khoản Flama')
    expect(container.textContent).toContain('Quyền hạn được cấp phép')
    expect(container.textContent).toContain('2 quyền')

    // Scopes titles in Vietnamese
    expect(container.textContent).toContain('Xem danh mục & cấu trúc bộ thẻ')
    expect(container.textContent).toContain('Tạo thẻ ghi nhớ flashcard mới')

    // Security note
    expect(container.textContent).toContain('Bảo mật & Quyền riêng tư:')

    // Buttons
    expect(container.textContent).toContain('Từ chối')
    expect(container.textContent).toContain('Cho phép kết nối')
  })

  it('dynamically switches to technical English when language is changed to en', async () => {
    vi.mocked(fetchConsentInfo).mockResolvedValueOnce(mockConsentData as any)

    await act(async () => {
      await i18n.changeLanguage('en')
    })

    await renderPage()

    // Title and client in English
    expect(container.textContent).toContain('Authorize')
    expect(container.textContent).toContain('ChatGPT Assistant')

    // Account badge and counts in English
    expect(container.textContent).toContain('Flama Account')
    expect(container.textContent).toContain('Requested Permissions')
    expect(container.textContent).toContain('2 permissions')

    // Scopes titles in English
    expect(container.textContent).toContain('View Decks & Folder Structure')
    expect(container.textContent).toContain('Create New Flashcards')

    // Security note in English
    expect(container.textContent).toContain('Security & Privacy:')

    // Action buttons in English
    expect(container.textContent).toContain('Deny')
    expect(container.textContent).toContain('Allow connection')

    // Ensure no Vietnamese strings remain in English view
    expect(container.textContent).not.toContain('Cấp quyền cho')
    expect(container.textContent).not.toContain('Tài khoản Flama')
    expect(container.textContent).not.toContain('Cho phép kết nối')
  })

  it('provides safe 3-tier fallback for unknown custom scopes', async () => {
    const customScopeData = {
      ...mockConsentData,
      scopes: [
        {
          id: 'custom:unrecognized_tool',
          title: 'Custom Server Tool Title',
          desc: 'Custom tool description from external extension.',
        },
      ],
    }
    vi.mocked(fetchConsentInfo).mockResolvedValueOnce(customScopeData as any)

    await renderPage()

    // Renders the server-provided fallback title and description without crashing
    expect(container.textContent).toContain('Custom Server Tool Title')
    expect(container.textContent).toContain('Custom tool description from external extension.')
  })

  it('renders localized invalid request error when client_id is missing', async () => {
    await renderPage('')

    expect(container.textContent).toContain('Yêu cầu không hợp lệ')
    expect(container.textContent).toContain('Thiếu tham số client_id')

    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(container.textContent).toContain('Invalid Request')
    expect(container.textContent).toContain('Missing client_id parameter')
  })

  it('handles deny action by invoking submitConsentDecision with action deny', async () => {
    vi.mocked(fetchConsentInfo).mockResolvedValue(mockConsentData as any)
    vi.mocked(submitConsentDecision).mockResolvedValue({ redirect_url: 'https://chatgpt.com/callback?error=access_denied' } as any)

    await renderPage()

    const buttons = Array.from(container.querySelectorAll('button'))
    const denyBtn = buttons.find((b) => b.textContent?.includes('Từ chối'))
    expect(denyBtn).toBeDefined()

    await act(async () => {
      denyBtn?.click()
    })

    expect(vi.mocked(submitConsentDecision).mock.calls[0][0]).toEqual(
      expect.objectContaining({
        client_id: 'chatgpt_flama',
        action: 'deny',
      }),
    )
  })

  it('handles approve action by invoking submitConsentDecision with action approve', async () => {
    vi.mocked(fetchConsentInfo).mockResolvedValue(mockConsentData as any)
    vi.mocked(submitConsentDecision).mockResolvedValue({ redirect_url: 'https://chatgpt.com/callback?code=splendid_code' } as any)

    await renderPage()

    const buttons = Array.from(container.querySelectorAll('button'))
    const approveBtn = buttons.find((b) => b.textContent?.includes('Cho phép kết nối'))
    expect(approveBtn).toBeDefined()

    await act(async () => {
      approveBtn?.click()
    })

    expect(vi.mocked(submitConsentDecision).mock.calls[0][0]).toEqual(
      expect.objectContaining({
        client_id: 'chatgpt_flama',
        action: 'approve',
      }),
    )
  })

  it('integrates LanguageSwitcher fixed overlay on OAuthConsentPage', async () => {
    vi.mocked(fetchConsentInfo).mockResolvedValueOnce(mockConsentData as any)

    await renderPage()

    const fixedSwitcher = container.querySelector('.fixed.top-4.right-4')
    expect(fixedSwitcher).not.toBeNull()
    // LanguageSwitcher pill contains VI and EN buttons
    expect(fixedSwitcher?.textContent).toContain('VI')
    expect(fixedSwitcher?.textContent).toContain('EN')
  })
})
