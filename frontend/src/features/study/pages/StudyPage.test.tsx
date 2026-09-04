// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  requestFullscreen: vi.fn(),
  requestTakeover: vi.fn(),
  answer: vi.fn(),
  undo: vi.fn(),
  commit: vi.fn(),
  prepareDecision: vi.fn(),
  updateCardContent: vi.fn(),
  getBootstrap: vi.fn(),
  blockerState: {
    state: 'unblocked' as 'unblocked' | 'blocked' | 'proceeding',
    proceed: vi.fn(),
    reset: vi.fn(),
  },
  sessionHookData: {
    session: null,
    view: null,
    receipt: null,
    error: null,
    leaseConflict: true,
    takeoverState: 'idle' as const,
    isLoading: false,
    isBusy: false,
    canUndo: false,
  } as any,
}))

vi.mock('@/app/api', () => ({
  appApi: {
    getBootstrap: mocks.getBootstrap,
  },
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
    useSearchParams: () => [new URLSearchParams('deck_id=12')],
    useBlocker: () => mocks.blockerState,
  }
})

vi.mock('../hooks/useStudySession', () => ({
  useStudySession: () => ({
    ...mocks.sessionHookData,
    prepareDecision: mocks.prepareDecision,
    answer: mocks.answer,
    undo: mocks.undo,
    commit: mocks.commit,
    requestTakeover: mocks.requestTakeover,
    updateCardContent: mocks.updateCardContent,
  }),
}))

import { MemoryRouter } from 'react-router-dom'
import { StudyPage } from './StudyPage'

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient

function renderWithClient(ui: React.ReactNode) {
  return (
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        {ui}
      </QueryClientProvider>
    </MemoryRouter>
  )
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  for (const mock of Object.values(mocks)) {
    if (typeof mock === 'function' && 'mockReset' in mock) {
      mock.mockReset()
    }
  }
  mocks.getBootstrap.mockResolvedValue({ user: { id: 7, is_admin: false } })
  mocks.sessionHookData = {
    session: null,
    view: null,
    receipt: null,
    error: null,
    leaseConflict: true,
    takeoverState: 'idle',
    isLoading: false,
    isBusy: false,
    canUndo: false,
    updateCardContent: mocks.updateCardContent,
  }
  mocks.blockerState = {
    state: 'unblocked',
    proceed: vi.fn(),
    reset: vi.fn(),
  }
  mocks.requestFullscreen.mockResolvedValue(undefined)
  Object.defineProperty(document.documentElement, 'requestFullscreen', {
    configurable: true,
    value: mocks.requestFullscreen,
  })
})

afterEach(async () => {
  if (root) await act(async () => root?.unmount())
  root = null
  container?.remove()
  container = null
  document.body.replaceChildren()
})

describe('StudyPage session conflict keyboard behavior', () => {
  it('leaves Enter, Space, and fullscreen shortcuts to the conflict UI', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    const takeoverButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('Chuyển phiên sang tab này'),
    )
    expect(takeoverButton).toBeDefined()
    takeoverButton?.focus()

    for (const event of [
      new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        bubbles: true,
        cancelable: true,
      }),
      new KeyboardEvent('keydown', {
        key: ' ',
        code: 'Space',
        bubbles: true,
        cancelable: true,
      }),
      new KeyboardEvent('keydown', {
        key: 'f',
        code: 'KeyF',
        bubbles: true,
        cancelable: true,
      }),
    ]) {
      await act(async () => {
        window.dispatchEvent(event)
      })
      expect(event.defaultPrevented).toBe(false)
    }

    expect(mocks.prepareDecision).not.toHaveBeenCalled()
    expect(mocks.answer).not.toHaveBeenCalled()
    expect(mocks.requestFullscreen).not.toHaveBeenCalled()
  })
})

