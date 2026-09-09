import {
  ClientAlgorithmContractError,
  ClientAlgorithmUnavailableError,
  validateSnapshotAlgorithmContract,
} from '../scheduler/algorithmRegistry'
import type { SchedulerCardState } from '../scheduler/types'
import type {
  Rating,
  StudyBatchPayload,
  StudySessionEvent,
  StudySessionSnapshot,
} from '../types'
import {
  REVIEW_RATINGS,
} from '../interactions/reviewInteraction'
import type {
  PersistedStudySession,
  StudyCommitReason,
  StudySessionAccumulatedStats,
  StudySessionUndoItem,
} from './sessionStore'
import {
  STUDY_SESSION_SCHEMA_V2,
  STUDY_SESSION_SCHEMA_V3,
  StudyWireContractError,
  reviewEventWireIdentity,
  validateReviewEventWireIdentity,
  wireEnvelopeForSession,
} from './wireContract'

export type StudySessionQuarantineReason =
  | 'ALGORITHM_UNAVAILABLE'
  | 'ALGORITHM_CONTRACT_MISMATCH'
  | 'BATCH_CONTRACT_MISMATCH'
  | 'COMPOSITION_CONTRACT_MISMATCH'
  | 'EVENT_CONTRACT_MISMATCH'
  | 'EVENT_ID_INVALID'
  | 'EVENT_SEQUENCE_INVALID'
  | 'EVENT_TIME_INVALID'
  | 'MALFORMED_SESSION'
  | 'SCOPE_MISMATCH'

export type StudySessionQuarantine = Readonly<{
  reason: StudySessionQuarantineReason
  message: string
}>

export type StudySessionRestoreResult =
  | {
      status: 'restored'
      session: PersistedStudySession
      migrated: boolean
    }
  | {
      status: 'quarantine'
      quarantine: StudySessionQuarantine
    }

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const VALID_CARD_TYPES = new Set(['new', 'learning', 'review', 'relearning'])
const VALID_RATINGS = new Set<string>(REVIEW_RATINGS)
const VALID_COMMIT_REASONS = new Set<StudyCommitReason>([
  'auto_finish',
  'manual_exit',
  'page_exit',
  'rollover',
])

