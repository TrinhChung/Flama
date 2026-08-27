// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  StudySessionCommitReceipt,
  StudySessionSnapshot,
} from '../types'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({
  bootstrap: { data: undefined } as { data?: { user?: { id: number } | null } },
  get: vi.fn(),
  mutate: vi.fn(),
  mutateKeepalive: vi.fn(),
  holdLease: vi.fn(),
  invalidateQueries: vi.fn(),
  loadSession: vi.fn(),
  loadQuarantine: null as null | { reason: string; message: string },
  saveSession: vi.fn(),
  removeSession: vi.fn(),
  removeSessionIfMatches: vi.fn(),
}))

vi.mock('@tanstack/react-query', () => ({
  useQueryClient: (() => {
    const queryClient = {
      invalidateQueries: mocks.invalidateQueries,
    }
    return () => queryClient
  })(),
}))

vi.mock('@/app/api', () => ({
  appApi: {
    get: mocks.get,
    mutate: mocks.mutate,
    mutateKeepalive: mocks.mutateKeepalive,
  },
}))

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => mocks.bootstrap,
}))

vi.mock('../session/sessionStore', () => ({
  loadStudySessionWithDurability: async (key: string) => ({
    session: await mocks.loadSession(key),
    durable: true,
    quarantine: mocks.loadQuarantine ?? undefined,
  }),
  saveStudySession: mocks.saveSession,
  removeStudySession: mocks.removeSession,
  removeStudySessionIfMatches: mocks.removeSessionIfMatches,
  scopeKey: (userId: number, scope: string, scopeId: string) => (
    `user:${userId}:${scope}:${scopeId}`
  ),
}))

vi.mock('../session/studySessionLease', () => ({
  holdStudyScopeLease: mocks.holdLease,
}))

import { useStudySession } from './useStudySession'

type LeaseRecord = {
  signal: AbortSignal
  handlers: {
    onBlocked: () => void
    onAcquired: () => void
    onLost?: (error: unknown) => void
  }
}

const leaseRecords: LeaseRecord[] = []

class FakeBroadcastChannel {
  static instances: FakeBroadcastChannel[] = []

  readonly name: string
  readonly posted: unknown[] = []
  private readonly listeners = new Set<(event: MessageEvent<unknown>) => void>()

  constructor(name: string) {
    this.name = name
    FakeBroadcastChannel.instances.push(this)
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    if (type !== 'message' || typeof listener !== 'function') return
    this.listeners.add(listener as (event: MessageEvent<unknown>) => void)
  }

  removeEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    if (type !== 'message' || typeof listener !== 'function') return
    this.listeners.delete(listener as (event: MessageEvent<unknown>) => void)
  }

  postMessage(value: unknown) {
    this.posted.push(value)
  }

  close() {
    this.listeners.clear()
  }

  emit(value: unknown) {
    const event = new MessageEvent('message', { data: value })
    for (const listener of this.listeners) listener(event)
  }
}

