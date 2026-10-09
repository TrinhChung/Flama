// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  StudySessionEvent,
  StudySessionCommitReceipt,
  StudySessionSnapshot,
  StudyBatchPayload,
} from '../types'
import { canonicalDigest } from '../session/canonicalDigest'

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
  acknowledgeQuarantine: vi.fn(),
  saveSession: vi.fn(),
  updateStoredCardContent: vi.fn().mockResolvedValue(undefined),
  removeSession: vi.fn(),
  removeSessionIfMatches: vi.fn(),
  quarantineSession: vi.fn(),
  templatePreset: vi.fn(),
  saveTemplatePreset: vi.fn(),
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

vi.mock('@/entities/card-template', () => ({
  fetchStudyTemplateInputs: async (deckId: string) => {
    const availability = await mocks.get(`/api/study/scopes/deck/${deckId}/compositions`)
    return { ...availability, note_counts: {}, template_inputs: Object.fromEntries(availability.compositions.map((choice: { composition_id: string }) => [choice.composition_id, {
      input_schema: [{ key: 'term', label: 'Term', type: 'text', required: true }],
      field_defs: [{ id: 'field-1', name: 'Front', field_type: 'text' }, { id: 'field-2', name: 'Back', field_type: 'text' }],
      input_bindings: { term: 'field-1' }, warnings: [],
    }])) }
  },
  fetchStudyTemplatePreset: mocks.templatePreset,
  saveStudyTemplatePreset: mocks.saveTemplatePreset,
}))

vi.mock('../session/sessionStore', () => ({
  acknowledgeStudySessionQuarantine: mocks.acknowledgeQuarantine,
  loadStudySessionWithDurability: async (key: string) => ({
    session: await mocks.loadSession(key),
    durable: true,
    quarantine: mocks.loadQuarantine ?? undefined,
  }),
  saveStudySession: mocks.saveSession,
  updateCardFieldValuesInSessions: mocks.updateStoredCardContent,
  removeStudySession: mocks.removeSession,
  removeStudySessionIfMatches: mocks.removeSessionIfMatches,
  quarantineStudySession: mocks.quarantineSession,
  scopeKey: (userId: number, scope: string, scopeId: string) => (
    `user:${userId}:${scope}:${scopeId}`
  ),
}))

vi.mock('../session/studySessionLease', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../session/studySessionLease')>()
  return {
    ...actual,
    holdStudyScopeLease: mocks.holdLease,
  }
})

import { openSnapshot, useStudySession } from './useStudySession'
import { createPersistedSession } from '../session/studySessionEngine'

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
    composition_contract_version: 'applied-composition.compat.v1',
    selected_composition_id: 'comp:notetype:type-1:template:template-1',
    selected_composition: {
      composition_id: 'comp:notetype:type-1:template:template-1',
      mode_key: 'flashcard',
      note_type_id: 'type-1',
      note_type_name: 'Basic',
      template_id: 'template-1',
      template_name: 'Front -> Back',
      is_default: true,
      context_kind: 'owned',
      interaction_key: 'review.four-rating',
      trigger_key: 'scheduler.review',
      trigger_contract_version: '1',
      algorithm_key: 'legacy-anki',
      algorithm_version: '1.0.0',
    },
    composition_selection_resolution: 'explicit',
    composition_binding: {
      schema_version: 'study-composition-binding.v1',
      composition_id: 'comp:notetype:type-1:template:template-1',
      definition_id: 'legacy-template:template-1',
      definition_version: 'v1',
      application_id: 'application:owned:type-1',
      application_occurrence_id: 'application:owned:type-1',
      binding_kind: 'legacy-fielddef-direct',
      binding_fingerprint: 'sha256-test-binding-hash',
      field_bindings: [],
    },
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

function compositionAvailability() {
  const composition = snapshot().selected_composition!
  return {
    schema_version: 'study-scope-compositions.v2',
    scope_type: 'deck',
    scope_id: '12',
    cardinality: 'one',
    default_composition_id: composition.composition_id,
    groups: [{
      note_type_id: composition.note_type_id,
      note_type_name: composition.note_type_name,
      compositions: [composition],
    }],
    compositions: [composition],
  }
}

function twoCompositionAvailability() {
  const first = snapshot().selected_composition!
  const second = {
    ...first,
    composition_id: 'comp:notetype:type-1:template:template-2',
    template_id: 'template-2',
    template_name: 'Back -> Front',
    is_default: false,
  }
  return {
    first,
    second,
    availability: {
      ...compositionAvailability(),
      cardinality: 'many',
      default_composition_id: null,
      groups: [{ note_type_id: 'type-1', note_type_name: 'Basic', compositions: [first, second] }],
      compositions: [first, second],
    },
  }
}

function lastOpenBody() {
  return mocks.mutate.mock.calls.filter(([path]) => path === '/api/study/sessions').at(-1)?.[2]
}

