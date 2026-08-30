// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { StudyGoalsPage } from './StudyGoalsPage'

describe('StudyGoalsPage Component', () => {
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

  it('renders title, hero banner, subject options, and save button', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <StudyGoalsPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    expect(container.textContent).toContain('Mục tiêu học tập')
    expect(container.textContent).toContain('Tiếng Nhật')
    expect(container.textContent).toContain('Tiếng Anh')
    expect(container.textContent).toContain('thẻ mới / ngày')
    expect(container.textContent).toContain('Lưu mục tiêu')
  })

  it('allows selecting a different daily target', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <StudyGoalsPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    // Find and click the "20 thẻ / ngày" option
    const target20Card = Array.from(container.querySelectorAll('div')).find(
      (el) => el.textContent?.includes('20 thẻ / ngày') && el.classList.contains('cursor-pointer'),
    )

    expect(target20Card).toBeDefined()

    await act(async () => {
      target20Card?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    expect(container.textContent).toContain('20 thẻ mới / ngày')
  })
})
