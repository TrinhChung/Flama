// @vitest-environment jsdom

// @ts-expect-error global declaration
globalThis.IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import i18n from '@/shared/config/i18n'
import { FeedbackPage } from './pages/FeedbackPage'
import { FlamaAudioGuidePage } from './pages/FlamaAudioGuidePage'
import { SupportPage } from './pages/SupportPage'
import { TtsKeyGuidePage } from './pages/TtsKeyGuidePage'

vi.mock('@/app/api', () => ({
  appApi: {
    get: vi.fn(),
    mutate: vi.fn(),
    mutateFormData: vi.fn(),
  },
}))

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: { user: { id: 'u1', name: 'Test User' } },
  }),
}))

describe('Support Feature Localization Suite', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    void i18n.changeLanguage('vi')
  })

  afterEach(() => {
    if (root && container) {
      act(() => {
        root?.unmount()
      })
      container.remove()
    }
    container = null
    root = null
  })

  it('renders FeedbackPage with Vietnamese copy and switches to English', async () => {
    vi.mocked(appApi.get).mockResolvedValue({ items: [] })

    await act(async () => {
      root?.render(
        <MemoryRouter>
          <QueryClientProvider client={queryClient}>
            <FeedbackPage />
          </QueryClientProvider>
        </MemoryRouter>
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    expect(container?.textContent).toContain('Góp ý & Báo lỗi Hệ thống')
    expect(container?.textContent).toContain('Gửi phản hồi mới')
    expect(container?.textContent).toContain('Báo lỗi (Bug)')

    // Switch to English
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(container?.textContent).toContain('System Feedback & Bug Reports')
    expect(container?.textContent).toContain('Submit Feedback')
    expect(container?.textContent).toContain('Bug Report')
  })

  it('renders SupportPage with online donation and manual transfer info', async () => {
    vi.mocked(appApi.get).mockImplementation(async (url: string) => {
      if (url === '/support-donation') {
        return {
          configured: true,
          title: 'Ủng hộ Flama',
          description: 'Giúp duy trì máy chủ',
          account_name: 'NGUYEN VAN A',
          account_number: '123456789',
          thank_you_message: 'Cảm ơn bạn!',
          qr_image_url: null,
          limits: {
            min_amount_minor: 10000,
            max_amount_minor: 50000000,
            suggested_amounts: [20000, 50000, 100000],
          },
        }
      }
      return null
    })

    await act(async () => {
      root?.render(
        <MemoryRouter>
          <QueryClientProvider client={queryClient}>
            <SupportPage />
          </QueryClientProvider>
        </MemoryRouter>
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    expect(container?.textContent).toContain('Ủng hộ Flama')
    expect(container?.textContent).toContain('Ủng hộ trực tuyến (QR Code / Ngân hàng)')
    expect(container?.textContent).toContain('Chuyển khoản thủ công')
    expect(container?.textContent).toContain('123456789')
  })

  it('renders TtsKeyGuidePage and FlamaAudioGuidePage correctly', async () => {
    await act(async () => {
      root?.render(
        <MemoryRouter>
          <QueryClientProvider client={queryClient}>
            <TtsKeyGuidePage />
          </QueryClientProvider>
        </MemoryRouter>
      )
    })

    expect(container?.textContent).toContain('Hướng dẫn lấy API Key tạo âm thanh (TTS)')
    expect(container?.textContent).toContain('VoiceVox (TTS Quest API)')

    await act(async () => {
      root?.render(
        <MemoryRouter>
          <QueryClientProvider client={queryClient}>
            <FlamaAudioGuidePage />
          </QueryClientProvider>
        </MemoryRouter>
      )
    })

    expect(container?.textContent).toContain('Hướng dẫn sử dụng & Tải Flama Audio Desktop')
    expect(container?.textContent).toContain('Trạng thái Flama Audio Service')
  })
})