function snapshot(): StudySessionSnapshot {
  return {
    schema_version: 'study-session.v2',
    session_id: 'session-1',
    user_id: 7,
    session_token: 'token',
    snapshot_hash: 'snapshot-hash',
    scope: { type: 'deck', id: '12', name: 'Deck N5' },
    server_now_utc: '2099-02-22T09:00:00.000Z',
    expires_at: '2099-02-23T09:00:00.000Z',
    timezone: 'UTC',
    day_boundary_hour_local: 4,
    learn_ahead_seconds: 1200,
    scheduler_algorithm: 'legacy-anki',
    algorithm_version: '1.0.0',
    queue_contract_version: 'flama-queue.v1',
    policies: {
      policy: {
        algorithm_key: 'legacy-anki',
        algorithm_version: '1.0.0',
        config_schema_version: 'scheduler-config.v1',
        config_hash: 'policy',
        timezone: 'UTC',
        preset_id: null,
        config: {
          learning_steps_ms: [60_000, 600_000],
          graduating_interval_days: 1,
          easy_interval_days: 5,
          relearning_steps_ms: [600_000],
          minimum_interval_days: 1,
          starting_ease: 2.5,
          easy_bonus: 1.3,
          interval_modifier: 1,
          hard_factor: 1.2,
          new_interval_factor: 0,
          min_ease: 1.3,
          max_interval_days: 36_500,
          day_boundary_hour_local: 4,
          learn_ahead_seconds: 1200,
          leech_threshold: 8,
          leech_suspend: true,
          scheduler_mode: 'legacy',
          review_fuzz_factor: null,
          fsrs_next_states: null,
        },
      },
    },
    cards: [{
      card_id: 'card-1',
      note_id: 'note-1',
      template_id: 'template-1',
      source_deck_id: 12,
      local_deck_id: 12,
      note_type_id: 'type-1',
      created_at: '2099-02-01T00:00:00.000Z',
      policy_key: 'policy',
      template_key: 'template',
      content_key: 'content',
      base_revision: 0,
      base_state_hash: 'base',
      can_edit_card: true,
      composition_id: 'comp:notetype:type-1:template:template-1',
      state: {
        type: 'new',
        step_index: 0,
        due_at: '2099-02-22T09:00:00.000Z',
        due_day: null,
        interval_days: 0,
        ease: 2.5,
        reps: 0,
        lapses: 0,
        last_review_at: null,
        review_kind: 'review',
        scheduler_mode: 'legacy',
        suspended: false,
        suspension_reason: null,
        leeched: false,
        memory_state: null,
      },
    }],
    templates: {
      template: {
        schema_version: 'study-template.v1',
        renderer_abi: 'test',
        id: 'template-1',
        version: 'v1',
        front_source: '{{Word}}',
        back_source: '{{Word}}',
        front_inline_scripts: [],
        back_inline_scripts: [],
        shared_css: '',
        field_defs: [],
      },
    },
    contents: {
      content: {
        schema_version: 'study-content.v1',
        renderer_abi: 'test',
        id: 'note-1',
        note_id: 'note-1',
        version: 'v1',
        field_values: { Word: 'cat' },
        render_context: { Word: 'cat' },
        media: [],
      },
    },
    compositions: {
      'comp:notetype:type-1:template:template-1': {
        composition_id: 'comp:notetype:type-1:template:template-1',
        mode_key: 'flashcard',
        note_type_id: 'type-1',
        template_id: 'template-1',
        template_name: 'Front -> Back',
        is_default: true,
        interaction_key: 'review.four-rating',
        trigger_key: 'scheduler.review',
        trigger_contract_version: '1',
        algorithm_key: 'legacy-anki',
        algorithm_version: '1.0.0',
      },
    },
  }
}

function receipt(): StudySessionCommitReceipt {
  return {
    schema_version: 'study-commit-receipt.v1',
    success: true,
    session_id: 'session-1',
    commit_id: 'commit-1',
    commit_reason: 'manual_exit',
    applied_event_count: 1,
    updated_cards: [],
    rating_counts: { again: 0, hard: 0, good: 1, easy: 0 },
    committed_at: '2099-02-22T09:01:00.000Z',
  }
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

let latest: ReturnType<typeof useStudySession>
let root: Root | null = null
let container: HTMLDivElement | null = null

function Harness({ deckId }: { deckId: string | null }) {
  latest = useStudySession(deckId)
  return null
}

async function renderHarness(deckId = '12') {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(<Harness deckId={deckId} />)
  })
}

async function waitFor(assertion: () => void) {
  let lastError: unknown
  for (let index = 0; index < 40; index += 1) {
    try {
      assertion()
      return
    } catch (error) {
      lastError = error
    }
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
  }
  throw lastError
}

async function openReadySession() {
  mocks.bootstrap = { data: { user: { id: 7 } } }
  await renderHarness()
  await waitFor(() => expect(latest.session?.snapshot.session_id).toBe('session-1'))
}

