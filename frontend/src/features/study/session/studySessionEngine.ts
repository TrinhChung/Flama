import type { Rating } from '../types'
import type {
  StudyBatchPayload,
  StudyContentArtifact,
  StudySessionCard,
  StudySessionCommitReceipt,
  StudySessionEvent,
  StudySessionSnapshot,
  StudyTemplateArtifact,
} from '../types'
import {
  resolveCardAlgorithm,
  validateSnapshotAlgorithmContract,
} from '../scheduler/algorithmRegistry'
import {
  queueCounts,
  selectNextCard,
  summarizePendingIntradayLearning,
} from '../scheduler/queue'
import type { SchedulerDecision } from '../scheduler/types'
import { resolveReviewAction } from '../interactions/reviewInteraction'
import type {
  PersistedStudySession,
  StudyCommitReason,
  StudySessionAccumulatedStats,
} from './sessionStore'

export type StudySessionView = {
  card: StudySessionCard | null
  template: StudyTemplateArtifact | null
  content: StudyContentArtifact | null
  counts: { new: number; learning: number; due: number }
  now_ms: number
  pending_learning_count: number
  next_due_at_ms: number | null
  next_eligible_at_ms: number | null
  session_state: 'active' | 'waiting' | 'complete_today'
}

export type AutomaticCommitMode = 'finish' | 'rollover'

export const DEFAULT_STUDY_BATCH_EVENT_LIMIT = 50

function cloneSnapshot(snapshot: StudySessionSnapshot): StudySessionSnapshot {
  return {
    ...snapshot,
    cards: snapshot.cards.map((card) => ({
      ...card,
      state: {
        ...card.state,
        memory_state: card.state.memory_state
          ? { ...card.state.memory_state }
          : null,
      },
    })),
  }
}

export function createPersistedSession(
  snapshot: StudySessionSnapshot,
  options?: {
    accumulated_stats?: StudySessionAccumulatedStats
    session_started_at_ms?: number
  },
): PersistedStudySession {
  validateSnapshotAlgorithmContract(snapshot)
  const cloned = cloneSnapshot(snapshot)
  const cards = cloned.cards.map((card) => ({
    card_id: card.card_id,
    created_at: card.created_at,
    state: card.state,
  }))
  const nowMs = Date.parse(snapshot.server_now_utc) || Date.now()
  const initialSelected = selectNextCard(
    cards,
    nowMs,
    snapshot.timezone,
    snapshot.day_boundary_hour_local,
    snapshot.learn_ahead_seconds,
  )
  const clientNow = Date.now()
  return {
    scope_key: `user:${snapshot.user_id}:${snapshot.scope.type}:${snapshot.scope.id}`,
    snapshot: cloned,
    events: [],
    touched_card_ids: [],
    undo_history: [],
    active_card_id: initialSelected?.card_id ?? null,
    opened_client_at_ms: clientNow,
    session_started_at_ms: options?.session_started_at_ms ?? clientNow,
    accumulated_stats: options?.accumulated_stats,
    status: 'active',
    commit_id: null,
    commit_reason: null,
    resume_after_commit: false,
    updated_at_ms: clientNow,
  }
}

function queueCards(session: PersistedStudySession) {
  return session.snapshot.cards.map((card) => ({
    card_id: card.card_id,
    created_at: card.created_at,
    state: card.state,
  }))
}

export function buildSessionView(
  session: PersistedStudySession,
  nowMs: number,
  compositionFilter?: string | null,
): StudySessionView {
  const snapshot = session.snapshot
  const allCards = queueCards(session)
  const cards = compositionFilter
    ? allCards.filter((c) => {
        const full = snapshot.cards.find((row) => row.card_id === c.card_id)
        return full?.composition_id === compositionFilter
      })
    : allCards
  const activeCard = session.active_card_id
    ? snapshot.cards.find(
        (row) => row.card_id === session.active_card_id && !row.state.suspended
          && (!compositionFilter || row.composition_id === compositionFilter),
      ) ?? null
    : null

  const selected = activeCard
    ? { card_id: activeCard.card_id }
    : selectNextCard(
        cards,
        nowMs,
        snapshot.timezone,
        snapshot.day_boundary_hour_local,
        snapshot.learn_ahead_seconds,
      )

  const counts = queueCounts(
    cards,
    nowMs,
    snapshot.timezone,
    snapshot.day_boundary_hour_local,
  )
  const card = selected
    ? snapshot.cards.find((row) => row.card_id === selected.card_id) ?? null
    : null
  const pendingLearning = summarizePendingIntradayLearning(
    cards,
    nowMs,
    snapshot.learn_ahead_seconds,
  )
  return {
    card,
    template: card
      ? snapshot.templates[card.template_key] ?? null
      : null,
    content: card
      ? snapshot.contents[card.content_key] ?? null
      : null,
    counts,
    now_ms: nowMs,
    pending_learning_count: pendingLearning.count,
    next_due_at_ms: pendingLearning.next_due_at_ms,
    next_eligible_at_ms: pendingLearning.next_eligible_at_ms,
    session_state: card
      ? 'active'
      : pendingLearning.count > 0
        ? 'waiting'
        : 'complete_today',
  }
}

