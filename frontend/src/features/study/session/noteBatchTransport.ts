import { appApi } from '@/app/api'
import { ApiError } from '@/shared/api/client'
import type { StudyBatchPayload, StudyBatchStatus, StudyNoteBatchCommitReceipt } from '../types'
import { requireNoteBatchReceipt } from './batchReceipt'
import { canonicalJson } from './canonicalDigest'
import type { PersistedStudySession, StudyCommitReason, StudySessionAccumulatedStats } from './sessionStore'
import { acknowledgeBatchReceipt, extractPendingBatch } from './studySessionEngine'

const MAX_BATCH_BYTES = 60 * 1024
const POLL_LIMIT = 30

type TransportContext = {
  /** Caller owns the session mutation and cross-tab lease for this entire operation. */
  checkOwner: () => void
  persist: (session: PersistedStudySession) => Promise<boolean>
  wait?: () => Promise<void>
}

export function usesNoteBatchTransport(session: PersistedStudySession) {
  return session.snapshot.schema_version === 'study-session.v4' && (
    session.snapshot.batch_transport === 'study-note-batch-transport.v1'
    || (session.batch_sequence ?? 0) > 0
  )
}

function pendingError() {
  return new ApiError('Batch đã nhận và đang chờ xử lý. Dữ liệu vẫn được giữ trên máy.', 202, 'BATCH_PENDING')
}

async function persist(session: PersistedStudySession, context: TransportContext) {
  context.checkOwner()
  if (!await context.persist(session)) {
    throw new ApiError('Không thể lưu batch bền vững trên máy. Chưa gửi thêm dữ liệu.', 503, 'STUDY_STORAGE_UNAVAILABLE')
  }
  context.checkOwner()
  return session
}

export function prepareNoteBatchOperation(
  session: PersistedStudySession,
  options: { reason?: StudyCommitReason; resumeAfterCommit?: boolean } = {},
): PersistedStudySession {
  if (!usesNoteBatchTransport(session)) throw new Error('NOTE batch transport was not negotiated.')
  if (session.status === 'pending_commit') return session
  return {
    ...session, status: 'pending_commit',
    commit_id: session.commit_id ?? crypto.randomUUID(),
    commit_reason: options.reason ?? 'manual_exit',
    resume_after_commit: Boolean(options.resumeAfterCommit),
    updated_at_ms: Date.now(),
  }
}

function allocateBatch(session: PersistedStudySession) {
  let limit = Math.min(session.events.length, 50)
  while (true) {
    const extracted = extractPendingBatch(session, Math.max(1, limit), {
      reason: session.commit_reason ?? 'manual_exit', isFinal: !session.resume_after_commit,
    })
    if (!extracted) return null
    if (new TextEncoder().encode(canonicalJson(extracted.batch)).length <= MAX_BATCH_BYTES) return extracted
    if (limit <= 1) throw new ApiError('Một event vượt giới hạn batch; dữ liệu vẫn được giữ.', 413, 'COMMIT_TOO_LARGE')
    limit = Math.max(1, Math.floor(limit / 2))
  }
}

function accumulate(session: PersistedStudySession, batch: StudyBatchPayload): StudySessionAccumulatedStats {
  const result = { ...(session.accumulated_stats ?? {
    total_reviews: 0, total_duration_ms: 0, again_count: 0, hard_count: 0, good_count: 0, easy_count: 0,
  }) }
  for (const event of batch.events) {
    result.total_reviews += 1
    result.total_duration_ms += event.duration_ms
    result[`${event.rating}_count`] += 1
  }
  return result
}

async function admit(session: PersistedStudySession, batch: StudyBatchPayload, keepalive = false) {
  const response = await (keepalive ? appApi.mutateKeepalive : appApi.mutate)<unknown>(
    `/api/study/sessions/${session.snapshot.session_id}/batch`, 'POST', batch,
  )
  const ack = response as Record<string, unknown> | null
  if (
    !ack || ack.schema_version !== 'study-batch-receipt.v1'
    || !['enqueued', 'already_processed'].includes(String(ack.status))
    || ack.session_id !== session.snapshot.session_id || ack.batch_id !== batch.batch_id
    || ack.batch_sequence !== batch.batch_sequence || ack.event_count !== batch.events.length
  ) throw new ApiError('Batch chưa có xác nhận hợp lệ.', 502, 'INVALID_BATCH_RECEIPT')
  return ack.status === 'already_processed' ? requireNoteBatchReceipt(session, batch, ack.receipt) : null
}

