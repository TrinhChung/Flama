// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const { getIncomingDeckChangeRequests } = vi.hoisted(() => ({
  getIncomingDeckChangeRequests: vi.fn(),
}))

vi.mock('../api', () => ({ getIncomingDeckChangeRequests }))

import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { ChangeRequestSummary } from '../types'
import { ChangeRequestInboxPage } from './ChangeRequestInboxPage'

function request(id: string, title: string): ChangeRequestSummary {
  return {
    id,
    deck_item_id: 'deck-1',
    title,
    status: 'pending_review',
    base_release_id: null,
    revision: 1,
    requester: { id: 2, username: 'nguoigop' },
    deck_item: { id: 'deck-1', title: 'Deck N5' },
    item_count: 1,
    unresolved_conflict_count: 0,
    submitted_at: null,
    updated_at: null,
  }
}

describe('ChangeRequestInboxPage cursor pagination', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    getIncomingDeckChangeRequests.mockReset()
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    queryClient.clear()
    container.remove()
  })

  it('fetches the next cursor lazily and keeps only the selected page in the DOM', async () => {
    getIncomingDeckChangeRequests.mockImplementation(
      (_deckItemId: string | null, query: { cursor?: string | null }) => Promise.resolve(
        query.cursor
          ? {
              items: [request('request-2', 'Đóng góp trang hai')],
              page: { limit: 30, has_more: false, next_cursor: null },
            }
          : {
              items: [request('request-1', 'Đóng góp trang một')],
              page: { limit: 30, has_more: true, next_cursor: 'cursor-2' },
            },
      ),
    )

    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={['/flashcards/change-requests/incoming?deck_item_id=deck-1']}>
          <QueryClientProvider client={queryClient}>
            <Routes>
              <Route
                path="/flashcards/change-requests/incoming"
                element={<ChangeRequestInboxPage />}
              />
            </Routes>
          </QueryClientProvider>
        </MemoryRouter>,
      )
    })

    await vi.waitFor(() => {
      expect(container.textContent).toContain('Đóng góp trang một')
    })
    expect(getIncomingDeckChangeRequests).toHaveBeenCalledTimes(1)
    expect(getIncomingDeckChangeRequests).toHaveBeenLastCalledWith(
      'deck-1',
      { cursor: null, limit: 30 },
      expect.any(AbortSignal),
    )

    const nextButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('Trang tiếp'),
    )
    await act(async () => nextButton?.click())

    await vi.waitFor(() => {
      expect(container.textContent).toContain('Đóng góp trang hai')
    })
    expect(getIncomingDeckChangeRequests).toHaveBeenCalledTimes(2)
    expect(getIncomingDeckChangeRequests).toHaveBeenLastCalledWith(
      'deck-1',
      { cursor: 'cursor-2', limit: 30 },
      expect.any(AbortSignal),
    )
    expect(container.textContent).not.toContain('Đóng góp trang một')

    const previousButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('Trang trước'),
    )
    await act(async () => previousButton?.click())

    expect(container.textContent).toContain('Đóng góp trang một')
    expect(container.textContent).not.toContain('Đóng góp trang hai')
    expect(container.textContent).toContain('Trang tiếp')
    expect(getIncomingDeckChangeRequests).toHaveBeenCalledTimes(2)
  })
})
