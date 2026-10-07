import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import { ApiError } from '@/shared/api/client'
import type {
  Rating,
  StudyCompositionGroup,
  StudyMediaArtifact,
  StudySessionCommitReceipt,
  StudySessionSnapshot,
  StudySessionStatus,
  StudySessionEvent,
} from '../types'
import { fetchStudyScopeCompositions } from '../api'
import type { SchedulerDecision } from '../scheduler/types'
import { NOTE_STORAGE_PROFILE } from '../scheduler/noteStoragePrecision'
import {
  applyCommitReceipt,
  applyLocalAnswer,
  automaticCommitMode,
  buildSessionView,
  createPersistedSession,
  decisionForCard,
  prepareCommit,
  undoLocalAnswer,
} from '../session/studySessionEngine'
import {
  acknowledgeStudySessionQuarantine,
  loadStudySessionWithDurability,
  quarantineStudySession,
  removeStudySessionIfMatches,
  saveStudySession,
  scopeKey,
  updateCardFieldValuesInSessions,
} from '../session/sessionStore'
import type {
  PersistedStudySession,
  StudyCommitReason,
  StudySessionAccumulatedStats,
  UpdatedTemplatePayload,
} from '../session/sessionStore'
import { applyCardContentPatch } from '../session/contentPatchAdapter'
import { hasUnacknowledgedStudyWork } from '../session/batchReceipt'
import { flushNoteBatchStream, sendNoteBatchOnExit, usesNoteBatchTransport } from '../session/noteBatchTransport'
import {
  useStudySessionLease,
  waitForNextOperationCheck,
} from './useStudySessionLease'

const openingRequests = new Map<string, Promise<StudySessionSnapshot>>()

type SessionMutationKind =
  | 'answer'
  | 'bootstrap'
  | 'commit'
  | 'composition-open'
  | 'content-update'
  | 'page-exit'
  | 'reload'
  | 'selection-persist'
  | 'template-update'
  | 'undo'

type SessionMutationOwner = Readonly<{
  token: symbol
  kind: SessionMutationKind
  controller: AbortController
  scopeKey: string | null
  sessionId: string | null
}>

function isCommitReceipt(value: unknown): value is StudySessionCommitReceipt {
  if (!value || typeof value !== 'object') return false
  const receipt = value as Partial<StudySessionCommitReceipt>
  return (
    receipt.schema_version === 'study-commit-receipt.v1'
    || receipt.schema_version === 'study-commit-receipt.v2'
  )
    && receipt.success === true
    && typeof receipt.session_id === 'string'
    && typeof receipt.commit_id === 'string'
    && Array.isArray(receipt.updated_cards)
}

function requireMatchingCommitReceipt(value: unknown, session: PersistedStudySession) {
  if (
    !isCommitReceipt(value)
    || value.session_id !== session.snapshot.session_id
    || value.commit_id !== session.commit_id
    || value.applied_event_count !== session.events.length
    || value.commit_reason !== session.commit_reason
    || (session.snapshot.schema_version === 'study-session.v4' && (
      value.schema_version !== 'study-commit-receipt.v2'
      || value.authority_mode !== 'NOTE'
      || value.enrollment_epoch !== session.snapshot.enrollment_epoch
    ))
  ) {
    throw new ApiError('Chưa nhận được xác nhận lưu hợp lệ. Dữ liệu vẫn được giữ để thử lại.', 502, 'INVALID_COMMIT_RECEIPT')
  }
  return value
}

/**
 * The server answered SESSION_ALREADY_COMMITTED for this lease: its stored
 * receipt is authoritative, whatever commit reason this retry carried. The
 * lease is closed, so local answers it does not cover can never be saved to
 * it; they are quarantined (kept, not deleted) so the scope can reopen.
 */
async function settleCommittedLease(value: unknown, session: PersistedStudySession) {
  if (
    !isCommitReceipt(value)
    || value.session_id !== session.snapshot.session_id
    || (session.snapshot.schema_version === 'study-session.v4' && (
      value.schema_version !== 'study-commit-receipt.v2'
      || value.authority_mode !== 'NOTE'
      || value.enrollment_epoch !== session.snapshot.enrollment_epoch
    ))
  ) {
    throw new ApiError('Chưa nhận được xác nhận lưu hợp lệ. Dữ liệu vẫn được giữ để thử lại.', 502, 'INVALID_COMMIT_RECEIPT')
  }
  if (value.commit_id === session.commit_id && value.applied_event_count === session.events.length) {
    return value
  }
  const message = `Phiên học này đã được lưu trước đó với ${value.applied_event_count} câu trả lời; `
    + `${session.events.length} câu trong trình duyệt khác bản đã lưu nên đã được cách ly (không xoá). `
    + 'Chọn Thử lại để mở phiên mới.'
  await quarantineStudySession(session.scope_key, session, { reason: 'COMMITTED_ELSEWHERE', message })
  throw new ApiError(message, 409, 'SESSION_ALREADY_COMMITTED')
}

function isTransientCommitFailure(caught: unknown) {
  return !(caught instanceof ApiError)
    || caught.code === 'BACKEND_UNAVAILABLE'
    || caught.code === 'INVALID_COMMIT_RECEIPT'
    || caught.status >= 500
}

/**
 * A restored synchronous lease the server no longer holds open can only be
 * settled by replaying the exact commit that closed it. Anything else can
 * never be saved to that lease, so it is quarantined (kept, not deleted)
 * instead of being retried on every visit. Resolves once the local copy is
 * settled and may be removed; transient failures are rethrown untouched.
 */
