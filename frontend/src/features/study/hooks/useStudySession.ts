import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import { ApiError } from '@/shared/api/client'
import type { Rating } from '../types'
import type {
  StudySessionCommitReceipt,
  StudySessionSnapshot,
  StudySessionStatus,
} from '../types'
import type { SchedulerDecision } from '../scheduler/types'
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
  loadStudySessionWithDurability,
  removeStudySessionIfMatches,
  saveStudySession,
  scopeKey,
} from '../session/sessionStore'
import type {
  PersistedStudySession,
  StudyCommitReason,
} from '../session/sessionStore'
import { holdStudyScopeLease } from '../session/studySessionLease'

const openingRequests = new Map<string, Promise<StudySessionSnapshot>>()
const HANDOFF_CHANNEL_PREFIX = 'flama-study-handoff:v1:'
const HANDOFF_RESPONSE_TIMEOUT_MS = 8_000
const HANDOFF_COMPLETION_TIMEOUT_MS = 30_000

type LeaseState = {
  key: string | null
  status: 'checking' | 'blocked' | 'error' | 'held' | 'transferred'
  error: unknown
}

type TakeoverState =
  | 'idle'
  | 'requesting'
  | 'waiting'
  | 'yielding'
  | 'unavailable'

type HandoffMessage = {
  type:
    | 'handoff-accepted'
    | 'handoff-rejected'
    | 'handoff-request'
  requester_id: string
}

function isHandoffMessage(value: unknown): value is HandoffMessage {
  if (!value || typeof value !== 'object') return false
  const message = value as Partial<HandoffMessage>
  return (
    (
      message.type === 'handoff-accepted'
      || message.type === 'handoff-rejected'
      || message.type === 'handoff-request'
    )
    && typeof message.requester_id === 'string'
  )
}

function waitForNextOperationCheck() {
  return new Promise<void>((resolve) => window.setTimeout(resolve, 25))
}