function receipt(): StudySessionCommitReceipt {
  return {
    schema_version: 'study-commit-receipt.v1',
    success: true,
    session_id: 'session-1',
    commit_id: '00000000-0000-4000-8000-000000000001',
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

function noteSnapshot(): StudySessionSnapshot {
  const base = snapshot()
  return {
    ...base, schema_version: 'study-session.v4', authority_mode: 'NOTE', enrollment_epoch: '1',
    batch_transport: 'study-note-batch-transport.v1',
    cards: base.cards.map((card) => ({ ...card, authority_pin: {
      schema_version: 'study-note-authority-pin.v1', authority_mode: 'NOTE', enrollment_epoch: '1',
      logical_note_key: card.note_id, subject_generation: '1', base_authority_revision: '0',
      base_authority_state_hash: '11'.repeat(32),
    } })),
  }
}

function mockNoteBatchApi() {
  let id = 0
  vi.stubGlobal('crypto', {
    randomUUID: () => `00000000-0000-4000-8000-${String(++id).padStart(12, '0')}`,
  })
  const batches = new Map<string, StudyBatchPayload>()
  let completed = true
  mocks.mutate.mockImplementation(async (path: string, _method: string, payload: StudyBatchPayload) => {
    if (path === '/api/study/sessions') return noteSnapshot()
    if (!path.endsWith('/batch')) throw new Error(`Unexpected sync mutation: ${path}`)
    batches.set(payload.batch_id, payload)
    return { schema_version: 'study-batch-receipt.v1', status: 'enqueued', session_id: 'session-1',
      batch_id: payload.batch_id, batch_sequence: payload.batch_sequence, event_count: payload.events.length }
  })
  const originalGet = mocks.get.getMockImplementation()!
  mocks.get.mockImplementation(async (path: string) => {
    if (!path.includes('/batch/')) return originalGet(path)
    const batch = batches.get(path.split('/').at(-1)!)
    if (!batch) {
      const { ApiError } = await import('@/shared/api/client')
      throw new ApiError('Not found', 404, 'BATCH_NOT_FOUND')
    }
    return { schema_version: 'study-batch-status.v1', status: completed ? 'completed' : 'enqueued',
      session_id: 'session-1', batch_id: batch.batch_id, batch_sequence: batch.batch_sequence,
      event_count: batch.events.length, is_final: batch.is_final,
      receipt: { ...receipt(), schema_version: 'study-commit-receipt.v2', authority_mode: 'NOTE', enrollment_epoch: '1',
        batch_receipt_schema_version: 'study-note-batch-receipt.v1', batch_id: batch.batch_id,
        commit_id: batch.batch_id, commit_reason: batch.commit_reason, batch_sequence: batch.batch_sequence,
        is_final: batch.is_final, applied_event_count: batch.events.length,
        cumulative_event_count: batch.events.at(-1)?.sequence ?? latest.session?.event_sequence,
        rating_counts: { again: 0, hard: 0, good: batch.events.length, easy: 0 },
        request_hash: canonicalDigest(batch), receipt_hash: `sha256-${'22'.repeat(32)}`,
      } }
  })
  return { batches, setCompleted: (value: boolean) => { completed = value } }
}

async function waitForLeaseAbort(record: LeaseRecord) {
  for (let attempt = 0; attempt < 20 && !record.signal.aborted; attempt += 1) {
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 25))
    })
  }
  expect(record.signal.aborted).toBe(true)
}

async function openReadySession() {
  await openReadySessionWithId('session-1')
}

async function openReadySessionWithId(sessionId: string) {
  mocks.bootstrap = { data: { user: { id: 7 } } }
  await renderHarness()
  await waitFor(() => expect(latest.session?.snapshot.session_id).toBe(sessionId))
}

