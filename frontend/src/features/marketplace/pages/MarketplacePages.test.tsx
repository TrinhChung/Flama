// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { appApi } from '@/app/api'
import { SharedDecksPage, SharedNoteTypesPage } from './MarketplacePages'

vi.mock('@/app/api', () => ({ appApi: { get: vi.fn() } }))
vi.mock('react-i18next', async (importOriginal) => ({
  ...await importOriginal<typeof import('react-i18next')>(),
  useTranslation: () => ({ t: (key: string, options?: { defaultValue?: string }) => options?.defaultValue ?? key }),
}))
vi.mock('../hooks/useTaxonomySchema', () => ({
  useTaxonomySchema: () => ({ domains: [], subjectsByDomain: () => [], frameworksForSubject: () => [], difficulties: [] }),
}))
vi.mock('@/shared/components/SpotlightTour', () => ({ SpotlightTour: () => null }))

const item = (id: string) => ({
  id, name: id, title: id, description: null, primary_category: 'Tiếng Nhật',
  rating_avg: 4.5, install_count: 10, pricing_mode: 'free', price_display: 'Miễn phí',
  is_installed: false, author: { username: 'sensei' },
})

describe('Marketplace paged listing', () => {
  let container: HTMLDivElement
  let root: Root
  let client: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('flama_marketplace_spotlight_tour_v1', 'true')
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  })

  afterEach(() => {
    act(() => root.unmount())
    client.clear()
    container.remove()
    localStorage.clear()
  })

  async function settle() {
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)) })
  }

  it('requests compact pages and appends the next page without refetching definitions', async () => {
    vi.mocked(appApi.get).mockImplementation(async (_path, args) => ({
      items: [item(args?.page === 2 ? 'note-type-second' : 'note-type-first')],
      pagination: { page: args?.page ?? 1, page_size: 24, total: 2, has_more: args?.page !== 2 },
    }) as never)
    await act(async () => root.render(
      <QueryClientProvider client={client}><MemoryRouter><SharedNoteTypesPage /></MemoryRouter></QueryClientProvider>,
    ))
    await settle()
    expect(appApi.get).toHaveBeenCalledWith('/api/shared/note-types', expect.objectContaining({ compact: 1, page: 1, page_size: 24 }))
    expect(container.querySelector('a[href="/marketplace/note-types/note-type-first"]')).not.toBeNull()
    const more = Array.from(container.querySelectorAll('button')).find((button) => button.textContent === 'Xem thêm')
    expect(more).toBeDefined()
    await act(async () => more?.click())
    await settle()
    expect(container.querySelector('a[href="/marketplace/note-types/note-type-first"]')).not.toBeNull()
    expect(container.querySelector('a[href="/marketplace/note-types/note-type-second"]')).not.toBeNull()
    expect(appApi.get).toHaveBeenCalledWith('/api/shared/note-types', expect.objectContaining({ page: 2 }))
    expect(Array.from(container.querySelectorAll('button')).some((button) => button.textContent === 'Xem thêm')).toBe(false)
  })

  it('uses complete category totals from the curated response while rendering four featured cards', async () => {
    const cards = ['featured-1', 'featured-2', 'featured-3', 'featured-4'].map(item)
    vi.mocked(appApi.get).mockResolvedValue({
      items: cards,
      pagination: { page: 1, page_size: 24, total: 87, has_more: false },
      curated_sections: { major_sections: [{ category: 'Tiếng Nhật', total: 87, item_ids: cards.map((card) => card.id) }], other_item_ids: [], other_total: 0 },
    })
    await act(async () => root.render(
      <QueryClientProvider client={client}><MemoryRouter><SharedDecksPage /></MemoryRouter></QueryClientProvider>,
    ))
    await settle()
    expect(appApi.get).toHaveBeenCalledWith('/api/shared/decks', expect.objectContaining({ compact: 1, curated: 1 }))
    expect(container.textContent).toContain('(87 bộ thẻ)')
    for (const card of cards) {
      expect(container.querySelector(`a[href="/marketplace/decks/${card.id}"]`)).not.toBeNull()
    }
  })
})
