// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DashboardPayload, DeckNode } from '../types'
import { DashboardPage } from './DashboardPage'

const sampleDeck: DeckNode = {
  id: 42,
  parent_id: null,
  name: 'N3 Vocabulary',
  depth: 0,
  study_url: '/study?deck_id=42',
  counts: { new: 10, learning: 2, due: 3 },
  move: { alias: 'deck-42', token: 'token', parent_alias: null, parent_token: null },
  actions: {
    rename: '/api/decks/42',
    move: '/api/decks/42',
    delete: '/api/decks/42',
    reset: '/api/decks/42/progress-reset',
    share: '/marketplace/decks',
  },
  children: [],
}

const dummyDashboard: DashboardPayload = {
  decks: [sampleDeck],
  totals: { new: 10, learning: 2, due: 3 },
  admin_mode: false,
  actions: { create: '/api/decks', move: '/api/decks/move' },
}

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: {
      user: { id: 1, is_admin: false },
      links: { study: '/study', browse: '/browse' },
    },
    isPending: false,
  }),
}))

vi.mock('../api', () => ({
  dashboardQueryKey: ['dashboard'],
  useDashboard: () => ({
    data: dummyDashboard,
    isPending: false,
    error: null,
  }),
  useDashboardOverview: () => ({
    data: { days: [] },
    isPending: false,
  }),
}))

describe('DashboardPage - Study Button State', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.clearAllMocks()
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('disables the Study button when no deck is selected', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <DashboardPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    // Find Study tab button
    const studyButton = container.querySelector<HTMLButtonElement>('button.dash-tab')
    expect(studyButton).not.toBeNull()
    expect(studyButton?.textContent).toContain('Study')
    expect(studyButton?.disabled).toBe(true)

    // Ensure there is no active Study link
    const studyLinks = Array.from(container.querySelectorAll<HTMLAnchorElement>('a.dash-tab'))
    const studyLink = studyLinks.find((el) => el.textContent?.includes('Study'))
    expect(studyLink).toBeUndefined()
  })

  it('enables the Study button with the correct link when a deck is selected', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <DashboardPage />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    // Initially disabled
    expect(container.querySelector<HTMLButtonElement>('button.dash-tab')?.disabled).toBe(true)

    // Click on the deck row to select it
    const deckRow = container.querySelector<HTMLElement>('[data-node-id="42"]')
    expect(deckRow).not.toBeNull()

    await act(async () => {
      deckRow?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    // Now the Study button should become a link to /study?deck_id=42
    const studyLinks = Array.from(container.querySelectorAll<HTMLAnchorElement>('a.dash-tab'))
    const studyLink = studyLinks.find((el) => el.textContent?.includes('Study'))
    expect(studyLink).toBeDefined()
    expect(studyLink?.getAttribute('href')).toBe('/study?deck_id=42')

    // And disabled button should no longer exist
    const studyButton = container.querySelector<HTMLButtonElement>('button.dash-tab')
    expect(studyButton).toBeNull()
  })
})