function quarantine(
  reason: StudySessionQuarantineReason,
  message: string,
): StudySessionRestoreResult {
  return { status: 'quarantine', quarantine: { reason, message } }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isFiniteTimestamp(value: unknown) {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number'
    && Number.isSafeInteger(value)
    && value >= 0
}

function isUuid(value: unknown): value is string {
  return typeof value === 'string' && UUID_PATTERN.test(value)
}

type NormalizedEvent = {
  event: StudySessionEvent
  migrated: boolean
}

function normalizeEvent(
  value: unknown,
  index: number,
  snapshot: StudySessionSnapshot,
): NormalizedEvent | StudySessionRestoreResult {
  if (!isRecord(value)) {
    return quarantine(
      'EVENT_CONTRACT_MISMATCH',
      `Stored study event ${index + 1} is not an object.`,
    )
  }
  if (!isUuid(value.event_id)) {
    return quarantine(
      'EVENT_ID_INVALID',
      `Stored study event ${index + 1} has an invalid event id.`,
    )
  }
  const cardId = typeof value.card_id === 'string' ? value.card_id : ''
  const card = snapshot.cards.find((row) => row.card_id === cardId)
  if (!card) {
    return quarantine(
      'EVENT_CONTRACT_MISMATCH',
      `Stored study event ${index + 1} references a card outside the session.`,
    )
  }
  if (!VALID_RATINGS.has(String(value.rating ?? ''))) {
    return quarantine(
      'EVENT_CONTRACT_MISMATCH',
      `Stored study event ${index + 1} has an invalid rating.`,
    )
  }
  if (!Number.isSafeInteger(value.sequence) || Number(value.sequence) <= 0) {
    return quarantine(
      'EVENT_SEQUENCE_INVALID',
      `Stored study event ${index + 1} has an invalid sequence.`,
    )
  }
  if (
    !isNonNegativeInteger(value.scheduler_offset_ms)
    || !isNonNegativeInteger(value.duration_ms)
    || value.duration_ms > 3_600_000
  ) {
    return quarantine(
      'EVENT_TIME_INVALID',
      `Stored study event ${index + 1} has invalid timing metadata.`,
    )
  }
  if (
    typeof value.policy_key !== 'string'
    || value.policy_key !== card.policy_key
    || !snapshot.policies[value.policy_key]
  ) {
    return quarantine(
      'EVENT_CONTRACT_MISMATCH',
      `Stored study event ${index + 1} uses the wrong scheduler policy.`,
    )
  }

  const rating = value.rating as Rating
  const policy = snapshot.policies[value.policy_key]
  let action
  try {
    action = validateReviewEventWireIdentity(value, {
      schema: snapshot.schema_version,
      sessionId: snapshot.session_id,
      policy,
    })
  } catch (error) {
    if (!(error instanceof StudyWireContractError)) throw error
    return quarantine(
      'EVENT_CONTRACT_MISMATCH',
      `Stored study event ${index + 1} has invalid wire identity.`,
    )
  }
  const isLegacyEvent = snapshot.schema_version === STUDY_SESSION_SCHEMA_V2
    && value.action_key === undefined
    && value.trigger_key === undefined
    && value.trigger_contract_version === undefined
  const wireIdentity = reviewEventWireIdentity(
    snapshot.schema_version,
    snapshot.session_id,
    action,
    policy,
  )

  return {
    migrated: isLegacyEvent,
    event: {
      event_id: value.event_id,
      sequence: value.sequence as number,
      card_id: cardId,
      rating,
      ...wireIdentity,
      policy_key: value.policy_key,
      scheduler_offset_ms: value.scheduler_offset_ms,
      duration_ms: value.duration_ms,
    } as StudySessionEvent,
  }
}

function normalizeUndoHistory(
  value: unknown,
  cardIds: Set<string>,
): StudySessionUndoItem[] | null {
  if (!Array.isArray(value)) return value === undefined ? [] : null
  const result: StudySessionUndoItem[] = []
  for (const item of value) {
    if (
      !isRecord(item)
      || typeof item.card_id !== 'string'
      || !cardIds.has(item.card_id)
      || !isRecord(item.previous_state)
      || !VALID_CARD_TYPES.has(String(item.previous_state.type ?? ''))
    ) return null
    result.push({
      card_id: item.card_id,
      previous_state: item.previous_state as SchedulerCardState,
    })
  }
  return result
}

function normalizeAccumulatedStats(
  value: unknown,
): StudySessionAccumulatedStats | undefined | null {
  if (value === undefined) return undefined
  if (!isRecord(value)) return null
  const fields = [
    value.total_reviews,
    value.total_duration_ms,
    value.again_count,
    value.hard_count,
    value.good_count,
    value.easy_count,
  ]
  if (!fields.every(isNonNegativeInteger)) return null
  return {
    total_reviews: value.total_reviews as number,
    total_duration_ms: value.total_duration_ms as number,
    again_count: value.again_count as number,
    hard_count: value.hard_count as number,
    good_count: value.good_count as number,
    easy_count: value.easy_count as number,
  }
}

type NormalizedBatch = {
  batch: StudyBatchPayload
  events: StudySessionEvent[]
  migrated: boolean
}

function normalizeBatch(
  value: unknown,
  index: number,
  snapshot: StudySessionSnapshot,
): NormalizedBatch | StudySessionRestoreResult {
  if (
    !isRecord(value)
    || value.schema_version !== wireEnvelopeForSession(
      snapshot.schema_version,
    ).batchSchema
    || !isUuid(value.batch_id)
    || !Number.isSafeInteger(value.batch_sequence)
    || Number(value.batch_sequence) <= 0
    || value.session_token !== snapshot.session_token
    || value.snapshot_hash !== snapshot.snapshot_hash
    || !Array.isArray(value.events)
    || value.events.length === 0
  ) {
    return quarantine(
      'BATCH_CONTRACT_MISMATCH',
      `Stored in-flight batch ${index + 1} is malformed.`,
    )
  }
  if (
    value.commit_reason !== undefined
    && (
      typeof value.commit_reason !== 'string'
      || !VALID_COMMIT_REASONS.has(value.commit_reason as StudyCommitReason)
    )
  ) {
    return quarantine(
      'BATCH_CONTRACT_MISMATCH',
      `Stored in-flight batch ${index + 1} has an invalid commit reason.`,
    )
  }
  if (value.is_final !== undefined && typeof value.is_final !== 'boolean') {
    return quarantine(
      'BATCH_CONTRACT_MISMATCH',
      `Stored in-flight batch ${index + 1} has an invalid final marker.`,
    )
  }

  const events: StudySessionEvent[] = []
  let migrated = false
  for (let eventIndex = 0; eventIndex < value.events.length; eventIndex += 1) {
    const normalized = normalizeEvent(value.events[eventIndex], eventIndex, snapshot)
    if ('status' in normalized) return normalized
    events.push(normalized.event)
    migrated ||= normalized.migrated
  }

  let finalStates: StudyBatchPayload['final_states']
  if (value.final_states !== undefined) {
    if (!Array.isArray(value.final_states)) {
      return quarantine(
        'BATCH_CONTRACT_MISMATCH',
        `Stored in-flight batch ${index + 1} has invalid final states.`,
      )
    }
    const touched = new Set(events.map((event) => event.card_id))
    const seen = new Set<string>()
    finalStates = []
    for (const item of value.final_states) {
      if (!isRecord(item)) {
        return quarantine(
          'BATCH_CONTRACT_MISMATCH',
          `Stored in-flight batch ${index + 1} has invalid final states.`,
        )
      }
      const cardId = typeof item.card_id === 'string' ? item.card_id : ''
      const card = snapshot.cards.find((row) => row.card_id === cardId)
      if (
        !card
        || !touched.has(cardId)
        || seen.has(cardId)
        || !isNonNegativeInteger(item.base_revision)
        || item.base_revision !== card.base_revision
        || !isRecord(item.state)
        || !VALID_CARD_TYPES.has(String(item.state.type ?? ''))
      ) {
        return quarantine(
          'BATCH_CONTRACT_MISMATCH',
          `Stored in-flight batch ${index + 1} has inconsistent final states.`,
        )
      }
      seen.add(cardId)
      finalStates.push({
        card_id: cardId,
        base_revision: item.base_revision,
        state: item.state as SchedulerCardState,
      })
    }
    if (seen.size !== touched.size) {
      return quarantine(
        'BATCH_CONTRACT_MISMATCH',
        `Stored in-flight batch ${index + 1} is missing final states.`,
      )
    }
  }

  return {
    events,
    migrated,
    batch: {
      schema_version: wireEnvelopeForSession(snapshot.schema_version).batchSchema,
      batch_id: value.batch_id,
      batch_sequence: value.batch_sequence as number,
      session_token: value.session_token,
      snapshot_hash: value.snapshot_hash,
      ...(value.commit_reason === undefined
        ? {}
        : { commit_reason: value.commit_reason as StudyCommitReason }),
      ...(value.is_final === undefined
        ? {}
        : { is_final: value.is_final }),
      events,
      ...(finalStates === undefined ? {} : { final_states: finalStates }),
    } as StudyBatchPayload,
  }
}

export function normalizePersistedStudySession(
  value: unknown,
  expectedScopeKey?: string,
): StudySessionRestoreResult {
  if (!isRecord(value) || !isRecord(value.snapshot)) {
    return quarantine('MALFORMED_SESSION', 'Stored study session is malformed.')
  }
  const snapshotValue = value.snapshot
  const policies = snapshotValue.policies
  const templates = snapshotValue.templates
  const contents = snapshotValue.contents
  const compositions = snapshotValue.compositions
  const serverNowMs = typeof snapshotValue.server_now_utc === 'string'
    ? Date.parse(snapshotValue.server_now_utc)
    : Number.NaN
  const expiresAtMs = typeof snapshotValue.expires_at === 'string'
    ? Date.parse(snapshotValue.expires_at)
    : Number.NaN
  if (
    (
      snapshotValue.schema_version !== STUDY_SESSION_SCHEMA_V2
      && snapshotValue.schema_version !== STUDY_SESSION_SCHEMA_V3
    )
    || !isUuid(snapshotValue.session_id)
    || !Number.isSafeInteger(snapshotValue.user_id)
    || Number(snapshotValue.user_id) <= 0
    || typeof snapshotValue.session_token !== 'string'
    || snapshotValue.session_token.length === 0
    || typeof snapshotValue.snapshot_hash !== 'string'
    || snapshotValue.snapshot_hash.length === 0
    || !isRecord(snapshotValue.scope)
    || (snapshotValue.scope.type !== 'deck' && snapshotValue.scope.type !== 'note_type')
    || typeof snapshotValue.scope.id !== 'string'
    || snapshotValue.scope.id.length === 0
    || !isFiniteTimestamp(snapshotValue.server_now_utc)
    || !isFiniteTimestamp(snapshotValue.expires_at)
    || expiresAtMs <= serverNowMs
    || !Number.isSafeInteger(snapshotValue.day_boundary_hour_local)
    || Number(snapshotValue.day_boundary_hour_local) < 0
    || Number(snapshotValue.day_boundary_hour_local) > 23
    || !isNonNegativeInteger(snapshotValue.learn_ahead_seconds)
    || !Array.isArray(snapshotValue.cards)
    || !isRecord(policies)
    || !isRecord(templates)
    || !isRecord(contents)
    || !isRecord(compositions)
  ) {
    return quarantine('MALFORMED_SESSION', 'Stored study snapshot is malformed.')
  }

  const snapshotCardIds = new Set<string>()
  if (!snapshotValue.cards.every((card) => {
    if (!isRecord(card) || !isRecord(card.state)) return false
    const cardId = typeof card.card_id === 'string' ? card.card_id : ''
    const policyKey = typeof card.policy_key === 'string' ? card.policy_key : ''
    const templateKey = typeof card.template_key === 'string' ? card.template_key : ''
    const contentKey = typeof card.content_key === 'string' ? card.content_key : ''
    if (!cardId || snapshotCardIds.has(cardId)) return false
    snapshotCardIds.add(cardId)
    return (
      VALID_CARD_TYPES.has(String(card.state.type ?? ''))
      && isRecord((policies as Record<string, unknown>)[policyKey])
      && isRecord((templates as Record<string, unknown>)[templateKey])
      && isRecord((contents as Record<string, unknown>)[contentKey])
    )
  })) {
    return quarantine('MALFORMED_SESSION', 'Stored study cards are malformed.')
  }

  const compositionFields = [
    snapshotValue.composition_contract_version,
    snapshotValue.selected_composition_id,
    snapshotValue.selected_composition,
    snapshotValue.composition_binding,
  ]
  const hasCompositionContract = compositionFields.some(
    (item) => item !== undefined,
  )
  if (hasCompositionContract) {
    const selectedId = snapshotValue.selected_composition_id
    const selected = snapshotValue.selected_composition
    const binding = snapshotValue.composition_binding
    const selectedFromDictionary = typeof selectedId === 'string'
      ? (compositions as Record<string, unknown>)[selectedId]
      : undefined
    if (
      snapshotValue.composition_contract_version !== 'applied-composition.compat.v1'
      || typeof selectedId !== 'string'
      || selectedId.length === 0
      || !isRecord(selected)
      || selected.composition_id !== selectedId
      || !isRecord(selectedFromDictionary)
      || selectedFromDictionary.composition_id !== selectedId
      || !isRecord(binding)
      || binding.schema_version !== 'study-composition-binding.v1'
      || binding.composition_id !== selectedId
      || typeof binding.binding_fingerprint !== 'string'
      || !binding.binding_fingerprint.startsWith('sha256-')
      || !Array.isArray(binding.field_bindings)
      || snapshotValue.cards.some((card) => (
        !isRecord(card) || card.composition_id !== selectedId
      ))
    ) {
      return quarantine(
        'COMPOSITION_CONTRACT_MISMATCH',
        'Stored study composition does not match its frozen session material.',
      )
    }
  }

  if (
    typeof value.scope_key !== 'string'
    || !Array.isArray(value.events)
    || !Array.isArray(value.touched_card_ids)
    || !isNonNegativeInteger(value.opened_client_at_ms)
    || (value.status !== 'active' && value.status !== 'pending_commit')
  ) {
    return quarantine('MALFORMED_SESSION', 'Stored study state is malformed.')
  }

  const expectedFromSnapshot = `user:${snapshotValue.user_id}:${snapshotValue.scope.type}:${snapshotValue.scope.id}`
  if (
    value.scope_key !== expectedFromSnapshot
    || (expectedScopeKey !== undefined && value.scope_key !== expectedScopeKey)
  ) {
    return quarantine(
      'SCOPE_MISMATCH',
      'Stored study session does not match the requested scope.',
    )
  }

  const snapshot = snapshotValue as StudySessionSnapshot
  try {
    validateSnapshotAlgorithmContract(snapshot)
  } catch (error) {
    if (error instanceof ClientAlgorithmUnavailableError) {
      return quarantine('ALGORITHM_UNAVAILABLE', error.message)
    }
    if (error instanceof ClientAlgorithmContractError) {
      return quarantine('ALGORITHM_CONTRACT_MISMATCH', error.message)
    }
    throw error
  }

  const hasBatchSequence = value.batch_sequence !== undefined
  const hasInFlightBatches = value.in_flight_batches !== undefined
  if (hasBatchSequence !== hasInFlightBatches) {
    return quarantine(
      'BATCH_CONTRACT_MISMATCH',
      'Stored study session has partial batch metadata.',
    )
  }
  if (
    hasBatchSequence
    && (
      !isNonNegativeInteger(value.batch_sequence)
      || !Array.isArray(value.in_flight_batches)
    )
  ) {
    return quarantine(
      'BATCH_CONTRACT_MISMATCH',
      'Stored study session has invalid batch metadata.',
    )
  }

  let migrated = !hasBatchSequence
  const inFlightBatches: StudyBatchPayload[] = []
  const retainedEvents: StudySessionEvent[] = []
  let previousBatchSequence = 0
  const rawBatches = hasInFlightBatches
    ? value.in_flight_batches as unknown[]
    : []
  for (let index = 0; index < rawBatches.length; index += 1) {
    const normalized = normalizeBatch(rawBatches[index], index, snapshot)
    if ('status' in normalized) return normalized
    if (
      normalized.batch.batch_sequence <= previousBatchSequence
      || normalized.batch.batch_sequence > Number(value.batch_sequence)
    ) {
      return quarantine(
        'BATCH_CONTRACT_MISMATCH',
        'Stored in-flight batch sequence is reordered or outside its checkpoint.',
      )
    }
    previousBatchSequence = normalized.batch.batch_sequence
    inFlightBatches.push(normalized.batch)
    retainedEvents.push(...normalized.events)
    migrated ||= normalized.migrated
  }

  const events: StudySessionEvent[] = []
  for (let index = 0; index < value.events.length; index += 1) {
    const normalized = normalizeEvent(value.events[index], index, snapshot)
    if ('status' in normalized) return normalized
    events.push(normalized.event)
    retainedEvents.push(normalized.event)
    migrated ||= normalized.migrated
  }

  const eventIds = new Set<string>()
  let previousSequence: number | null = null
  let previousOffset: number | null = null
  const leaseDurationMs = expiresAtMs - serverNowMs
  for (const event of retainedEvents) {
    if (eventIds.has(event.event_id)) {
      return quarantine(
        'EVENT_ID_INVALID',
        'Stored study event ids must be unique within a session.',
      )
    }
    if (previousSequence !== null && event.sequence !== previousSequence + 1) {
      return quarantine(
        'EVENT_SEQUENCE_INVALID',
        'Stored study event sequence is reordered or contains a gap.',
      )
    }
    if (
      event.scheduler_offset_ms > leaseDurationMs
      || (previousOffset !== null && event.scheduler_offset_ms < previousOffset)
    ) {
      return quarantine(
        'EVENT_TIME_INVALID',
        'Stored study event offsets must be monotonic and within the session lease.',
      )
    }
    eventIds.add(event.event_id)
    previousSequence = event.sequence
    previousOffset = event.scheduler_offset_ms
  }

  const suppliedEventSequence = value.event_sequence
  let eventSequence: number
  if (suppliedEventSequence === undefined) {
    if (
      hasBatchSequence
      && Number(value.batch_sequence) > 0
      && retainedEvents.length === 0
    ) {
      return quarantine(
        'BATCH_CONTRACT_MISMATCH',
        'Stored study session is missing the event checkpoint for acknowledged batches.',
      )
    }
    eventSequence = retainedEvents.at(-1)?.sequence ?? 0
    migrated = true
  } else if (!isNonNegativeInteger(suppliedEventSequence)) {
    return quarantine(
      'EVENT_SEQUENCE_INVALID',
      'Stored study session has an invalid event sequence checkpoint.',
    )
  } else {
    eventSequence = suppliedEventSequence
  }
  if (
    retainedEvents.length > 0
    && retainedEvents[retainedEvents.length - 1].sequence !== eventSequence
  ) {
    return quarantine(
      'EVENT_SEQUENCE_INVALID',
      'Stored study event sequence does not match its checkpoint.',
    )
  }
  if (
    Number(value.batch_sequence ?? 0) === 0
    && retainedEvents.length > 0
    && retainedEvents[0].sequence !== 1
  ) {
    return quarantine(
      'EVENT_SEQUENCE_INVALID',
      'Stored study event sequence must start at 1 without a batch checkpoint.',
    )
  }
  if (!hasBatchSequence && events.length > 0 && events[0].sequence !== 1) {
    return quarantine(
      'EVENT_SEQUENCE_INVALID',
      'Legacy stored study event sequence must start at 1.',
    )
  }

  const touchedCardIds = [...new Set(events.map((event) => event.card_id))]
  const suppliedTouched = value.touched_card_ids
  if (
    suppliedTouched.length !== touchedCardIds.length
    || suppliedTouched.some((item, index) => item !== touchedCardIds[index])
  ) migrated = true

  const undoHistory = normalizeUndoHistory(value.undo_history, snapshotCardIds)
  if (undoHistory === null || undoHistory.length > events.length) {
    return quarantine(
      'MALFORMED_SESSION',
      'Stored study undo history is malformed.',
    )
  }
  if (!Array.isArray(value.undo_history)) migrated = true

  const suppliedActiveCardId = value.active_card_id
  const activeCardId = typeof suppliedActiveCardId === 'string'
    && snapshotCardIds.has(suppliedActiveCardId)
    ? suppliedActiveCardId
    : null
  if (suppliedActiveCardId === undefined) migrated = true
  else if (suppliedActiveCardId !== activeCardId) {
    return quarantine('MALFORMED_SESSION', 'Stored active card is outside the session.')
  }

  let commitReason: StudyCommitReason | null = null
  if (value.commit_reason === undefined) migrated = true
  else if (value.commit_reason !== null) {
    if (
      typeof value.commit_reason !== 'string'
      || !VALID_COMMIT_REASONS.has(value.commit_reason as StudyCommitReason)
    ) {
      return quarantine('MALFORMED_SESSION', 'Stored commit reason is invalid.')
    }
    commitReason = value.commit_reason as StudyCommitReason
  }

  let commitId: string | null = null
  if (value.commit_id === undefined) migrated = true
  else if (value.commit_id !== null) {
    if (!isUuid(value.commit_id)) {
      return quarantine('MALFORMED_SESSION', 'Stored commit id is invalid.')
    }
    commitId = value.commit_id
  }
  if (value.resume_after_commit === undefined) migrated = true
  else if (typeof value.resume_after_commit !== 'boolean') {
    return quarantine('MALFORMED_SESSION', 'Stored resume marker is invalid.')
  }
  if (value.status === 'pending_commit' && (!commitId || !commitReason)) {
    return quarantine(
      'MALFORMED_SESSION',
      'Stored pending commit is missing its idempotency metadata.',
    )
  }

  const updatedAtMs = value.updated_at_ms
  if (updatedAtMs === undefined) migrated = true
  else if (!isNonNegativeInteger(updatedAtMs)) {
    return quarantine('MALFORMED_SESSION', 'Stored update timestamp is invalid.')
  }
  const sessionStartedAtMs = value.session_started_at_ms
  if (sessionStartedAtMs !== undefined && !isNonNegativeInteger(sessionStartedAtMs)) {
    return quarantine('MALFORMED_SESSION', 'Stored session start timestamp is invalid.')
  }
  const accumulatedStats = normalizeAccumulatedStats(value.accumulated_stats)
  if (accumulatedStats === null) {
    return quarantine('MALFORMED_SESSION', 'Stored accumulated statistics are invalid.')
  }

  return {
    status: 'restored',
    migrated,
    session: {
      scope_key: value.scope_key,
      snapshot,
      events,
      touched_card_ids: touchedCardIds,
      undo_history: undoHistory,
      active_card_id: activeCardId,
      opened_client_at_ms: value.opened_client_at_ms,
      session_started_at_ms: sessionStartedAtMs,
      accumulated_stats: accumulatedStats,
      status: value.status,
      commit_id: commitId,
      commit_reason: commitReason,
      resume_after_commit: value.resume_after_commit ?? false,
      batch_sequence: hasBatchSequence ? value.batch_sequence as number : 0,
      event_sequence: eventSequence,
      in_flight_batches: inFlightBatches,
      updated_at_ms: updatedAtMs ?? Date.now(),
    },
  }
}