beforeEach(() => {
  mocks.bootstrap = { data: undefined }
  mocks.get.mockReset().mockResolvedValue({
    schema_version: 'study-session-status.v1',
    session_id: 'session-1',
    status: 'open',
    expires_at: '2099-02-23T09:00:00.000Z',
    committed_at: null,
  })
  mocks.mutate.mockReset().mockImplementation((path: string) => {
    if (path === '/api/study/sessions') return Promise.resolve(snapshot())
    throw new Error(`Unexpected mutation: ${path}`)
  })
  mocks.mutateKeepalive.mockReset().mockResolvedValue(receipt())
  mocks.invalidateQueries.mockReset().mockResolvedValue(undefined)
  mocks.loadSession.mockReset().mockResolvedValue(null)
  mocks.loadQuarantine = null
  mocks.saveSession.mockReset().mockResolvedValue(true)
  mocks.removeSession.mockReset().mockResolvedValue(undefined)
  mocks.removeSessionIfMatches.mockReset().mockResolvedValue(undefined)
  mocks.holdLease.mockReset().mockImplementation((
    _manager: LockManager | undefined,
    _name: string,
    signal: AbortSignal,
    handlers: LeaseRecord['handlers'],
  ) => {
    leaseRecords.push({ signal, handlers })
    handlers.onAcquired()
    return new Promise<void>((resolve) => {
      if (signal.aborted) {
        resolve()
        return
      }
      signal.addEventListener('abort', () => resolve(), { once: true })
    })
  })
  leaseRecords.length = 0
  FakeBroadcastChannel.instances.length = 0
  vi.stubGlobal('BroadcastChannel', FakeBroadcastChannel)
  vi.stubGlobal('crypto', {
    randomUUID: vi.fn(() => '00000000-0000-4000-8000-000000000001'),
  })
  Object.defineProperty(navigator, 'locks', {
    configurable: true,
    value: {},
  })
})

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount())
  }
  root = null
  container?.remove()
  container = null
  document.body.replaceChildren()
  vi.unstubAllGlobals()
})