beforeEach(() => {
  mocks.bootstrap = { data: undefined }
  mocks.templatePreset.mockReset().mockResolvedValue({ schema_version: 'study-template-preset.v2', deck_id: 12,
    selected_compositions: [snapshot().selected_composition_id!], input_bindings: {}, ask_before_study: false, stale_compositions: [] })
  mocks.saveTemplatePreset.mockReset().mockResolvedValue({})
  mocks.get.mockReset().mockImplementation((path: string) => {
    if (path.endsWith('/compositions')) return Promise.resolve(compositionAvailability())
    return Promise.resolve({
      schema_version: 'study-session-status.v1',
      session_id: 'session-1',
      status: 'open',
      expires_at: '2099-02-23T09:00:00.000Z',
      committed_at: null,
    })
  })
  mocks.mutate.mockReset().mockImplementation((path: string) => {
    if (path === '/api/study/sessions') return Promise.resolve(snapshot())
    throw new Error(`Unexpected mutation: ${path}`)
  })
  mocks.mutateKeepalive.mockReset().mockImplementation((_path, _method, payload) => Promise.resolve({
    ...receipt(), commit_id: payload.commit_id, commit_reason: payload.commit_reason,
    applied_event_count: payload.events.length,
  }))
  mocks.invalidateQueries.mockReset().mockResolvedValue(undefined)
  mocks.loadSession.mockReset().mockResolvedValue(null)
  mocks.loadQuarantine = null
  mocks.acknowledgeQuarantine.mockReset().mockResolvedValue(undefined)
  mocks.saveSession.mockReset().mockResolvedValue(true)
  mocks.removeSession.mockReset().mockResolvedValue(undefined)
  mocks.removeSessionIfMatches.mockReset().mockResolvedValue(undefined)
  mocks.quarantineSession.mockReset().mockResolvedValue(undefined)
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
  it('starts a single-template deck at once with template defaults even when the preset asks first', async () => {
    mocks.templatePreset.mockResolvedValue({ selected_compositions: [], input_bindings: {}, ask_before_study: true, stale_compositions: [] })
    await openReadySession()
    expect(latest.awaitingCompositionSelection).toBe(false)
    expect(lastOpenBody()).not.toHaveProperty('input_bindings')
    expect(mocks.saveTemplatePreset).not.toHaveBeenCalled()
  })

  it('opens a single-template deck with the saved field map', async () => {
    const choice = snapshot().selected_composition_id!
    mocks.templatePreset.mockResolvedValue({ selected_compositions: [choice], input_bindings: { [choice]: { term: 'field-2' } }, ask_before_study: true, stale_compositions: [] })
    await openReadySession()
    expect(lastOpenBody()).toEqual(expect.objectContaining({ composition_id: choice, input_bindings: { term: 'field-2' } }))
  })

  it('replaces a saved target that no longer fits with the template default instead of blocking study', async () => {
    const choice = snapshot().selected_composition_id!
    mocks.templatePreset.mockResolvedValue({ selected_compositions: [choice], input_bindings: { [choice]: { term: 'deleted-field' } }, ask_before_study: true, stale_compositions: [] })
    await openReadySession()
    expect(lastOpenBody()?.input_bindings).toEqual({ term: 'field-1' })
  })

  it('still studies with template defaults when the preset request fails', async () => {
    mocks.templatePreset.mockRejectedValue(new Error('preset unavailable'))
    await openReadySession()
    expect(lastOpenBody()).not.toHaveProperty('input_bindings')
    expect(latest.error).toBeNull()
  })

  it('asks for one of several templates and starts the clicked one with its saved map', async () => {
    const { second, availability } = twoCompositionAvailability()
    mocks.get.mockImplementation((path: string) => path.endsWith('/compositions') ? Promise.resolve(availability) : Promise.resolve({ status: 'open' }))
    // A remembered "do not ask" choice no longer hides the picker; one click starts.
    mocks.templatePreset.mockResolvedValue({ selected_compositions: [second.composition_id], input_bindings: { [second.composition_id]: { term: 'field-2' } }, ask_before_study: false, stale_compositions: [] })
    mocks.bootstrap = { data: { user: { id: 7 } } }
    await renderHarness(); await waitFor(() => expect(latest.awaitingCompositionSelection).toBe(true))
    expect(mocks.mutate).not.toHaveBeenCalled()
    await act(async () => latest.startComposition(second.composition_id))
    expect(lastOpenBody()).toEqual(expect.objectContaining({ composition_id: second.composition_id, input_bindings: { term: 'field-2' } }))
    expect(latest.session?.snapshot.session_id).toBe('session-1'); expect(mocks.saveTemplatePreset).not.toHaveBeenCalled()
  })

  it('saves and resets one template map without dropping the other templates', async () => {
    const { first, second, availability } = twoCompositionAvailability()
    mocks.get.mockImplementation((path: string) => path.endsWith('/compositions') ? Promise.resolve(availability) : Promise.resolve({ status: 'open' }))
    mocks.templatePreset.mockResolvedValue({ selected_compositions: [second.composition_id], input_bindings: { [second.composition_id]: { term: 'field-2' } }, ask_before_study: true, stale_compositions: [] })
    mocks.bootstrap = { data: { user: { id: 7 } } }
    await renderHarness(); await waitFor(() => expect(latest.awaitingCompositionSelection).toBe(true))
    expect(latest.templatePreparation.mappingOf(first.composition_id)).toEqual({ inputBindings: { term: 'field-1' }, staleInputs: [], customized: false })
    await act(async () => { await latest.templatePreparation.saveBindings(first.composition_id, { term: null }) })
    expect(mocks.saveTemplatePreset).toHaveBeenLastCalledWith('12', {
      selected_compositions: [second.composition_id, first.composition_id],
      input_bindings: { [second.composition_id]: { term: 'field-2' }, [first.composition_id]: { term: null } },
      ask_before_study: true,
    })
    expect(latest.templatePreparation.mappingOf(first.composition_id)?.customized).toBe(true)
    await act(async () => { await latest.templatePreparation.saveBindings(first.composition_id, null) })
    expect(mocks.saveTemplatePreset).toHaveBeenLastCalledWith('12', {
      selected_compositions: [second.composition_id],
      input_bindings: { [second.composition_id]: { term: 'field-2' } },
      ask_before_study: true,
    })
    await act(async () => latest.startComposition(first.composition_id))
    expect(lastOpenBody()).not.toHaveProperty('input_bindings')
  })

  it('applies a new field map to the running session by saving it and reopening the lease', async () => {
    const choice = snapshot().selected_composition_id!
    await openReadySession()
    let applied = false
    await act(async () => { applied = await latest.applyTemplateBindings({ term: 'field-2' }) })
    expect(applied).toBe(true)
    expect(mocks.saveTemplatePreset).toHaveBeenCalledWith('12', { selected_compositions: [choice], input_bindings: { [choice]: { term: 'field-2' } }, ask_before_study: false })
    await waitFor(() => expect(mocks.mutate.mock.calls.filter(([path]) => path === '/api/study/sessions')).toHaveLength(2))
    expect(lastOpenBody()?.input_bindings).toEqual({ term: 'field-2' })
  })

  it('keeps the running session when saving a field map fails', async () => {
    await openReadySession()
    mocks.saveTemplatePreset.mockRejectedValueOnce(new Error('Save failed'))
    let applied = true
    await act(async () => { applied = await latest.applyTemplateBindings({ term: 'field-2' }) })
    expect(applied).toBe(false)
    expect(String(latest.templatePreparation.error)).toContain('Save failed')
    expect(mocks.mutate.mock.calls.filter(([path]) => path === '/api/study/sessions')).toHaveLength(1)
    expect(latest.session?.snapshot.session_id).toBe('session-1')
  })

  it('bypasses preparation for an existing active frozen lease', async () => {
    mocks.loadSession.mockResolvedValue(createPersistedSession(snapshot()))
    mocks.templatePreset.mockRejectedValue(new Error('must not fetch'))
    await openReadySession()
    expect(mocks.templatePreset).not.toHaveBeenCalled(); expect(mocks.saveTemplatePreset).not.toHaveBeenCalled()
    expect(mocks.get.mock.calls.some(([path]) => String(path).includes('/compositions'))).toBe(false)
  })

  it('keeps a restored pending commit in its existing recovery flow without fetching preferences', async () => {
    mocks.loadSession.mockResolvedValue({ ...createPersistedSession(snapshot()), status: 'pending_commit', commit_id: '00000000-0000-4000-8000-000000000001', commit_reason: 'manual_exit' })
    mocks.mutate.mockRejectedValue(new Error('Offline commit'))
    await openReadySession()
    expect(latest.session?.status).toBe('pending_commit'); expect(mocks.templatePreset).not.toHaveBeenCalled(); expect(mocks.saveTemplatePreset).not.toHaveBeenCalled()
    expect(mocks.get.mock.calls.some(([path]) => String(path).includes('/compositions'))).toBe(false)
  })

  it('deduplicates equivalent binding maps and keeps distinct maps and absence separate', async () => {
    const pending = deferred<StudySessionSnapshot>(); mocks.mutate.mockReturnValue(pending.promise)
    const map = { term: 'field-1', answer: null }
    const first = openSnapshot(7, '12', 'dedupe-choice', map)
    map.term = 'field-2'
    const same = openSnapshot(7, '12', 'dedupe-choice', { answer: null, term: 'field-1' })
    const different = openSnapshot(7, '12', 'dedupe-choice', { term: 'field-2', answer: null })
    const empty = openSnapshot(7, '12', 'dedupe-choice', {})
    const defaults = openSnapshot(7, '12', 'dedupe-choice')
    expect(first).toBe(same); expect(first).not.toBe(different); expect(empty).not.toBe(defaults)
    expect(mocks.mutate).toHaveBeenCalledTimes(4)
    expect(mocks.mutate.mock.calls[0][2].input_bindings).toEqual({ term: 'field-1', answer: null })
    pending.resolve(snapshot()); await Promise.all([first, same, different, empty, defaults])
  })

  it('carries transient bindings on reload and synchronous rollover without writing preferences', async () => {
    await openReadySession()
    const choice = snapshot().selected_composition_id!
    await act(async () => latest.selectComposition(choice, { term: 'field-2' }))
    await act(async () => latest.reloadSession())
    expect(mocks.mutate.mock.calls.filter(([path]) => path === '/api/study/sessions').at(-1)?.[2].input_bindings).toEqual({ term: 'field-2' })
    await act(async () => latest.answer('card-1', 'again', latest.prepareDecision('card-1'), 250))
    mocks.mutate.mockImplementation((path: string) => path.endsWith('/commit')
      ? Promise.resolve({ ...receipt(), commit_reason: 'rollover', applied_event_count: 1 }) : Promise.resolve({ ...snapshot(), session_id: 'session-2' }))
    await act(async () => latest.commit({ reason: 'rollover', resumeAfterCommit: true }))
    expect(mocks.mutate.mock.calls.filter(([path]) => path === '/api/study/sessions').at(-1)?.[2].input_bindings).toEqual({ term: 'field-2' })
    expect(latest.session?.snapshot.session_id).toBe('session-2'); expect(mocks.saveTemplatePreset).not.toHaveBeenCalled()
  })

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

  it('opens a replacement only after explicit quarantine recovery', async () => {
    mocks.loadQuarantine = {
      reason: 'EVENT_CONTRACT_MISMATCH',
      message: 'Stored event mismatch.',
    }
    mocks.bootstrap = { data: { user: { id: 7 } } }

    await renderHarness()
    await waitFor(() => expect(latest.error).toBeInstanceOf(Error))

    await act(async () => {
      await latest.reloadSession(true)
    })

    expect(mocks.acknowledgeQuarantine).toHaveBeenCalledWith('user:7:deck:12')
    expect(mocks.mutate).toHaveBeenCalledWith(
      '/api/study/sessions',
      'POST',
      expect.any(Object),
    )
    expect(latest.session?.snapshot.session_id).toBe('session-1')
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
      {
        scope: 'deck',
        scope_id: '12',
        composition_id: 'comp:notetype:type-1:template:template-1',
        accepted_session_schema_versions: [
          'study-session.v4',
          'study-session.v3',
          'study-session.v2',
        ],
        accepted_batch_schema_versions: ['study-batch.v3'],
        accepted_note_storage_profiles: ['note-mysql-float-text.v1'],
      },
    )
  })

  it('does not open a session until one composition is selected from an ambiguous scope', async () => {
    mocks.templatePreset.mockResolvedValue({ selected_compositions: [], input_bindings: {}, ask_before_study: true, stale_compositions: [] })
    const first = snapshot().selected_composition!
    const second = {
      ...first,
      composition_id: 'comp:notetype:type-1:template:template-2',
      template_id: 'template-2',
      template_name: 'Back -> Front',
      is_default: false,
    }
    mocks.get.mockImplementation((path: string) => {
      if (path.endsWith('/compositions')) {
        return Promise.resolve({
          ...compositionAvailability(),
          cardinality: 'many',
          default_composition_id: null,
          groups: [{
            note_type_id: 'type-1',
            note_type_name: 'Basic',
            compositions: [first, second],
          }],
          compositions: [first, second],
        })
      }
      return Promise.resolve({ status: 'open' })
    })
    mocks.bootstrap = { data: { user: { id: 7 } } }

    await renderHarness()
    await waitFor(() => expect(latest.awaitingCompositionSelection).toBe(true))
    expect(latest.session).toBeNull()
    expect(mocks.mutate).not.toHaveBeenCalled()

    await act(async () => {
      await latest.selectComposition(first.composition_id)
    })

    expect(mocks.mutate).toHaveBeenCalledWith(
      '/api/study/sessions',
      'POST',
      expect.objectContaining({ composition_id: first.composition_id }),
    )
    expect(latest.session?.snapshot.session_id).toBe('session-1')
    expect(latest.awaitingCompositionSelection).toBe(false)
  })

  it('keeps an empty scope sessionless', async () => {
    mocks.get.mockImplementation((path: string) => {
      if (path.endsWith('/compositions')) {
        return Promise.resolve({
          ...compositionAvailability(),
          cardinality: 'zero',
          default_composition_id: null,
          groups: [],
          compositions: [],
        })
      }
      return Promise.resolve({ status: 'open' })
    })
    mocks.bootstrap = { data: { user: { id: 7 } } }

    await renderHarness()
    await waitFor(() => expect(latest.error).not.toBeNull())

    expect(latest.session).toBeNull()
    expect(latest.awaitingCompositionSelection).toBe(false)
    expect(mocks.mutate).not.toHaveBeenCalled()
  })

  it('recovers a failed selection without allowing duplicate open requests', async () => {
    mocks.templatePreset.mockResolvedValue({ selected_compositions: [], input_bindings: {}, ask_before_study: true, stale_compositions: [] })
    const first = snapshot().selected_composition!
    const second = {
      ...first,
      composition_id: 'comp:notetype:type-1:template:template-2',
      template_id: 'template-2',
      template_name: 'Back -> Front',
      is_default: false,
    }
    mocks.get.mockImplementation((path: string) => {
      if (path.endsWith('/compositions')) {
        return Promise.resolve({
          ...compositionAvailability(),
          cardinality: 'many',
          default_composition_id: null,
          groups: [{
            note_type_id: 'type-1',
            note_type_name: 'Basic',
            compositions: [first, second],
          }],
          compositions: [first, second],
        })
      }
      return Promise.resolve({ status: 'open' })
    })
    mocks.bootstrap = { data: { user: { id: 7 } } }
    await renderHarness()
    await waitFor(() => expect(latest.awaitingCompositionSelection).toBe(true))

    mocks.mutate.mockRejectedValueOnce(new Error('open failed'))
    await act(async () => {
      await latest.selectComposition(first.composition_id)
    })
    expect(latest.awaitingCompositionSelection).toBe(true)
    expect(latest.error).toBeInstanceOf(Error)

    const pendingOpen = deferred<StudySessionSnapshot>()
    mocks.mutate.mockReturnValueOnce(pendingOpen.promise)
    let firstRetry!: Promise<void>
    let duplicateRetry!: Promise<void>
    await act(async () => {
      firstRetry = latest.selectComposition(first.composition_id)
      duplicateRetry = latest.selectComposition(first.composition_id)
      await Promise.resolve()
    })
    expect(mocks.mutate).toHaveBeenCalledTimes(2)
    pendingOpen.resolve(snapshot())
    await act(async () => {
      await Promise.all([firstRetry, duplicateRetry])
    })
    expect(latest.session?.snapshot.session_id).toBe('session-1')
    expect(mocks.mutate).toHaveBeenCalledTimes(2)
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
    await waitForLeaseAbort(record)
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
    })
    await waitForLeaseAbort(record)
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
    })
    await waitForLeaseAbort(record)
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

  it('does not re-anchor the session clock after a local answer', async () => {
    await openReadySession()
    const before = latest.view?.now_ms
    expect(before).toBeTypeOf('number')
    const decision = latest.prepareDecision('card-1')
    const futureWallTime = Date.now() + 10_000
    const wallClock = vi.spyOn(Date, 'now').mockReturnValue(futureWallTime)
    try {
      await act(async () => {
        await latest.answer('card-1', 'good', decision, 250)
      })
      expect(latest.view?.now_ms).toBeLessThan(before! + 5_000)
    } finally {
      wallClock.mockRestore()
    }
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
    await waitForLeaseAbort(record)
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

  it('updates card content live while deferring template authoring changes', async () => {
    await openReadySession()
    mocks.saveSession.mockClear()
    mocks.updateStoredCardContent.mockClear()

    await act(async () => {
      await latest.updateCardContent('card-1', { Word: 'dog' }, { noteId: 'note-1' })
      await latest.updateTemplateContent('template-1', {
        front_source: '<strong>updated</strong>',
        shared_css: '.updated { color: red; }',
      })
      window.dispatchEvent(new CustomEvent('flama_study_template_updated', {
        detail: {
          templateId: 'template-1',
          updated: { front_source: '<strong>cross-tab</strong>' },
        },
      }))
      await Promise.resolve()
    })

    // Template remains frozen for active lease per P3/P4 contract
    expect(latest.session?.snapshot.templates.template).toMatchObject({
      version: 'v1',
      front_source: '{{Word}}',
      shared_css: '',
    })

    // Card content is updated live so learner sees edits immediately
    const updatedContentKey = latest.session?.snapshot.cards[0]?.content_key
    expect(updatedContentKey).toBeDefined()
    expect(latest.session?.snapshot.contents[updatedContentKey!]).toMatchObject({
      field_values: { Word: 'dog' },
      render_context: { Word: 'dog' },
    })
    expect(mocks.saveSession).toHaveBeenCalled()
    expect(mocks.updateStoredCardContent).toHaveBeenCalledExactlyOnceWith('card-1', { Word: 'dog' }, {
      noteId: 'note-1', media: undefined,
    })
  })

  it('admits only one same-tick answer while the owner is becoming durable', async () => {
    await openReadySession()
    const pendingSave = deferred<boolean>()
    mocks.saveSession.mockClear().mockImplementationOnce(() => pendingSave.promise)
    const decision = latest.prepareDecision('card-1')

    let first!: Promise<void>
    let duplicate!: Promise<void>
    await act(async () => {
      first = latest.answer('card-1', 'good', decision, 250)
      duplicate = latest.answer('card-1', 'good', decision, 250)
      await Promise.resolve()
    })

    expect(latest.session?.events).toHaveLength(1)
    expect(mocks.saveSession).toHaveBeenCalledTimes(1)
    pendingSave.resolve(true)
    await act(async () => {
      await Promise.all([first, duplicate])
    })
    expect(latest.session?.events).toHaveLength(1)
  })

  it('does not run undo inside a same-tick answer transition', async () => {
    await openReadySession()
    const pendingSave = deferred<boolean>()
    mocks.saveSession.mockImplementationOnce(() => pendingSave.promise)
    const decision = latest.prepareDecision('card-1')

    let answerPromise!: Promise<void>
    let undoPromise!: Promise<string | null>
    await act(async () => {
      answerPromise = latest.answer('card-1', 'good', decision, 250)
      undoPromise = latest.undo()
      await Promise.resolve()
    })

    expect(await undoPromise).toBeNull()
    expect(latest.session?.events).toHaveLength(1)
    pendingSave.resolve(true)
    await act(async () => {
      await answerPromise
    })
  })

  it('does not answer while a synchronous commit owns the session', async () => {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => {
      await latest.answer('card-1', 'good', decision, 250)
    })
    mocks.saveSession.mockClear()
    const pendingCommit = deferred<StudySessionCommitReceipt>()
    mocks.mutate.mockImplementation((path: string) => {
      if (path === '/api/study/sessions/session-1/commit') return pendingCommit.promise
      if (path === '/api/study/sessions') return Promise.resolve(snapshot())
      throw new Error(`Unexpected mutation: ${path}`)
    })

    let commitPromise!: Promise<StudySessionCommitReceipt | null>
    let answerPromise!: Promise<void>
    await act(async () => {
      commitPromise = latest.commit({ reason: 'manual_exit' })
      answerPromise = latest.answer('card-1', 'easy', decision, 250)
      await Promise.resolve()
    })

    expect(latest.session?.events).toHaveLength(1)
    expect(mocks.saveSession).toHaveBeenCalledTimes(1)
    pendingCommit.resolve(receipt())
    await act(async () => {
      await Promise.all([commitPromise, answerPromise])
    })
  })

  it('does not run undo while a retrying commit owns the session', async () => {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => {
      await latest.answer('card-1', 'good', decision, 250)
    })
    const pendingCommit = deferred<StudySessionCommitReceipt>()
    mocks.mutate.mockImplementation((path: string) => {
      if (path === '/api/study/sessions/session-1/commit') return pendingCommit.promise
      if (path === '/api/study/sessions') return Promise.resolve(snapshot())
      throw new Error(`Unexpected mutation: ${path}`)
    })

    let commitPromise!: Promise<StudySessionCommitReceipt | null>
    let undoPromise!: Promise<string | null>
    await act(async () => {
      commitPromise = latest.commit({ reason: 'manual_exit' })
      undoPromise = latest.undo()
      await Promise.resolve()
    })

    expect(await undoPromise).toBeNull()
    expect(latest.session?.events).toHaveLength(1)
    pendingCommit.resolve(receipt())
    await act(async () => {
      await commitPromise
    })
  })

  it('retries a durable pending commit when the browser comes back online', async () => {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => {
      await latest.answer('card-1', 'good', decision, 250)
    })
    let networkAvailable = false
    mocks.mutate.mockImplementation((path: string) => {
      if (path === '/api/study/sessions/session-1/commit') {
        return networkAvailable
          ? Promise.resolve(receipt())
          : Promise.reject(new TypeError('Network unavailable'))
      }
      if (path === '/api/study/sessions') return Promise.resolve(snapshot())
      throw new Error(`Unexpected mutation: ${path}`)
    })

    await act(async () => {
      await expect(latest.commit({ reason: 'manual_exit' })).rejects.toThrow('Network unavailable')
    })
    await waitFor(() => expect(latest.session?.status).toBe('pending_commit'))
    expect(latest.session?.events).toHaveLength(1)

    networkAvailable = true
    await act(async () => {
      window.dispatchEvent(new Event('online'))
    })
    await waitFor(() => expect(latest.receipt?.commit_id).toBe('00000000-0000-4000-8000-000000000001'))
    expect(latest.session?.events).toHaveLength(1)
    expect(mocks.removeSessionIfMatches).toHaveBeenCalledWith('user:7:deck:12', 'session-1')
  })

  async function pendingAfterLostReceipt() {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => { await latest.answer('card-1', 'good', decision, 250) })
    mocks.mutate.mockImplementation((path: string) => {
      if (path === '/api/study/sessions/session-1/commit') {
        return Promise.reject(new TypeError('Network unavailable'))
      }
      if (path === '/api/study/sessions') return Promise.resolve(snapshot())
      throw new Error(`Unexpected mutation: ${path}`)
    })
    await act(async () => {
      await expect(latest.commit({ reason: 'auto_finish' })).rejects.toThrow('Network unavailable')
    })
    await waitFor(() => expect(latest.session?.status).toBe('pending_commit'))
  }

  function alreadyCommitted(details: StudySessionCommitReceipt) {
    return async (path: string) => {
      if (path !== '/api/study/sessions/session-1/commit') throw new Error(`Unexpected mutation: ${path}`)
      const { ApiError } = await import('@/shared/api/client')
      throw new ApiError('Study session was already committed.', 409, 'SESSION_ALREADY_COMMITTED', undefined, details)
    }
  }

  it('resends a pending commit with its original reason and settles on the stored receipt', async () => {
    await pendingAfterLostReceipt()
    const stored = { ...receipt(), commit_reason: 'auto_finish' as const }
    mocks.mutate.mockImplementation(alreadyCommitted(stored))

    await act(async () => {
      await expect(latest.commit({ reason: 'manual_exit' })).resolves.toEqual(stored)
    })
    const [, , payload] = mocks.mutate.mock.calls.at(-1)!
    expect(payload.commit_reason).toBe('auto_finish')
    expect(latest.receipt).toEqual(stored)
    expect(mocks.removeSessionIfMatches).toHaveBeenCalledWith('user:7:deck:12', 'session-1')
    expect(mocks.quarantineSession).not.toHaveBeenCalled()
  })

  it('quarantines local answers a committed lease does not cover instead of deleting them', async () => {
    await pendingAfterLostReceipt()
    mocks.mutate.mockImplementation(alreadyCommitted({ ...receipt(), applied_event_count: 0 }))

    await act(async () => {
      await expect(latest.commit({ reason: 'manual_exit' })).rejects.toMatchObject({
        code: 'SESSION_ALREADY_COMMITTED',
      })
    })
    expect(mocks.quarantineSession).toHaveBeenCalledWith(
      'user:7:deck:12',
      expect.objectContaining({ events: expect.arrayContaining([expect.anything()]) }),
      expect.objectContaining({ reason: 'COMMITTED_ELSEWHERE' }),
    )
    expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
    expect(latest.error).toMatchObject({ code: 'SESSION_ALREADY_COMMITTED' })
  })

  async function restorePendingAfterLostReceipt(status: 'committed' | 'expired' | 'missing') {
    await pendingAfterLostReceipt()
    const pending = latest.session!
    await act(async () => root?.unmount())
    root = null
    container?.remove()
    container = null
    for (const mock of [
      mocks.mutate, mocks.mutateKeepalive, mocks.saveSession,
      mocks.removeSessionIfMatches, mocks.quarantineSession,
    ]) mock.mockClear()
    mocks.loadSession.mockResolvedValue(pending)
    const { ApiError } = await import('@/shared/api/client')
    mocks.get.mockImplementation((path: string) => {
      if (path.endsWith('/compositions')) return Promise.resolve(compositionAvailability())
      if (status === 'missing') {
        return Promise.reject(new ApiError('Study session was not found.', 404, 'SESSION_NOT_FOUND'))
      }
      return Promise.resolve({
        schema_version: 'study-session-status.v1',
        session_id: 'session-1',
        status,
        expires_at: '2099-02-23T09:00:00.000Z',
        committed_at: status === 'committed' ? '2099-02-22T09:01:00.000Z' : null,
      })
    })
    return pending
  }

  function commitAlreadySettled(details: StudySessionCommitReceipt) {
    const rejectCommit = alreadyCommitted(details)
    return (path: string) => (
      path === '/api/study/sessions'
        ? Promise.resolve({ ...snapshot(), session_id: 'session-2' })
        : rejectCommit(path)
    )
  }

  it('settles a restored lease the server already committed and opens a new session', async () => {
    const pending = await restorePendingAfterLostReceipt('committed')
    mocks.mutate.mockImplementation(commitAlreadySettled({
      ...receipt(), commit_id: pending.commit_id!, commit_reason: 'auto_finish',
    }))

    await openReadySessionWithId('session-2')
    expect(mocks.mutate).toHaveBeenCalledWith(
      '/api/study/sessions/session-1/commit',
      'POST',
      expect.objectContaining({ commit_id: pending.commit_id, commit_reason: 'auto_finish' }),
    )
    expect(latest.receipt).toBeNull()
    expect(latest.error).toBeNull()
    expect(mocks.removeSessionIfMatches).toHaveBeenCalledWith('user:7:deck:12', 'session-1')
    expect(mocks.quarantineSession).not.toHaveBeenCalled()
  })

  it('quarantines a restored committed lease whose stored receipt does not cover local answers', async () => {
    await restorePendingAfterLostReceipt('committed')
    mocks.mutate.mockImplementation(commitAlreadySettled({ ...receipt(), applied_event_count: 0 }))

    mocks.bootstrap = { data: { user: { id: 7 } } }
    await renderHarness()
    await waitFor(() => expect(latest.error).toMatchObject({ code: 'SESSION_ALREADY_COMMITTED' }))
    expect(latest.session).toBeNull()
    expect(mocks.quarantineSession).toHaveBeenCalledWith(
      'user:7:deck:12',
      expect.objectContaining({ events: [expect.anything()] }),
      expect.objectContaining({ reason: 'COMMITTED_ELSEWHERE' }),
    )
    expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
  })

  it.each(['expired', 'missing'] as const)(
    'quarantines unsaved answers of a restored %s lease instead of retrying them forever',
    async (status) => {
      await restorePendingAfterLostReceipt(status)

      mocks.bootstrap = { data: { user: { id: 7 } } }
      await renderHarness()
      await waitFor(() => expect(latest.error).toMatchObject({ code: 'SESSION_LEASE_CLOSED', status: 409 }))
      expect(latest.session).toBeNull()
      expect(mocks.mutate).not.toHaveBeenCalled()
      expect(mocks.quarantineSession).toHaveBeenCalledWith(
        'user:7:deck:12',
        expect.objectContaining({ events: [expect.anything()] }),
        expect.objectContaining({ reason: 'LEASE_CLOSED' }),
      )
      expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
    },
  )

  it('keeps a restored committed lease for retry when settling it fails transiently', async () => {
    await restorePendingAfterLostReceipt('committed')
    mocks.mutate.mockImplementation((path: string) => (
      path === '/api/study/sessions/session-1/commit'
        ? Promise.reject(new TypeError('Network unavailable'))
        : Promise.reject(new Error(`Unexpected mutation: ${path}`))
    ))

    mocks.bootstrap = { data: { user: { id: 7 } } }
    await renderHarness()
    await waitFor(() => expect(latest.error).toBeInstanceOf(TypeError))
    expect(mocks.quarantineSession).not.toHaveBeenCalled()
    expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
  })

  it('never revives or resends a lease after its final receipt when the page closes', async () => {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => { await latest.answer('card-1', 'good', decision, 250) })
    mocks.mutate.mockImplementation((path: string) => (
      path === '/api/study/sessions/session-1/commit'
        ? Promise.resolve(receipt())
        : Promise.reject(new Error(`Unexpected mutation: ${path}`))
    ))
    await act(async () => { await latest.commit({ reason: 'manual_exit' }) })
    expect(latest.receipt?.commit_id).toBe(receipt().commit_id)
    const savesAfterReceipt = mocks.saveSession.mock.calls.length

    await act(async () => { window.dispatchEvent(new Event('pagehide')) })
    await act(async () => root?.unmount())
    root = null
    expect(mocks.mutateKeepalive).not.toHaveBeenCalled()
    expect(mocks.saveSession).toHaveBeenCalledTimes(savesAfterReceipt)
  })

  it('settles a page-exit commit the server already stored instead of keeping it', async () => {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => { await latest.answer('card-1', 'good', decision, 250) })
    const { ApiError } = await import('@/shared/api/client')
    mocks.mutateKeepalive.mockImplementation((_path, _method, payload) => Promise.reject(new ApiError(
      'Study session was already committed.', 409, 'SESSION_ALREADY_COMMITTED', undefined,
      { ...receipt(), commit_id: payload.commit_id, commit_reason: 'page_exit' },
    )))

    await act(async () => { window.dispatchEvent(new Event('pagehide')) })
    await waitFor(() => expect(mocks.removeSessionIfMatches).toHaveBeenCalledWith('user:7:deck:12', 'session-1'))
    expect(mocks.quarantineSession).not.toHaveBeenCalled()
  })

  it('removes an unstarted session with 0 events on page exit so next visit starts fresh with preparation', async () => {
    await openReadySession()
    expect(latest.session?.events).toHaveLength(0)

    await act(async () => { window.dispatchEvent(new Event('pagehide')) })
    await waitFor(() => expect(mocks.removeSessionIfMatches).toHaveBeenCalledWith('user:7:deck:12', 'session-1'))
    expect(mocks.mutateKeepalive).not.toHaveBeenCalled()
  })

  it('discards an active session and removes it from storage', async () => {
    await openReadySession()
    expect(latest.session).not.toBeNull()

    await act(async () => { await latest.discardSession() })
    expect(mocks.removeSessionIfMatches).toHaveBeenCalledWith('user:7:deck:12', 'session-1')
    expect(latest.session).toBeNull()
  })

  it('pagehide waits for the answer owner and flushes the latest durable state', async () => {
    await openReadySession()
    const pendingSave = deferred<boolean>()
    mocks.saveSession.mockImplementationOnce(() => pendingSave.promise)
    const decision = latest.prepareDecision('card-1')

    let answerPromise!: Promise<void>
    await act(async () => {
      answerPromise = latest.answer('card-1', 'good', decision, 250)
      window.dispatchEvent(new Event('pagehide'))
      await Promise.resolve()
    })

    expect(mocks.mutateKeepalive).not.toHaveBeenCalled()
    pendingSave.resolve(true)
    await act(async () => {
      await answerPromise
    })
    await waitFor(() => expect(mocks.mutateKeepalive).toHaveBeenCalledWith(
      '/api/study/sessions/session-1/commit',
      'POST',
      expect.objectContaining({
        events: [expect.objectContaining({
          card_id: 'card-1',
          rating: 'good',
        })],
      }),
    ))
  })

  it('keeps bootstrap as the mutation owner before a restored session is live', async () => {
    const pendingLoad = deferred<null>()
    mocks.loadSession.mockReturnValueOnce(pendingLoad.promise)
    mocks.bootstrap = { data: { user: { id: 7 } } }
    await renderHarness()
    await waitFor(() => expect(mocks.loadSession).toHaveBeenCalledOnce())

    await expect(latest.answer(
      'card-1',
      'good',
      {} as ReturnType<typeof latest.prepareDecision>,
      250,
    )).resolves.toBeUndefined()
    expect(mocks.saveSession).not.toHaveBeenCalled()

    pendingLoad.resolve(null)
    await waitFor(() => expect(latest.session).not.toBeNull())
  })

  it.each([
    { schema_version: 'study-batch-receipt.v1', status: 'enqueued' },
    { ...receipt(), session_id: 'another-session' },
    { ...receipt(), commit_id: 'another-commit' },
    { ...receipt(), applied_event_count: 0 },
  ])('retains pending work for an unverified commit response %#', async (response) => {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => { await latest.answer('card-1', 'good', decision, 250) })
    mocks.mutate.mockResolvedValue(response)
    await act(async () => {
      await expect(latest.commit()).rejects.toMatchObject({ code: 'INVALID_COMMIT_RECEIPT' })
    })
    expect(latest.session?.events).toHaveLength(1)
    expect(latest.session?.status).toBe('pending_commit')
    expect(latest.receipt).toBeNull()
    expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
  })

  it('pagehide does not delete pending work on a queue acknowledgment', async () => {
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => { await latest.answer('card-1', 'good', decision, 250) })
    mocks.mutateKeepalive.mockResolvedValue({ schema_version: 'study-batch-receipt.v1', status: 'enqueued' })
    await act(async () => { window.dispatchEvent(new Event('pagehide')) })
    await waitFor(() => expect(mocks.mutateKeepalive).toHaveBeenCalledOnce())
    expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
    expect(mocks.saveSession.mock.calls.at(-1)?.[0].events).toHaveLength(1)
  })

  it.each(['committed', 'expired', 'open'])('retains in-flight batches when restoring a %s session', async (status) => {
    const persisted = createPersistedSession(snapshot())
    persisted.snapshot.expires_at = status === 'expired' ? '2020-01-01T00:00:00Z' : snapshot().expires_at
    persisted.batch_sequence = 1
    persisted.in_flight_batches = [{
      schema_version: 'study-batch.v1', batch_id: 'batch-1', batch_sequence: 1,
      session_token: 'token', snapshot_hash: 'snapshot-hash', events: [],
      is_final: true, commit_reason: 'manual_exit',
    }]
    mocks.loadSession.mockResolvedValue(persisted)
    mocks.get.mockResolvedValue({ status, stale: true })
    await openReadySession()
    expect(latest.session?.in_flight_batches).toEqual(persisted.in_flight_batches)
    expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
    expect(mocks.mutate).not.toHaveBeenCalled()
  })

  it('uses the negotiated NOTE batch transport and clears only a completed final receipt', async () => {
    const api = mockNoteBatchApi()
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => { await latest.answer('card-1', 'good', decision, 250) })
    await act(async () => { await latest.commit({ reason: 'manual_exit' }) })
    expect(latest.receipt).toMatchObject({ authority_mode: 'NOTE', applied_event_count: 1 })
    expect(latest.totalSessionStats.total_reviews).toBe(1)
    expect(mocks.removeSessionIfMatches).toHaveBeenCalledWith('user:7:deck:12', 'session-1')
    expect(api.batches.size).toBe(1)
    expect(mocks.mutate.mock.calls.some(([path]) => path.endsWith('/commit'))).toBe(false)
    mocks.mutateKeepalive.mockClear()
    await act(async () => { window.dispatchEvent(new Event('pagehide')) })
    expect(mocks.mutateKeepalive).not.toHaveBeenCalled()
  })

  it('continues the same NOTE lease after rollover and preserves its stats through empty finalization', async () => {
    mockNoteBatchApi()
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => { await latest.answer('card-1', 'good', decision, 250) })
    await act(async () => { await latest.commit({ reason: 'rollover', resumeAfterCommit: true }) })
    expect(latest.session?.status).toBe('active')
    expect(latest.session?.batch_sequence).toBe(1)
    expect(latest.receipt).toBeNull()
    expect(latest.totalSessionStats.total_reviews).toBe(1)
    expect(mocks.mutate.mock.calls.filter(([path]) => path === '/api/study/sessions')).toHaveLength(1)
    await act(async () => { await latest.commit({ reason: 'manual_exit' }) })
    expect(latest.receipt).toMatchObject({ applied_event_count: 0 })
    expect(latest.totalSessionStats.total_reviews).toBe(1)
  })

  it('never deletes the durable NOTE batch after ownership is lost during polling', async () => {
    const api = mockNoteBatchApi()
    api.setCompleted(false)
    await openReadySession()
    const decision = latest.prepareDecision('card-1')
    await act(async () => { await latest.answer('card-1', 'good', decision, 250) })
    let commitPromise!: Promise<StudySessionCommitReceipt | null>
    await act(async () => { commitPromise = latest.commit().catch(() => null); await Promise.resolve() })
    await waitFor(() => expect(api.batches.size).toBe(1))
    expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
    await act(async () => {
      leaseRecords[0].handlers.onLost?.(new DOMException('Lost lease', 'AbortError'))
      await commitPromise
    })
    expect(latest.receipt).toBeNull()
    expect(mocks.removeSessionIfMatches).not.toHaveBeenCalled()
    expect(mocks.saveSession.mock.calls.at(-1)?.[0].in_flight_batches).toHaveLength(1)
  })

  it('contains automatic rollover to the synchronous commit path', async () => {
    const events: StudySessionEvent[] = Array.from({ length: 50 }, (_, index) => ({
      event_id: `00000000-0000-4000-8000-${(index + 1).toString().padStart(12, '0')}`,
      sequence: index + 1,
      card_id: 'card-1',
      rating: 'good',
      action_key: 'review.good',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
      policy_key: 'policy',
      scheduler_offset_ms: index * 1000,
      duration_ms: 250,
    }))
    mocks.loadSession.mockResolvedValueOnce({
      scope_key: 'user:7:deck:12',
      snapshot: snapshot(),
      events,
      touched_card_ids: ['card-1'],
      undo_history: [],
      active_card_id: 'card-1',
      opened_client_at_ms: Date.now(),
      status: 'active',
      commit_id: null,
      commit_reason: null,
      resume_after_commit: false,
      batch_sequence: 0,
      event_sequence: 50,
      in_flight_batches: [],
      updated_at_ms: Date.now(),
    })
    mocks.mutate.mockImplementation((path: string) => {
      if (path === '/api/study/sessions/session-1/commit') {
        return Promise.resolve({ ...receipt(), commit_reason: 'rollover', applied_event_count: 50 })
      }
      if (path === '/api/study/sessions') return Promise.resolve(snapshot())
      throw new Error(`Unexpected mutation: ${path}`)
    })

    await openReadySession()
    await waitFor(() => expect(mocks.mutate).toHaveBeenCalledWith(
      '/api/study/sessions/session-1/commit',
      'POST',
      expect.objectContaining({
        schema_version: 'study-commit.v1',
        commit_reason: 'rollover',
      }),
    ))

    expect(mocks.mutate.mock.calls.some(([path]) => String(path).endsWith('/batch')))
      .toBe(false)
  })
})
