// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/client'
import { BROWSE_SORT_FIELDS, BROWSE_STATUS_FILTERS, type BrowseCardRow, type BrowseCardsResponse } from '../types'
import { BrowsePage } from './BrowsePage'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({ get: vi.fn(), mutate: vi.fn() }))

vi.mock('@/app/api', () => ({ appApi: { get: mocks.get, mutate: mocks.mutate } }))
vi.mock('@/shared/api/bootstrap', () => ({
  bootstrapQueryKey: ['bootstrap'],
  useBootstrap: () => ({ data: { user: { id: 1, is_admin: false }, links: { dashboard: '/dashboard' } } }),
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))
vi.mock('../components/BrowseDeckSidebar', () => ({ BrowseDeckSidebar: () => null }))
vi.mock('../components/BrowseCardEditor', () => ({ BrowseCardEditor: () => null }))
vi.mock('../components/BrowseTtsModal', () => ({ BrowseTtsModal: () => null }))
vi.mock('../components/BrowseStrokeModal', () => ({ BrowseStrokeModal: () => null }))
vi.mock('@/features/worksheets/components/LazyDeckWorksheetModal', () => ({ LazyDeckWorksheetModal: () => null }))
vi.mock('@/features/audio/components/LocalAudioDialog', () => ({ LocalAudioDialog: () => null }))
vi.mock('@/features/guide/components/ContextHelpButton', () => ({ ContextHelpButton: () => null }))

type CardsParams = { q: string; deck_id: number | ''; status: string; sort_by: string; sort_dir: string; page: number; per_page: number }

function row(id: number): BrowseCardRow {
  return {
    card_id: String(id), note_id: `n${id}`, deck_id: 1, deck_name: 'Deck', word: `word-${id}`,
    reading: '', meaning: '', tags: [], status: 'new', due_label: '',
  }
}

function pageOf(page: number, pages: number): BrowseCardsResponse {
  return { items: [row(page * 10), row(page * 10 + 1)], page, total: pages * 2, pages, has_next: page < pages }
}

describe('BrowsePage card list contract with GET /api/browse/cards', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  let listCards: (params: CardsParams) => Promise<BrowseCardsResponse>

  const cardRequests = () =>
    mocks.get.mock.calls.filter(([path]) => path === '/browse/cards').map(([, params]) => params as CardsParams)
  const lastRequest = () => cardRequests().at(-1)!

  async function waitFor(check: () => boolean) {
    for (let attempt = 0; attempt < 100 && !check(); attempt++) {
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)) })
    }
    expect(check()).toBe(true)
  }

  async function renderPage(url = '/browse') {
    await act(async () => root.render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[url]}><BrowsePage /></MemoryRouter>
      </QueryClientProvider>,
    ))
  }

  function header(text: string) {
    return Array.from(container.querySelectorAll('th')).find((th) => th.textContent?.includes(text))!
  }

  async function chooseStatus(value: string) {
    const select = container.querySelector<HTMLSelectElement>('select')!
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value')!.set!.call(select, value)
      select.dispatchEvent(new Event('change', { bubbles: true }))
    })
  }

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    listCards = async (params) => pageOf(params.page, 1)
    mocks.get.mockImplementation(async (path: string, params: CardsParams) => {
      if (path === '/browse/cards') return listCards(params)
      if (path === '/browse/decks') return { decks: [{ id: 7, name: 'Deck' }] }
      if (path === '/note-types') return { items: [] }
      throw new Error(`unexpected GET ${path}`)
    })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  })

  afterEach(() => {
    act(() => root.unmount())
    queryClient.clear()
    container.remove()
  })

  it('sends only status filters and sort fields the API accepts', async () => {
    await renderPage()
    await waitFor(() => cardRequests().length === 1)
    expect(lastRequest()).toMatchObject({ status: 'all', sort_by: 'due', sort_dir: 'asc', page: 1 })

    const options = Array.from(container.querySelectorAll<HTMLOptionElement>('select option')).map((option) => option.value)
    expect(options).toEqual(['all', 'new', 'learn', 'review'])
    await chooseStatus('learn')
    await waitFor(() => lastRequest().status === 'learn')

    for (const text of ['Đọc', 'Ý nghĩa', 'Trạng thái']) {
      await act(async () => header(text).click())
    }
    await act(async () => header('Từ vựng').click())
    await waitFor(() => lastRequest().sort_by === 'word')
    expect(lastRequest()).toMatchObject({ sort_by: 'word', sort_dir: 'asc', status: 'learn' })
    await act(async () => header('Từ vựng').click())
    await waitFor(() => lastRequest().sort_dir === 'desc')

    for (const params of cardRequests()) {
      expect(BROWSE_STATUS_FILTERS).toContain(params.status)
      expect(BROWSE_SORT_FIELDS).toContain(params.sort_by)
    }
  })

  it('shows the API error message instead of "no cards found", without retrying a 400', async () => {
    listCards = async () => { throw new ApiError('Invalid status filter.', 400, 'BAD_REQUEST', 'status') }
    await renderPage()

    await waitFor(() => Boolean(container.querySelector('[role="alert"]')))
    expect(container.querySelector('[role="alert"]')!.textContent).toContain('Invalid status filter.')
    expect(container.textContent).not.toContain('Không tìm thấy thẻ nào')
    expect(cardRequests()).toHaveLength(1)

    listCards = async (params) => pageOf(params.page, 1)
    await act(async () => container.querySelector<HTMLButtonElement>('[role="alert"] button')!.click())
    await waitFor(() => container.textContent!.includes('word-10'))
  })

  it('ignores a deck_id in the URL that is not a positive integer', async () => {
    await renderPage('/browse?deck_id=12abc')
    await waitFor(() => cardRequests().length > 0)
    expect(cardRequests().every((params) => params.deck_id === '')).toBe(true)

    act(() => root.unmount())
    root = createRoot(container)
    mocks.get.mockClear()
    await renderPage('/browse?deck_id=7')
    await waitFor(() => cardRequests().length > 0)
    expect(lastRequest().deck_id).toBe(7)
  })

  it('keeps the previous rows on screen while the next page loads, then clamps a page past the end', async () => {
    let releaseLastPage!: () => void
    listCards = async (params) => {
      if (params.page === 3) {
        // The last rows were deleted meanwhile: the server now reports 2 pages.
        await new Promise<void>((resolve) => { releaseLastPage = resolve })
        return { items: [], page: 3, total: 4, pages: 2, has_next: false }
      }
      return pageOf(params.page, 3)
    }
    await renderPage()
    await waitFor(() => container.textContent!.includes('word-10'))

    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="Đến trang cuối"]')!.click())
    await waitFor(() => lastRequest().page === 3)
    expect(container.textContent).toContain('word-10')
    expect(container.textContent).not.toContain('Đang tìm thẻ...')

    await act(async () => releaseLastPage())
    await waitFor(() => lastRequest().page === 2)
    await waitFor(() => container.textContent!.includes('word-20'))
  })
})
