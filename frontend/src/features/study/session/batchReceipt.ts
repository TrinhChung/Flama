import type { StudyBatchPayload, StudyNoteBatchCommitReceipt } from '../types'
import { canonicalDigest } from './canonicalDigest'
import type { PersistedStudySession } from './sessionStore'

export function hasUnacknowledgedStudyWork(session: PersistedStudySession) {
  return session.events.length > 0 || (session.in_flight_batches?.length ?? 0) > 0
}

export function requireNoteBatchReceipt(
  session: PersistedStudySession,
  batch: StudyBatchPayload,
  value: unknown,
): StudyNoteBatchCommitReceipt {
  const receipt = value as Partial<StudyNoteBatchCommitReceipt> | null
  const ratings = { again: 0, hard: 0, good: 0, easy: 0 }
  for (const event of batch.events) ratings[event.rating] += 1
  if (
    !receipt
    || session.snapshot.schema_version !== 'study-session.v4'
    || receipt.schema_version !== 'study-commit-receipt.v2'
    || receipt.batch_receipt_schema_version !== 'study-note-batch-receipt.v1'
    || receipt.success !== true
    || receipt.authority_mode !== 'NOTE'
    || receipt.enrollment_epoch !== session.snapshot.enrollment_epoch
    || receipt.session_id !== session.snapshot.session_id
    || receipt.batch_id !== batch.batch_id || receipt.commit_id !== batch.batch_id
    || receipt.batch_sequence !== batch.batch_sequence
    || receipt.commit_reason !== batch.commit_reason
    || receipt.is_final !== batch.is_final
    || receipt.applied_event_count !== batch.events.length
    || receipt.request_hash !== canonicalDigest(batch)
    || typeof receipt.receipt_hash !== 'string'
    || !/^sha256-[0-9a-f]{64}$/.test(receipt.receipt_hash)
    || !Number.isSafeInteger(receipt.cumulative_event_count)
    || receipt.cumulative_event_count !== (
      batch.events.at(-1)?.sequence
      ?? session.event_sequence
    )
    || !Array.isArray(receipt.updated_cards)
    || typeof receipt.committed_at !== 'string'
    || !Number.isFinite(Date.parse(receipt.committed_at))
    || !receipt.rating_counts
    || Object.entries(ratings).some(([rating, count]) => (
      receipt.rating_counts?.[rating as keyof typeof ratings] !== count
    ))
  ) {
    throw new Error('Chưa có receipt bền vững khớp với batch; dữ liệu học vẫn được giữ để thử lại.')
  }
  // Server verifies the receipt digest from stored canonical bytes. Do not
  // rehash the parsed response: Python 1.0 and JS 1 have different JSON bytes.
  return receipt as StudyNoteBatchCommitReceipt
}
