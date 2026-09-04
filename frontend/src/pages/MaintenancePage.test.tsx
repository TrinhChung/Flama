// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MaintenancePage } from './MaintenancePage'

describe('MaintenancePage', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('renders brand, maintenance status, and reassurance points', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <MaintenancePage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    // Assert key refined texts are present
    expect(container.textContent).toContain('Flama')
    expect(container.textContent).toContain('Bảo dưỡng máy chủ định kỳ')
    expect(container.textContent).toContain('Flama đang được nâng cấp')
    expect(container.textContent).toContain('Dữ liệu thẻ')
    expect(container.textContent).toContain('Tiến độ SRS')
    expect(container.textContent).toContain('Khôi phục')
    expect(container.textContent).toContain('Thử kết nối lại')

    // Confirm AI-trope text/elements are absent
    expect(container.textContent).not.toContain('Máy chủ đang bảo trì')
    expect(container.textContent).not.toContain('Kết nối tạm gián đoạn')

    await act(async () => root.unmount())
  })

  it('triggers reconnection on button click', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const resetQueriesSpy = vi.spyOn(queryClient, 'resetQueries')
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <MaintenancePage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    const button = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Thử kết nối lại'),
    )
    expect(button).toBeDefined()

    await act(async () => {
      button?.click()
    })

    expect(resetQueriesSpy).toHaveBeenCalledTimes(1)

    await act(async () => root.unmount())
  })

  it('triggers reconnection on pressing R key', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const resetQueriesSpy = vi.spyOn(queryClient, 'resetQueries')
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <MaintenancePage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'r' }))
    })

    expect(resetQueriesSpy).toHaveBeenCalledTimes(1)

    await act(async () => root.unmount())
  })
})