export function decisionForCard(
  session: PersistedStudySession,
  cardId: string,
  schedulerAtMs: number,
) {
  const card = session.snapshot.cards.find((row) => row.card_id === cardId)
  if (!card) throw new Error('Card is not part of the active session.')
  const { algorithm, policy } = resolveCardAlgorithm(session.snapshot, card)
  return algorithm.computeDecision(
    card,
    policy,
    schedulerAtMs,
    session.snapshot.timezone,
  )
}

export function applyLocalAnswer(
  session: PersistedStudySession,
  cardId: string,
  rating: Rating,
  decision: SchedulerDecision,
  durationMs: number,
) {
  if (session.status !== 'active') {
    throw new Error('Study session is waiting to be committed.')
  }
  const card = session.snapshot.cards.find((row) => row.card_id === cardId)
  if (!card) throw new Error('Card is not part of the active session.')
  const policy = session.snapshot.policies[card.policy_key]
  if (!policy) throw new Error('Scheduler policy is missing.')
  const serverAnchor = Date.parse(session.snapshot.server_now_utc)
  const schedulerOffset = Math.max(
    0,
    Math.round(decision.scheduler_at_ms - serverAnchor),
  )
  const action = resolveReviewAction(rating)
  const event: StudySessionEvent = {
    event_id: crypto.randomUUID(),
    sequence: session.events.length + 1,
    card_id: card.card_id,
    rating,
    action_key: action.actionKey,
    trigger_key: action.triggerKey,
    trigger_contract_version: action.triggerContractVersion,
    policy_key: card.policy_key,
    scheduler_offset_ms: schedulerOffset,
    duration_ms: Math.max(0, Math.min(3_600_000, Math.round(durationMs))),
  }
  const touched = session.touched_card_ids.includes(cardId)
    ? session.touched_card_ids
    : [...session.touched_card_ids, cardId]

  const previousState = {
    ...card.state,
    memory_state: card.state.memory_state
      ? { ...card.state.memory_state }
      : null,
  }
  const undoHistory = [
    ...(session.undo_history ?? []),
    { card_id: cardId, previous_state: previousState },
  ]

  const nextSnapshotCards = session.snapshot.cards.map((row) => (
    row.card_id === cardId
      ? { ...row, state: decision.outcomes[rating] }
      : row
  ))
  const nextQueue = nextSnapshotCards.map((c) => ({
    card_id: c.card_id,
    created_at: c.created_at,
    state: c.state,
  }))
  const nextSelected = selectNextCard(
    nextQueue,
    decision.scheduler_at_ms,
    session.snapshot.timezone,
    session.snapshot.day_boundary_hour_local,
    session.snapshot.learn_ahead_seconds,
  )

  return {
    ...session,
    snapshot: {
      ...session.snapshot,
      cards: nextSnapshotCards,
    },
    events: [...session.events, event],
    touched_card_ids: touched,
    undo_history: undoHistory,
    active_card_id: nextSelected?.card_id ?? null,
    updated_at_ms: Date.now(),
  } satisfies PersistedStudySession
}

export type UndoResult = {
  session: PersistedStudySession
  undoneCardId: string
}

export function undoLocalAnswer(
  session: PersistedStudySession,
): UndoResult | null {
  if (session.status !== 'active') return null
  if (session.events.length === 0) return null
  const undoHistory = session.undo_history ?? []
  if (undoHistory.length === 0) return null

  const lastUndo = undoHistory[undoHistory.length - 1]
  const remainingUndoHistory = undoHistory.slice(0, -1)
  const remainingEvents = session.events.slice(0, -1)
  const cardId = lastUndo.card_id

  const restoredCards = session.snapshot.cards.map((row) => (
    row.card_id === cardId
      ? { ...row, state: lastUndo.previous_state }
      : row
  ))

  const touchedSet = new Set(remainingEvents.map((e) => e.card_id))
  const touchedCardIds = session.touched_card_ids.filter((id) => touchedSet.has(id))

  const nextSession: PersistedStudySession = {
    ...session,
    snapshot: {
      ...session.snapshot,
      cards: restoredCards,
    },
    events: remainingEvents,
    touched_card_ids: touchedCardIds,
    undo_history: remainingUndoHistory,
    active_card_id: cardId,
    updated_at_ms: Date.now(),
  }

  return {
    session: nextSession,
    undoneCardId: cardId,
  }
}

export function automaticCommitMode(
  session: PersistedStudySession,
  view: StudySessionView,
  eventLimit = DEFAULT_STUDY_BATCH_EVENT_LIMIT,
): AutomaticCommitMode | null {
  if (session.status !== 'active' || session.events.length === 0) return null
  if (view.session_state === 'complete_today') return 'finish'
  if (session.events.length >= Math.max(1, eventLimit)) return 'rollover'
  return null
}

