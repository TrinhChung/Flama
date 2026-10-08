// @vitest-environment jsdom

// @ts-expect-error global declaration
globalThis.IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import i18n from '@/shared/config/i18n'
import { OrdersPage } from './pages/OrdersPage'

vi.mock('@/app/api', () => ({
  appApi: {
    get: vi.fn(),
  },
}))

describe('OrdersPage', () => {
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

  it('renders empty state when there are no orders in Vietnamese', async () => {
    vi.mocked(appApi.get).mockResolvedValueOnce({
      items: [],
      total: 0,
    })

    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <OrdersPage />
        </QueryClientProvider>
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    expect(container?.textContent).toContain('Lịch sử đơn hàng')
    expect(container?.textContent).toContain('Chưa có đơn hàng')
  })

  it('renders orders table with localized headers and items', async () => {
    vi.mocked(appApi.get).mockResolvedValueOnce({
      items: [
        {
          id: 'ord_123',
          merchant_order_code: 'FLAMA-999',
          title: 'JLPT N3 Kanji Deck',
          total_amount_display: '50.000 VND',
          status: 'completed',
          status_label: 'Hoàn thành',
          status_tone: 'success',
          created_at_display: '08/10/2026',
        },
      ],
      total: 1,
    })

    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <OrdersPage />
        </QueryClientProvider>
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    expect(container?.textContent).toContain('Lịch sử đơn hàng')
    expect(container?.textContent).toContain('Mã đơn')
    expect(container?.textContent).toContain('Học liệu')
    expect(container?.textContent).toContain('FLAMA-999')
    expect(container?.textContent).toContain('JLPT N3 Kanji Deck')
    expect(container?.textContent).toContain('Tổng cộng 1 đơn hàng')
  })

  it('switches to English properly', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    vi.mocked(appApi.get).mockResolvedValueOnce({
      items: [],
      total: 0,
    })

    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <OrdersPage />
        </QueryClientProvider>
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    expect(container?.textContent).toContain('Order History')
    expect(container?.textContent).toContain('No orders yet')
  })
})
