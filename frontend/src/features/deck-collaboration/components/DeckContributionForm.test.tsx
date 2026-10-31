// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DeckChangeRequest, LocalChangesPreview } from '../types'
import { ApiError } from '@/shared/api/client'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const { getLocalDeckChanges, getActiveDeckChangeRequest, sendDeckContribution, success, warning, error } = vi.hoisted(() => ({
  getLocalDeckChanges: vi.fn(), getActiveDeckChangeRequest: vi.fn(), sendDeckContribution: vi.fn(),
  success: vi.fn(), warning: vi.fn(), error: vi.fn(),
}))
vi.mock('../api', async () => ({
  ...await vi.importActual('../api'), getLocalDeckChanges, getActiveDeckChangeRequest, sendDeckContribution,
}))
vi.mock('sonner', () => ({ toast: { success, warning, error } }))

import i18n, { i18nReady } from '@/shared/config/i18n'
import { DeckContributionForm } from './DeckContributionForm'

const fingerprint = 'a'.repeat(64)
function request(overrides: Partial<DeckChangeRequest> = {}): DeckChangeRequest {
  return {
    id: 'request-1', deck_item_id: 'deck-1', status: 'pending_review', revision: 2,
    title: 'Sửa nghĩa', description: 'Giải thích', overlay_fingerprint: fingerprint,
    requester: { id: 2, username: 'learner' }, owner: { id: 1, username: 'author' },
    item_count: 1, unresolved_conflict_count: 0, change_counts: { note_field_set: 1 },
    can_submit: false, can_review: false, can_resolve: false,
    items: [{ id: 'item-1', change_type: 'note_field_set', path_key: 'Meaning',
      before_value: 'dog', after_value: 'hound', metadata: { field_name: 'Meaning' }, is_conflict: false }],
    conflicts: [], ...overrides,
  }
}

