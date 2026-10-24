// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { dashboardApi } from '../api/dashboardApi'
import type { DashboardPayload, DeckNode } from '../types'
import { CreateDeckModal, DeckActionModal } from './DeckModals'

vi.mock('@/app/api', () => ({ appApi: {} }))

vi.mock('../api/dashboardApi', () => ({
  dashboardApi: {
    createDeck: vi.fn().mockResolvedValue({ id: 99, name: 'New Deck' }),
    renameDeck: vi.fn().mockResolvedValue({}),
    deleteDeck: vi.fn().mockResolvedValue({}),
    resetDeck: vi.fn().mockResolvedValue({}),
    getDeckNoteType: vi.fn().mockResolvedValue({ note_type_id: 'nt-kanji' }),
    listNoteTypes: vi.fn().mockResolvedValue({
      items: [
        { id: 'nt-default', name: 'Từ vựng Flama' },
        { id: 'nt-kanji', name: 'Mẫu Kanji N2' },
      ],
    }),
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
  note_type_id: 'nt-kanji',
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
  note_type_id: 'nt-kanji',
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

  it('pre-fills the hierarchical sibling deck path (N1 Master::N1:Bài 2) and inherits parent note_type_id when child deck is selected', async () => {
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
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })

    const nameInput = document.querySelector<HTMLInputElement>('#create-deck-name')
    expect(nameInput).not.toBeNull()
    expect(nameInput?.value).toBe('N1 Master::N1:Bài 2')

    // Ensure Note Type select is rendered and pre-filled with childDeck.note_type_id
    const noteTypeSelect = document.querySelector<HTMLSelectElement>('#create-deck-notetype')
    expect(noteTypeSelect).not.toBeNull()
    expect(noteTypeSelect?.value).toBe('nt-kanji')

    // Submit form
    const form = document.querySelector('form')
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    })

    expect(dashboardApi.createDeck).toHaveBeenCalledWith({
      name: 'N1 Master::N1:Bài 2',
      deck_path: 'N1 Master::N1:Bài 2',
      parent_id: '',
      note_type_id: 'nt-kanji',
    })
  })

  it('defaults to root level and fallback note type when no deck is selected', async () => {
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
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })

    const nameInput = document.querySelector<HTMLInputElement>('#create-deck-name')
    expect(nameInput).not.toBeNull()
    expect(nameInput?.value).toBe('')

    // Note Type should default to fallback ('nt-default')
    const noteTypeSelect = document.querySelector<HTMLSelectElement>('#create-deck-notetype')
    expect(noteTypeSelect).not.toBeNull()
    expect(noteTypeSelect?.value).toBe('nt-default')

    // Ensure parent select is not rendered
    expect(document.querySelector('#create-deck-parent')).toBeNull()
  })

  it('asks the server which note type a deck without its own type passes on', async () => {
    const untypedDeck: DeckNode = { ...parentDeck, id: 7, note_type_id: null, children: [] }
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <CreateDeckModal opened={true} onClose={vi.fn()} dashboard={dummyDashboard} selectedDeck={untypedDeck} />
        </QueryClientProvider>,
      )
    })
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })

    expect(dashboardApi.getDeckNoteType).toHaveBeenCalledExactlyOnceWith(7)
    expect(document.querySelector<HTMLSelectElement>('#create-deck-notetype')?.value).toBe('nt-kanji')
  })

  it('does not ask the server when the selected deck has its own note type', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <CreateDeckModal opened={true} onClose={vi.fn()} dashboard={dummyDashboard} selectedDeck={childDeck} />
        </QueryClientProvider>,
      )
    })
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })

    expect(dashboardApi.getDeckNoteType).not.toHaveBeenCalled()
  })
})

describe('DeckActionModal cache invalidation', () => {
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

  async function runAction(type: 'rename' | 'delete' | 'reset') {
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const onClose = vi.fn()
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <DeckActionModal
            selection={{ type, deck: parentDeck }}
            onClose={onClose}
            dashboard={dummyDashboard}
          />
        </QueryClientProvider>,
      )
    })
    await act(async () => {
      if (type === 'rename') {
        document.querySelector('form')?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
      } else {
        const footerButtons = document.querySelectorAll<HTMLButtonElement>('[data-slot="dialog-footer"] button')
        footerButtons[footerButtons.length - 1]?.click()
      }
    })
    await act(async () => {
      await vi.waitFor(() => expect(onClose).toHaveBeenCalled())
    })
    return invalidate.mock.calls.map(([filters]) => filters?.queryKey)
  }

  it('refreshes only the deck tree after a rename', async () => {
    const keys = await runAction('rename')
    expect(dashboardApi.renameDeck).toHaveBeenCalledWith(2, { name: 'N1 Master' })
    expect(keys).toEqual([['frontend', 'dashboard']])
  })

  it.each(['delete', 'reset'] as const)('also refreshes the heatmap overview after %s', async (type) => {
    const keys = await runAction(type)
    expect(keys).toEqual([['frontend', 'dashboard'], ['frontend', 'statistics', 'overview']])
  })
})