async function settleClosedRestoredLease(
  session: PersistedStudySession,
  serverStatus: StudySessionStatus['status'] | 'missing',
) {
  if (
    serverStatus === 'committed'
    && session.status === 'pending_commit'
    && session.commit_id
  ) {
    const prepared = prepareCommit(session)
    try {
      const response = await appApi.mutate<unknown>(
        `/api/study/sessions/${prepared.session.snapshot.session_id}/commit`,
        'POST',
        prepared.payload,
      )
      requireMatchingCommitReceipt(response, prepared.session)
      return
    } catch (caught) {
      if (
        caught instanceof ApiError
        && caught.code === 'SESSION_ALREADY_COMMITTED'
        && isCommitReceipt(caught.details)
      ) {
        await settleCommittedLease(caught.details, prepared.session)
        return
      }
      if (isTransientCommitFailure(caught)) throw caught
    }
  }
  const unsaved = session.events.length
  const message = serverStatus === 'missing'
    ? `Máy chủ không còn phiên học cũ trong trình duyệt này; ${unsaved} câu trả lời chưa lưu đã được cách ly (không xoá). `
      + 'Chọn Thử lại để mở phiên mới.'
    : `Phiên học cũ trong trình duyệt này đã đóng trên máy chủ (${serverStatus}); ${unsaved} câu trả lời chưa lưu đã được cách ly (không xoá). `
      + 'Chọn Thử lại để mở phiên mới.'
  await quarantineStudySession(session.scope_key, session, { reason: 'LEASE_CLOSED', message })
  throw new ApiError(message, 409, 'SESSION_LEASE_CLOSED')
}

function openSnapshot(userId: number, deckId: string, compositionId: string) {
  const key = `${scopeKey(userId, 'deck', deckId)}:composition:${compositionId}`
  const existing = openingRequests.get(key)
  if (existing) return existing
  const request = appApi.mutate<StudySessionSnapshot>(
    '/api/study/sessions',
    'POST',
    {
      scope: 'deck',
      scope_id: deckId,
      composition_id: compositionId,
      accepted_session_schema_versions: [
        'study-session.v4',
        'study-session.v3',
        'study-session.v2',
      ],
      accepted_batch_schema_versions: ['study-batch.v3'],
      accepted_note_storage_profiles: [NOTE_STORAGE_PROFILE],
    },
  ).finally(() => {
    openingRequests.delete(key)
  })
  openingRequests.set(key, request)
  return request
}

