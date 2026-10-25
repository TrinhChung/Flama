// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/client'
import { useBrowseFilters } from './useBrowseFilters'
import { useBrowseData } from './useBrowseData'
import { useBrowseDeckSidebar } from './useBrowseDeckSidebar'
import type { BrowseCardsParams } from '../api/browseApi'
import type { BrowseDeck } from '../types'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const mocks = vi.hoisted(() => ({ structure: vi.fn(), summaries: vi.fn(), cards: vi.fn() }))
vi.mock('../api/browseApi', () => ({
  browseQueryKeys: { noteTypes: ['note-types', 'browse', 'compact'] },
  browseApi: {
    fetchDeckStructure: (signal: AbortSignal) => mocks.structure(signal),
    fetchDeckSummaries: (ids: number[], signal: AbortSignal) => mocks.summaries(ids, signal),
    fetchNoteTypes: async () => ({ items: [] }),
    fetchCards: (params: BrowseCardsParams, signal: AbortSignal) => mocks.cards(params, signal),
  },
}))

describe('Browse request state and lazy deck summaries', () => {
  let root: Root
  let element: HTMLDivElement
  let queryClient: QueryClient
  let filters: ReturnType<typeof useBrowseFilters>
  let data: ReturnType<typeof useBrowseData>
  let sidebar: ReturnType<typeof useBrowseDeckSidebar>
  let navigate: ReturnType<typeof useNavigate>
  let search: string
  let decks: BrowseDeck[]

  function Harness() {
    filters = useBrowseFilters()
    data = useBrowseData(filters)
    sidebar = useBrowseDeckSidebar(data.decksQuery.data?.decks, filters.selectedDeckId, filters.deckSearch, data.setVisibleDeckIds)
    navigate = useNavigate()
    search = useLocation().search
    return null
  }

  async function waitFor(check: () => boolean) {
    for (let i = 0; i < 100 && !check(); i++) await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)) })
    expect(check()).toBe(true)
  }
  async function render(url = '/browse') {
    await act(async () => root.render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[url]}><Harness /></MemoryRouter></QueryClientProvider>))
    await waitFor(() => !data.cardsQuery.isPending)
  }
  const requestedIds = () => mocks.summaries.mock.calls.flatMap(([ids]) => ids as number[])
  const requests = () => mocks.cards.mock.calls.map(([params]) => params as BrowseCardsParams)

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    decks = [{ id: 1, name: 'Root', summary_loaded: false }, { id: 2, name: 'Child', parent_id: 1, summary_loaded: false }, { id: 3, name: 'Grandchild', parent_id: 2, summary_loaded: false }, { id: 7, name: 'Other root', summary_loaded: false }]
    mocks.structure.mockImplementation(async () => ({ decks }))
    mocks.summaries.mockImplementation(async (ids: number[]) => ({ decks: ids.map((id) => ({ id, name: decks.find((deck) => deck.id === id)!.name, counts: { total: 20, due: 3 }, summary_loaded: true, has_mixed_note_types: id === 7 })) }))
    mocks.cards.mockImplementation(async (params: BrowseCardsParams) => ({ items: [], page: params.page, pages: 20, total: 1000, has_next: true }))
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    element = document.createElement('div')
    document.body.append(element)
    root = createRoot(element)
  })
  afterEach(() => { act(() => root.unmount()); queryClient.clear(); element.remove() })

  it('requests the URL deck/page/size on the first render and restores Back/Forward atomically', async () => {
    localStorage.setItem('flama_browse_per_page', '20')
    await render('/browse?deck_id=7&page=3&per_page=50&note_id=bookmark')
    expect(requests()[0]).toMatchObject({ deck_id: 7, page: 3, per_page: 50 })
    await act(async () => filters.setPage(4))
    await waitFor(() => filters.page === 4)
    expect(new URLSearchParams(search).get('note_id')).toBe('bookmark')
    await act(async () => filters.setSelectedDeckId(1))
    await waitFor(() => filters.selectedDeckId === 1)
    expect(requests().at(-1)).toMatchObject({ deck_id: 1, page: 1, per_page: 50 })
    expect(requests().some((params) => params.deck_id === 1 && params.page === 4)).toBe(false)
    await act(async () => navigate(-1))
    await waitFor(() => filters.selectedDeckId === 7 && filters.page === 4)
    await act(async () => navigate(-1))
    await waitFor(() => filters.page === 3)
    await act(async () => navigate(1))
    await waitFor(() => filters.page === 4)
    await act(async () => filters.handlePerPageChange(200))
    await waitFor(() => filters.perPage === 200 && filters.page === 1)
    expect(localStorage.getItem('flama_browse_per_page')).toBe('200')
    expect(new URLSearchParams(search).get('note_id')).toBe('bookmark')
  })

  it('loads rows independently, then only summarizes selected and rendered tree nodes', async () => {
    const resolveSummaries: Array<() => void> = []
    mocks.summaries.mockImplementation((ids: number[]) => new Promise((resolve) => resolveSummaries.push(() => resolve({ decks: ids.map((id) => ({ id, name: decks.find((deck) => deck.id === id)!.name, counts: { total: 20 }, summary_loaded: true, has_mixed_note_types: id === 7 })) }))))
    await render('/browse?deck_id=7')
    await waitFor(() => requestedIds().includes(1))
    expect(data.selectedDeckSummaryPending).toBe(true)
    expect(data.selectedDeck?.counts).toBeUndefined()
    expect(requestedIds().sort()).toEqual([1, 7])
    await act(async () => resolveSummaries.splice(0).forEach((resolve) => resolve()))
    await waitFor(() => !data.selectedDeckSummaryPending)
    expect(data.selectedDeck).toMatchObject({ has_mixed_note_types: true, counts: { total: 20 } })
    await act(async () => sidebar.toggleExpand(1))
    await waitFor(() => requestedIds().includes(2))
    expect(requestedIds()).not.toContain(3)
    expect(requestedIds().filter((id) => id === 1)).toHaveLength(1)
    await act(async () => resolveSummaries.splice(0).forEach((resolve) => resolve()))
    await act(async () => sidebar.toggleExpand(1))
    await act(async () => sidebar.toggleExpand(1))
    expect(requestedIds().filter((id) => id === 2)).toHaveLength(1)
    await act(async () => filters.setDeckSearch('Grandchild'))
    await waitFor(() => requestedIds().includes(3))
  })

  it('batches summaries at 50 IDs, caches individual decks, and keeps broad invalidation', async () => {
    decks = Array.from({ length: 105 }, (_, index) => ({ id: index + 1, name: `Deck ${index + 1}`, summary_loaded: false }))
    await render()
    await waitFor(() => requestedIds().length === 105 && data.decksQuery.data?.decks.every((deck) => deck.summary_loaded === true) === true)
    expect(mocks.summaries.mock.calls.map(([ids]) => ids.length)).toEqual([50, 50, 5])
    await act(async () => filters.setSelectedDeckId(50))
    expect(requestedIds()).toHaveLength(105)
    await act(async () => { await queryClient.invalidateQueries({ queryKey: ['browse', 'decks'] }) })
    await waitFor(() => requestedIds().length === 210)
    expect(mocks.structure).toHaveBeenCalledTimes(2)
    expect(mocks.summaries.mock.calls.every(([ids]) => ids.length <= 50)).toBe(true)
  })

  it('reports failed summaries without assuming an empty or single-type deck', async () => {
    mocks.summaries.mockRejectedValue(new ApiError('Deck not found.', 404, 'NOT_FOUND'))
    await render('/browse?deck_id=7')
    await waitFor(() => Boolean(data.deckSummaryError))
    expect(data.cardsQuery.isSuccess).toBe(true)
    expect(data.selectedDeckSummaryPending).toBe(true)
    expect(data.selectedDeck?.counts).toBeUndefined()
    expect(data.selectedDeck?.has_mixed_note_types).toBeUndefined()
    const count = mocks.summaries.mock.calls.length
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)) })
    expect(mocks.summaries).toHaveBeenCalledTimes(count)
  })

  it('keeps the displayed page and size with retained rows, and drops rows when deck scope changes', async () => {
    await render('/browse?deck_id=7&page=3&per_page=50')
    const responses: Array<() => void> = []
    mocks.cards.mockImplementation((params: BrowseCardsParams) => new Promise((resolve) => responses.push(() => resolve({ items: [], page: params.page, pages: 20, total: 1000, has_next: true }))))
    await act(async () => filters.setPage(4))
    expect(data.cardsQuery.isPlaceholderData).toBe(true)
    expect(data.displayedPage).toBe(3)
    expect(data.displayedPerPage).toBe(50)
    await act(async () => responses.shift()!())
    await waitFor(() => data.displayedPage === 4)
    await act(async () => filters.handlePerPageChange(200))
    expect(filters.page).toBe(1)
    expect(data.displayedPage).toBe(4)
    expect(data.displayedPerPage).toBe(50)
    await act(async () => responses.shift()!())
    await waitFor(() => data.displayedPage === 1 && data.displayedPerPage === 200)
    await act(async () => filters.setSelectedDeckId(1))
    expect(data.cardsQuery.isPlaceholderData).toBe(false)
    expect(data.cardsQuery.data).toBeUndefined()
    await act(async () => responses.shift()!())
  })

  it('resets search/filter/sort pages atomically and replaces history for debounced typing', async () => {
    await render('/browse?deck_id=7&page=3&per_page=50&card_id=bookmark')
    await act(async () => filters.setQueryText('word'))
    await waitFor(() => filters.debouncedQuery === 'word')
    expect(requests().at(-1)).toMatchObject({ q: 'word', page: 1 })
    await act(async () => navigate(-1))
    expect(filters.debouncedQuery).toBe('word')
    expect(filters.page).toBe(1)
    await act(async () => filters.setPage(4))
    await act(async () => filters.setStatusFilter('new'))
    expect(requests().at(-1)).toMatchObject({ status: 'new', page: 1 })
    await act(async () => filters.setPage(5))
    await act(async () => filters.handleSortChange('word'))
    expect(requests().at(-1)).toMatchObject({ sort_by: 'word', sort_dir: 'asc', page: 1 })
    expect(new URLSearchParams(search).get('card_id')).toBe('bookmark')
    expect(requests().some((params) => params.status === 'new' && params.page === 4)).toBe(false)
    expect(requests().some((params) => params.sort_by === 'word' && params.page === 5)).toBe(false)
  })
})
