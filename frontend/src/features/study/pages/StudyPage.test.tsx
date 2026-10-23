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
  reloadSession: vi.fn(),
  discardSession: vi.fn(),
  prepareDecision: vi.fn(),
  updateCardContent: vi.fn(),
  startPreparedSession: vi.fn(),
  startComposition: vi.fn(),
  applyTemplateBindings: vi.fn(),
  loadPreparation: vi.fn(),
  saveBindings: vi.fn(),
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
    reloadSession: mocks.reloadSession,
    discardSession: mocks.discardSession,
    requestTakeover: mocks.requestTakeover,
    updateCardContent: mocks.updateCardContent,
    startPreparedSession: mocks.startPreparedSession,
    startComposition: mocks.startComposition,
    applyTemplateBindings: mocks.applyTemplateBindings,
    templatePreparation: mocks.sessionHookData.templatePreparation ?? preparationState(null),
  }),
}))

import { MemoryRouter } from 'react-router-dom'
import { StudyPage } from './StudyPage'

function preparationState(availability: unknown) {
  return {
    availability, preset: null, isLoading: false, isSaving: false, error: null,
    compositionId: 'c1',
    inputBindings: { term: 'f1' },
    staleInputs: [],
    remember: false,
    askBeforeStudy: true,
    entry: {
      input_schema: [{ key: 'term', label: 'Term', type: 'text', required: true }],
      field_defs: [{ id: 'f1', name: 'Front', field_type: 'text' }],
      input_bindings: { term: 'f1' },
      warnings: [],
    },
    load: mocks.loadPreparation,
    submit: vi.fn(),
    selectComposition: vi.fn(),
    changeBindings: vi.fn(),
    setRemember: vi.fn(),
    setAskBeforeStudy: vi.fn(),
    saveBindings: mocks.saveBindings,
    mappingOf: (compositionId: string) => compositionId === 'c1'
      ? { inputBindings: { term: 'f1' }, staleInputs: [], customized: false } : null,
    selectionFor: (compositionId: string) => ({ compositionId }),
  }
}

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
    templatePreparation: preparationState(null),
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
  it('shows preparation for a new lease and forwards its start action without study controls', async () => {
    const first = { composition_id: 'c1', template_name: 'Card A', context_kind: 'owned' }
    const second = { composition_id: 'c2', template_name: 'Card B', context_kind: 'owned' }
    mocks.sessionHookData = { ...mocks.sessionHookData, leaseConflict: false, awaitingCompositionSelection: true,
      compositionGroups: [{ note_type_id: 'nt', note_type_name: 'Basic', compositions: [first, second] }],
      templatePreparation: preparationState({
        compositions: [first, second], note_counts: { c1: 5, c2: 3 },
        template_inputs: {
          c1: { input_schema: [{ key: 'term', label: 'Term', type: 'text', required: true }], field_defs: [{ id: 'f1', name: 'Front', field_type: 'text' }], input_bindings: { term: 'f1' }, warnings: [] },
          c2: { input_schema: [], field_defs: [], input_bindings: {}, warnings: [] },
        },
      }) }
    container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container)
    await act(async () => root?.render(renderWithClient(<StudyPage />)))
    expect(container.textContent).toContain('Chuẩn bị phiên học')
    expect(container.querySelector('.study-page')).toBeNull()
    expect(container.querySelector('a[href="/dashboard"]')).not.toBeNull()
    expect(container.querySelector('select')).not.toBeNull()
    const start = Array.from(container.querySelectorAll('button')).find((button) => button.textContent === 'Bắt đầu học')!
    await act(async () => start.click())
    expect(mocks.startPreparedSession).toHaveBeenCalledOnce()
  })

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

  it('reloads normally without passing the click event as the force flag', async () => {
    setupActiveStudy()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })

    const moreButton = container.querySelector<HTMLButtonElement>('button[aria-haspopup="menu"]')
    expect(moreButton).not.toBeNull()
    await act(async () => {
      moreButton?.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, cancelable: true }))
      moreButton?.click()
    })
    const reloadItem = Array.from(document.body.querySelectorAll('[role="menuitem"]')).find(
      (item) => item.querySelector('svg.lucide-rotate-ccw'),
    )
    expect(reloadItem).not.toBeUndefined()
    await act(async () => {
      reloadItem?.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
    })
    expect(mocks.reloadSession).toHaveBeenCalledExactlyOnceWith()
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

