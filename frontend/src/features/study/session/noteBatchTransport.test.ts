import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/client'
import type { StudyBatchPayload, StudyNoteBatchCommitReceipt } from '../types'
import { canonicalDigest, canonicalJson } from './canonicalDigest'
import { flushNoteBatchStream, sendNoteBatchOnExit } from './noteBatchTransport'
import { createPersistedSession, applyLocalAnswer, decisionForCard } from './studySessionEngine'
import { normalizePersistedStudySession } from './sessionRestore'
import { studySnapshotFixture } from './studySessionTestFixture'
import type { PersistedStudySession } from './sessionStore'

const api = vi.hoisted(() => ({ get: vi.fn(), mutate: vi.fn(), mutateKeepalive: vi.fn() }))
vi.mock('@/app/api', () => ({ appApi: api }))

function session(eventCount = 1) {
  const base = studySnapshotFixture()
  let current = createPersistedSession({
    ...base, schema_version: 'study-session.v4', authority_mode: 'NOTE', enrollment_epoch: '1',
    batch_transport: 'study-note-batch-transport.v1',
    cards: base.cards.map((card) => ({ ...card, authority_pin: {
      schema_version: 'study-note-authority-pin.v1', authority_mode: 'NOTE', enrollment_epoch: '1',
      logical_note_key: card.note_id, subject_generation: '1', base_authority_revision: '0',
      base_authority_state_hash: '11'.repeat(32),
    } })),
  })
  for (let sequence = 1; sequence <= eventCount; sequence += 1) {
    const card = current.snapshot.cards[0]
    current = applyLocalAnswer(current, card.card_id, 'good', decisionForCard(
      current, card.card_id, Date.parse(base.server_now_utc) + sequence * 1000,
    ), 250)
  }
  return current
}

function receiptFor(batch: StudyBatchPayload, current: PersistedStudySession): StudyNoteBatchCommitReceipt {
  return {
    schema_version: 'study-commit-receipt.v2', authority_mode: 'NOTE', enrollment_epoch: '1',
    batch_receipt_schema_version: 'study-note-batch-receipt.v1', success: true,
    session_id: current.snapshot.session_id, batch_id: batch.batch_id, commit_id: batch.batch_id,
    batch_sequence: batch.batch_sequence, commit_reason: batch.commit_reason!, is_final: batch.is_final!,
    applied_event_count: batch.events.length,
    cumulative_event_count: batch.events.at(-1)?.sequence ?? current.event_sequence!,
    updated_cards: [], rating_counts: { again: 0, hard: 0, good: batch.events.length, easy: 0 },
    committed_at: current.snapshot.server_now_utc, request_hash: canonicalDigest(batch),
    receipt_hash: `sha256-${'22'.repeat(32)}`,
  }
}

function harness(initial: PersistedStudySession) {
  let durable = initial
  let owned = true
  const admitted = new Map<string, StudyBatchPayload>()
  const context = {
    checkOwner: () => { if (!owned) throw new DOMException('Lost lease', 'AbortError') },
    persist: vi.fn(async (value: PersistedStudySession) => {
      const normalized = normalizePersistedStudySession(structuredClone(value), value.scope_key)
      expect(normalized.status, JSON.stringify(normalized)).toBe('restored')
      if (normalized.status === 'restored') durable = normalized.session
      return true
    }),
    wait: vi.fn(async () => {}),
  }
  api.get.mockImplementation(async (url: string) => {
    const batch = admitted.get(url.split('/').at(-1)!)
    if (!batch) throw new ApiError('Missing batch', 404, 'BATCH_NOT_FOUND')
    return {
      schema_version: 'study-batch-status.v1', status: 'completed', session_id: initial.snapshot.session_id,
      batch_id: batch.batch_id, batch_sequence: batch.batch_sequence, event_count: batch.events.length,
      is_final: batch.is_final, receipt: receiptFor(batch, durable),
    }
  })
  const admit = async (_url: string, _method: string, batch: StudyBatchPayload) => {
    expect(durable.in_flight_batches?.some((item) => item.batch_id === batch.batch_id)).toBe(true)
    admitted.set(batch.batch_id, structuredClone(batch))
    return {
      schema_version: 'study-batch-receipt.v1', status: 'enqueued', session_id: initial.snapshot.session_id,
      batch_id: batch.batch_id, batch_sequence: batch.batch_sequence, event_count: batch.events.length,
    }
  }
  api.mutate.mockImplementation(admit)
  api.mutateKeepalive.mockImplementation(admit)
  return { context, admitted, durable: () => durable, loseLease: () => { owned = false } }
}