describe('StudyPage undo interactions', () => {
  function setupActiveStudy() {
    mocks.sessionHookData = {
      session: {
        snapshot: {
          session_id: 'session-1',
          scope: { name: 'Test Deck' },
        },
        events: [{ event_id: 'e1' }],
      } as any,
      view: {
        card: { card_id: 'card-2', note_id: 10 },
        template: { front_source: 'front', back_source: 'back' },
        content: { field_values: {} },
        counts: { new: 5, learning: 1, due: 2 },
        session_state: 'active',
      } as any,
      receipt: null,
      error: null,
      leaseConflict: false,
      takeoverState: 'idle',
      isLoading: false,
      isBusy: false,
      canUndo: true,
    }
    mocks.undo.mockResolvedValue('card-1')
    mocks.prepareDecision.mockReturnValue({ previews: {} })
  }

  it('triggers undo via Ctrl+Z shortcut', async () => {
    setupActiveStudy()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    const ctrlZEvent = new KeyboardEvent('keydown', {
      key: 'z',
      code: 'KeyZ',
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    })

    await act(async () => {
      window.dispatchEvent(ctrlZEvent)
    })

    expect(ctrlZEvent.defaultPrevented).toBe(true)
    expect(mocks.undo).toHaveBeenCalledOnce()
  })

  it('triggers undo via Z key shortcut', async () => {
    setupActiveStudy()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    const zEvent = new KeyboardEvent('keydown', {
      key: 'z',
      code: 'KeyZ',
      bubbles: true,
      cancelable: true,
    })

    await act(async () => {
      window.dispatchEvent(zEvent)
    })

    expect(zEvent.defaultPrevented).toBe(true)
    expect(mocks.undo).toHaveBeenCalledOnce()
  })

  it('triggers undo via clicking the Hoàn tác button in StudyBottomBar', async () => {
    setupActiveStudy()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    const undoButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('Hoàn tác'),
    )
    expect(undoButton).toBeDefined()
    expect(undoButton?.hasAttribute('disabled')).toBe(false)

    await act(async () => {
      undoButton?.click()
    })

    expect(mocks.undo).toHaveBeenCalledOnce()
  })

  it('ignores forged flama:host-command events without modifying study state', async () => {
    setupActiveStudy()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    await act(async () => {
      window.dispatchEvent(
        new CustomEvent('flama:host-command', {
          detail: { command: 'rate_good', instanceId: 'test-inst' },
        }),
      )
    })

    expect(mocks.answer).not.toHaveBeenCalled()
    expect(mocks.undo).not.toHaveBeenCalled()
  })
})

describe('StudyPage quick edit interactions', () => {
  function setupActiveStudy() {
    mocks.sessionHookData = {
      session: {
        snapshot: {
          session_id: 'session-1',
          scope: { name: 'Test Deck' },
        },
        events: [{ event_id: 'e1' }],
      } as any,
      view: {
        card: { card_id: 'card-2', note_id: '10', can_edit_card: true },
        template: {
          front_source: 'front',
          back_source: 'back',
          field_defs: [{ name: 'Word', field_type: 'text', required: true }],
        },
        content: { field_values: { Word: '日本語' } },
        counts: { new: 5, learning: 1, due: 2 },
        session_state: 'active',
      } as any,
      receipt: null,
      error: null,
      leaseConflict: false,
      takeoverState: 'idle',
      isLoading: false,
      isBusy: false,
      canUndo: false,
    }
    mocks.prepareDecision.mockReturnValue({ previews: {} })
  }

  it('opens quick edit dialog via E key shortcut', async () => {
    setupActiveStudy()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    const eEvent = new KeyboardEvent('keydown', {
      key: 'e',
      code: 'KeyE',
      bubbles: true,
      cancelable: true,
    })

    await act(async () => {
      window.dispatchEvent(eEvent)
    })

    expect(eEvent.defaultPrevented).toBe(true)
    const dialogTitle = document.querySelector('[data-slot="dialog-content"]')
    expect(dialogTitle).not.toBeNull()
    expect(document.body.textContent).toContain('Sửa nhanh thẻ')
  })

  it('opens quick edit dialog via Sửa thẻ button in header toolbar', async () => {
    setupActiveStudy()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    const editButtons = Array.from(container.querySelectorAll('button')).filter(
      (button) => button.textContent?.includes('Sửa thẻ') || button.getAttribute('aria-label')?.includes('Sửa nhanh thẻ'),
    )
    expect(editButtons.length).toBeGreaterThan(0)

    await act(async () => {
      editButtons[0].click()
    })

    expect(document.body.textContent).toContain('Sửa nhanh thẻ')
  })
})

describe('StudyPage error state rendering', () => {
  it('renders StudyScopeErrorCard when session fails with DECK_ACCESS_DENIED', async () => {
    const { ApiError } = await import('@/shared/api/client')
    mocks.sessionHookData = {
      session: null,
      view: null,
      receipt: null,
      error: new ApiError('Bạn không thể truy cập bộ thẻ này.', 403, 'DECK_ACCESS_DENIED', undefined, {
        deck_id: 12,
        deck_name: 'Minna no Nihongo',
        marketplace_url: '/marketplace/decks/item-minna',
      }),
      leaseConflict: false,
      takeoverState: 'idle',
      isLoading: false,
      isBusy: false,
      canUndo: false,
    }

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    expect(container?.textContent).toContain('Bạn không thể truy cập bộ thẻ này')
    expect(container?.textContent).toContain('Minna no Nihongo')
    const links = Array.from(container?.querySelectorAll('a') || [])
    const marketLink = links.find((a) => a.textContent?.includes('Khám phá Chợ bộ thẻ'))
    expect(marketLink?.getAttribute('href')).toBe('/marketplace/decks/item-minna')
  })

  it('renders StudyScopeErrorCard when session fails with DECK_NOT_FOUND', async () => {
    const { ApiError } = await import('@/shared/api/client')
    mocks.sessionHookData = {
      session: null,
      view: null,
      receipt: null,
      error: new ApiError('Bộ thẻ không tồn tại hoặc đã bị xóa.', 404, 'DECK_NOT_FOUND'),
      leaseConflict: false,
      takeoverState: 'idle',
      isLoading: false,
      isBusy: false,
      canUndo: false,
    }

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    expect(container?.textContent).toContain('Bộ thẻ không tồn tại')
    const links = Array.from(container?.querySelectorAll('a') || [])
    const dashboardLink = links.find((a) => a.textContent?.includes('Về Dashboard'))
    expect(dashboardLink?.getAttribute('href')).toBe('/dashboard')
  })
})