describe('StudyPage trusted keyboard boundary', () => {
  function setupActiveStudy() {
    mocks.sessionHookData = {
      session: {
        snapshot: {
          session_id: 'session-keyboard',
          scope: { name: 'Keyboard Deck' },
        },
        events: [],
      } as any,
      view: {
        card: { card_id: 'card-keyboard', note_id: 'note-keyboard' },
        template: { front_source: 'front', back_source: 'back' },
        content: { field_values: {} },
        counts: { new: 1, learning: 0, due: 0 },
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

  async function renderActiveStudy() {
    setupActiveStudy()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyPage />))
    })
  }

  it('does not capture shortcuts from editable parent controls', async () => {
    await renderActiveStudy()
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    const event = new KeyboardEvent('keydown', {
      key: ' ',
      code: 'Space',
      bubbles: true,
      cancelable: true,
    })
    await act(async () => window.dispatchEvent(event))

    expect(event.defaultPrevented).toBe(false)
    expect(mocks.prepareDecision).not.toHaveBeenCalled()
    expect(mocks.answer).not.toHaveBeenCalled()
  })

  it('does not capture IME composition or repeated keydown events', async () => {
    await renderActiveStudy()
    const composing = new KeyboardEvent('keydown', {
      key: ' ',
      code: 'Space',
      bubbles: true,
      cancelable: true,
      isComposing: true,
    })
    const repeated = new KeyboardEvent('keydown', {
      key: ' ',
      code: 'Space',
      bubbles: true,
      cancelable: true,
      repeat: true,
    })

    await act(async () => {
      window.dispatchEvent(composing)
      window.dispatchEvent(repeated)
    })

    expect(composing.defaultPrevented).toBe(false)
    expect(repeated.defaultPrevented).toBe(false)
    expect(mocks.prepareDecision).not.toHaveBeenCalled()
    expect(mocks.answer).not.toHaveBeenCalled()
  })

  function keydown(key: string, code: string) {
    return new KeyboardEvent('keydown', { key, code, bubbles: true, cancelable: true })
  }

  it('handles shortcuts and drops focus left on a control by a click or a closed menu', async () => {
    await renderActiveStudy()
    const moreButton = container!.querySelector<HTMLButtonElement>('button[aria-haspopup="menu"]')!
    // Radix hands focus back to the trigger on close; a mouse click leaves it too.
    moreButton.focus()

    // Dispatched on the trigger itself, so Radix's own Space handler sees it too.
    const space = keydown(' ', 'Space')
    await act(async () => moreButton.dispatchEvent(space))

    expect(space.defaultPrevented).toBe(true)
    expect(mocks.prepareDecision).toHaveBeenCalledOnce()
    expect(document.querySelector('[role="menu"]')).toBeNull()
    expect(document.activeElement).not.toBe(moreButton)

    moreButton.focus()
    const good = keydown('3', 'Digit3')
    await act(async () => moreButton.dispatchEvent(good))

    expect(good.defaultPrevented).toBe(true)
    expect(mocks.answer).toHaveBeenCalledOnce()
  })

  it('keeps native Space on a control reached with Tab', async () => {
    await renderActiveStudy()
    const moreButton = container!.querySelector<HTMLButtonElement>('button[aria-haspopup="menu"]')!
    await act(async () => {
      window.dispatchEvent(keydown('Tab', 'Tab'))
      moreButton.focus()
      window.dispatchEvent(new KeyboardEvent('keyup', { key: 'Tab', code: 'Tab', bubbles: true }))
    })

    const space = keydown(' ', 'Space')
    await act(async () => moreButton.dispatchEvent(space))
    expect(mocks.prepareDecision).not.toHaveBeenCalled()
    // Radix opened its menu natively from the Tab-focused trigger.
    expect(document.querySelector('[role="menu"]')).not.toBeNull()
  })

  it('keeps native Enter on a link reached with Tab', async () => {
    await renderActiveStudy()
    const decksLink = container!.querySelector<HTMLAnchorElement>('a[href="/dashboard"]')!
    await act(async () => {
      window.dispatchEvent(keydown('Tab', 'Tab'))
      decksLink.focus()
    })

    const enter = keydown('Enter', 'Enter')
    await act(async () => decksLink.dispatchEvent(enter))

    expect(enter.defaultPrevented).toBe(false)
    expect(mocks.prepareDecision).not.toHaveBeenCalled()
  })

  it('ignores Tab focus tracking left over from before a mouse focus', async () => {
    await renderActiveStudy()
    const moreButton = container!.querySelector<HTMLButtonElement>('button[aria-haspopup="menu"]')!
    await act(async () => {
      window.dispatchEvent(keydown('Tab', 'Tab'))
      window.dispatchEvent(new KeyboardEvent('keyup', { key: 'Tab', code: 'Tab', bubbles: true }))
      moreButton.focus()
    })

    const space = keydown(' ', 'Space')
    await act(async () => moreButton.dispatchEvent(space))

    expect(space.defaultPrevented).toBe(true)
    expect(mocks.prepareDecision).toHaveBeenCalledOnce()
  })

  it('takes rating keys on a Tab-focused control without blurring it', async () => {
    await renderActiveStudy()
    const moreButton = container!.querySelector<HTMLButtonElement>('button[aria-haspopup="menu"]')!
    await act(async () => window.dispatchEvent(keydown(' ', 'Space')))
    expect(mocks.prepareDecision).toHaveBeenCalledOnce()
    await act(async () => {
      window.dispatchEvent(keydown('Tab', 'Tab'))
      moreButton.focus()
    })

    const good = keydown('3', 'Digit3')
    await act(async () => moreButton.dispatchEvent(good))
    expect(good.defaultPrevented).toBe(true)
    expect(mocks.answer).toHaveBeenCalledOnce()
    expect(document.activeElement).toBe(moreButton)
  })

  it('leaves keys to an open menu instead of the card behind it', async () => {
    await renderActiveStudy()
    const moreButton = container!.querySelector<HTMLButtonElement>('button[aria-haspopup="menu"]')!
    await act(async () => {
      moreButton.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, cancelable: true }))
      moreButton.click()
    })
    expect(document.querySelector('[role="menu"]')).not.toBeNull()

    const events = [keydown(' ', 'Space'), keydown('z', 'KeyZ'), keydown('f', 'KeyF')]
    await act(async () => {
      for (const event of events) window.dispatchEvent(event)
    })

    for (const event of events) expect(event.defaultPrevented).toBe(false)
    expect(mocks.prepareDecision).not.toHaveBeenCalled()
    expect(mocks.undo).not.toHaveBeenCalled()
    expect(mocks.requestFullscreen).not.toHaveBeenCalled()
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
    expect(mocks.discardSession).toHaveBeenCalledOnce()
    expect(mocks.blockerState.proceed).toHaveBeenCalledOnce()
  })

  it.each([
    ['complete_today', 'auto_finish'],
    ['active', 'page_exit'],
    ['waiting', 'manual_exit'],
  ])('shows the final receipt instead of a spinner for %s / %s', async (sessionState, commitReason) => {
    mocks.sessionHookData = {
      session: {
        status: 'pending_commit',
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
        counts: { new: sessionState === 'active' ? 10 : 0, learning: sessionState === 'waiting' ? 1 : 0, due: 0 },
        session_state: sessionState,
      } as any,
      receipt: {
        schema_version: 'study-commit-receipt.v1',
        session_id: 'session-1',
        commit_id: 'commit-finish',
        commit_reason: commitReason,
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
    expect(container?.textContent).not.toContain('Đang đồng bộ phiên học')
    const shortcut = new KeyboardEvent('keydown', {
      key: 'f', code: 'KeyF', bubbles: true, cancelable: true,
    })
    await act(async () => { window.dispatchEvent(shortcut) })
    expect(shortcut.defaultPrevented).toBe(false)
    expect(mocks.requestFullscreen).not.toHaveBeenCalled()
  })

  it('renders completion screen without error boundary when session completes on a card with array fields', async () => {
    mocks.sessionHookData = {
      session: {
        status: 'active',
        snapshot: {
          session_id: 'session-array-complete',
          scope: { name: 'Array Deck' },
        },
        events: [],
      } as any,
      view: {
        card: null,
        template: null,
        content: {
          schema_version: 'study-content.v1',
          renderer_abi: 'client_v1',
          id: 'cnt-array',
          note_id: 'note-array',
          version: '1',
          field_values: {
            Front: 'Kanji',
            Readings: ['かんじ', 'カンジ'],
            Tags: ['n5', 'array-test'],
          },
          render_context: {},
          media: [],
        },
        counts: { new: 0, learning: 0, due: 0 },
        session_state: 'complete_today',
      } as any,
      receipt: null,
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

    expect(container?.textContent).toContain('Hoàn thành lượt học hôm nay')
    expect(container?.textContent).not.toContain('trim is not a function')
  })
})