export function isBackgroundRolloverCommit(
  session: PersistedStudySession | null,
) {
  return session?.status === 'pending_commit'
    && session.resume_after_commit
}

export type ExtractedBatchResult = {
  session: PersistedStudySession
  batch: StudyBatchPayload
}

export function extractPendingBatch(
  session: PersistedStudySession,
  limit = DEFAULT_STUDY_BATCH_EVENT_LIMIT,
  options: {
    reason?: StudyCommitReason
    isFinal?: boolean
  } = {},
): ExtractedBatchResult | null {
  if (session.events.length === 0) return null

  const batchCount = Math.min(session.events.length, Math.max(1, limit))
  const batchEvents = session.events.slice(0, batchCount)
  const remainingEvents = session.events.slice(batchCount)

  const batchId = crypto.randomUUID()
  const nextSeq = (session.batch_sequence ?? 0) + 1
  const isFinal = Boolean(options.isFinal)
  const commitReason = options.reason ?? (isFinal ? 'auto_finish' : 'rollover')

  const batchTouchedCardIds = Array.from(new Set(batchEvents.map((e) => e.card_id)))
  const finalStates = batchTouchedCardIds.map((cardId) => {
    const card = session.snapshot.cards.find((row) => row.card_id === cardId)
    if (!card) throw new Error(`Missing touched card ${cardId}.`)
    return {
      card_id: card.card_id,
      base_revision: card.base_revision,
      state: card.state,
    }
  })

  const batchPayload: StudyBatchPayload = {
    schema_version: 'study-batch.v1',
    batch_id: batchId,
    batch_sequence: nextSeq,
    session_token: session.snapshot.session_token,
    snapshot_hash: session.snapshot.snapshot_hash,
    commit_reason: commitReason,
    is_final: isFinal,
    events: batchEvents,
    final_states: finalStates,
  }

  const remainingTouchedSet = new Set(remainingEvents.map((e) => e.card_id))
  const remainingTouchedCardIds = session.touched_card_ids.filter((id) =>
    remainingTouchedSet.has(id),
  )

  const nextInFlight = [
    ...(session.in_flight_batches ?? []),
    batchPayload,
  ]

  const nextSession: PersistedStudySession = {
    ...session,
    events: remainingEvents,
    touched_card_ids: remainingTouchedCardIds,
    batch_sequence: nextSeq,
    in_flight_batches: nextInFlight,
    updated_at_ms: Date.now(),
  }

  return {
    session: nextSession,
    batch: batchPayload,
  }
}

export function acknowledgeBatchReceipt(
  session: PersistedStudySession,
  batchId: string,
): PersistedStudySession {
  const remainingInFlight = (session.in_flight_batches ?? []).filter(
    (b) => b.batch_id !== batchId,
  )
  return {
    ...session,
    in_flight_batches: remainingInFlight,
    updated_at_ms: Date.now(),
  }
}

export function prepareCommit(
  session: PersistedStudySession,
  options: {
    reason?: StudyCommitReason
    resumeAfterCommit?: boolean
  } = {},
) {
  const commitId = session.commit_id ?? crypto.randomUUID()
  const resumeAfterCommit = options.resumeAfterCommit
    ?? session.resume_after_commit
  const commitReason = options.reason
    ?? session.commit_reason
    ?? (resumeAfterCommit ? 'rollover' : 'manual_exit')
  const prepared = {
    ...session,
    status: 'pending_commit' as const,
    commit_id: commitId,
    commit_reason: commitReason,
    resume_after_commit: Boolean(resumeAfterCommit),
    updated_at_ms: Date.now(),
  }
  const finalStates = prepared.touched_card_ids.map((cardId) => {
    const card = prepared.snapshot.cards.find((row) => row.card_id === cardId)
    if (!card) throw new Error(`Missing touched card ${cardId}.`)
    return {
      card_id: card.card_id,
      base_revision: card.base_revision,
      state: card.state,
    }
  })
  return {
    session: prepared,
    payload: {
      schema_version: 'study-commit.v1',
      commit_id: commitId,
      commit_reason: commitReason,
      session_token: prepared.snapshot.session_token,
      snapshot_hash: prepared.snapshot.snapshot_hash,
      events: prepared.events,
      final_states: finalStates,
    },
  }
}

export function applyCommitReceipt(
  session: PersistedStudySession,
  receipt: StudySessionCommitReceipt,
  options?: {
    accumulated_stats?: StudySessionAccumulatedStats
  },
) {
  const updates = new Map(
    receipt.updated_cards.map((row) => [row.card_id, row]),
  )
  return {
    ...session,
    accumulated_stats: options?.accumulated_stats ?? session.accumulated_stats,
    snapshot: {
      ...session.snapshot,
      cards: session.snapshot.cards.map((card) => {
        const update = updates.get(card.card_id)
        return update
          ? {
              ...card,
              base_revision: update.revision,
              state: update.state,
            }
          : card
      }),
    },
  }
}