describe('StudyPage exit confirmation and completion card gating', () => {
  function setupActiveStudyWithUncommittedEvents() {
    mocks.sessionHookData = {
      session: {
        status: 'active',
        snapshot: {
          session_id: 'session-1',
          scope: { name: 'Test Deck' },
        },
        events: [{ event_id: 'e1' }, { event_id: 'e2' }],
      } as any,
      view: {
        card: { card_id: 'card-1', note_id: 10 },
        template: { front_source: 'front', back_source: 'back' },
        content: { field_values: {} },
        counts: { new: 3, learning: 1, due: 2 },
        session_state: 'active',
      } as any,
      receipt: null,
      error: null,
      leaseConflict: false,
      takeoverState: 'idle',
      isLoading: false,
      isBusy: false,
      canUndo: false,
    }
    mocks.commit.mockResolvedValue({
      schema_version: 'study-commit-receipt.v1',
      session_id: 'session-1',
      commit_id: 'commit-1',
      commit_reason: 'manual_exit',
      applied_event_count: 2,
      updated_cards: [],
      rating_counts: { again: 0, hard: 0, good: 2, easy: 0 },
      committed_at: '2026-09-05T00:00:00.000Z',
    })
  }

  it('calls commit and blocker.proceed on Save & Exit without showing completion card', async () => {
    setupActiveStudyWithUncommittedEvents()
    mocks.blockerState = {
      state: 'blocked',
      proceed: vi.fn(),
      reset: vi.fn(),
    }

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    expect(document.body.textContent).toContain('Kết thúc phiên học?')
    expect(document.body.textContent).toContain('2 thẻ')

    const saveButton = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Lưu & Thoát'),
    )
    expect(saveButton).toBeDefined()

    await act(async () => {
      saveButton?.click()
    })

    expect(mocks.commit).toHaveBeenCalledWith({ reason: 'manual_exit' })
    expect(mocks.blockerState.proceed).toHaveBeenCalledOnce()
    expect(document.body.textContent).not.toContain('Hoàn thành lượt học hôm nay')
  })

  it('calls blocker.proceed on Discard & Exit without calling commit', async () => {
    setupActiveStudyWithUncommittedEvents()
    mocks.blockerState = {
      state: 'blocked',
      proceed: vi.fn(),
      reset: vi.fn(),
    }

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    const discardButton = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Thoát không lưu tiến độ này'),
    )
    expect(discardButton).toBeDefined()

    await act(async () => {
      discardButton?.click()
    })

    expect(mocks.commit).not.toHaveBeenCalled()
    expect(mocks.blockerState.proceed).toHaveBeenCalledOnce()
  })

  it('renders StudyCompletionCard only when session is complete for today', async () => {
    mocks.sessionHookData = {
      session: {
        status: 'committed',
        snapshot: {
          session_id: 'session-1',
          scope: { name: 'Test Deck' },
        },
        events: [],
      } as any,
      view: {
        card: null,
        template: null,
        content: null,
        counts: { new: 0, learning: 0, due: 0 },
        session_state: 'complete_today',
      } as any,
      receipt: {
        schema_version: 'study-commit-receipt.v1',
        session_id: 'session-1',
        commit_id: 'commit-finish',
        commit_reason: 'auto_finish',
        applied_event_count: 10,
        updated_cards: [],
        rating_counts: { again: 1, hard: 1, good: 6, easy: 2 },
        committed_at: '2026-09-05T00:00:00.000Z',
      },
      error: null,
      leaseConflict: false,
      takeoverState: 'idle',
      isLoading: false,
      isBusy: false,
      canUndo: false,
    }

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    expect(container?.textContent).toContain('Đã đồng bộ phiên học')
    expect(container?.textContent).toContain('Về Dashboard')
  })
})