function createLeaseClientId() {
  return globalThis.crypto?.randomUUID?.()
    ?? `lease-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function isCommitReceipt(value: unknown): value is StudySessionCommitReceipt {
  if (!value || typeof value !== 'object') return false
  const receipt = value as Partial<StudySessionCommitReceipt>
  return receipt.schema_version === 'study-commit-receipt.v1'
    && receipt.success === true
    && typeof receipt.session_id === 'string'
    && typeof receipt.commit_id === 'string'
    && Array.isArray(receipt.updated_cards)
}

function openSnapshot(userId: number, deckId: string) {
  const key = scopeKey(userId, 'deck', deckId)
  const existing = openingRequests.get(key)
  if (existing) return existing
  const request = appApi.mutate<StudySessionSnapshot>(
    '/api/study/sessions',
    'POST',
    { scope: 'deck', scope_id: deckId },
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
  const [leaseState, setLeaseState] = useState<LeaseState>({
    key: null,
    status: 'checking',
    error: null,
  })
  const [takeoverState, setTakeoverState] = useState<TakeoverState>('idle')
  const [leaseAttempt, setLeaseAttempt] = useState(0)
  const [receipt, setReceipt] = useState<StudySessionCommitReceipt | null>(null)
  const [tick, setTick] = useState(0)
  const clockRef = useRef<{
    serverAtMs: number
    performanceAtMs: number
  } | null>(null)
  const operationRef = useRef(false)
  const leaseWorkCountsRef = useRef(new WeakMap<AbortController, number>())
  const bootstrapStartedRef = useRef(new WeakSet<AbortController>())
  const ownedLeaseControllersRef = useRef(new WeakSet<AbortController>())
  const sessionRef = useRef<PersistedStudySession | null>(null)
  const hasLeaseRef = useRef(false)
  const leaseControllerRef = useRef<AbortController | null>(null)
  const leaseChannelRef = useRef<BroadcastChannel | null>(null)
  const handoffTargetRef = useRef<string | null>(null)
  const requestOnBlockedRef = useRef(false)
  const takeoverTimerRef = useRef<number | null>(null)
  const sessionDurableRef = useRef(true)
  const exitFlushRef = useRef<string | null>(null)
  const recoveryAttemptRef = useRef<string | null>(null)
  const [leaseClientId] = useState(createLeaseClientId)
  const currentScopeKey = useMemo(() => (
    deckId && userId !== null ? scopeKey(userId, 'deck', deckId) : null
  ), [deckId, userId])

  const activateSession = useCallback((next: PersistedStudySession | null) => {
    sessionRef.current = next
    setSession(next)
    if (!next) {
      clockRef.current = null
      return
    }
    const elapsedWall = Math.max(
      0,
      Date.now() - next.opened_client_at_ms,
    )
    clockRef.current = {
      serverAtMs: Date.parse(next.snapshot.server_now_utc) + elapsedWall,
      performanceAtMs: performance.now(),
    }
  }, [])

  const now = useCallback(() => {
    const clock = clockRef.current
    if (!clock) return Date.now()
    return clock.serverAtMs + performance.now() - clock.performanceAtMs
  }, [])

  const beginLeaseWork = useCallback((controller: AbortController) => {
    const counts = leaseWorkCountsRef.current
    counts.set(controller, (counts.get(controller) ?? 0) + 1)
  }, [])

  const endLeaseWork = useCallback((controller: AbortController) => {
    const counts = leaseWorkCountsRef.current
    const remaining = (counts.get(controller) ?? 1) - 1
    if (remaining > 0) counts.set(controller, remaining)
    else counts.delete(controller)
  }, [])

  const hasLeaseWork = useCallback((controller: AbortController) => (
    (leaseWorkCountsRef.current.get(controller) ?? 0) > 0
  ), [])

  const clearTakeoverTimer = useCallback(() => {
    if (takeoverTimerRef.current === null) return
    window.clearTimeout(takeoverTimerRef.current)
    takeoverTimerRef.current = null
  }, [])

  useEffect(() => () => clearTakeoverTimer(), [clearTakeoverTimer])

  const releaseLeaseWhenIdle = useCallback(async (
    controller: AbortController,
  ) => {
    // Let the remaining effect cleanups reserve their flush work first.
    await waitForNextOperationCheck()
    if (
      !bootstrapStartedRef.current.has(controller)
      && hasLeaseWork(controller)
    ) {
      // onAcquired reserves one slot so bootstrap cannot be skipped by a
      // same-tick handoff/unmount. No bootstrap means that slot is unused.
      endLeaseWork(controller)
    }
    while (hasLeaseWork(controller) && !controller.signal.aborted) {
      await waitForNextOperationCheck()
    }
    if (!controller.signal.aborted) controller.abort()
    ownedLeaseControllersRef.current.delete(controller)
    if (leaseControllerRef.current === controller) {
      leaseControllerRef.current = null
    }
  }, [endLeaseWork, hasLeaseWork])

  useEffect(() => {
    if (!currentScopeKey) {
      hasLeaseRef.current = true
      setLeaseState({ key: null, status: 'held', error: null })
      setTakeoverState('idle')
      return
    }
    let disposed = false
    const controller = new AbortController()
    leaseControllerRef.current = controller
    hasLeaseRef.current = false
    activateSession(null)
    setLoading(true)
    setLeaseState({
      key: currentScopeKey,
      status: 'checking',
      error: null,
    })
    void holdStudyScopeLease(
      navigator.locks,
      `flama-study:${currentScopeKey}`,
      controller.signal,
      {
        onBlocked: () => {
          if (disposed) return
          setLoading(false)
          setLeaseState({
            key: currentScopeKey,
            status: 'blocked',
            error: null,
          })
          if (requestOnBlockedRef.current) {
            requestOnBlockedRef.current = false
            try {
              leaseChannelRef.current?.postMessage({
                type: 'handoff-request',
                requester_id: leaseClientId,
              } satisfies HandoffMessage)
            } catch {
              setTakeoverState('unavailable')
            }
          }
        },
        onAcquired: () => {
          if (disposed) return
          // Reserve one work slot before publishing `held`, so a handoff that
          // arrives immediately cannot release the lock before bootstrap starts.
          beginLeaseWork(controller)
          ownedLeaseControllersRef.current.add(controller)
          hasLeaseRef.current = true
          requestOnBlockedRef.current = false
          handoffTargetRef.current = null
          clearTakeoverTimer()
          setTakeoverState('idle')
          setLoading(true)
          setLeaseState({
            key: currentScopeKey,
            status: 'held',
            error: null,
          })
        },
        onLost: () => {
          if (disposed) return
          hasLeaseRef.current = false
          ownedLeaseControllersRef.current.delete(controller)
          controller.abort()
          activateSession(null)
          setLoading(false)
          setLeaseState({
            key: currentScopeKey,
            status: 'transferred',
            error: null,
          })
        },
      },
    ).catch((caught) => {
      if (disposed || controller.signal.aborted) return
      hasLeaseRef.current = false
      setLoading(false)
      setLeaseState({
        key: currentScopeKey,
        status: 'error',
        error: caught,
      })
    })
    return () => {
      disposed = true
      if (leaseControllerRef.current === controller) {
        hasLeaseRef.current = false
      }
      void releaseLeaseWhenIdle(controller)
    }
  }, [
    activateSession,
    beginLeaseWork,
    clearTakeoverTimer,
    currentScopeKey,
    leaseClientId,
    leaseAttempt,
    releaseLeaseWhenIdle,
  ])

  useEffect(() => {
    clearTakeoverTimer()
    handoffTargetRef.current = null
    setTakeoverState('idle')
    if (!currentScopeKey || typeof BroadcastChannel === 'undefined') return

    let channel: BroadcastChannel
    try {
      channel = new BroadcastChannel(
        `${HANDOFF_CHANNEL_PREFIX}${currentScopeKey}`,
      )
    } catch {
      leaseChannelRef.current = null
      return
    }
    leaseChannelRef.current = channel
    const handleMessage = (event: MessageEvent<unknown>) => {
      if (!isHandoffMessage(event.data)) return
      const message = event.data
      if (
        message.type === 'handoff-accepted'
      ) {
        if (message.requester_id !== leaseClientId) {
          // Once the owner accepts a specific requester, every other queued
          // tab withdraws so the Web Lock is handed to the selected tab.
          const waitingController = leaseControllerRef.current
          if (
            !hasLeaseRef.current
            && waitingController
            && !waitingController.signal.aborted
          ) {
            waitingController.abort()
            setLoading(false)
            setLeaseState({
              key: currentScopeKey,
              status: 'transferred',
              error: null,
            })
          }
          return
        }
        clearTakeoverTimer()
        setTakeoverState((current) => (
          current === 'requesting'
            ? 'waiting'
            : current
        ))
        takeoverTimerRef.current = window.setTimeout(() => {
          takeoverTimerRef.current = null
          if (!hasLeaseRef.current) setTakeoverState('unavailable')
        }, HANDOFF_COMPLETION_TIMEOUT_MS)
        return
      }
      if (
        message.type === 'handoff-rejected'
        && message.requester_id === leaseClientId
      ) {
        clearTakeoverTimer()
        const waitingController = leaseControllerRef.current
        if (
          !hasLeaseRef.current
          && waitingController
          && !waitingController.signal.aborted
        ) {
          waitingController.abort()
          setLeaseState({
            key: currentScopeKey,
            status: 'transferred',
            error: null,
          })
        }
        setTakeoverState('unavailable')
        return
      }
      if (
        message.type !== 'handoff-request'
        || message.requester_id === leaseClientId
      ) return
      if (handoffTargetRef.current) {
        if (handoffTargetRef.current === message.requester_id) {
          return
        }
        try {
          channel.postMessage({
            type: 'handoff-rejected',
            requester_id: message.requester_id,
          } satisfies HandoffMessage)
        } catch {
          // The requester timeout provides the same safe retry guidance.
        }
        return
      }
      if (!hasLeaseRef.current) return

      // Fence new actions immediately. Keep physically holding the Web Lock
      // until bootstrap and any in-flight answer/commit are durable.
      handoffTargetRef.current = message.requester_id
      hasLeaseRef.current = false
      setTakeoverState('yielding')
      setLoading(false)
      setLeaseState({
        key: currentScopeKey,
        status: 'transferred',
        error: null,
      })
      try {
        channel.postMessage({
          type: 'handoff-accepted',
          requester_id: message.requester_id,
        } satisfies HandoffMessage)
      } catch {
        // The requester still has its queued Web Lock request as a fallback.
      }

      const controller = leaseControllerRef.current
      void (async () => {
        while (
          controller
          && hasLeaseWork(controller)
          && !controller.signal.aborted
        ) {
          await waitForNextOperationCheck()
        }
        if (
          controller
          && !sessionDurableRef.current
          && (sessionRef.current?.events.length ?? 0) > 0
        ) {
          try {
            channel.postMessage({
              type: 'handoff-rejected',
              requester_id: message.requester_id,
            } satisfies HandoffMessage)
          } catch {
            // The requester timeout provides the same safe guidance.
          }
          if (leaseControllerRef.current === controller) {
            handoffTargetRef.current = null
            hasLeaseRef.current = true
            setTakeoverState('idle')
            setLeaseState({
              key: currentScopeKey,
              status: 'held',
              error: null,
            })
          }
          return
        }
        if (
          controller
          && leaseControllerRef.current === controller
          && !controller.signal.aborted
        ) {
          // Give passive waiters one task to process the selected-requester
          // broadcast and withdraw before releasing the FIFO Web Lock.
          await waitForNextOperationCheck()
          activateSession(null)
          controller.abort()
        }
        if (leaseControllerRef.current === controller) {
          handoffTargetRef.current = null
          setTakeoverState('idle')
        }
      })()
    }
    channel.addEventListener('message', handleMessage)

    return () => {
      clearTakeoverTimer()
      channel.removeEventListener('message', handleMessage)
      channel.close()
      if (leaseChannelRef.current === channel) leaseChannelRef.current = null
    }
  }, [
    activateSession,
    clearTakeoverTimer,
    currentScopeKey,
    hasLeaseWork,
    leaseClientId,
  ])

  useEffect(() => {
    if (!deckId || userId === null) {
      activateSession(null)
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
    const isCurrentLease = () => (
      leaseControllerRef.current === controller
      && !controller.signal.aborted
    )
    if (hasLeaseRef.current) {
      setLoading(true)
      setError(null)
      setReceipt(null)
    }
    void (async () => {
      try {
        const loaded = await loadStudySessionWithDurability(key)
        const restored = loaded.session
        sessionDurableRef.current = loaded.durable
        if (!isCurrentLease()) return
        const expiresAt = restored
          ? Date.parse(restored.snapshot.expires_at)
          : 0
        let active = restored
        if (active && expiresAt <= Date.now()) {
          await removeStudySessionIfMatches(
            key,
            active.snapshot.session_id,
          )
          if (!isCurrentLease()) return
          active = null
        }
        if (active) {
          const activeSessionId = active.snapshot.session_id
          try {
            const serverSession = await appApi.get<StudySessionStatus>(
              `/api/study/sessions/${activeSessionId}`,
            )
            if (!isCurrentLease()) return
            if (serverSession.status !== 'open') {
              await removeStudySessionIfMatches(
                key,
                activeSessionId,
              )
              if (!isCurrentLease()) return
              active = null
            }
          } catch (caught) {
            if (!isCurrentLease()) return
            if (caught instanceof ApiError && caught.code === 'SESSION_NOT_FOUND') {
              await removeStudySessionIfMatches(
                key,
                activeSessionId,
              )
              if (!isCurrentLease()) return
              active = null
            } else if (
              !(caught instanceof ApiError)
              || caught.code !== 'BACKEND_UNAVAILABLE'
            ) {
              throw caught
            }
          }
        }
        if (!active) {
          const opened = await openSnapshot(userId, deckId)
          if (!isCurrentLease()) return
          active = createPersistedSession(opened)
          sessionDurableRef.current = await saveStudySession(active)
          if (!isCurrentLease()) return
        }
        if (hasLeaseRef.current) activateSession(active)
      } catch (caught) {
        if (isCurrentLease() && hasLeaseRef.current) setError(caught)
      } finally {
        endLeaseWork(controller)
        if (isCurrentLease() && hasLeaseRef.current) setLoading(false)
      }
    })()
  }, [
    activateSession,
    currentScopeKey,
    deckId,
    endLeaseWork,
    leaseState.key,
    leaseState.status,
    userId,
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
    const active = sessionRef.current
    const controller = leaseControllerRef.current
    if (
      !active
      || !controller
      || controller.signal.aborted
      || !hasLeaseRef.current
      || operationRef.current
    ) return
    const isCurrentLease = () => (
      leaseControllerRef.current === controller
      && !controller.signal.aborted
    )
    operationRef.current = true
    beginLeaseWork(controller)
    setBusy(true)
    setError(null)
    let optimisticSession: PersistedStudySession | null = null
    try {
      optimisticSession = applyLocalAnswer(
        active,
        cardId,
        rating,
        decision,
        durationMs,
      )
      // Advance the visible queue immediately. IndexedDB durability should not
      // keep the old card on screen while the local session write completes.
      activateSession(optimisticSession)
      sessionDurableRef.current = await saveStudySession(optimisticSession)
    } catch (caught) {
      if (isCurrentLease() && sessionRef.current === optimisticSession) {
        activateSession(active)
      }
      if (isCurrentLease() && hasLeaseRef.current) setError(caught)
      throw caught
    } finally {
      operationRef.current = false
      endLeaseWork(controller)
      setBusy(false)
    }
  }, [activateSession, beginLeaseWork, endLeaseWork])

  const undo = useCallback(async (): Promise<string | null> => {
    const active = sessionRef.current
    const controller = leaseControllerRef.current
    if (
      !active
      || !controller
      || controller.signal.aborted
      || !hasLeaseRef.current
      || operationRef.current
    ) return null
    const isCurrentLease = () => (
      leaseControllerRef.current === controller
      && !controller.signal.aborted
    )
    const result = undoLocalAnswer(active)
    if (!result) return null

    operationRef.current = true
    beginLeaseWork(controller)
    setBusy(true)
    setError(null)
    const { session: undoneSession, undoneCardId } = result
    try {
      activateSession(undoneSession)
      sessionDurableRef.current = await saveStudySession(undoneSession)
      return undoneCardId
    } catch (caught) {
      if (isCurrentLease() && sessionRef.current === undoneSession) {
        activateSession(active)
      }
      if (isCurrentLease() && hasLeaseRef.current) setError(caught)
      throw caught
    } finally {
      operationRef.current = false
      endLeaseWork(controller)
      setBusy(false)
    }
  }, [activateSession, beginLeaseWork, endLeaseWork])

  const commit = useCallback(async (
    options: {
      reason?: StudyCommitReason
      resumeAfterCommit?: boolean
    } = {},
  ) => {
    const active = sessionRef.current
    const controller = leaseControllerRef.current
    if (
      !active
      || !deckId
      || userId === null
      || !controller
      || controller.signal.aborted
      || !hasLeaseRef.current
      || operationRef.current
    ) return null
    const isCurrentLease = () => (
      leaseControllerRef.current === controller
      && !controller.signal.aborted
    )
    operationRef.current = true
    beginLeaseWork(controller)
    setBusy(true)
    setError(null)
    try {
      const resumeAfterCommit = options.resumeAfterCommit
        ?? active.resume_after_commit
      const prepared = prepareCommit(active, {
        reason: options.reason,
        resumeAfterCommit,
      })
      sessionDurableRef.current = await saveStudySession(prepared.session)
      if (!isCurrentLease()) return null
      activateSession(prepared.session)
      const result = await appApi.mutate<StudySessionCommitReceipt>(
        `/api/study/sessions/${active.snapshot.session_id}/commit`,
        'POST',
        prepared.payload,
      )
      if (!isCurrentLease()) return result
      const reconciled = applyCommitReceipt(prepared.session, result)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
        queryClient.invalidateQueries({ queryKey: ['stats'] }),
      ])
      if (!isCurrentLease()) return result
      if (resumeAfterCommit) {
        const opened = await openSnapshot(userId, deckId)
        if (!isCurrentLease()) return result
        const next = createPersistedSession(opened)
        sessionDurableRef.current = await saveStudySession(next)
        if (!isCurrentLease()) return result
        activateSession(next)
        setReceipt(null)
      } else {
        await removeStudySessionIfMatches(
          prepared.session.scope_key,
          prepared.session.snapshot.session_id,
        )
        if (!isCurrentLease()) return result
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
        if (!isCurrentLease()) return caught.details
        const pending = sessionRef.current
        if (pending) {
          const result = caught.details
          const reconciled = applyCommitReceipt(pending, result)
          await Promise.all([
            queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
            queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
            queryClient.invalidateQueries({ queryKey: ['stats'] }),
          ])
          if (!isCurrentLease()) return result
          if (pending.resume_after_commit) {
            const opened = await openSnapshot(userId, deckId)
            if (!isCurrentLease()) return result
            const next = createPersistedSession(opened)
            sessionDurableRef.current = await saveStudySession(next)
            if (!isCurrentLease()) return result
            activateSession(next)
            setReceipt(null)
          } else {
            await removeStudySessionIfMatches(
              pending.scope_key,
              pending.snapshot.session_id,
            )
            if (!isCurrentLease()) return result
            activateSession(reconciled)
            setReceipt(result)
          }
          return result
        }
      }
      if (isCurrentLease() && hasLeaseRef.current) setError(caught)
      throw caught
    } finally {
      operationRef.current = false
      endLeaseWork(controller)
      setBusy(false)
    }
  }, [
    activateSession,
    beginLeaseWork,
    deckId,
    endLeaseWork,
    queryClient,
    userId,
  ])

  const hasLease = Boolean(
    currentScopeKey
    && leaseState.key === currentScopeKey
    && leaseState.status === 'held',
  )

  const requestTakeover = useCallback(() => {
    if (!currentScopeKey || hasLeaseRef.current) return
    const currentController = leaseControllerRef.current
    if (
      handoffTargetRef.current
      && currentController
      && !currentController.signal.aborted
    ) return
    clearTakeoverTimer()
    setTakeoverState('requesting')

    // A tab that previously handed off no longer has a queued request, so start
    // a fresh normal attempt before asking the current owner to release.
    if (
      leaseState.key === currentScopeKey
      && leaseState.status === 'transferred'
    ) {
      requestOnBlockedRef.current = true
      setLeaseAttempt((current) => current + 1)
    } else {
      try {
        leaseChannelRef.current?.postMessage({
          type: 'handoff-request',
          requester_id: leaseClientId,
        } satisfies HandoffMessage)
      } catch {
        // The timeout below explains how to retry or continue in the other tab.
      }
    }
    takeoverTimerRef.current = window.setTimeout(() => {
      takeoverTimerRef.current = null
      if (!hasLeaseRef.current) setTakeoverState('unavailable')
    }, HANDOFF_RESPONSE_TIMEOUT_MS)
  }, [
    clearTakeoverTimer,
    currentScopeKey,
    leaseClientId,
    leaseState.key,
    leaseState.status,
  ])

  useEffect(() => {
    if (!session || !view || busy || receipt || !hasLease) return
    if (session.status === 'pending_commit') {
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
    void commit({
      reason: mode === 'rollover' ? 'rollover' : 'auto_finish',
      resumeAfterCommit: mode === 'rollover',
    }).catch(() => {})
  }, [busy, commit, hasLease, receipt, session, view])

  const flushOnExit = useCallback(() => {
    const active = sessionRef.current
    const controller = leaseControllerRef.current
    if (
      !active
      || active.events.length === 0
      || !controller
      || controller.signal.aborted
      || !ownedLeaseControllersRef.current.has(controller)
    ) return null
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
    if (exitFlushRef.current === flushKey) return null
    exitFlushRef.current = flushKey
    beginLeaseWork(controller)
    return (async () => {
      try {
        // Do not race an answer/regular commit that already owns this lease.
        while (operationRef.current && !controller.signal.aborted) {
          await waitForNextOperationCheck()
        }
        if (controller.signal.aborted) return
        if (leaseControllerRef.current === controller) {
          sessionRef.current = prepared.session
        }
        sessionDurableRef.current = await saveStudySession(prepared.session)
        await appApi.mutateKeepalive<StudySessionCommitReceipt>(
          `/api/study/sessions/${prepared.session.snapshot.session_id}/commit`,
          'POST',
          prepared.payload,
        )
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
        endLeaseWork(controller)
      }
    })()
  }, [beginLeaseWork, endLeaseWork, queryClient])

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
  }, [deckId, flushOnExit, releaseLeaseWhenIdle, userId])

  const canUndo = Boolean(
    hasLease
    && session
    && session.status === 'active'
    && session.events.length > 0
    && (session.undo_history?.length ?? 0) > 0,
  )

  return {
    session,
    view,
    receipt,
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
    canUndo,
    undo,
    prepareDecision,
    answer,
    commit,
    requestTakeover,
  }
}
