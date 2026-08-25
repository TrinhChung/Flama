// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const {
  applyPreparedInstalledUpdate,
  getInstalledDeckUpdate,
  getInstalledDeckUpdates,
  getInstalledUpdateConflicts,
  markInstalledDeckUpdateSeen,
  prepareInstalledDeckUpdate,
  resolveInstalledUpdateConflict,
} = vi.hoisted(() => ({
  applyPreparedInstalledUpdate: vi.fn(),
  getInstalledDeckUpdate: vi.fn(),
  getInstalledDeckUpdates: vi.fn(),
  getInstalledUpdateConflicts: vi.fn(),
  markInstalledDeckUpdateSeen: vi.fn(),
  prepareInstalledDeckUpdate: vi.fn(),
  resolveInstalledUpdateConflict: vi.fn(),
}))

vi.mock('../api', () => ({
  applyPreparedInstalledUpdate,
  getInstalledDeckUpdate,
  getInstalledDeckUpdates,
  getInstalledUpdateConflicts,
  markInstalledDeckUpdateSeen,
  prepareInstalledDeckUpdate,
  resolveInstalledUpdateConflict,
}))

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    loading: vi.fn(),
    dismiss: vi.fn(),
  },
}))

import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { InstalledDeckUpdatePage } from './InstalledDeckUpdatePage'

function findButton(root: ParentNode, label: string) {
  const button = Array.from(root.querySelectorAll('button')).find(
    (candidate) => candidate.textContent?.includes(label),
  )
  expect(button, `Không tìm thấy nút “${label}”`).toBeTruthy()
  return button as HTMLButtonElement
}

function conflict(id: string, noteLabel: string) {
  return {
    id,
    change_id: `change-${id}`,
    note_label: noteLabel,
    field_name: 'Meaning',
    base_value: 'old',
    local_value: 'local',
    upstream_value: 'upstream',
    resolution_mode: null,
    resolved_at: null,
  }
}

describe('InstalledDeckUpdatePage rebase conflict pagination', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    getInstalledDeckUpdates.mockResolvedValue({
      installation: {
        id: 'install-1',
        deck_item_id: 'deck-1',
        title: 'Deck N5',
        applied_release: { id: 'release-1', version_label: '1.0.0' },
        available_release: { id: 'release-2', version_label: '1.1.0' },
        overlay_revision: 7,
      },
      items: [],
      update_available: true,
      unread_update: false,
      change_count: 101,
    })
    getInstalledDeckUpdate.mockResolvedValue({
      installation: {
        id: 'install-1',
        applied_release: { id: 'release-1', version_label: '1.0.0' },
      },
      from_release: { id: 'release-1', version_label: '1.0.0' },
      target_release: { id: 'release-2', version_label: '1.1.0' },
      changelog: 'Bổ sung nghĩa mới',
      summary: {
        total: 101,
        entities: 101,
        added: 0,
        modified: 101,
        removed: 0,
        conflicts: 0,
      },
      items: [],
      next_cursor: null,
    })
    prepareInstalledDeckUpdate.mockResolvedValue({
      rebase_id: 'rebase-1',
      status: 'conflicts',
      conflict_count: 101,
      resolved_conflict_count: 0,
      expected_overlay_revision: 7,
      conflicts: [conflict('100', 'Note trang đầu')],
      conflict_page: {
        limit: 100,
        has_more: true,
        next_after_id: '100',
      },
    })
    getInstalledUpdateConflicts.mockResolvedValue({
      rebase_id: 'rebase-1',
      status: 'conflicts',
      conflict_count: 101,
      resolved_conflict_count: 1,
      items: [conflict('101', 'Note trang sau')],
      page: {
        limit: 100,
        has_more: false,
        next_after_id: null,
      },
    })
    resolveInstalledUpdateConflict.mockImplementation(
      (_rebaseId: string, conflictId: string) => Promise.resolve({
        rebase_id: 'rebase-1',
        status: conflictId === '101' ? 'ready' : 'conflicts',
        conflict_count: 101,
        resolved_conflict_count: conflictId === '101' ? 101 : 1,
        conflicts: [],
      }),
    )
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    queryClient.clear()
    container.remove()
  })

  it('saves choices immediately, lazy-loads next pages, and enables apply from backend counts', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={['/installed-decks/install-1/updates/release-2']}>
          <QueryClientProvider client={queryClient}>
            <Routes>
              <Route
                path="/installed-decks/:installId/updates/:releaseId"
                element={<InstalledDeckUpdatePage />}
              />
            </Routes>
          </QueryClientProvider>
        </MemoryRouter>,
      )
    })

    await vi.waitFor(() => {
      expect(container.textContent).toContain('Bổ sung nghĩa mới')
    })

    await act(async () => findButton(container, 'Kiểm tra xung đột').click())
    await vi.waitFor(() => {
      expect(container.textContent).toContain('Note trang đầu')
    })
    expect(getInstalledUpdateConflicts).not.toHaveBeenCalled()

    const conflictSection = container.querySelector('#update-conflicts-title')?.closest('section')
    expect(conflictSection).toBeTruthy()
    const applyButton = findButton(container, 'Áp dụng phiên bản')
    expect(applyButton.disabled).toBe(true)

    await act(async () => findButton(conflictSection!, 'Giữ bản của tôi').click())
    await vi.waitFor(() => {
      expect(resolveInstalledUpdateConflict).toHaveBeenCalledWith(
        'rebase-1',
        '100',
        'keep_mine',
      )
      expect(conflictSection?.textContent).toContain('Đã xử lý 1/101')
    })
    expect(applyButton.disabled).toBe(true)
    expect(applyPreparedInstalledUpdate).not.toHaveBeenCalled()

    await act(async () => findButton(conflictSection!, 'Trang tiếp').click())
    await vi.waitFor(() => {
      expect(conflictSection?.textContent).toContain('Note trang sau')
    })
    expect(getInstalledUpdateConflicts).toHaveBeenCalledWith(
      'rebase-1',
      '100',
      100,
      expect.any(AbortSignal),
    )
    expect(conflictSection?.textContent).not.toContain('Note trang đầu')

    await act(async () => findButton(conflictSection!, 'Trang trước').click())
    expect(conflictSection?.textContent).toContain('Note trang đầu')
    expect(conflictSection?.textContent).not.toContain('Note trang sau')
    expect(getInstalledUpdateConflicts).toHaveBeenCalledTimes(1)

    await act(async () => findButton(conflictSection!, 'Trang tiếp').click())
    expect(conflictSection?.textContent).toContain('Note trang sau')
    expect(getInstalledUpdateConflicts).toHaveBeenCalledTimes(1)

    await act(async () => findButton(conflictSection!, 'Nhận bản cập nhật').click())
    await vi.waitFor(() => {
      expect(resolveInstalledUpdateConflict).toHaveBeenLastCalledWith(
        'rebase-1',
        '101',
        'keep_upstream',
      )
      expect(conflictSection?.textContent).toContain('Đã xử lý 101/101')
      expect(applyButton.disabled).toBe(false)
    })
  })
})
