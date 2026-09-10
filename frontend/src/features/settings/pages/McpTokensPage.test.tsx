// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { McpTokensPage } from './McpTokensPage'

// Mock appApi
vi.mock('@/app/api', () => ({
  appApi: {
    get: vi.fn().mockImplementation((url: string) => {
      if (url === '/mcp-tokens' || url === '/api/mcp/tokens') {
        return Promise.resolve({
          items: [],
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
      if (url === '/api/oauth/clients') {
        return Promise.resolve({ items: [] })
      }
      if (url === '/api/oauth/connected-apps') {
        return Promise.resolve({ items: [] })
      }
      return Promise.resolve({})
    }),
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue({}),
  },
}))

// Mock useBootstrap
vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: {
      user: {
        id: 1,
        email: 'test@example.com',
        is_admin: false,
      },
    },
  }),
}))

describe('McpTokensPage Component', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    localStorage.clear()
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
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

  it('renders prominent segmented tabs with ChatGPT as the default active tab', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <McpTokensPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    await waitForContent('1. Kết nối ChatGPT')

    // Tabs should be clearly present and prominent
    expect(container.textContent).toContain('1. Kết nối ChatGPT')
    expect(container.textContent).toContain('Khuyên dùng')
    expect(container.textContent).toContain('2. Quản lý Quyền & Token API')

    // ChatGPT 5-step guide should be rendered by default
    expect(container.textContent).toContain('Hướng Dẫn 5 Bước Kết Nối ChatGPT')
    expect(container.textContent).toContain('Bật Chế độ Nhà phát triển (Developer Mode) trên ChatGPT')
    expect(container.textContent).toContain('Mở kho Plugin và chọn "Tự tạo plugin của bạn"')
    expect(container.textContent).toContain('Dán Đường dẫn Máy chủ Flama (Server URL)')
    expect(container.textContent).toContain('Cấu hình Nâng cao (Authentication: OAuth)')
    expect(container.textContent).toContain('Bấm Lưu & Đồng ý Điều Khoản Cấp Quyền')
  })

  it('contains Developer Mode warning for ChatGPT and quick copy parameters', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <McpTokensPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    await waitForContent('Flama Plugin đang trong giai đoạn thử nghiệm')

    expect(container.textContent).toContain('Flama Plugin đang trong giai đoạn thử nghiệm')
    expect(container.textContent).toContain('Cần bật Chế độ nhà phát triển')
    expect(container.textContent).toContain('Bảng Tóm Tắt Nhanh 4 Thông Số')
  })
})
