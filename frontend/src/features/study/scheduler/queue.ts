import { dayIndex, epochMsFromIso } from './time'
import type { SchedulerCardState } from './types'

export type QueueCard = {
  card_id: string
  created_at: string
  state: SchedulerCardState
}

export type QueueCounts = {
  new: number
  learning: number
  due: number
}

function isLearningDue(
  state: SchedulerCardState,
  nowMs: number,
  today: number,
) {
  if (state.due_day !== null) return state.due_day <= today
  const dueMs = epochMsFromIso(state.due_at)
  return dueMs === null || dueMs <= nowMs
}

function isReviewDue(
  state: SchedulerCardState,
  today: number,
  nowMs: number,
) {
  if (state.due_day !== null) return state.due_day <= today
  const dueMs = epochMsFromIso(state.due_at)
  return dueMs === null || dueMs <= nowMs
}

function createdOrder(left: QueueCard, right: QueueCard) {
  return left.created_at.localeCompare(right.created_at)
    || left.card_id.localeCompare(right.card_id)
}

function learningOrder(left: QueueCard, right: QueueCard) {
  const leftDue = epochMsFromIso(left.state.due_at)
    ?? Number.MAX_SAFE_INTEGER
  const rightDue = epochMsFromIso(right.state.due_at)
    ?? Number.MAX_SAFE_INTEGER
  return leftDue - rightDue || createdOrder(left, right)
}

function reviewOrder(left: QueueCard, right: QueueCard) {
  const leftDay = left.state.due_day ?? Number.MAX_SAFE_INTEGER
  const rightDay = right.state.due_day ?? Number.MAX_SAFE_INTEGER
  return leftDay - rightDay || learningOrder(left, right)
}

export function selectNextCard(
  cards: QueueCard[],
  nowMs: number,
  timezone: string,
  boundaryHour: number,
  learnAheadSeconds: number,
) {
  const today = dayIndex(nowMs, boundaryHour, timezone)
  const dueRelearning: QueueCard[] = []
  const dueLearning: QueueCard[] = []
  const dueReview: QueueCard[] = []
  const dueNew: QueueCard[] = []
  const aheadRelearning: QueueCard[] = []
  const aheadLearning: QueueCard[] = []
  const aheadLimit = nowMs + learnAheadSeconds * 1000

  for (const card of cards) {
    const state = card.state
    if (state.suspended) continue
    if (state.type === 'new') {
      dueNew.push(card)
      continue
    }
    if (state.type === 'review') {
      if (isReviewDue(state, today, nowMs)) dueReview.push(card)
      continue
    }
    const dueNow = isLearningDue(state, nowMs, today)
    if (dueNow) {
      if (state.type === 'relearning') dueRelearning.push(card)
      else dueLearning.push(card)
      continue
    }
    const dueMs = epochMsFromIso(state.due_at)
    if (
      state.due_day === null
      && dueMs !== null
      && dueMs > nowMs
      && dueMs <= aheadLimit
    ) {
      if (state.type === 'relearning') aheadRelearning.push(card)
      else aheadLearning.push(card)
    }
  }

  dueRelearning.sort(learningOrder)
  dueLearning.sort(learningOrder)
  dueReview.sort(reviewOrder)
  dueNew.sort(createdOrder)
  aheadRelearning.sort(learningOrder)
  aheadLearning.sort(learningOrder)
  return dueRelearning[0]
    ?? dueLearning[0]
    ?? dueReview[0]
    ?? dueNew[0]
    ?? aheadRelearning[0]
    ?? aheadLearning[0]
    ?? null
}

export function queueCounts(
  cards: QueueCard[],
  nowMs: number,
  timezone: string,
  boundaryHour: number,
): QueueCounts {
  const today = dayIndex(nowMs, boundaryHour, timezone)
  const counts = { new: 0, learning: 0, due: 0 }
  for (const card of cards) {
    const state = card.state
    if (state.suspended) continue
    if (state.type === 'new') counts.new += 1
    else if (state.type === 'learning' || state.type === 'relearning') {
      counts.learning += 1
    } else if (isReviewDue(state, today, nowMs)) counts.due += 1
  }
  return counts
}

export function nextPendingLearningAt(cards: QueueCard[], nowMs: number) {
  let next: number | null = null
  for (const card of cards) {
    const state = card.state
    if (
      state.suspended
      || (state.type !== 'learning' && state.type !== 'relearning')
      || state.due_day !== null
    ) continue
    const due = epochMsFromIso(state.due_at)
    if (due !== null && due > nowMs && (next === null || due < next)) {
      next = due
    }
  }
  return next
}
