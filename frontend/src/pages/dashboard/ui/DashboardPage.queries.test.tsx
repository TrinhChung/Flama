// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { studyOverviewQueryKey } from '@/entities/study-overview'
import type { DashboardOverview, DashboardPayload } from '@/features/dashboard'
import { dashboardQueryKey } from '@/features/dashboard/api'
import { DashboardPage } from './DashboardPage'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const api = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  getDashboardOverview: vi.fn(),
}))

vi.mock('@/entities/study-overview/api/studyOverviewApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/entities/study-overview/api/studyOverviewApi')>()),
  fetchStudyOverview: api.getDashboardOverview,
}))
vi.mock('@/features/dashboard/api/dashboardApi', () => ({ dashboardApi: { getDashboard: api.getDashboard } }))

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: {
      user: { id: 1, is_admin: false },
      links: { study: '/study', browse: '/browse' },
    },
    isPending: false,
  }),
}))

// Keep real Dashboard queries and deck rendering; expose the heatmap's public
// loading/data props without mounting hundreds of unrelated calendar cells.
vi.mock('@/shared/components/StudyHeatmap', () => ({
  StudyHeatmap: ({ overview, loading, year, onYearChange }: {
    overview?: DashboardOverview
    loading: boolean
    year: number
    onYearChange: (year: number) => void
  }) => (
    <div data-testid="heatmap" data-loading={String(loading)}>
      {overview ? `Heatmap ${overview.year}` : 'Heatmap pending'}
      <button type="button" data-testid="prev-year" onClick={() => onYearChange(year - 1)} />
    </div>
  ),
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function dashboard(name = 'Vocabulary'): DashboardPayload {
  return {
    decks: [{
      id: 42,
      parent_id: null,
      name,
      depth: 0,
      study_url: '/study?deck_id=42',
      counts: { new: 10, learning: 2, due: 3 },
      move: { alias: 'deck-42', token: '', parent_alias: null, parent_token: null },
      actions: {
        rename: '/api/decks/42',
        move: '/api/decks/42',
        delete: '/api/decks/42',
        reset: '/api/decks/42/progress-reset',
        share: '/marketplace/decks',
      },
      children: [],
    }],
    totals: { new: 10, learning: 2, due: 3 },
    admin_mode: false,
    actions: { create: '/api/decks', move: '/api/decks/move' },
  }
}

describe('Dashboard query scheduling', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  let year: number
  let overviewKey: ReturnType<typeof studyOverviewQueryKey>

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    year = new Date().getFullYear()
    overviewKey = studyOverviewQueryKey(year)
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, staleTime: 30_000, refetchOnWindowFocus: false },
      },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    queryClient.clear()
    container.remove()
    localStorage.clear()
  })

  async function renderPage() {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <DashboardPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })
  }

  async function waitForDeck(name: string) {
    await act(async () => {
      await vi.waitFor(() => {
        expect(container.querySelector('[data-node-id="42"]')?.textContent).toContain(name)
      })
    })
  }

  it('starts the deck tree and heatmap requests together and renders the tree without waiting for the heatmap', async () => {
    const deckRequest = deferred<DashboardPayload>()
    const overviewRequest = deferred<DashboardOverview>()
    api.getDashboard.mockReturnValue(deckRequest.promise)
    api.getDashboardOverview.mockReturnValue(overviewRequest.promise)

    await renderPage()

    expect(api.getDashboard).toHaveBeenCalledTimes(1)
    expect(api.getDashboardOverview).toHaveBeenCalledExactlyOnceWith(year)
    expect(container.querySelector('[data-node-id="42"]')).toBeNull()

    await act(async () => deckRequest.resolve(dashboard()))
    await waitForDeck('Vocabulary')

    expect(container.querySelector('[data-testid="heatmap"]')?.getAttribute('data-loading')).toBe('true')
    expect(container.querySelector('.deck-board')).not.toBeNull()

    await act(async () => overviewRequest.resolve({ year, heatmap: [] }))
    await act(async () => {
      await vi.waitFor(() => {
        expect(container.querySelector('[data-testid="heatmap"]')?.getAttribute('data-loading')).toBe('false')
      })
    })
    expect(container.querySelector('[data-node-id="42"]')).not.toBeNull()
  })

  it('shows fresh cached decks and heatmap without making API requests', async () => {
    queryClient.setQueryData(dashboardQueryKey, dashboard('Cached vocabulary'))
    queryClient.setQueryData(overviewKey, { year, heatmap: [] })

    await renderPage()
    await waitForDeck('Cached vocabulary')

    expect(container.querySelector('[data-testid="heatmap"]')?.textContent).toBe(`Heatmap ${year}`)
    expect(api.getDashboard).not.toHaveBeenCalled()
    expect(api.getDashboardOverview).not.toHaveBeenCalled()
  })

  it('shows a heatmap that finished first as soon as the deck tree arrives', async () => {
    const deckRequest = deferred<DashboardPayload>()
    api.getDashboard.mockReturnValue(deckRequest.promise)
    api.getDashboardOverview.mockResolvedValue({ year, heatmap: [] })

    await renderPage()
    await act(async () => {
      await vi.waitFor(() => expect(queryClient.getQueryState(overviewKey)?.status).toBe('success'))
    })

    await act(async () => deckRequest.resolve(dashboard()))
    await waitForDeck('Vocabulary')

    expect(container.querySelector('[data-testid="heatmap"]')?.textContent).toBe(`Heatmap ${year}`)
    expect(container.querySelector('[data-testid="heatmap"]')?.getAttribute('data-loading')).toBe('false')
  })

  it('keeps stale cached content visible while both requests refresh in parallel', async () => {
    const deckRequest = deferred<DashboardPayload>()
    const overviewRequest = deferred<DashboardOverview>()
    api.getDashboard.mockReturnValue(deckRequest.promise)
    api.getDashboardOverview.mockReturnValue(overviewRequest.promise)
    const staleAt = Date.now() - 60_000
    queryClient.setQueryData(dashboardQueryKey, dashboard('Cached vocabulary'), { updatedAt: staleAt })
    queryClient.setQueryData(overviewKey, { year, heatmap: [] }, { updatedAt: staleAt })

    await renderPage()
    await waitForDeck('Cached vocabulary')

    expect(api.getDashboard).toHaveBeenCalledTimes(1)
    expect(api.getDashboardOverview).toHaveBeenCalledExactlyOnceWith(year)
    expect(container.querySelector('[data-testid="heatmap"]')?.textContent).toBe(`Heatmap ${year}`)
    expect(container.querySelector('[data-testid="heatmap"]')?.getAttribute('data-loading')).toBe('false')

    await act(async () => deckRequest.resolve(dashboard('Refreshed vocabulary')))
    await waitForDeck('Refreshed vocabulary')
    await act(async () => overviewRequest.resolve({ year, heatmap: [] }))
  })

  it('refetches only the deck tree when deck queries are invalidated', async () => {
    queryClient.setQueryData(dashboardQueryKey, dashboard('Cached vocabulary'))
    queryClient.setQueryData(overviewKey, { year, heatmap: [] })
    api.getDashboard.mockResolvedValue(dashboard('Moved vocabulary'))

    await renderPage()
    await waitForDeck('Cached vocabulary')

    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: dashboardQueryKey })
    })
    await waitForDeck('Moved vocabulary')

    expect(api.getDashboard).toHaveBeenCalledTimes(1)
    expect(api.getDashboardOverview).not.toHaveBeenCalled()
  })

  it('keeps the previous year on screen, marked loading, until the new year arrives', async () => {
    queryClient.setQueryData(dashboardQueryKey, dashboard())
    queryClient.setQueryData(overviewKey, { year, heatmap: [] })
    const previousYearRequest = deferred<DashboardOverview>()
    api.getDashboardOverview.mockReturnValue(previousYearRequest.promise)

    await renderPage()
    await waitForDeck('Vocabulary')
    await act(async () => {
      container.querySelector<HTMLButtonElement>('[data-testid="prev-year"]')?.click()
    })

    expect(api.getDashboardOverview).toHaveBeenCalledExactlyOnceWith(year - 1)
    const heatmap = container.querySelector('[data-testid="heatmap"]')
    expect(heatmap?.textContent).toBe(`Heatmap ${year}`)
    expect(heatmap?.getAttribute('data-loading')).toBe('true')

    await act(async () => previousYearRequest.resolve({ year: year - 1, heatmap: [] }))
    await act(async () => {
      await vi.waitFor(() => {
        expect(container.querySelector('[data-testid="heatmap"]')?.textContent).toBe(`Heatmap ${year - 1}`)
      })
    })
    expect(container.querySelector('[data-testid="heatmap"]')?.getAttribute('data-loading')).toBe('false')
  })

  it('shows the deck error even though the heatmap request ran alongside it', async () => {
    const deckRequest = deferred<DashboardPayload>()
    api.getDashboard.mockReturnValue(deckRequest.promise)
    api.getDashboardOverview.mockResolvedValue({ year, heatmap: [] })

    await renderPage()
    await act(async () => deckRequest.reject(new Error('Dashboard unavailable')))
    await act(async () => {
      await vi.waitFor(() => {
        expect(container.textContent).toContain('Dashboard unavailable')
      })
    })

    expect(container.querySelector('[data-node-id="42"]')).toBeNull()
    expect(container.querySelector('[data-testid="heatmap"]')).toBeNull()
  })
})
