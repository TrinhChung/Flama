// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { YomitanTokensPage } from '../../pages/YomitanTokensPage'
import { AsbplayerTokensPage } from '../../pages/AsbplayerTokensPage'
import { McpTokensPage } from '../../pages/McpTokensPage'
import { McpValueIntro } from '../mcp/McpValueIntro'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('@/app/api', () => ({
  appApi: {
    get: vi.fn().mockImplementation((url: string) => {
      if (url === '/mcp-tokens' || url === '/api/mcp/tokens') {
        return Promise.resolve({
          items: [
            {
              id: 1,
              name: 'Test MCP Token',
              status: 'active',
              scopes: ['deck:read'],
              created_at: '2026-10-12T00:00:00Z',
              expires_at: null,
            },
          ],
          policy: {
            default_expiry_days: 180,
            allowed_expiry_days: [30, 90, 180, 365],
            allow_no_expiry: true,
            scopes: ['deck:read', 'note:create'],
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
      if (url === '/api/oauth/clients' || url === '/api/oauth/connected-apps') {
        return Promise.resolve({ items: [] })
      }
      if (url === '/integration-tokens' || url === '/api/v1/integration-tokens') {
        return Promise.resolve({
          items: [
            {
              id: 1,
              name: 'Test Yomitan Token',
              status: 'active',
              scopes: [],
              preset: 'legacy',
              token_prefix: 'yt_test',
              created_at: '2026-10-12T00:00:00Z',
            },
          ],
          policy: {
            default_expiry_days: 180,
            allowed_expiry_days: [30, 90, 180, 365],
            allow_no_expiry: true,
          },
        })
      }
      return Promise.resolve({ items: [] })
    }),
    mutate: vi.fn().mockResolvedValue({}),
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

describe('Adversarial 3-Tab Architecture & Content Isolation Verification', () => {
  let root: Root
  let host: HTMLDivElement
  let client: QueryClient

  beforeEach(async () => {
    vi.clearAllMocks()
    localStorage.clear()
    await i18n.changeLanguage('vi')
    host = document.createElement('div')
    document.body.append(host)
    root = createRoot(host)
    client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
  })

  afterEach(async () => {
    await act(async () => {
      root.unmount()
    })
    client.clear()
    host.remove()
    localStorage.clear()
  })

  const waitForAssertion = async (fn: () => void, timeoutMs = 2500) => {
    const start = Date.now()
    let lastErr: unknown
    while (Date.now() - start < timeoutMs) {
      try {
        fn()
        return
      } catch (e) {
        lastErr = e
        await act(async () => {
          await new Promise((r) => setTimeout(r, 20))
        })
      }
    }
    if (lastErr) throw lastErr
  }

  const clickTab = async (element: HTMLElement) => {
    await act(async () => {
      element.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0 }))
      element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }))
      element.click()
    })
  }

  it('verifies McpValueIntro standalone onStartSetup callback and presence/absence of CTA', async () => {
    const onStartSetup = vi.fn()
    await act(async () => {
      root.render(<McpValueIntro onStartSetup={onStartSetup} />)
    })

    // Check title and content
    expect(host.textContent).toContain('Gia sư AI riêng cho Flama')
    expect(host.textContent).toContain('Tại sao nên kết nối Trợ lý AI cùng Flama?')

    // CTA button exists
    const ctaBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bắt đầu kết nối tiện ích'),
    )
    expect(ctaBtn).toBeDefined()

    // Clicking CTA fires onStartSetup
    act(() => {
      ctaBtn?.click()
    })
    expect(onStartSetup).toHaveBeenCalledTimes(1)

    // Render without onStartSetup: CTA button must NOT be rendered
    await act(async () => {
      root.render(<McpValueIntro />)
    })
    const ctaAbsent = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bắt đầu kết nối tiện ích'),
    )
    expect(ctaAbsent).toBeUndefined()
  })

  it('YomitanTokensPage: strictly enforces 3-Tab DOM isolation, removes quick links, and validates CTA navigation', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <YomitanTokensPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    await waitForAssertion(() => {
      expect(host.textContent).toContain('Bậc thầy đọc hiểu')
    })

    // 1. Visual noise removal: Floating quick links bar must NOT exist
    expect(host.textContent).not.toContain('Tra cứu nhanh:')
    expect(host.textContent).not.toContain('quick_links_label')

    // 2. Tab 1 is active by default:
    // Tab 1 contains ValueIntro and FeatureHighlights
    expect(host.textContent).toContain('Tại sao bạn nên kết hợp Yomitan cùng Flama?')
    expect(host.textContent).toContain('Tra từ 0.1s')
    expect(host.textContent).toContain('Tạo thẻ 1-Click')

    // Tab 1 must NOT contain token creation input, token table, or markers table
    expect(host.querySelector('#connect-token-name')).toBeNull()
    expect(host.textContent).not.toContain('Bảng Tra Cứu 55 Field Markers Tích Hợp')

    // CTA button must be present in Tab 1
    const ctaBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đi đến Cài đặt & Tạo Token kết nối'),
    )
    expect(ctaBtn).toBeTruthy()

    // 3. Click CTA button -> transitions to Tab 2 (tokens)
    await act(async () => {
      ctaBtn?.click()
    })

    await waitForAssertion(() => {
      expect(host.querySelector('#connect-token-name')).not.toBeNull()
    })

    // In Tab 2:
    // Token creation input and token management exist
    expect(host.querySelector('#connect-token-name')).not.toBeNull()
    expect(host.textContent).toContain('Tạo API Token Flama Connect')
    expect(host.textContent).toContain('Danh sách Token đã tạo')

    // In Tab 2: Markers explorer from Tab 3 must NOT be rendered
    expect(host.textContent).not.toContain('Bảng Tra Cứu 55 Field Markers Tích Hợp')

    // 4. Click Tab 3 (guide)
    const tabs = Array.from(host.querySelectorAll<HTMLButtonElement>('button[role="tab"], [data-slot="tabs-trigger"]'))
    const guideTrigger = tabs.find((b) => b.textContent?.includes('Hướng dẫn & Tra cứu'))
    expect(guideTrigger).toBeTruthy()

    await clickTab(guideTrigger!)

    await waitForAssertion(() => {
      expect(host.textContent).toContain('Tải Tiện Ích Yomitan Chính Thức')
      expect(host.textContent).toContain('Bảng Tra Cứu 55 Field Markers Tích Hợp')
      expect(host.textContent).toContain('Kiwi Browser')
    })

    // In Tab 3: Token creation input must NOT exist
    expect(host.querySelector('#connect-token-name')).toBeNull()
  })

  it('AsbplayerTokensPage: strictly enforces 3-Tab DOM isolation, removes quick links, and validates CTA navigation', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <AsbplayerTokensPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    await waitForAssertion(() => {
      expect(host.textContent).toContain('Cao thủ luyện nghe')
    })

    // 1. Visual noise removal: Quick links bar must NOT exist
    expect(host.textContent).not.toContain('Tra cứu nhanh:')

    // 2. Tab 1 is active by default
    expect(host.textContent).toContain('Tại sao nên kết hợp asbplayer cùng Flama?')
    expect(host.textContent).toContain('Video & Anime Mining')
    expect(host.textContent).toContain('Audio & Ảnh 1-Click')

    // Tab 1 must NOT contain token creation input, token table, or mapping table
    expect(host.querySelector('#asbplayer-token-name')).toBeNull()
    expect(host.textContent).not.toContain('Bảng Quy Chuẩn Ánh Xạ 7 Trường Dữ Liệu')

    // CTA button exists in Tab 1
    const ctaBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đi đến Cài đặt & Tạo Token kết nối'),
    )
    expect(ctaBtn).toBeTruthy()

    // 3. Click CTA button -> transitions to Tab 2 (tokens)
    await act(async () => {
      ctaBtn?.click()
    })

    await waitForAssertion(() => {
      expect(host.querySelector('#asbplayer-token-name')).not.toBeNull()
    })

    // In Tab 2:
    expect(host.querySelector('#asbplayer-token-name')).not.toBeNull()
    expect(host.textContent).toContain('Tạo API Token asbplayer (Flama Connect)')
    expect(host.textContent).toContain('Chuẩn bị deck và model')

    // In Tab 2: 7-field mapping table from Tab 3 must NOT be rendered
    expect(host.textContent).not.toContain('Bảng Quy Chuẩn Ánh Xạ 7 Trường Dữ Liệu')

    // 4. Click Tab 3 (guide)
    const tabs = Array.from(host.querySelectorAll<HTMLButtonElement>('button[role="tab"], [data-slot="tabs-trigger"]'))
    const guideTrigger = tabs.find((b) => b.textContent?.includes('Hướng dẫn & Tra cứu'))
    expect(guideTrigger).toBeTruthy()

    await clickTab(guideTrigger!)

    await waitForAssertion(() => {
      expect(host.textContent).toContain('Tải Tiện Ích & Trình Phát asbplayer')
      expect(host.textContent).toContain('Bảng Quy Chuẩn Ánh Xạ 7 Trường Dữ Liệu')
      expect(host.textContent).toContain('Phím Tắt Khai Thác & Điều Hướng Video')
    })

    // In Tab 3: Token creation input must NOT exist
    expect(host.querySelector('#asbplayer-token-name')).toBeNull()
  })

  it('McpTokensPage: strictly enforces 3-Tab DOM isolation, removes quick links and docs footer, and validates CTA navigation', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <McpTokensPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    await waitForAssertion(() => {
      expect(host.textContent).toContain('Gia sư AI riêng cho Flama')
    })

    // 1. Visual noise removal: Quick links bar and docs strip must NOT exist
    expect(host.textContent).not.toContain('Tra cứu nhanh:')
    expect(host.textContent).not.toContain('docs_strip')

    // 2. Tab 1 is active by default
    expect(host.textContent).toContain('Tại sao nên kết nối Trợ lý AI cùng Flama?')
    expect(host.textContent).toContain('Không sợ rò rỉ dữ liệu cá nhân')
    expect(host.textContent).toContain('Tra cứu Marketplace an toàn')
    expect(host.textContent).toContain('Tích hợp trợ lý AI 1 chạm')

    // Tab 1 must NOT contain personal access token form or IDE code snippets
    expect(host.textContent).not.toContain('Tạo MCP Access Token mới')
    expect(host.textContent).not.toContain('claude_desktop_config.json')

    // CTA button exists in Tab 1
    const ctaBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bắt đầu kết nối tiện ích'),
    )
    expect(ctaBtn).toBeTruthy()

    // 3. Click CTA button -> transitions to Tab 2 (setup)
    await act(async () => {
      ctaBtn?.click()
    })

    await waitForAssertion(() => {
      expect(host.textContent).toContain('Phương Thức Kết Nối AI')
      expect(host.textContent).toContain('1. Kết nối ChatGPT')
      expect(host.textContent).toContain('Hướng Dẫn 5 Bước Kết Nối ChatGPT')
    })

    // In Tab 2: Switch to Personal Tokens subtab (2. Quản lý Quyền & Token API)
    const tokensSubtabTrigger = Array.from(host.querySelectorAll<HTMLButtonElement>('button[role="tab"]')).find((b) =>
      b.textContent?.includes('2. Quản lý Quyền & Token API'),
    )
    expect(tokensSubtabTrigger).toBeTruthy()

    await clickTab(tokensSubtabTrigger!)

    await waitForAssertion(() => {
      expect(host.textContent).toContain('Tạo MCP Access Token mới')
      expect(host.textContent).toContain('Danh sách Token & Secrets')
    })

    // In Tab 2: Claude Desktop snippets from Tab 3 must NOT be rendered
    expect(host.textContent).not.toContain('claude_desktop_config.json')

    // 4. Click Tab 3 (guide)
    const topTabs = Array.from(host.querySelectorAll<HTMLButtonElement>('button[role="tab"], [data-slot="tabs-trigger"]'))
    const guideTrigger = topTabs.find((b) => b.textContent?.includes('3. Hướng dẫn & Tra cứu'))
    expect(guideTrigger).toBeTruthy()

    await clickTab(guideTrigger!)

    await waitForAssertion(() => {
      expect(host.textContent).toContain('Cấu hình Ứng dụng & IDE')
      expect(host.textContent).toContain('Danh mục Công cụ & Prompts')
      expect(host.textContent).toContain('Khắc phục Sự cố MCP')
    })

    // In Tab 3: Token creation form and tables must NOT exist
    expect(host.textContent).not.toContain('Tạo MCP Access Token mới')
  })
})