export function useStudySession(deckId: string | null) {
  const queryClient = useQueryClient()
  const bootstrapQuery = useBootstrap()
  const userId = bootstrapQuery.data?.user?.id ?? null
  const [session, setSession] = useState<PersistedStudySession | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(Boolean(deckId))
  const [busy, setBusy] = useState(false)
  const [compositionGroups, setCompositionGroups] = useState<StudyCompositionGroup[]>([])
  const [selectedCompositionId, setSelectedCompositionId] = useState<string | null>(null)
  const [awaitingCompositionSelection, setAwaitingCompositionSelection] = useState(false)
  const [scopeName, setScopeName] = useState<string | null>(null)
  const [receipt, setReceipt] = useState<StudySessionCommitReceipt | null>(null)
  const [tick, setTick] = useState(0)
  const [onlineRetrySequence, setOnlineRetrySequence] = useState(0)
  const finalizedSessionRef = useRef<string | null>(null)

  const clockRef = useRef<{
    sessionId: string
    openedClientAtMs: number
    serverNowUtc: string
    serverAtMs: number
    performanceAtMs: number
  } | null>(null)
  const mutationOwnerRef = useRef<SessionMutationOwner | null>(null)
  const mountedRef = useRef(true)
  const sessionRef = useRef<PersistedStudySession | null>(null)
  const sessionDurableRef = useRef(true)
  const exitFlushRef = useRef<string | null>(null)
  const recoveryAttemptRef = useRef<string | null>(null)

  useEffect(() => {
    const retryPendingCommit = () => {
      recoveryAttemptRef.current = null
      setOnlineRetrySequence((value) => value + 1)
    }
    window.addEventListener('online', retryPendingCommit)
    return () => window.removeEventListener('online', retryPendingCommit)
  }, [])

  const currentScopeKey = useMemo(() => (
    deckId && userId !== null ? scopeKey(userId, 'deck', deckId) : null
  ), [deckId, userId])

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const activateSession = useCallback((next: PersistedStudySession | null) => {
    sessionRef.current = next
    setSession(next)
    if (!next) {
      clockRef.current = null
      return
    }
    const clock = clockRef.current
    if (
      clock?.sessionId === next.snapshot.session_id
      && clock.openedClientAtMs === next.opened_client_at_ms
      && clock.serverNowUtc === next.snapshot.server_now_utc
    ) return
    const elapsedWall = Math.max(
      0,
      Date.now() - next.opened_client_at_ms,
    )
    clockRef.current = {
      sessionId: next.snapshot.session_id,
      openedClientAtMs: next.opened_client_at_ms,
      serverNowUtc: next.snapshot.server_now_utc,
      serverAtMs: Date.parse(next.snapshot.server_now_utc) + elapsedWall,
      performanceAtMs: performance.now(),
    }
  }, [])

  const now = useCallback(() => {
    const clock = clockRef.current
    if (!clock) return Date.now()
    return clock.serverAtMs + performance.now() - clock.performanceAtMs
  }, [])

  const {
    leaseState,
    takeoverState,
    hasLease,
    hasLeaseRef,
    leaseControllerRef,
    bootstrapStartedRef,
    ownedLeaseControllersRef,
    beginLeaseWork,
    endLeaseWork,
    releaseLeaseWhenIdle,
    requestTakeover,
    forceTakeover,
    isCurrentLease,
  } = useStudySessionLease({
    currentScopeKey,
    activateSession,
    sessionRef,
    sessionDurableRef,
    setLoading,
  })

  const acquireMutation = useCallback((
    kind: SessionMutationKind,
    controller: AbortController,
  ): SessionMutationOwner | null => {
    if (mutationOwnerRef.current || controller.signal.aborted) return null
    const owner: SessionMutationOwner = {
      token: Symbol(kind),
      kind,
      controller,
      scopeKey: currentScopeKey,
      sessionId: sessionRef.current?.snapshot.session_id ?? null,
    }
    mutationOwnerRef.current = owner
    if (mountedRef.current) setBusy(true)
    return owner
  }, [currentScopeKey])

  const releaseMutation = useCallback((owner: SessionMutationOwner) => {
    if (mutationOwnerRef.current?.token !== owner.token) return
    mutationOwnerRef.current = null
    if (mountedRef.current) setBusy(false)
  }, [])

  const waitForMutation = useCallback(async (
    kind: SessionMutationKind,
    controller: AbortController,
  ) => {
    while (!controller.signal.aborted) {
      const owner = acquireMutation(kind, controller)
      if (owner) return owner
      await waitForNextOperationCheck()
    }
    return null
  }, [acquireMutation])

  // Bootstrap session data
  useEffect(() => {
    if (!deckId || userId === null) {
      activateSession(null)
      setCompositionGroups([])
      setSelectedCompositionId(null)
      setAwaitingCompositionSelection(false)
      setScopeName(null)
      setLoading(Boolean(deckId))
      return
    }
    if (
      !currentScopeKey
      || leaseState.key !== currentScopeKey
      || (
        leaseState.status !== 'held'
        && leaseState.status !== 'transferred'
      )
    ) return
    const controller = leaseControllerRef.current
    if (
      !controller
      || controller.signal.aborted
      || bootstrapStartedRef.current.has(controller)
    ) return
    bootstrapStartedRef.current.add(controller)
    const key = currentScopeKey
    const isThisLease = () => isCurrentLease(controller)

    if (hasLeaseRef.current) {
      setLoading(true)
      setError(null)
      setReceipt(null)
      setAwaitingCompositionSelection(false)
    }
    void (async () => {
      const mutationOwner = await waitForMutation('bootstrap', controller)
      if (!mutationOwner) {
        endLeaseWork(controller)
        return
      }
      try {
        const loaded = await loadStudySessionWithDurability(key)
        const restored = loaded.session
        sessionDurableRef.current = loaded.durable
        if (!isThisLease()) return
        if (loaded.quarantine) {
          throw new Error(
            `Phiên học đã lưu không tương thích (${loaded.quarantine.reason}) và đã được cách ly. Chọn Thử lại để mở phiên mới; dữ liệu cũ vẫn được giữ để chẩn đoán.`,
          )
        }
        const expiresAt = restored
          ? Date.parse(restored.snapshot.expires_at)
          : 0
        let active = restored
        if (active && expiresAt <= Date.now() && !hasUnacknowledgedStudyWork(active)) {
          await removeStudySessionIfMatches(
            key,
            active.snapshot.session_id,
          )
          if (!isThisLease()) return
          active = null
        }
        if (active) {
          const activeSessionId = active.snapshot.session_id
          // NOTE batch streams settle through their own batch receipts.
          const settlesSynchronously = !usesNoteBatchTransport(active)
            && !active.in_flight_batches?.length
          let closedLeaseStatus: StudySessionStatus['status'] | 'missing' | null = null
          try {
            const serverSession = await appApi.get<StudySessionStatus>(
              `/api/study/sessions/${activeSessionId}`,
            )
            if (!isThisLease()) return
            if (!hasUnacknowledgedStudyWork(active) && (serverSession.status !== 'open' || serverSession.stale)) {
              await removeStudySessionIfMatches(
                key,
                activeSessionId,
              )
              if (!isThisLease()) return
              active = null
            } else if (serverSession.status !== 'open') {
              closedLeaseStatus = serverSession.status
            }
          } catch (caught) {
            if (!isThisLease()) return
            if (caught instanceof ApiError && caught.code === 'SESSION_NOT_FOUND' && active && !hasUnacknowledgedStudyWork(active)) {
              await removeStudySessionIfMatches(
                key,
                activeSessionId,
              )
              if (!isThisLease()) return
              active = null
            } else if (
              caught instanceof ApiError
              && caught.code === 'SESSION_NOT_FOUND'
              && settlesSynchronously
            ) {
              closedLeaseStatus = 'missing'
            } else if (
              !(caught instanceof ApiError)
              || caught.code !== 'BACKEND_UNAVAILABLE'
            ) {
              throw caught
            }
          }
          // Reviving a lease the server already closed would replay its old
          // receipt (or fail) on every visit instead of opening a new session.
          if (active && closedLeaseStatus && settlesSynchronously) {
            await settleClosedRestoredLease(active, closedLeaseStatus)
            if (!isThisLease()) return
            await removeStudySessionIfMatches(key, activeSessionId)
            if (!isThisLease()) return
            active = null
          }
        }
        if (active) {
          setSelectedCompositionId(
            active.snapshot.selected_composition_id ?? null,
          )
          setScopeName(active.snapshot.scope.name || null)
          setCompositionGroups([])
          setAwaitingCompositionSelection(false)
        } else {
          const availability = await fetchStudyScopeCompositions(deckId)
          if (!isThisLease()) return
          setCompositionGroups(availability.groups)
          setScopeName(null)
          if (availability.compositions.length === 0) {
            throw new ApiError(
              'Bộ thẻ này hiện chưa có thẻ nào để bắt đầu phiên ôn tập.',
              404,
              'NO_STUDY_CARDS',
            )
          }
          if (availability.compositions.length > 1) {
            setSelectedCompositionId(null)
            setAwaitingCompositionSelection(true)
            return
          }
          const compositionId = availability.compositions[0].composition_id
          setSelectedCompositionId(compositionId)
          const opened = await openSnapshot(userId, deckId, compositionId)
          if (!isThisLease()) return
          active = createPersistedSession(opened)
          sessionDurableRef.current = await saveStudySession(active)
          if (!isThisLease()) return
        }
        if (hasLeaseRef.current) activateSession(active)
      } catch (caught) {
        if (isThisLease() && hasLeaseRef.current) setError(caught)
      } finally {
        releaseMutation(mutationOwner)
        endLeaseWork(controller)
        if (isThisLease() && hasLeaseRef.current) setLoading(false)
      }
    })()
  }, [
    activateSession,
    bootstrapStartedRef,
    currentScopeKey,
    deckId,
    endLeaseWork,
    hasLeaseRef,
    isCurrentLease,
    leaseControllerRef,
    leaseState.key,
    leaseState.status,
    releaseMutation,
    userId,
    waitForMutation,
  ])

  useEffect(() => {
    if (!session) return
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [session])

  const view = useMemo(() => {
    // `tick` advances waiting learning cards without a network request.
    void tick
    return session ? buildSessionView(session, now()) : null
  }, [now, session, tick])

  useEffect(() => {
    if (!session || !view?.card?.card_id) return
    if (session.active_card_id === view.card.card_id) return
    if (finalizedSessionRef.current === session.snapshot.session_id) return
    const controller = leaseControllerRef.current
    if (!controller || controller.signal.aborted || !hasLeaseRef.current) return
    void (async () => {
      const owner = await waitForMutation('selection-persist', controller)
      if (!owner) return
      beginLeaseWork(controller)
      try {
        if (!isCurrentLease(controller) || !hasLeaseRef.current) return
        const active = sessionRef.current
        if (!active || finalizedSessionRef.current === active.snapshot.session_id) return
        const selectedCardId = buildSessionView(active, now()).card?.card_id
        if (!selectedCardId || active.active_card_id === selectedCardId) return
        const nextSession: PersistedStudySession = {
          ...active,
          active_card_id: selectedCardId,
          updated_at_ms: Date.now(),
        }
        activateSession(nextSession)
        sessionDurableRef.current = await saveStudySession(nextSession)
      } finally {
        endLeaseWork(controller)
        releaseMutation(owner)
      }
    })()
  }, [
    activateSession,
    beginLeaseWork,
    endLeaseWork,
    hasLeaseRef,
    isCurrentLease,
    leaseControllerRef,
    now,
    releaseMutation,
    session,
    view?.card?.card_id,
    waitForMutation,
  ])

  const prepareDecision = useCallback((cardId: string) => {
    const active = sessionRef.current
    if (!active) throw new Error('Study session is not ready.')
    return decisionForCard(active, cardId, now())
  }, [now])

  const answer = useCallback(async (
    cardId: string,
    rating: Rating,
    decision: SchedulerDecision,
    durationMs: number,
  ) => {
    const controller = leaseControllerRef.current
    if (!controller || controller.signal.aborted || !hasLeaseRef.current) {
      throw new Error('Study session lease is not held by this window.')
    }
    const owner = acquireMutation('answer', controller)
    if (!owner) return
    beginLeaseWork(controller)
    try {
      const active = sessionRef.current
      if (!active || !isCurrentLease(controller) || !hasLeaseRef.current) {
        throw new Error('Study session lease is not held by this window.')
      }
      const next = applyLocalAnswer(
        active,
        cardId,
        rating,
        decision,
        durationMs,
      )
      activateSession(next)
      sessionDurableRef.current = await saveStudySession(next)
    } finally {
      endLeaseWork(controller)
      releaseMutation(owner)
    }
  }, [
    acquireMutation,
    activateSession,
    beginLeaseWork,
    endLeaseWork,
    hasLeaseRef,
    isCurrentLease,
    leaseControllerRef,
    releaseMutation,
  ])

  const undo = useCallback(async (): Promise<string | null> => {
    const controller = leaseControllerRef.current
    if (!controller || controller.signal.aborted || !hasLeaseRef.current) {
      throw new Error('Study session lease is not held by this window.')
    }
    const owner = acquireMutation('undo', controller)
    if (!owner) return null
    beginLeaseWork(controller)
    try {
      const active = sessionRef.current
      if (!active || !isCurrentLease(controller) || !hasLeaseRef.current) {
        throw new Error('Study session lease is not held by this window.')
      }
      const undoResult = undoLocalAnswer(active)
      if (!undoResult) return null
      activateSession(undoResult.session)
      sessionDurableRef.current = await saveStudySession(undoResult.session)
      return undoResult.undoneCardId
    } finally {
      endLeaseWork(controller)
      releaseMutation(owner)
    }
  }, [
    acquireMutation,
    activateSession,
    beginLeaseWork,
    endLeaseWork,
    hasLeaseRef,
    isCurrentLease,
    leaseControllerRef,
    releaseMutation,
  ])

  const commit = useCallback(async (options?: {
    reason?: StudyCommitReason
    resumeAfterCommit?: boolean
  }) => {
    const controller = leaseControllerRef.current
    if (
      !controller
      || controller.signal.aborted
      || !hasLeaseRef.current
      || userId === null
      || !deckId
    ) {
      throw new Error('Study session lease is not held by this window.')
    }
    const owner = acquireMutation('commit', controller)
    if (!owner) return null
    const isThisLease = () => isCurrentLease(controller)
    beginLeaseWork(controller)
    try {
      const active = sessionRef.current
      if (!active || !isThisLease() || !hasLeaseRef.current) {
        throw new Error('Study session lease is not held by this window.')
      }
      if (finalizedSessionRef.current === active.snapshot.session_id) return null
      if (usesNoteBatchTransport(active)) {
        const flushed = await flushNoteBatchStream(active, {
          checkOwner: () => {
            if (!isThisLease() || !hasLeaseRef.current) throw new DOMException('Study lease changed.', 'AbortError')
          },
          persist: async (next) => {
            activateSession(next)
            sessionDurableRef.current = await saveStudySession(next)
            return sessionDurableRef.current
          },
        }, options)
        if (!isThisLease() || !hasLeaseRef.current) return flushed.receipt
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
          queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
          queryClient.invalidateQueries({ queryKey: ['stats'] }),
        ])
        if (!isThisLease() || !hasLeaseRef.current) return flushed.receipt
        if (flushed.receipt?.is_final) {
          await removeStudySessionIfMatches(active.scope_key, active.snapshot.session_id)
          if (!isThisLease() || !hasLeaseRef.current) return flushed.receipt
          finalizedSessionRef.current = active.snapshot.session_id
          setReceipt(flushed.receipt)
        } else {
          setReceipt(null)
        }
        activateSession(flushed.session)
        setError(null)
        return flushed.receipt
      }
      const prepared = prepareCommit(active, options)
      if (isThisLease()) activateSession(prepared.session)
      sessionDurableRef.current = await saveStudySession(prepared.session)
      const response = await appApi.mutate<unknown>(
        `/api/study/sessions/${prepared.session.snapshot.session_id}/commit`,
        'POST',
        prepared.payload,
      )
      const result = requireMatchingCommitReceipt(response, prepared.session)
      if (!isThisLease()) return result
      const batchReviews = prepared.session.events.length
      const batchDurationMs = prepared.session.events.reduce(
        (sum, ev) => sum + (ev.duration_ms || 0),
        0,
      )
      const batchAgain = prepared.session.events.filter((ev) => ev.rating === 'again').length
      const batchHard = prepared.session.events.filter((ev) => ev.rating === 'hard').length
      const batchGood = prepared.session.events.filter((ev) => ev.rating === 'good').length
      const batchEasy = prepared.session.events.filter((ev) => ev.rating === 'easy').length

      const prevStats = prepared.session.accumulated_stats || {
        total_reviews: 0,
        total_duration_ms: 0,
        again_count: 0,
        hard_count: 0,
        good_count: 0,
        easy_count: 0,
      }

      const nextAccumulated: StudySessionAccumulatedStats = {
        total_reviews: prevStats.total_reviews + batchReviews,
        total_duration_ms: prevStats.total_duration_ms + batchDurationMs,
        again_count: prevStats.again_count + batchAgain,
        hard_count: prevStats.hard_count + batchHard,
        good_count: prevStats.good_count + batchGood,
        easy_count: prevStats.easy_count + batchEasy,
      }

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
        queryClient.invalidateQueries({ queryKey: ['stats'] }),
      ])
      if (!isThisLease()) return result
      if (prepared.session.resume_after_commit) {
        const compositionId = prepared.session.snapshot.selected_composition_id
        if (!compositionId) {
          throw new Error('Phiên học cũ không có composition đã khóa để tiếp tục an toàn.')
        }
        const opened = await openSnapshot(userId, deckId, compositionId)
        if (!isThisLease()) return result
        const next = createPersistedSession(opened, {
          accumulated_stats: nextAccumulated,
          session_started_at_ms: prepared.session.session_started_at_ms ?? prepared.session.opened_client_at_ms,
        })
        sessionDurableRef.current = await saveStudySession(next)
        if (!isThisLease()) return result
        activateSession(next)
        setReceipt(null)
      } else {
        await removeStudySessionIfMatches(
          prepared.session.scope_key,
          prepared.session.snapshot.session_id,
        )
        // The receipt closes this lease: nothing may persist or resend it.
        finalizedSessionRef.current = prepared.session.snapshot.session_id
        if (!isThisLease()) return result
        const reconciled = applyCommitReceipt(prepared.session, result, {
          accumulated_stats: nextAccumulated,
        })
        activateSession(reconciled)
        setReceipt(result)
      }
      return result
    } catch (caught) {
      if (
        caught instanceof ApiError
        && caught.code === 'SESSION_ALREADY_COMMITTED'
        && isCommitReceipt(caught.details)
      ) {
        if (!isThisLease()) return caught.details
        const pending = sessionRef.current
        if (pending) {
          let result: StudySessionCommitReceipt
          try {
            result = await settleCommittedLease(caught.details, pending)
          } catch (unsettled) {
            if (isThisLease() && hasLeaseRef.current) setError(unsettled)
            throw unsettled
          }
          if (!isThisLease()) return result
          const batchReviews = pending.events.length
          const batchDurationMs = pending.events.reduce(
            (sum, ev) => sum + (ev.duration_ms || 0),
            0,
          )
          const batchAgain = pending.events.filter((ev) => ev.rating === 'again').length
          const batchHard = pending.events.filter((ev) => ev.rating === 'hard').length
          const batchGood = pending.events.filter((ev) => ev.rating === 'good').length
          const batchEasy = pending.events.filter((ev) => ev.rating === 'easy').length

          const prevStats = pending.accumulated_stats || {
            total_reviews: 0,
            total_duration_ms: 0,
            again_count: 0,
            hard_count: 0,
            good_count: 0,
            easy_count: 0,
          }

          const nextAccumulated: StudySessionAccumulatedStats = {
            total_reviews: prevStats.total_reviews + batchReviews,
            total_duration_ms: prevStats.total_duration_ms + batchDurationMs,
            again_count: prevStats.again_count + batchAgain,
            hard_count: prevStats.hard_count + batchHard,
            good_count: prevStats.good_count + batchGood,
            easy_count: prevStats.easy_count + batchEasy,
          }

          await Promise.all([
            queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
            queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
            queryClient.invalidateQueries({ queryKey: ['stats'] }),
          ])
          if (!isThisLease()) return result
          if (pending.resume_after_commit) {
            const compositionId = pending.snapshot.selected_composition_id
            if (!compositionId) {
              throw new Error('Phiên học cũ không có composition đã khóa để tiếp tục an toàn.')
            }
            const opened = await openSnapshot(userId, deckId, compositionId)
            if (!isThisLease()) return result
            const next = createPersistedSession(opened, {
              accumulated_stats: nextAccumulated,
              session_started_at_ms: pending.session_started_at_ms ?? pending.opened_client_at_ms,
            })
            sessionDurableRef.current = await saveStudySession(next)
            if (!isThisLease()) return result
            activateSession(next)
            setReceipt(null)
          } else {
            await removeStudySessionIfMatches(
              pending.scope_key,
              pending.snapshot.session_id,
            )
            finalizedSessionRef.current = pending.snapshot.session_id
            if (!isThisLease()) return result
            const reconciled = applyCommitReceipt(pending, result, {
              accumulated_stats: nextAccumulated,
            })
            activateSession(reconciled)
            setReceipt(result)
          }
          return result
        }
      }
      if (isThisLease() && hasLeaseRef.current) setError(caught)
      throw caught
    } finally {
      endLeaseWork(controller)
      releaseMutation(owner)
    }
  }, [
    acquireMutation,
    activateSession,
    beginLeaseWork,
    deckId,
    endLeaseWork,
    hasLeaseRef,
    isCurrentLease,
    leaseControllerRef,
    queryClient,
    releaseMutation,
    userId,
  ])

  useEffect(() => {
    if (!session || !view || busy || receipt || !hasLease) return
    if (session.status === 'pending_commit' || (
      usesNoteBatchTransport(session) && Boolean(session.in_flight_batches?.length)
    )) {
      const recoveryKey = [
        session.snapshot.session_id,
        session.commit_id,
      ].join(':')
      if (recoveryAttemptRef.current === recoveryKey) return
      recoveryAttemptRef.current = recoveryKey
      void commit().catch(() => {})
      return
    }
    const mode = automaticCommitMode(session, view)
    if (!mode) return
    if (mode === 'rollover') {
      void commit({
        reason: 'rollover',
        resumeAfterCommit: true,
      }).catch(() => {})
    } else {
      void commit({
        reason: 'auto_finish',
        resumeAfterCommit: false,
      }).catch(() => {})
    }
  }, [busy, commit, hasLease, onlineRetrySequence, receipt, session, view])

  useEffect(() => {
    if (!hasLease || busy || receipt || !(error instanceof ApiError) || error.code !== 'BATCH_PENDING') return
    const timer = window.setTimeout(() => {
      recoveryAttemptRef.current = null
      setOnlineRetrySequence((value) => value + 1)
    }, 1000)
    return () => window.clearTimeout(timer)
  }, [busy, error, hasLease, receipt])

  const flushOnExit = useCallback(() => {
    const controller = leaseControllerRef.current
    if (
      !controller
      || controller.signal.aborted
      || !ownedLeaseControllersRef.current.has(controller)
    ) return null
    beginLeaseWork(controller)
    return (async () => {
      let owner: SessionMutationOwner | null = null
      try {
        owner = await waitForMutation('page-exit', controller)
        if (!owner || controller.signal.aborted) return
        const active = sessionRef.current
        if (!active || finalizedSessionRef.current === active.snapshot.session_id) return
        if (usesNoteBatchTransport(active)) {
          await sendNoteBatchOnExit(active, {
            checkOwner: () => {
              if (controller.signal.aborted || !ownedLeaseControllersRef.current.has(controller)) {
                throw new DOMException('Study lease changed.', 'AbortError')
              }
            },
            persist: async (next) => {
              if (leaseControllerRef.current === controller) sessionRef.current = next
              sessionDurableRef.current = await saveStudySession(next)
              return sessionDurableRef.current
            },
          })
          return
        }
        if (active.events.length === 0) return
        const prepared = prepareCommit(active, {
          reason: active.status === 'pending_commit'
            ? active.commit_reason ?? undefined
            : 'page_exit',
          resumeAfterCommit: active.status === 'pending_commit'
            ? active.resume_after_commit
            : false,
        })
        const flushKey = [
          prepared.session.snapshot.session_id,
          prepared.session.commit_id,
        ].join(':')
        if (exitFlushRef.current === flushKey) return
        exitFlushRef.current = flushKey
        if (leaseControllerRef.current === controller) {
          sessionRef.current = prepared.session
        }
        sessionDurableRef.current = await saveStudySession(prepared.session)
        try {
          const response = await appApi.mutateKeepalive<unknown>(
            `/api/study/sessions/${prepared.session.snapshot.session_id}/commit`,
            'POST',
            prepared.payload,
          )
          requireMatchingCommitReceipt(response, prepared.session)
        } catch (caught) {
          if (
            !(caught instanceof ApiError)
            || caught.code !== 'SESSION_ALREADY_COMMITTED'
            || !isCommitReceipt(caught.details)
          ) throw caught
          // Same settlement as an in-page retry: a covering stored receipt
          // clears the copy, anything else is quarantined, never revived.
          await settleCommittedLease(caught.details, prepared.session)
        }
        finalizedSessionRef.current = prepared.session.snapshot.session_id
        await removeStudySessionIfMatches(
          prepared.session.scope_key,
          prepared.session.snapshot.session_id,
        )
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
          queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
          queryClient.invalidateQueries({ queryKey: ['stats'] }),
        ])
      } catch {
        // The pending batch remains durable in IndexedDB and can be retried.
      } finally {
        if (owner) releaseMutation(owner)
        endLeaseWork(controller)
      }
    })()
  }, [
    beginLeaseWork,
    endLeaseWork,
    leaseControllerRef,
    ownedLeaseControllersRef,
    queryClient,
    releaseMutation,
    waitForMutation,
  ])

  const selectComposition = useCallback(async (compositionId: string) => {
    if (!deckId || userId === null || !currentScopeKey) return
    const selected = compositionGroups
      .flatMap((group) => group.compositions)
      .find((composition) => composition.composition_id === compositionId)
    if (!selected) {
      setError(new ApiError(
        'Composition đã chọn không còn thuộc phạm vi học hiện tại.',
        409,
        'COMPOSITION_STALE',
      ))
      return
    }
    const controller = leaseControllerRef.current
    if (
      !controller
      || controller.signal.aborted
      || !hasLeaseRef.current
      || mutationOwnerRef.current
    ) return
    const owner = await waitForMutation('composition-open', controller)
    if (!owner) return
    beginLeaseWork(controller)
    setLoading(true)
    setError(null)
    setSelectedCompositionId(compositionId)
    setAwaitingCompositionSelection(false)
    try {
      const opened = await openSnapshot(userId, deckId, compositionId)
      if (!isCurrentLease(controller) || !hasLeaseRef.current) return
      const next = createPersistedSession(opened)
      sessionDurableRef.current = await saveStudySession(next)
      if (!isCurrentLease(controller) || !hasLeaseRef.current) return
      setScopeName(next.snapshot.scope.name || null)
      activateSession(next)
    } catch (caught) {
      if (isCurrentLease(controller) && hasLeaseRef.current) {
        setAwaitingCompositionSelection(true)
        setError(caught)
      }
    } finally {
      if (isCurrentLease(controller) && hasLeaseRef.current) setLoading(false)
      endLeaseWork(controller)
      releaseMutation(owner)
    }
  }, [
    activateSession,
    beginLeaseWork,
    compositionGroups,
    currentScopeKey,
    deckId,
    endLeaseWork,
    hasLeaseRef,
    isCurrentLease,
    leaseControllerRef,
    releaseMutation,
    userId,
    waitForMutation,
  ])

  useEffect(() => {
    const handlePageHide = (event: PageTransitionEvent) => {
      void flushOnExit()
      if (event.persisted) {
        const controller = leaseControllerRef.current
        hasLeaseRef.current = false
        if (controller) void releaseLeaseWhenIdle(controller)
      }
    }
    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted) window.location.reload()
    }
    window.addEventListener('pagehide', handlePageHide)
    window.addEventListener('pageshow', handlePageShow)
    return () => {
      window.removeEventListener('pagehide', handlePageHide)
      window.removeEventListener('pageshow', handlePageShow)
      void flushOnExit()
    }
  }, [deckId, flushOnExit, hasLeaseRef, leaseControllerRef, releaseLeaseWhenIdle, userId])

  const canUndo = Boolean(
    hasLease
    && session
    && session.status === 'active'
    && session.events.length > 0
    && (session.undo_history?.length ?? 0) > 0,
  )

  const updateCardContent = useCallback(async (
    cardId: string,
    updatedFieldValues: Record<string, string>,
    options?: { noteId?: string | null; skipBroadcast?: boolean; media?: StudyMediaArtifact[] },
  ) => {
    const controller = leaseControllerRef.current
    if (!controller || controller.signal.aborted || !hasLeaseRef.current) return
    const owner = await waitForMutation('content-update', controller)
    if (!owner) return
    beginLeaseWork(controller)
    try {
      if (!isCurrentLease(controller) || !hasLeaseRef.current) return
      const current = sessionRef.current
      if (!current) return

      const { updated, nextSession } = applyCardContentPatch(
        current,
        cardId,
        updatedFieldValues,
        options,
      )
      if (!updated) return

      activateSession(nextSession)
      sessionDurableRef.current = await saveStudySession(nextSession)
      if (!options?.skipBroadcast) {
        await updateCardFieldValuesInSessions(cardId, updatedFieldValues, {
          noteId: options?.noteId,
          media: options?.media,
        })
      }
    } catch {
      // Retain in-memory copy when storage is temporarily unavailable.
    } finally {
      endLeaseWork(controller)
      releaseMutation(owner)
    }
  }, [
    activateSession,
    beginLeaseWork,
    endLeaseWork,
    hasLeaseRef,
    isCurrentLease,
    leaseControllerRef,
    releaseMutation,
    waitForMutation,
  ])

  const updateTemplateContent = useCallback(async (
    templateId: string,
    updated: UpdatedTemplatePayload,
  ) => {
    // Template source, version and binding are immutable for an active lease.
    // The saved authoring change becomes visible only in a newly opened one.
    void templateId
    void updated
  }, [])

  const reloadSession = useCallback(async (force = false) => {
    if (!deckId || userId === null) return
    const key = currentScopeKey
    if (!key) return
    const controller = leaseControllerRef.current
    if (
      !controller
      || controller.signal.aborted
      || !hasLeaseRef.current
      || mutationOwnerRef.current
    ) return
    const beforeReload = sessionRef.current
    if (!force && beforeReload && finalizedSessionRef.current !== beforeReload.snapshot.session_id && (
      hasUnacknowledgedStudyWork(beforeReload) || usesNoteBatchTransport(beforeReload)
    )) {
      const committed = await commit({ reason: 'manual_exit' })
      if (!committed) return
    }
    const owner = await waitForMutation('reload', controller)
    if (!owner) return
    beginLeaseWork(controller)
    try {
      if (!isCurrentLease(controller) || !hasLeaseRef.current) return
      const active = sessionRef.current
      if (force) await acknowledgeStudySessionQuarantine(key)
      if (active) {
        await removeStudySessionIfMatches(key, active.snapshot.session_id)
      }
      setLoading(true)
      setError(null)
      let compositionId = active?.snapshot.selected_composition_id
        ?? selectedCompositionId
      if (!compositionId) {
        const availability = await fetchStudyScopeCompositions(deckId)
        if (!isCurrentLease(controller) || !hasLeaseRef.current) return
        setCompositionGroups(availability.groups)
        if (availability.compositions.length === 0) {
          throw new ApiError(
            'Bộ thẻ này hiện chưa có thẻ nào để bắt đầu phiên ôn tập.',
            404,
            'NO_STUDY_CARDS',
          )
        }
        if (availability.compositions.length > 1) {
          setSelectedCompositionId(null)
          setAwaitingCompositionSelection(true)
          activateSession(null)
          return
        }
        compositionId = availability.compositions[0].composition_id
      }
      setSelectedCompositionId(compositionId)
      setAwaitingCompositionSelection(false)
      const opened = await openSnapshot(userId, deckId, compositionId)
      if (!isCurrentLease(controller) || !hasLeaseRef.current) return
      const next = createPersistedSession(opened)
      sessionDurableRef.current = await saveStudySession(next)
      if (!isCurrentLease(controller) || !hasLeaseRef.current) return
      setScopeName(next.snapshot.scope.name || null)
      activateSession(next)
    } catch (err) {
      if (isCurrentLease(controller) && hasLeaseRef.current) setError(err)
    } finally {
      setLoading(false)
      endLeaseWork(controller)
      releaseMutation(owner)
    }
  }, [
    activateSession,
    beginLeaseWork,
    commit,
    currentScopeKey,
    deckId,
    endLeaseWork,
    hasLeaseRef,
    isCurrentLease,
    leaseControllerRef,
    releaseMutation,
    selectedCompositionId,
    userId,
    waitForMutation,
  ])

  // Synchronize card content and template updates in real-time (from Browse, Note Modal, or other tabs)
  useEffect(() => {
    const handleCardSync = (detail: {
      cardId?: string
      noteId?: string | null
      fieldValues?: Record<string, string>
      media?: StudyMediaArtifact[]
    }) => {
      if (!detail?.cardId || !detail?.fieldValues) return
      void updateCardContent(detail.cardId, detail.fieldValues, {
        noteId: detail.noteId,
        media: detail.media,
        skipBroadcast: true,
      })
    }

    const handleTemplateSync = (detail: { templateId?: string; updated?: UpdatedTemplatePayload }) => {
      if (!detail?.templateId || !detail?.updated) return
      void updateTemplateContent(detail.templateId, detail.updated)
    }

    const handleWindowCustomCardEvent = (event: Event) => {
      const customEvent = event as CustomEvent
      handleCardSync(customEvent.detail)
    }

    const handleWindowCustomTemplateEvent = (event: Event) => {
      const customEvent = event as CustomEvent
      handleTemplateSync(customEvent.detail)
    }

    window.addEventListener('flama_study_card_updated', handleWindowCustomCardEvent)
    window.addEventListener('flama_study_template_updated', handleWindowCustomTemplateEvent)

    let broadcastChannel: BroadcastChannel | null = null
    try {
      broadcastChannel = new BroadcastChannel('flama_study_sync_channel')
      broadcastChannel.onmessage = (event) => {
        if (event.data?.type === 'CARD_UPDATED') {
          handleCardSync({
            cardId: event.data.cardId,
            noteId: event.data.noteId,
            fieldValues: event.data.fieldValues,
          })
        } else if (event.data?.type === 'TEMPLATE_UPDATED') {
          handleTemplateSync({
            templateId: event.data.templateId,
            updated: event.data.updated,
          })
        }
      }
    } catch {}

    return () => {
      window.removeEventListener('flama_study_card_updated', handleWindowCustomCardEvent)
      window.removeEventListener('flama_study_template_updated', handleWindowCustomTemplateEvent)
      if (broadcastChannel) {
        broadcastChannel.close()
      }
    }
  }, [updateCardContent, updateTemplateContent])

  const totalSessionStats: StudySessionAccumulatedStats = useMemo(() => {
    const acc = session?.accumulated_stats || {
      total_reviews: 0,
      total_duration_ms: 0,
      again_count: 0,
      hard_count: 0,
      good_count: 0,
      easy_count: 0,
    }
    // If the session is active and has uncommitted events, combine with accumulated
    const pendingEvents = session && usesNoteBatchTransport(session) && !receipt
      ? [...(session.in_flight_batches ?? []).flatMap<StudySessionEvent>((batch) => batch.events), ...session.events]
      : session?.events ?? []
    const isUncommitted = session && !receipt && (
      session.status === 'active' || usesNoteBatchTransport(session)
    ) && pendingEvents.length > 0
    if (!isUncommitted || !session) return acc
    const batchDurationMs = pendingEvents.reduce((sum, ev) => sum + (ev.duration_ms || 0), 0)
    const batchAgain = pendingEvents.filter((ev) => ev.rating === 'again').length
    const batchHard = pendingEvents.filter((ev) => ev.rating === 'hard').length
    const batchGood = pendingEvents.filter((ev) => ev.rating === 'good').length
    const batchEasy = pendingEvents.filter((ev) => ev.rating === 'easy').length
    return {
      total_reviews: acc.total_reviews + pendingEvents.length,
      total_duration_ms: acc.total_duration_ms + batchDurationMs,
      again_count: acc.again_count + batchAgain,
      hard_count: acc.hard_count + batchHard,
      good_count: acc.good_count + batchGood,
      easy_count: acc.easy_count + batchEasy,
    }
  }, [receipt, session])

  return {
    session,
    view,
    receipt,
    totalSessionStats,
    error: leaseState.status === 'error' ? leaseState.error : error,
    leaseConflict: Boolean(
      currentScopeKey
      && leaseState.key === currentScopeKey
      && (
        leaseState.status === 'blocked'
        || leaseState.status === 'transferred'
      )
    ),
    takeoverState,
    isLoading: loading,
    isBusy: busy,
    compositionGroups,
    selectedCompositionId,
    awaitingCompositionSelection,
    scopeName,
    canUndo,
    undo,
    prepareDecision,
    answer,
    commit,
    requestTakeover,
    forceTakeover,
    updateCardContent,
    updateTemplateContent,
    selectComposition,
    reloadSession,
  }
}