describe('useStudySession cross-tab ownership', () => {
  it('blocks opening a replacement session when restored data was quarantined', async () => {
    mocks.loadQuarantine = {
      reason: 'EVENT_CONTRACT_MISMATCH',
      message: 'Stored event mismatch.',
    }
    mocks.bootstrap = { data: { user: { id: 7 } } }

    await renderHarness()

    await waitFor(() => expect(latest.error).toBeInstanceOf(Error))
    expect(latest.session).toBeNull()
    expect(String(latest.error)).toContain('EVENT_CONTRACT_MISMATCH')
    expect(mocks.mutate).not.toHaveBeenCalled()
    expect(mocks.saveSession).not.toHaveBeenCalled()
  })

  it('waits for bootstrap identity before acquiring or opening a session', async () => {
    await renderHarness()

    expect(latest.isLoading).toBe(true)
    expect(mocks.holdLease).not.toHaveBeenCalled()
    expect(mocks.mutate).not.toHaveBeenCalled()

    mocks.bootstrap = { data: { user: { id: 7 } } }
    await act(async () => {
      root?.render(<Harness deckId="12" />)
    })

    await waitFor(() => expect(latest.session).not.toBeNull())
    expect(mocks.holdLease).toHaveBeenCalledWith(
      navigator.locks,
      'flama-study:user:7:deck:12',
      expect.any(AbortSignal),
      expect.any(Object),
    )
    expect(mocks.mutate).toHaveBeenCalledWith(
      '/api/study/sessions',
      'POST',
      { scope: 'deck', scope_id: '12' },
    )
  })

  it('keeps the lease through bootstrap before handing it to another tab', async () => {
    const pendingLoad = deferred<null>()
    mocks.loadSession.mockReturnValueOnce(pendingLoad.promise)
    mocks.bootstrap = { data: { user: { id: 7 } } }
    await renderHarness()
    await waitFor(() => expect(mocks.loadSession).toHaveBeenCalledOnce())

    const record = leaseRecords[0]
    const channel = FakeBroadcastChannel.instances[0]
    await act(async () => {
      channel.emit({
        type: 'handoff-request',
        requester_id: 'requesting-tab',
      })
    })

    expect(latest.leaseConflict).toBe(true)
    expect(record.signal.aborted).toBe(false)
    expect(channel.posted).toContainEqual({
      type: 'handoff-accepted',
      requester_id: 'requesting-tab',
    })

    pendingLoad.resolve(null)
    await waitFor(() => expect(mocks.saveSession).toHaveBeenCalledOnce())
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 80))
    })

    expect(record.signal.aborted).toBe(true)
    expect(latest.session).toBeNull()
  })

  it('withdraws a passive waiter after the owner selects another tab', async () => {
    mocks.holdLease.mockImplementationOnce((
      _manager: LockManager | undefined,
      _name: string,
      signal: AbortSignal,
      handlers: LeaseRecord['handlers'],
    ) => {
      leaseRecords.push({ signal, handlers })
      handlers.onBlocked()
      return new Promise<void>((resolve) => {
        signal.addEventListener('abort', () => resolve(), { once: true })
      })
    })
    mocks.bootstrap = { data: { user: { id: 7 } } }
    await renderHarness()
    await waitFor(() => expect(latest.leaseConflict).toBe(true))

    const record = leaseRecords[0]
    const channel = FakeBroadcastChannel.instances[0]
    await act(async () => {
      channel.emit({
        type: 'handoff-accepted',
        requester_id: 'selected-tab',
      })
    })

    expect(record.signal.aborted).toBe(true)
    expect(latest.leaseConflict).toBe(true)
    expect(mocks.mutate).not.toHaveBeenCalled()
  })

  it('keeps the lease until an in-flight answer is durable before handoff', async () => {
    await openReadySession()
    const pendingSave = deferred<boolean>()
    mocks.saveSession.mockImplementationOnce(() => pendingSave.promise)
    const record = leaseRecords[0]
    const channel = FakeBroadcastChannel.instances[0]
    const decision = latest.prepareDecision('card-1')

    let answerPromise!: Promise<void>
    await act(async () => {
      answerPromise = latest.answer('card-1', 'good', decision, 250)
      await Promise.resolve()
    })
    expect(latest.isBusy).toBe(true)

    await act(async () => {
      channel.emit({
        type: 'handoff-request',
        requester_id: 'requesting-tab',
      })
    })

    expect(latest.leaseConflict).toBe(true)
    expect(record.signal.aborted).toBe(false)
    expect(channel.posted).toContainEqual({
      type: 'handoff-accepted',
      requester_id: 'requesting-tab',
    })

    pendingSave.resolve(true)
    await act(async () => {
      await answerPromise
      await new Promise((resolve) => window.setTimeout(resolve, 80))
    })

    expect(record.signal.aborted).toBe(true)
    expect(latest.session).toBeNull()
  })

  it('does not let a second requester interrupt an owner that is yielding', async () => {
    await openReadySession()
    const pendingSave = deferred<boolean>()
    mocks.saveSession.mockImplementationOnce(() => pendingSave.promise)
    const record = leaseRecords[0]
    const channel = FakeBroadcastChannel.instances[0]
    const decision = latest.prepareDecision('card-1')

    let answerPromise!: Promise<void>
    await act(async () => {
      answerPromise = latest.answer('card-1', 'good', decision, 250)
      await Promise.resolve()
      channel.emit({ type: 'handoff-request', requester_id: 'tab-b' })
      channel.emit({ type: 'handoff-request', requester_id: 'tab-c' })
    })

    expect(record.signal.aborted).toBe(false)
    expect(channel.posted).toContainEqual({
      type: 'handoff-accepted',
      requester_id: 'tab-b',
    })
    expect(channel.posted).toContainEqual({
      type: 'handoff-rejected',
      requester_id: 'tab-c',
    })

    pendingSave.resolve(true)
    await act(async () => {
      await answerPromise
      await new Promise((resolve) => window.setTimeout(resolve, 80))
    })
    expect(record.signal.aborted).toBe(true)
  })

  it('refuses handoff when the current session is not durably stored', async () => {
    await openReadySession()
    mocks.saveSession.mockResolvedValueOnce(false)
    const record = leaseRecords[0]
    const channel = FakeBroadcastChannel.instances[0]
    const decision = latest.prepareDecision('card-1')

    await act(async () => {
      await latest.answer('card-1', 'good', decision, 250)
      channel.emit({
        type: 'handoff-request',
        requester_id: 'requesting-tab',
      })
      await new Promise((resolve) => window.setTimeout(resolve, 40))
    })

    expect(record.signal.aborted).toBe(false)
    expect(channel.posted).toContainEqual({
      type: 'handoff-rejected',
      requester_id: 'requesting-tab',
    })
    expect(latest.leaseConflict).toBe(false)
    expect(latest.session).not.toBeNull()
  })

  it('keeps the physical lease until the exit batch finishes', async () => {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => {
      await latest.answer('card-1', 'good', decision, 250)
    })
    const pendingExitCommit = deferred<StudySessionCommitReceipt>()
    mocks.mutateKeepalive.mockReturnValueOnce(pendingExitCommit.promise)
    const record = leaseRecords[0]

    await act(async () => {
      root?.unmount()
    })
    root = null
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 40))
    })

    expect(mocks.mutateKeepalive).toHaveBeenCalledOnce()
    expect(record.signal.aborted).toBe(false)

    pendingExitCommit.resolve(receipt())
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 80))
    })
    expect(record.signal.aborted).toBe(true)
  })

  it('does not reconcile a commit response after ownership loss', async () => {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => {
      await latest.answer('card-1', 'good', decision, 250)
    })

    const pendingCommit = deferred<StudySessionCommitReceipt>()
    mocks.mutate.mockImplementation((path: string) => {
      if (path === '/api/study/sessions/session-1/commit') {
        return pendingCommit.promise
      }
      if (path === '/api/study/sessions') return Promise.resolve(snapshot())
      throw new Error(`Unexpected mutation: ${path}`)
    })
    mocks.removeSessionIfMatches.mockClear()

    let commitPromise!: Promise<StudySessionCommitReceipt | null>
    await act(async () => {
      commitPromise = latest.commit({ reason: 'manual_exit' })
      await Promise.resolve()
    })
    await waitFor(() => expect(mocks.mutate).toHaveBeenCalledWith(
      '/api/study/sessions/session-1/commit',
      'POST',
      expect.any(Object),
    ))

    await act(async () => {
      leaseRecords[0].handlers.onLost?.(new DOMException(
        'Lock was stolen.',
        'AbortError',
      ))
    })
    expect(latest.leaseConflict).toBe(true)
    expect(latest.session).toBeNull()

    pendingCommit.resolve(receipt())
    await act(async () => {
      await commitPromise
    })

    expect(latest.session).toBeNull()
    expect(latest.receipt).toBeNull()
    expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
  })

  it('allows undoing an answered card and persists the restored session', async () => {
    await openReadySession()
    expect(latest.canUndo).toBe(false)

    const decision = latest.prepareDecision('card-1')
    await act(async () => {
      await latest.answer('card-1', 'good', decision, 250)
    })

    expect(latest.session?.events).toHaveLength(1)
    expect(latest.canUndo).toBe(true)

    let undoneCardId: string | null = null
    await act(async () => {
      undoneCardId = await latest.undo()
    })

    expect(undoneCardId).toBe('card-1')
    expect(latest.session?.events).toHaveLength(0)
    expect(latest.canUndo).toBe(false)
    expect(latest.view?.card?.card_id).toBe('card-1')
    expect(mocks.saveSession).toHaveBeenCalled()
  })
})
