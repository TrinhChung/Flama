// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/client'
import type { DeckChangeRequest } from '../types'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const { getDeckChangeRequest, sendDeckContribution, resolveDeckChangeRequestConflict, success, warning, error } = vi.hoisted(() => ({
  getDeckChangeRequest: vi.fn(), sendDeckContribution: vi.fn(), resolveDeckChangeRequestConflict: vi.fn(),
  success: vi.fn(), warning: vi.fn(), error: vi.fn(),
}))
vi.mock('../api', async () => ({ ...await vi.importActual('../api'),
  getDeckChangeRequest, sendDeckContribution, resolveDeckChangeRequestConflict,
}))
vi.mock('@/shared/api/bootstrap', () => ({ useBootstrap: () => ({ data: { user: { id: 2 } } }) }))
vi.mock('sonner', () => ({ toast: { success, warning, error } }))

import i18n, { i18nReady } from '@/shared/config/i18n'
import { ChangeRequestDetailView } from './ChangeRequestDetailView'

describe('contribution detail automatic sending', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let request: DeckChangeRequest

  beforeEach(async () => {
    vi.clearAllMocks()
    await i18nReady
    await i18n.changeLanguage('vi')
    request = {
      id: 'request-1', deck_item_id: 'deck-1', status: 'needs_sync', revision: 1,
      title: 'Sửa nghĩa', description: 'Giải thích', overlay_fingerprint: 'a'.repeat(64),
      requester: { id: 2, username: 'learner' }, owner: { id: 1, username: 'author' },
      item_count: 1, unresolved_conflict_count: 0, change_counts: { note_field_set: 1 },
      can_submit: false, can_review: false, can_resolve: false, items: [], conflicts: [],
    }
    getDeckChangeRequest.mockImplementation(async () => request)
    sendDeckContribution.mockImplementation(async () => {
      request = { ...request, status: 'pending_review', can_submit: false }
      return request
    })
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    client.clear()
    container.remove()
  })

  async function waitFor(check: () => void) {
    await vi.waitFor(async () => {
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
      check()
    })
  }

  async function render() {
    await act(async () => root.render(
      <MemoryRouter initialEntries={['/flashcards/change-requests/request-1']}>
        <QueryClientProvider client={client}>
          <Routes>
            <Route path="/flashcards/change-requests/:requestId" element={<ChangeRequestDetailView />} />
            <Route path="/flashcards/shared-decks/:deckItemId/change-request" element={<div>Xem lại thay đổi đã lưu</div>} />
          </Routes>
        </QueryClientProvider>
      </MemoryRouter>,
    ))
    await waitFor(() => expect(container.textContent).toContain('Giải thích'))
  }

  function button(text: string) {
    return Array.from(container.querySelectorAll('button')).find((element) => element.textContent?.includes(text))
  }

  it('lets a requester send an older unsynced draft without a sync button', async () => {
    await render()
    expect(button('Đồng bộ')).toBeUndefined()
    expect(button('Gửi đóng góp')?.disabled).toBe(false)
    await act(async () => button('Gửi đóng góp')!.click())
    await waitFor(() => expect(success).toHaveBeenCalled())
    expect(sendDeckContribution).toHaveBeenCalledWith('deck-1', {
      title: 'Sửa nghĩa', description: 'Giải thích', expected_overlay_fingerprint: 'a'.repeat(64),
    })
  })

  it('allows sending immediately after the final conflict decision is saved', async () => {
    request = { ...request, status: 'has_conflict', can_resolve: true, unresolved_conflict_count: 1,
      conflicts: [{ id: 'conflict-1', conflict_type: 'note_field', base_value: 'old',
        local_value: 'mine', upstream_value: 'new' }] }
    resolveDeckChangeRequestConflict.mockImplementation(async () => {
      request = { ...request, status: 'draft', can_submit: true, can_resolve: false,
        unresolved_conflict_count: 0, conflicts: [{ ...request.conflicts[0], resolved_at: '2026-10-31' }] }
      return request
    })
    await render()
    expect(button('Gửi đóng góp')).toBeUndefined()
    await act(async () => button('Giữ bản của tôi')!.click())
    await waitFor(() => expect(button('Gửi đóng góp')?.disabled).toBe(false))
    expect(button('Đồng bộ')).toBeUndefined()
    await act(async () => button('Gửi đóng góp')!.click())
    await waitFor(() => expect(sendDeckContribution).toHaveBeenCalledTimes(1))
  })

  it('keeps newly discovered conflicts visible instead of reporting success', async () => {
    sendDeckContribution.mockImplementation(async () => {
      request = { ...request, status: 'has_conflict', can_resolve: true, unresolved_conflict_count: 1,
        conflicts: [{ id: 'conflict-1', conflict_type: 'note_field' }] }
      return request
    })
    await render()
    await act(async () => button('Gửi đóng góp')!.click())
    await waitFor(() => expect(container.textContent).toContain('Xử lý xung đột'))
    expect(warning).toHaveBeenCalled()
    expect(success).not.toHaveBeenCalled()
  })

  it('returns to the saved-change preview if personal edits changed after the draft', async () => {
    sendDeckContribution.mockRejectedValueOnce(new ApiError('Changed', 409, 'CHANGE_REQUEST_STALE'))
    await render()
    await act(async () => button('Gửi đóng góp')!.click())
    await waitFor(() => expect(container.textContent).toContain('Xem lại thay đổi đã lưu'))
    expect(error).toHaveBeenCalled()
  })
})
