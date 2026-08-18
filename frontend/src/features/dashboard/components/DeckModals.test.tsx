// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { appApi } from '@/app/api'
import type { DashboardPayload, DeckNode } from '../types'
import { CreateDeckModal } from './DeckModals'

vi.mock('@/app/api', () => ({
  appApi: {
    createDeck: vi.fn().mockResolvedValue({ id: 99, name: 'New Deck' }),
  },
}))

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({ data: { user: { is_admin: false } } }),
}))

const childDeck: DeckNode = {
  id: 10,
  parent_id: 2,
  name: 'N1:Bài 1',
  depth: 1,
  study_url: '/study?deck_id=10',
  counts: { new: 5, learning: 1, due: 2 },
  move: { alias: 'deck-10', token: 'token', parent_alias: 'deck-2', parent_token: 'token2' },
  actions: {
    rename: '/api/decks/10',
    move: '/api/decks/10',
    delete: '/api/decks/10',
    reset: '/api/decks/10/progress-reset',
    share: '/marketplace/decks',
  },
  children: [],
}

const parentDeck: DeckNode = {
  id: 2,
  parent_id: null,
  name: 'N1 Master',
  depth: 0,
  study_url: '/study?deck_id=2',
  counts: { new: 10, learning: 2, due: 3 },
  move: { alias: 'deck-2', token: 'token', parent_alias: null, parent_token: null },
  actions: {
    rename: '/api/decks/2',
    move: '/api/decks/2',
    delete: '/api/decks/2',
    reset: '/api/decks/2/progress-reset',
    share: '/marketplace/decks',
  },
  children: [childDeck],
}

const dummyDashboard: DashboardPayload = {
  decks: [parentDeck],
  totals: { new: 15, learning: 3, due: 5 },
  admin_mode: false,
  stats_initial_year: 2026,
  actions: { create: '/api/decks', move: '/api/decks/move' },
}

describe('CreateDeckModal', () => {
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

  it('pre-fills the next sibling deck name (N1:Bài 2) and sets sibling parent_id when child deck is selected', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <CreateDeckModal
            opened={true}
            onClose={vi.fn()}
            dashboard={dummyDashboard}
            selectedDeck={childDeck}
          />
        </QueryClientProvider>,
      )
    })

    const nameInput = document.querySelector<HTMLInputElement>('#create-deck-name')
    expect(nameInput).not.toBeNull()
    expect(nameInput?.value).toBe('N1:Bài 2')

    // Ensure parent deck selection dropdown is NOT present in DOM
    const parentSelect = document.querySelector('#create-deck-parent')
    expect(parentSelect).toBeNull()

    // Submit form
    const form = document.querySelector('form')
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    })

    expect(appApi.createDeck).toHaveBeenCalledWith({
      name: 'N1:Bài 2',
      deck_path: '',
      parent_id: '2',
    })
  })

  it('defaults to root level and empty name when no deck is selected', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <CreateDeckModal
            opened={true}
            onClose={vi.fn()}
            dashboard={dummyDashboard}
            selectedDeck={null}
          />
        </QueryClientProvider>,
      )
    })

    const nameInput = document.querySelector<HTMLInputElement>('#create-deck-name')
    expect(nameInput).not.toBeNull()
    expect(nameInput?.value).toBe('')

    // Ensure parent select is not rendered
    expect(document.querySelector('#create-deck-parent')).toBeNull()
  })
})