beforeEach(() => {
  api.get.mockReset(); api.mutate.mockReset(); api.mutateKeepalive.mockReset()
})

describe('durable NOTE batch transport', () => {
  it('posts only after persistence, finalizes and restores the same terminal batch', async () => {
    const initial = session()
    const h = harness(initial)
    const result = await flushNoteBatchStream(initial, h.context)
    expect(result.receipt?.is_final).toBe(true)
    expect(result.session.accumulated_stats?.total_reviews).toBe(1)
    expect(h.durable().in_flight_batches).toHaveLength(1)
    const retry = await flushNoteBatchStream(h.durable(), h.context)
    expect(retry.receipt).toEqual(result.receipt)
    expect(retry.session.accumulated_stats?.total_reviews).toBe(1)
    expect(api.mutate).toHaveBeenCalledTimes(1)
  })

  it('rolls over on the same lease then finalizes with an empty batch', async () => {
    const initial = session(2)
    const h = harness(initial)
    const rollover = await flushNoteBatchStream(initial, h.context, { reason: 'rollover', resumeAfterCommit: true })
    expect(rollover.receipt?.is_final).toBe(false)
    expect(rollover.session.status).toBe('active')
    expect(rollover.session.snapshot).toEqual(initial.snapshot)
    expect(rollover.session.accumulated_stats?.total_reviews).toBe(2)
    expect(rollover.session.acknowledged_scheduler_offset_ms).toBe(2000)
    expect(decisionForCard(
      h.durable(), initial.snapshot.cards[0].card_id,
      Date.parse(initial.snapshot.server_now_utc) + 500,
    ).scheduler_at_ms).toBe(Date.parse(initial.snapshot.server_now_utc) + 2000)
    const final = await flushNoteBatchStream(h.durable(), h.context)
    expect(final.receipt).toMatchObject({ is_final: true, applied_event_count: 0, cumulative_event_count: 2 })
    expect(final.session.accumulated_stats?.total_reviews).toBe(2)
  })

  it('splits a final operation into ordered batches without dropping unsent actions', async () => {
    const initial = session(51)
    const h = harness(initial)
    const final = await flushNoteBatchStream(initial, h.context)
    const batches = [...h.admitted.values()]
    expect(batches.map((item) => [item.batch_sequence, item.events.length, item.is_final])).toEqual([
      [1, 50, false], [2, 1, true],
    ])
    expect(batches[0].commit_reason).toBe('rollover')
    expect(final.session.accumulated_stats?.total_reviews).toBe(51)
    expect(h.durable().accumulated_stats?.total_reviews).toBe(50)
    const retry = await flushNoteBatchStream(h.durable(), h.context)
    expect(retry.session.accumulated_stats?.total_reviews).toBe(51)
    expect(api.mutate).toHaveBeenCalledTimes(2)
  })

  it('retains the exact batch after a lost admission response and recovers without reposting', async () => {
    const initial = session()
    const h = harness(initial)
    const admit = api.mutate.getMockImplementation()!
    api.mutate.mockImplementationOnce(async (...args) => { await admit(...args); throw new TypeError('Offline') })
    await expect(flushNoteBatchStream(initial, h.context)).rejects.toThrow('Offline')
    const batch = h.durable().in_flight_batches![0]
    const recovered = await flushNoteBatchStream(h.durable(), h.context)
    expect(recovered.receipt?.batch_id).toBe(batch.batch_id)
    expect(api.mutate).toHaveBeenCalledTimes(1)
  })

  it('cannot treat 202 as completion and yields after bounded polling', async () => {
    const initial = session()
    const h = harness(initial)
    api.get.mockImplementation(async () => {
      const batch = h.durable().in_flight_batches![0]
      return { schema_version: 'study-batch-status.v1', status: 'enqueued', session_id: initial.snapshot.session_id,
        batch_id: batch.batch_id, batch_sequence: batch.batch_sequence, event_count: batch.events.length, is_final: batch.is_final }
    })
    await expect(flushNoteBatchStream(initial, h.context)).rejects.toMatchObject({ code: 'BATCH_PENDING' })
    expect(h.context.wait).toHaveBeenCalledTimes(30)
    expect(h.durable().in_flight_batches).toHaveLength(1)
    expect(h.durable().accumulated_stats?.total_reviews ?? 0).toBe(0)
  })

  it('does not send if IndexedDB persistence fails', async () => {
    const initial = session()
    const h = harness(initial)
    h.context.persist.mockResolvedValue(false)
    await expect(flushNoteBatchStream(initial, h.context)).rejects.toMatchObject({ code: 'STUDY_STORAGE_UNAVAILABLE' })
    expect(api.mutate).not.toHaveBeenCalled()
    expect(api.get).not.toHaveBeenCalled()
  })

  it('leaves completed work unacknowledged after lease ownership loss', async () => {
    const initial = session()
    const h = harness(initial)
    const get = api.get.getMockImplementation()!
    api.get.mockImplementation(async (...args) => { const result = await get(...args); h.loseLease(); return result })
    await expect(flushNoteBatchStream(initial, h.context)).rejects.toMatchObject({ name: 'AbortError' })
    expect(h.durable().in_flight_batches).toHaveLength(1)
    expect(h.durable().accumulated_stats?.total_reviews ?? 0).toBe(0)
  })

  it('keeps a page-exit batch until restore fetches its durable receipt', async () => {
    const initial = session()
    const h = harness(initial)
    await sendNoteBatchOnExit(initial, h.context)
    expect(h.durable().in_flight_batches).toHaveLength(1)
    expect(api.get).not.toHaveBeenCalled()
    expect(api.mutateKeepalive).toHaveBeenCalledOnce()
    const result = await flushNoteBatchStream(h.durable(), h.context)
    expect(result.receipt?.commit_reason).toBe('page_exit')
    expect(result.session.accumulated_stats?.total_reviews).toBe(1)
  })

  it.each(['failed', 'corrupt', 'wrong-session'])('retains pending data for a %s server result', async (kind) => {
    const initial = session()
    const h = harness(initial)
    const get = api.get.getMockImplementation()!
    api.get.mockImplementation(async (...args) => {
      const result = await get(...args)
      if (kind === 'failed') return { ...result, status: 'failed', error_code: 'AUTHORITY_STATE_CONFLICT' }
      if (kind === 'wrong-session') return { ...result, session_id: 'another-session' }
      return { ...result, receipt: { ...result.receipt, request_hash: 'corrupted' } }
    })
    await expect(flushNoteBatchStream(initial, h.context)).rejects.toThrow()
    expect(h.durable().in_flight_batches).toHaveLength(1)
    expect(h.durable().accumulated_stats?.total_reviews ?? 0).toBe(0)
  })

  it('reduces batch size to the UTF-8 storage bound without losing event order', async () => {
    const initial = session(50)
    initial.snapshot.session_token = '猫'.repeat(14_000)
    const h = harness(initial)
    const result = await flushNoteBatchStream(initial, h.context)
    expect(h.admitted.size).toBeGreaterThan(1)
    const batches = [...h.admitted.values()]
    for (const batch of batches) expect(new TextEncoder().encode(canonicalJson(batch)).length).toBeLessThanOrEqual(60 * 1024)
    expect(batches.flatMap((batch) => batch.events.map((event) => event.sequence))).toEqual(
      Array.from({ length: 50 }, (_, index) => index + 1),
    )
    expect(result.session.accumulated_stats?.total_reviews).toBe(50)
    expect(batches.at(-1)?.is_final).toBe(true)
  })

  it('retains an oversized single batch without submitting it', async () => {
    const initial = session()
    initial.snapshot.session_token = 'x'.repeat(61 * 1024)
    const h = harness(initial)
    await expect(flushNoteBatchStream(initial, h.context)).rejects.toMatchObject({ code: 'COMMIT_TOO_LARGE' })
    expect(h.durable().events).toHaveLength(1)
    expect(api.mutate).not.toHaveBeenCalled()
  })

  it('page exit preserves an uncertain rollover payload and then finishes its stream', async () => {
    const initial = session()
    const h = harness(initial)
    api.mutate.mockRejectedValueOnce(new TypeError('Offline'))
    await expect(flushNoteBatchStream(initial, h.context, {
      reason: 'rollover', resumeAfterCommit: true,
    })).rejects.toThrow('Offline')
    const originalBatch = structuredClone(h.durable().in_flight_batches![0])
    await sendNoteBatchOnExit(h.durable(), h.context)
    expect(h.durable().resume_after_commit).toBe(false)
    expect(h.durable().in_flight_batches![0]).toEqual(originalBatch)
    const completed = await flushNoteBatchStream(h.durable(), h.context)
    expect(completed.receipt).toMatchObject({ is_final: true, commit_reason: 'page_exit', applied_event_count: 0 })
    expect(completed.session.accumulated_stats?.total_reviews).toBe(1)
  })
})
