import {
  ClientAlgorithmContractError,
  ClientAlgorithmUnavailableError,
  validateSnapshotAlgorithmContract,
} from '../scheduler/algorithmRegistry'
import type { SchedulerCardState } from '../scheduler/types'
import type {
  Rating,
  StudySessionEvent,
  StudySessionSnapshot,
} from '../types'
import {
  REVIEW_RATINGS,
  resolveReviewAction,
} from '../interactions/reviewInteraction'
import type {
  PersistedStudySession,
  StudyCommitReason,
  StudySessionUndoItem,
} from './sessionStore'

export type StudySessionQuarantineReason =
  | 'ALGORITHM_UNAVAILABLE'
  | 'ALGORITHM_CONTRACT_MISMATCH'
  | 'EVENT_CONTRACT_MISMATCH'
  | 'MALFORMED_SESSION'

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

const VALID_CARD_TYPES = new Set([
  'new',
  'learning',
  'review',
  'relearning',
])
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

function normalizeEvent(
  value: unknown,
  index: number,
  snapshot: StudySessionSnapshot,
): { event: StudySessionEvent; migrated: boolean } | StudySessionRestoreResult {
  if (!isRecord(value)) {
    return quarantine(
      'EVENT_CONTRACT_MISMATCH',
      `Stored study event ${index + 1} is not an object.`,
    )
  }
  const cardId = typeof value.card_id === 'string' ? value.card_id : ''
  const card = snapshot.cards.find((row) => row.card_id === cardId)
  const ratingText = String(value.rating || '')
  const sequence = Number(value.sequence)
  const schedulerOffsetMs = Number(value.scheduler_offset_ms)
  const durationMs = Number(value.duration_ms)
  if (
    typeof value.event_id !== 'string'
    || !value.event_id
    || !card
    || !VALID_RATINGS.has(ratingText)
    || !Number.isInteger(sequence)
    || sequence <= 0
    || !Number.isFinite(schedulerOffsetMs)
    || !Number.isInteger(schedulerOffsetMs)
    || schedulerOffsetMs < 0
    || !Number.isFinite(durationMs)
    || !Number.isInteger(durationMs)
    || durationMs < 0
    || durationMs > 3_600_000
    || typeof value.policy_key !== 'string'
    || value.policy_key !== card.policy_key
  ) {
    return quarantine(
      'EVENT_CONTRACT_MISMATCH',
      `Stored study event ${index + 1} has invalid replay fields.`,
    )
  }

  const rating = ratingText as Rating
  const action = resolveReviewAction(rating)
  const suppliedContract = [
    value.action_key,
    value.trigger_key,
    value.trigger_contract_version,
  ]
  const isLegacyEvent = suppliedContract.every((item) => item === undefined)
  if (
    !isLegacyEvent
    && (
      value.action_key !== action.actionKey
      || value.trigger_key !== action.triggerKey
      || value.trigger_contract_version !== action.triggerContractVersion
    )
  ) {
    return quarantine(
      'EVENT_CONTRACT_MISMATCH',
      `Stored study event ${index + 1} has inconsistent Action metadata.`,
    )
  }

  return {
    migrated: isLegacyEvent,
    event: {
      event_id: value.event_id,
      sequence,
      card_id: cardId,
      rating,
      action_key: action.actionKey,
      trigger_key: action.triggerKey,
      trigger_contract_version: action.triggerContractVersion,
      policy_key: value.policy_key,
      scheduler_offset_ms: schedulerOffsetMs,
      duration_ms: durationMs,
    },
  }
}

function normalizeUndoHistory(
  value: unknown,
  cardIds: Set<string>,
): StudySessionUndoItem[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (
      !isRecord(item)
      || typeof item.card_id !== 'string'
      || !cardIds.has(item.card_id)
      || !isRecord(item.previous_state)
      || !VALID_CARD_TYPES.has(String(item.previous_state.type || ''))
    ) return []
    return [{
      card_id: item.card_id,
      previous_state: item.previous_state as SchedulerCardState,
    }]
  })
}