describe('single-action deck contributions', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let local: LocalChangesPreview
  let active: DeckChangeRequest | null

  beforeEach(async () => {
    vi.clearAllMocks()
    await i18nReady
    await i18n.changeLanguage('vi')
    local = {
      deck_install_id: 'install-1', deck_item_id: 'deck-1', overlay_fingerprint: fingerprint,
      item_count: 1, change_counts: { note_field_set: 1 },
      items: [{ change_type: 'note_field_set', path_key: 'Meaning', before_value: 'dog',
        after_value: 'hound', metadata_json: { field_name: 'Meaning' } }],
    }
    active = null
    getLocalDeckChanges.mockImplementation(async () => local)
    getActiveDeckChangeRequest.mockImplementation(async () => ({ request: active }))
    sendDeckContribution.mockImplementation(async () => { active = request(); return active })
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

  async function render() {
    await act(async () => root.render(
      <MemoryRouter initialEntries={['/flashcards/shared-decks/deck-1/change-request']}>
        <QueryClientProvider client={client}>
          <Routes>
            <Route path="/flashcards/shared-decks/:deckItemId/change-request" element={<DeckContributionForm />} />
            <Route path="/flashcards/change-requests/:requestId" element={<div>Xử lý các field xung đột</div>} />
          </Routes>
        </QueryClientProvider>
      </MemoryRouter>,
    ))
    await vi.waitFor(() => expect(container.querySelector('#contribution-title')).not.toBeNull())
  }

  function sendButton() {
    return Array.from(container.querySelectorAll('button')).find((button) =>
      /Gửi đóng góp|Đang gửi đóng góp|Đã gửi/.test(button.textContent || ''))!
  }

  async function waitFor(check: () => void) {
    await vi.waitFor(async () => {
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
      check()
    })
  }

  async function fill(selector: string, value: string) {
    const input = container.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!
    const prototype = input.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
    await act(async () => {
      Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(input, value)
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
  }

  it('sends directly from saved Note edits with no manual draft or sync buttons', async () => {
    await render()
    expect(container.textContent).not.toContain('Tạo bản nháp')
    expect(container.textContent).not.toContain('Đồng bộ với deck gốc')
    await fill('#contribution-title', '  Sửa nghĩa  ')
    await fill('#contribution-description', '  Giải thích  ')
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false))
    await act(async () => sendButton().click())
    await vi.waitFor(() => expect(sendDeckContribution).toHaveBeenCalledWith('deck-1', {
      title: 'Sửa nghĩa', description: 'Giải thích', expected_overlay_fingerprint: fingerprint,
    }))
    await vi.waitFor(() => expect(sendButton().textContent).toContain('Chờ tác giả duyệt'))
    expect(sendButton().disabled).toBe(true)
  })

  it('explains why title and description alone cannot submit', async () => {
    local = { ...local, item_count: 0, items: [], change_counts: {} }
    await render()
    await fill('#contribution-title', 'Chỉ góp ý')
    await fill('#contribution-description', 'Chưa sửa Note')
    expect(sendButton().disabled).toBe(true)
    expect(container.textContent).toContain('Tiêu đề và mô tả chỉ dùng để giải thích đóng góp.')
    expect(sendDeckContribution).not.toHaveBeenCalled()
  })

  it('handles an older needs_sync request with the same single send action', async () => {
    active = request({ status: 'needs_sync', can_submit: false })
    await render()
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false))
    await act(async () => sendButton().click())
    await vi.waitFor(() => expect(success).toHaveBeenCalled())
    expect(sendDeckContribution).toHaveBeenCalledTimes(1)
  })

  it('opens conflict resolution when the automatic check finds conflicts', async () => {
    sendDeckContribution.mockImplementation(async () => {
      active = request({ status: 'has_conflict', unresolved_conflict_count: 1 })
      return active
    })
    await render()
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false))
    await act(async () => sendButton().click())
    await vi.waitFor(() => expect(container.textContent).toContain('Xử lý các field xung đột'))
    expect(warning).toHaveBeenCalled()
    expect(success).not.toHaveBeenCalled()
  })

  it('prevents a second click while sending and after review submission', async () => {
    let finish!: (value: DeckChangeRequest) => void
    sendDeckContribution.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    await render()
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false))
    await act(async () => sendButton().click())
    await waitFor(() => expect(sendButton().disabled).toBe(true))
    await act(async () => sendButton().click())
    expect(sendDeckContribution).toHaveBeenCalledTimes(1)
    active = request()
    await act(async () => finish(active!))
    await vi.waitFor(() => expect(sendButton().textContent).toContain('Chờ tác giả duyệt'))
    expect(sendButton().disabled).toBe(true)
  })

  it('keeps the form after a network failure so the user can retry', async () => {
    sendDeckContribution.mockRejectedValueOnce(new Error('Mất kết nối'))
    await render()
    await fill('#contribution-title', 'Chưa mất tiêu đề')
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false))
    await act(async () => sendButton().click())
    await vi.waitFor(() => expect(error).toHaveBeenCalledWith('Mất kết nối'))
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false))
    expect(container.querySelector<HTMLInputElement>('#contribution-title')!.value).toBe('Chưa mất tiêu đề')
  })

  it('refreshes a stale preview and asks the user to review before retrying', async () => {
    sendDeckContribution.mockRejectedValueOnce(new ApiError('Stale', 409, 'CHANGE_REQUEST_STALE'))
    await render()
    await vi.waitFor(() => expect(sendButton().disabled).toBe(false))
    await act(async () => sendButton().click())
    await vi.waitFor(() => expect(error).toHaveBeenCalledWith(
      'Nội dung đã lưu vừa thay đổi. Hãy kiểm tra lại danh sách trước khi gửi.',
    ))
    await vi.waitFor(() => expect(getLocalDeckChanges.mock.calls.length).toBeGreaterThan(1))
    expect(sendDeckContribution).toHaveBeenCalledTimes(1)
  })

  it('shows current personal edits when they have changed since the old draft', async () => {
    active = request({ status: 'draft', overlay_fingerprint: 'b'.repeat(64),
      items: [{ ...request().items[0], after_value: 'old draft value' }] })
    local = { ...local, items: [{ ...local.items[0], after_value: 'latest saved value' }] }
    await render()
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-expanded="false"]')!.click())
    expect(container.textContent).toContain('latest saved value')
    expect(container.textContent).not.toContain('old draft value')
  })
})
