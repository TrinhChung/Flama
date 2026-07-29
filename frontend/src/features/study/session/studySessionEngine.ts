import type { Rating } from '../types'
import type {
  StudyContentArtifact,
  StudySessionCard,
  StudySessionCommitReceipt,
  StudySessionEvent,
  StudySessionSnapshot,
  StudyTemplateArtifact,
} from '../types'
import { computeDecision } from '../scheduler/legacyEngine'
import {
  nextPendingLearningAt,
  queueCounts,
  selectNextCard,
} from '../scheduler/queue'
import type { SchedulerDecision } from '../scheduler/types'
import type { PersistedStudySession } from './sessionStore'

export type StudySessionView = {
  card: StudySessionCard | null
  template: StudyTemplateArtifact | null
  content: StudyContentArtifact | null
  counts: { new: number; learning: number; due: number }
  next_due_at_ms: number | null
  session_state: 'active' | 'waiting' | 'complete'
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
): PersistedStudySession {
  return {
    scope_key: `user:${snapshot.user_id}:${snapshot.scope.type}:${snapshot.scope.id}`,
    snapshot: cloneSnapshot(snapshot),
    events: [],
    touched_card_ids: [],
    opened_client_at_ms: Date.now(),
    status: 'active',
    commit_id: null,
    resume_after_commit: false,
    updated_at_ms: Date.now(),
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
): StudySessionView {
  const snapshot = session.snapshot
  const cards = queueCards(session)
  const selected = selectNextCard(
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
  const nextDueAt = nextPendingLearningAt(cards, nowMs)
  return {
    card,
    template: card
      ? snapshot.templates[card.template_key] ?? null
      : null,
    content: card
      ? snapshot.contents[card.content_key] ?? null
      : null,
    counts,
    next_due_at_ms: nextDueAt,
    session_state: card
      ? 'active'
      : nextDueAt !== null
        ? 'waiting'
        : 'complete',
  }
}

export function decisionForCard(
  session: PersistedStudySession,
  cardId: string,
  schedulerAtMs: number,
) {
  const card = session.snapshot.cards.find((row) => row.card_id === cardId)
  if (!card) throw new Error('Card is not part of the active session.')
  const policy = session.snapshot.policies[card.policy_key]
  if (!policy) throw new Error('Scheduler policy is missing.')
  return computeDecision(
    card.state,
    policy.config,
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
  const event: StudySessionEvent = {
    event_id: crypto.randomUUID(),
    sequence: session.events.length + 1,
    card_id: card.card_id,
    rating,
    policy_key: card.policy_key,
    scheduler_offset_ms: schedulerOffset,
    duration_ms: Math.max(0, Math.min(3_600_000, Math.round(durationMs))),
  }
  const touched = session.touched_card_ids.includes(cardId)
    ? session.touched_card_ids
    : [...session.touched_card_ids, cardId]
  return {
    ...session,
    snapshot: {
      ...session.snapshot,
      cards: session.snapshot.cards.map((row) => (
        row.card_id === cardId
          ? { ...row, state: decision.outcomes[rating] }
          : row
      )),
    },
    events: [...session.events, event],
    touched_card_ids: touched,
    updated_at_ms: Date.now(),
  } satisfies PersistedStudySession
}

export function automaticCommitMode(
  session: PersistedStudySession,
  view: StudySessionView,
  eventLimit = DEFAULT_STUDY_BATCH_EVENT_LIMIT,
): AutomaticCommitMode | null {
  if (session.status !== 'active' || session.events.length === 0) return null
  if (view.session_state === 'complete') return 'finish'
  if (session.events.length >= Math.max(1, eventLimit)) return 'rollover'
  return null
}

export function prepareCommit(
  session: PersistedStudySession,
  options: { resumeAfterCommit?: boolean } = {},
) {
  const commitId = session.commit_id ?? crypto.randomUUID()
  const resumeAfterCommit = options.resumeAfterCommit
    ?? session.resume_after_commit
  const prepared = {
    ...session,
    status: 'pending_commit' as const,
    commit_id: commitId,
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
) {
  const updates = new Map(
    receipt.updated_cards.map((row) => [row.card_id, row]),
  )
  return {
    ...session,
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
