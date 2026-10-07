// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DashboardOverview, DashboardPayload } from '../types'
import { dashboardQueryKey } from '../api'
import { DashboardPage } from '../pages/DashboardPage'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const api = vi.hoisted(() => ({
  getDashboard: vi.fn(),
  getDashboardOverview: vi.fn(),
}))

vi.mock('@/app/api', () => ({ appApi: api }))

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
  StudyHeatmap: ({ overview, loading }: {
    overview?: DashboardOverview
    loading: boolean
  }) => (
    <div data-testid="heatmap" data-loading={String(loading)}>
      {overview ? `Heatmap ${overview.year}` : 'Heatmap pending'}
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
    stats_initial_year: new Date().getFullYear(),
    actions: { create: '/api/decks', move: '/api/decks/move' },
  }
}

describe('Dashboard query scheduling', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  let year: number
  let overviewKey: readonly ['frontend', 'dashboard', 'overview', number]

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    year = new Date().getFullYear()
    overviewKey = ['frontend', 'dashboard', 'overview', year]
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

  it('fetches the deck tree first and renders it while the heatmap is still pending', async () => {
    const deckRequest = deferred<DashboardPayload>()
    const overviewRequest = deferred<DashboardOverview>()
    api.getDashboard.mockReturnValue(deckRequest.promise)
    api.getDashboardOverview.mockReturnValue(overviewRequest.promise)

    await renderPage()

    expect(api.getDashboard).toHaveBeenCalledTimes(1)
    expect(api.getDashboardOverview).not.toHaveBeenCalled()
    expect(container.querySelector('[data-node-id="42"]')).toBeNull()

    await act(async () => deckRequest.resolve(dashboard()))
    await waitForDeck('Vocabulary')

    expect(api.getDashboardOverview).toHaveBeenCalledExactlyOnceWith(year)
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

  it('keeps stale cached content visible and postpones heatmap refresh until deck refresh completes', async () => {
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
    expect(api.getDashboardOverview).not.toHaveBeenCalled()
    expect(container.querySelector('[data-testid="heatmap"]')?.textContent).toBe(`Heatmap ${year}`)
    expect(container.querySelector('[data-testid="heatmap"]')?.getAttribute('data-loading')).toBe('false')

    await act(async () => deckRequest.resolve(dashboard('Refreshed vocabulary')))
    await waitForDeck('Refreshed vocabulary')

    expect(api.getDashboardOverview).toHaveBeenCalledExactlyOnceWith(year)
    expect(queryClient.getQueryState(overviewKey)?.fetchStatus).toBe('fetching')
    expect(container.querySelector('[data-testid="heatmap"]')?.getAttribute('data-loading')).toBe('false')

    await act(async () => overviewRequest.resolve({ year, heatmap: [] }))
  })

  it('does not run a heatmap request when the initial deck request fails', async () => {
    const deckRequest = deferred<DashboardPayload>()
    api.getDashboard.mockReturnValue(deckRequest.promise)

    await renderPage()
    await act(async () => deckRequest.reject(new Error('Dashboard unavailable')))
    await act(async () => {
      await vi.waitFor(() => {
        expect(container.textContent).toContain('Dashboard unavailable')
      })
    })

    expect(api.getDashboardOverview).not.toHaveBeenCalled()
    expect(container.querySelector('[data-node-id="42"]')).toBeNull()
  })
})
