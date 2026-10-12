// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { YomitanGuideTab } from '../yomitan/YomitanGuideTab'
import { AsbplayerGuideTab } from '../asbplayer/AsbplayerGuideTab'
import { McpGuideTab } from '../mcp/McpGuideTab'
import { McpTokensPage } from '../../pages/McpTokensPage'

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
          default_client: null,
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

describe('Challenger 2 Empirical Verification: Zero Hardcoded Vietnamese in English Mode', () => {
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
      await i18n.changeLanguage('en')
    })
  })

  afterEach(async () => {
    await act(async () => {
      root.unmount()
      await i18n.changeLanguage('vi')
    })
    container.remove()
    localStorage.clear()
  })

  it('YomitanGuideTab: must not contain hardcoded Vietnamese text when language is en', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <YomitanGuideTab />
        </MemoryRouter>
      )
    })

    const text = container.textContent || ''
    // These strings are known hardcoded Vietnamese strings in YomitanGuideTab
    const violations: string[] = []
    if (text.includes('Tải Tiện Ích Yomitan Chính Thức')) violations.push('Tải Tiện Ích Yomitan Chính Thức')
    if (text.includes('Bảng Tra Cứu 55 Field Markers Tích Hợp')) violations.push('Bảng Tra Cứu 55 Field Markers Tích Hợp')
    if (text.includes('Hướng Dẫn Sử Dụng Trên Di Động')) violations.push('Hướng Dẫn Sử Dụng Trên Di Động')
    if (text.includes('Khắc Phục Sự Cố & Tài Liệu Chuyên Sâu')) violations.push('Khắc Phục Sự Cố & Tài Liệu Chuyên Sâu')

    expect(violations, `Hardcoded Vietnamese strings found in YomitanGuideTab in en mode: ${violations.join(', ')}`).toEqual([])
  })

  it('AsbplayerGuideTab: must not contain hardcoded Vietnamese text when language is en', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <AsbplayerGuideTab />
        </MemoryRouter>
      )
    })

    const text = container.textContent || ''
    const violations: string[] = []
    if (text.includes('Tải Tiện Ích & Trình Phát asbplayer')) violations.push('Tải Tiện Ích & Trình Phát asbplayer')
    if (text.includes('Bảng Quy Chuẩn Ánh Xạ 7 Trường Dữ Liệu')) violations.push('Bảng Quy Chuẩn Ánh Xạ 7 Trường Dữ Liệu')
    if (text.includes('Mã Nguồn GitHub')) violations.push('Mã Nguồn GitHub')
    if (text.includes('Sao chép JSON mẫu')) violations.push('Sao chép JSON mẫu')

    expect(violations, `Hardcoded Vietnamese strings found in AsbplayerGuideTab in en mode: ${violations.join(', ')}`).toEqual([])
  })

  it('McpGuideTab: must not contain hardcoded Vietnamese text when language is en', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <McpGuideTab />
        </MemoryRouter>
      )
    })

    const text = container.textContent || ''
    const violations: string[] = []
    if (text.includes('cURL Kiểm tra')) violations.push('cURL Kiểm tra')
    if (text.includes('Lệnh cURL kiểm tra kết nối JSON-RPC 2.0:')) violations.push('Lệnh cURL kiểm tra kết nối JSON-RPC 2.0:')
    if (text.includes('Hướng dẫn cấu hình nhanh trong Cursor IDE:')) violations.push('Hướng dẫn cấu hình nhanh trong Cursor IDE:')
    if (text.includes('Tiến Trình Flama Connect')) violations.push('Tiến Trình Flama Connect')
    if (text.includes('Chống Cào Dữ Liệu An Toàn')) violations.push('Chống Cào Dữ Liệu An Toàn')

    expect(violations, `Hardcoded Vietnamese strings found in McpGuideTab in en mode: ${violations.join(', ')}`).toEqual([])
  })

  it('McpTokensPage: Setup Tab header must not contain hardcoded Vietnamese in en mode', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <McpTokensPage />
          </MemoryRouter>
        </QueryClientProvider>
      )
    })

    const waitForContent = async (text: string, maxAttempts = 30) => {
      for (let i = 0; i < maxAttempts; i++) {
        if (container.textContent?.includes(text)) return
        await act(async () => {
          await new Promise((r) => setTimeout(r, 20))
        })
      }
    }

    await waitForContent('Start Connecting Extension ➔')

    // Click CTA button to navigate to Tab 2
    const ctaButton = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Start Connecting Extension')
    )
    expect(ctaButton).toBeTruthy()
    await act(async () => {
      ctaButton?.click()
    })

    await waitForContent('ChatGPT')

    const text = container.textContent || ''
    const violations: string[] = []
    if (text.includes('Phương Thức Kết Nối AI')) violations.push('Phương Thức Kết Nối AI')
    if (text.includes('Chọn kết nối 1 chạm qua ChatGPT OAuth')) violations.push('Chọn kết nối 1 chạm qua ChatGPT OAuth')

    expect(violations, `Hardcoded Vietnamese strings found in McpTokensPage setup tab in en mode: ${violations.join(', ')}`).toEqual([])
  })
})
