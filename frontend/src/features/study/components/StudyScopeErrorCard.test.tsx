// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/client'
import { StudyScopeErrorCard } from './StudyScopeErrorCard'

let root: Root | null = null
let container: HTMLDivElement | null = null

function render(ui: React.ReactNode) {
  return (
    <MemoryRouter>
      {ui}
    </MemoryRouter>
  )
}

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(async () => {
  if (root) await act(async () => root?.unmount())
  root = null
  container?.remove()
  container = null
  document.body.replaceChildren()
})

describe('StudyScopeErrorCard', () => {
  it('renders access denied screen when error is 403 or DECK_ACCESS_DENIED', async () => {
    const error = new ApiError(
      'Bạn không thể truy cập bộ thẻ này.',
      403,
      'DECK_ACCESS_DENIED',
      undefined,
      {
        deck_id: 954,
        deck_name: 'Bài 001',
        marketplace_url: '/marketplace/decks/item-123',
      },
    )

    await act(async () => {
      root?.render(render(<StudyScopeErrorCard error={error} deckId="954" />))
    })

    expect(container?.textContent).toContain('Bạn không thể truy cập bộ thẻ này')
    expect(container?.textContent).toContain('Bài 001')

    const links = Array.from(container?.querySelectorAll('a') || [])
    const marketLink = links.find((a) => a.textContent?.includes('Khám phá Chợ bộ thẻ'))
    const dashboardLink = links.find((a) => a.textContent?.includes('Về Dashboard'))

    expect(marketLink?.getAttribute('href')).toBe('/marketplace/decks/item-123')
    expect(dashboardLink?.getAttribute('href')).toBe('/dashboard')
  })

  it('renders deck not found screen when error is 404 or DECK_NOT_FOUND', async () => {
    const error = new ApiError(
      'Bộ thẻ này không tồn tại hoặc đã bị xóa.',
      404,
      'DECK_NOT_FOUND',
    )

    await act(async () => {
      root?.render(render(<StudyScopeErrorCard error={error} deckId="999999" />))
    })

    expect(container?.textContent).toContain('Bộ thẻ không tồn tại')
    expect(container?.textContent).toContain('Deck #999999')

    const links = Array.from(container?.querySelectorAll('a') || [])
    const dashboardLink = links.find((a) => a.textContent?.includes('Về Dashboard'))
    expect(dashboardLink?.getAttribute('href')).toBe('/dashboard')
  })

  it('renders no study cards screen when error is NO_STUDY_CARDS', async () => {
    const error = new ApiError(
      'Bộ thẻ này chưa có thẻ học nào.',
      404,
      'NO_STUDY_CARDS',
    )

    await act(async () => {
      root?.render(render(<StudyScopeErrorCard error={error} deckName="Empty Deck" deckId="12" />))
    })

    expect(container?.textContent).toContain('Bộ thẻ chưa có thẻ học')
    expect(container?.textContent).toContain('Empty Deck')

    const links = Array.from(container?.querySelectorAll('a') || [])
    const dashboardLink = links.find((a) => a.textContent?.includes('Về Dashboard'))
    expect(dashboardLink?.getAttribute('href')).toBe('/dashboard')
  })

  it('renders generic fallback error with retry button if provided', async () => {
    const onRetry = vi.fn()
    const error = new Error('Network timeout')

    await act(async () => {
      root?.render(render(<StudyScopeErrorCard error={error} onRetry={onRetry} />))
    })

    expect(container?.textContent).toContain('Không thể tải phiên học')
    expect(container?.textContent).toContain('Network timeout')

    const retryBtn = Array.from(container?.querySelectorAll('button') || []).find((b) => b.textContent?.includes('Thử lại'))
    expect(retryBtn).toBeDefined()
    await act(async () => {
      retryBtn?.click()
    })
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