async function settle(session: PersistedStudySession, batch: StudyBatchPayload, context: TransportContext) {
  const url = `/api/study/sessions/${session.snapshot.session_id}/batch/${batch.batch_id}`
  let admitted = false
  for (let attempt = 0; attempt < POLL_LIMIT; attempt += 1) {
    context.checkOwner()
    let result: StudyBatchStatus
    try {
      result = await appApi.get<StudyBatchStatus>(url)
    } catch (error) {
      context.checkOwner()
      if (!(error instanceof ApiError) || error.code !== 'BATCH_NOT_FOUND' || admitted) throw error
      const receipt = await admit(session, batch)
      context.checkOwner()
      if (receipt) return receipt
      admitted = true
      continue
    }
    context.checkOwner()
    if (
      result.schema_version !== 'study-batch-status.v1'
      || result.session_id !== session.snapshot.session_id || result.batch_id !== batch.batch_id
      || result.batch_sequence !== batch.batch_sequence || result.event_count !== batch.events.length
      || result.is_final !== batch.is_final
    ) throw new ApiError('Trạng thái batch không khớp dữ liệu đang lưu.', 502, 'INVALID_BATCH_RECEIPT')
    if (result.status === 'completed') return requireNoteBatchReceipt(session, batch, result.receipt)
    if (result.status === 'failed') {
      throw new ApiError('Batch không thể áp dụng. Dữ liệu đang giữ để xử lý xung đột.', 409, result.error_code ?? 'BATCH_FAILED')
    }
    if (result.status !== 'enqueued') throw new ApiError('Trạng thái batch không hợp lệ.', 502, 'INVALID_BATCH_RECEIPT')
    admitted = true
    if (context.wait) await context.wait()
    else await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw pendingError()
}

export async function flushNoteBatchStream(
  initial: PersistedStudySession, context: TransportContext,
  options: { reason?: StudyCommitReason; resumeAfterCommit?: boolean } = {},
): Promise<{ session: PersistedStudySession; receipt: StudyNoteBatchCommitReceipt | null }> {
  let current = await persist(prepareNoteBatchOperation(initial, options), context)
  let lastReceipt: StudyNoteBatchCommitReceipt | null = null
  while (true) {
    let batch = current.in_flight_batches?.[0]
    if (!batch) {
      const extracted = allocateBatch(current)
      if (!extracted) break
      current = await persist(extracted.session, context)
      batch = extracted.batch
    }
    if (batch.is_final && (current.events.length || current.in_flight_batches!.length !== 1)) {
      throw new ApiError('Có dữ liệu sau batch kết thúc phiên.', 409, 'BATCH_AFTER_FINAL')
    }
    lastReceipt = await settle(current, batch, context)
    context.checkOwner()
    const next = {
      ...acknowledgeBatchReceipt(current, batch.batch_id, lastReceipt),
      accumulated_stats: accumulate(current, batch),
    }
    if (batch.is_final) {
      // Keep the final batch durable until the hook removes the session. A crash
      // here re-reads its historical receipt and counts its stats exactly once.
      return { session: next, receipt: lastReceipt }
    }
    current = await persist(next, context)
    if (current.resume_after_commit && current.events.length === 0 && !current.in_flight_batches?.length) break
  }
  current = await persist({
    ...current, status: 'active', commit_id: null, commit_reason: null, resume_after_commit: false,
  }, context)
  return { session: current, receipt: lastReceipt }
}

export async function sendNoteBatchOnExit(initial: PersistedStudySession, context: TransportContext) {
  let current = prepareNoteBatchOperation(initial, { reason: 'page_exit' })
  if (current.resume_after_commit) {
    // Preserve any already-created payload, but finish the stream after that
    // nonfinal rollover instead of resuming study after the browser was closed.
    current = { ...current, resume_after_commit: false, commit_reason: 'page_exit' }
  }
  if (!current.in_flight_batches?.length) {
    const extracted = allocateBatch(current)
    if (!extracted) return
    current = extracted.session
  }
  current = await persist(current, context)
  await admit(current, current.in_flight_batches![0], true)
  // No acknowledgment/removal during page exit; restore reconciles the receipt.
}