export function normalizePersistedStudySession(
  value: unknown,
): StudySessionRestoreResult {
  if (!isRecord(value) || !isRecord(value.snapshot)) {
    return quarantine('MALFORMED_SESSION', 'Stored study session is malformed.')
  }
  const snapshotValue = value.snapshot
  const policies = snapshotValue.policies
  const templates = snapshotValue.templates
  const contents = snapshotValue.contents
  if (
    snapshotValue.schema_version !== 'study-session.v2'
    || !isFiniteTimestamp(snapshotValue.server_now_utc)
    || !isFiniteTimestamp(snapshotValue.expires_at)
    || typeof snapshotValue.learn_ahead_seconds !== 'number'
    || !Number.isFinite(snapshotValue.learn_ahead_seconds)
    || snapshotValue.learn_ahead_seconds < 0
    || !Array.isArray(snapshotValue.cards)
    || !isRecord(policies)
    || !isRecord(templates)
    || !isRecord(contents)
  ) {
    return quarantine('MALFORMED_SESSION', 'Stored study snapshot is malformed.')
  }

  if (!snapshotValue.cards.every((card) => {
    if (!isRecord(card) || !isRecord(card.state)) return false
    const policyKey = String(card.policy_key || '')
    const templateKey = String(card.template_key || '')
    const contentKey = String(card.content_key || '')
    return (
      typeof card.card_id === 'string'
      && VALID_CARD_TYPES.has(String(card.state.type || ''))
      && isRecord(policies[policyKey])
      && isRecord(templates[templateKey])
      && isRecord(contents[contentKey])
    )
  })) {
    return quarantine('MALFORMED_SESSION', 'Stored study cards are malformed.')
  }

  if (
    typeof value.scope_key !== 'string'
    || !Array.isArray(value.events)
    || !Array.isArray(value.touched_card_ids)
    || typeof value.opened_client_at_ms !== 'number'
    || !Number.isFinite(value.opened_client_at_ms)
    || (value.status !== 'active' && value.status !== 'pending_commit')
  ) {
    return quarantine('MALFORMED_SESSION', 'Stored study state is malformed.')
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

  let migrated = false
  const events: StudySessionEvent[] = []
  let previousSequence = 0
  for (let index = 0; index < value.events.length; index += 1) {
    const normalized = normalizeEvent(value.events[index], index, snapshot)
    if ('status' in normalized) return normalized
    if (normalized.event.sequence <= previousSequence) {
      return quarantine(
        'EVENT_CONTRACT_MISMATCH',
        'Stored study event sequence is not strictly increasing.',
      )
    }
    previousSequence = normalized.event.sequence
    events.push(normalized.event)
    migrated ||= normalized.migrated
  }

  const cardIds = new Set(snapshot.cards.map((card) => card.card_id))
  const touchedCardIds = [...new Set(events.map((event) => event.card_id))]
  const suppliedTouched = value.touched_card_ids.filter(
    (item): item is string => typeof item === 'string' && cardIds.has(item),
  )
  if (
    suppliedTouched.length !== touchedCardIds.length
    || suppliedTouched.some((item, index) => item !== touchedCardIds[index])
  ) migrated = true

  const undoHistory = normalizeUndoHistory(value.undo_history, cardIds)
  if (!Array.isArray(value.undo_history)) migrated = true

  const suppliedActiveCardId = value.active_card_id
  const activeCardId = typeof suppliedActiveCardId === 'string'
    && cardIds.has(suppliedActiveCardId)
    ? suppliedActiveCardId
    : null
  if (suppliedActiveCardId === undefined || suppliedActiveCardId !== activeCardId) {
    migrated = true
  }

  const commitReason = typeof value.commit_reason === 'string'
    && VALID_COMMIT_REASONS.has(value.commit_reason as StudyCommitReason)
    ? value.commit_reason as StudyCommitReason
    : null
  if (value.commit_reason === undefined || value.commit_reason !== commitReason) {
    migrated = true
  }

  const commitId = typeof value.commit_id === 'string' ? value.commit_id : null
  if (value.commit_id !== commitId) migrated = true
  if (value.resume_after_commit === undefined) migrated = true
  const updatedAtMs = typeof value.updated_at_ms === 'number'
    && Number.isFinite(value.updated_at_ms)
    ? value.updated_at_ms
    : Date.now()
  if (updatedAtMs !== value.updated_at_ms) migrated = true
  if (value.status === 'pending_commit' && (!commitId || !commitReason)) {
    return quarantine(
      'MALFORMED_SESSION',
      'Stored pending commit is missing its idempotency metadata.',
    )
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
      status: value.status,
      commit_id: commitId,
      commit_reason: commitReason,
      resume_after_commit: Boolean(value.resume_after_commit),
      updated_at_ms: updatedAtMs,
    },
  }
}
