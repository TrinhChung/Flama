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
} from '../session/studySessionEngine'
import {
  loadStudySession,
  removeStudySession,
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

type LeaseState = {
  key: string | null
  status: 'checking' | 'blocked' | 'held'
  error: unknown
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
  const [receipt, setReceipt] = useState<StudySessionCommitReceipt | null>(null)
  const [tick, setTick] = useState(0)
  const clockRef = useRef<{
    serverAtMs: number
    performanceAtMs: number
  } | null>(null)
  const operationRef = useRef(false)
  const sessionRef = useRef<PersistedStudySession | null>(null)
  const hasLeaseRef = useRef(false)
  const exitFlushRef = useRef<string | null>(null)
  const recoveryAttemptRef = useRef<string | null>(null)
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

  useEffect(() => {
    if (!currentScopeKey) {
      hasLeaseRef.current = true
      setLeaseState({ key: null, status: 'held', error: null })
      return
    }
    let disposed = false
    const controller = new AbortController()
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
        },
        onAcquired: () => {
          if (disposed) return
          hasLeaseRef.current = true
          setLoading(true)
          setLeaseState({
            key: currentScopeKey,
            status: 'held',
            error: null,
          })
        },
      },
    ).catch((caught) => {
      if (disposed || controller.signal.aborted) return
      setLoading(false)
      setLeaseState({
        key: currentScopeKey,
        status: 'blocked',
        error: caught,
      })
    })
    return () => {
      disposed = true
      controller.abort()
    }
  }, [activateSession, currentScopeKey])

  useEffect(() => {
    if (!deckId || userId === null) {
      activateSession(null)
      setLoading(Boolean(deckId))
      return
    }
    if (
      !currentScopeKey
      || leaseState.key !== currentScopeKey
      || leaseState.status !== 'held'
    ) return
    let cancelled = false
    const key = currentScopeKey
    setLoading(true)
    setError(null)
    setReceipt(null)
    void (async () => {
      try {
        const restored = await loadStudySession(key)
        const expiresAt = restored
          ? Date.parse(restored.snapshot.expires_at)
          : 0
        let active = restored
        if (active && expiresAt <= Date.now()) {
          await removeStudySession(key)
          active = null
        }
        if (active) {
          try {
            const serverSession = await appApi.get<StudySessionStatus>(
              `/api/study/sessions/${active.snapshot.session_id}`,
            )
            if (serverSession.status !== 'open') {
              await removeStudySession(key)
              active = null
            }
          } catch (caught) {
            if (caught instanceof ApiError && caught.code === 'SESSION_NOT_FOUND') {
              await removeStudySession(key)
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
          active = createPersistedSession(await openSnapshot(userId, deckId))
          await saveStudySession(active)
        }
        if (cancelled) return
        activateSession(active)
      } catch (caught) {
        if (!cancelled) setError(caught)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [
    activateSession,
    currentScopeKey,
    deckId,
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
    if (!active || !hasLeaseRef.current || operationRef.current) return
    operationRef.current = true
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
      await saveStudySession(optimisticSession)
    } catch (caught) {
      if (sessionRef.current === optimisticSession) {
        activateSession(active)
      }
      setError(caught)
      throw caught
    } finally {
      operationRef.current = false
      setBusy(false)
    }
  }, [activateSession])

  const commit = useCallback(async (
    options: {
      reason?: StudyCommitReason
      resumeAfterCommit?: boolean
    } = {},
  ) => {
    const active = sessionRef.current
    if (
      !active
      || !deckId
      || userId === null
      || !hasLeaseRef.current
      || operationRef.current
    ) return null
    operationRef.current = true
    setBusy(true)
    setError(null)
    try {
      const resumeAfterCommit = options.resumeAfterCommit
        ?? active.resume_after_commit
      const prepared = prepareCommit(active, {
        reason: options.reason,
        resumeAfterCommit,
      })
      await saveStudySession(prepared.session)
      activateSession(prepared.session)
      const result = await appApi.mutate<StudySessionCommitReceipt>(
        `/api/study/sessions/${active.snapshot.session_id}/commit`,
        'POST',
        prepared.payload,
      )
      const reconciled = applyCommitReceipt(prepared.session, result)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
        queryClient.invalidateQueries({ queryKey: ['stats'] }),
      ])
      if (resumeAfterCommit) {
        const next = createPersistedSession(
          await openSnapshot(userId, deckId),
        )
        await saveStudySession(next)
        activateSession(next)
        setReceipt(null)
      } else {
        activateSession(reconciled)
        setReceipt(result)
        await removeStudySession(prepared.session.scope_key)
      }
      return result
    } catch (caught) {
      if (
        caught instanceof ApiError
        && caught.code === 'SESSION_ALREADY_COMMITTED'
        && isCommitReceipt(caught.details)
      ) {
        const pending = sessionRef.current
        if (pending) {
          const result = caught.details
          const reconciled = applyCommitReceipt(pending, result)
          await Promise.all([
            queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
            queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
            queryClient.invalidateQueries({ queryKey: ['stats'] }),
          ])
          if (pending.resume_after_commit) {
            const next = createPersistedSession(
              await openSnapshot(userId, deckId),
            )
            await saveStudySession(next)
            activateSession(next)
            setReceipt(null)
          } else {
            activateSession(reconciled)
            setReceipt(result)
            await removeStudySession(pending.scope_key)
          }
          return result
        }
      }
      setError(caught)
      throw caught
    } finally {
      operationRef.current = false
      setBusy(false)
    }
  }, [activateSession, deckId, queryClient, userId])

  const hasLease = Boolean(
    currentScopeKey
    && leaseState.key === currentScopeKey
    && leaseState.status === 'held',
  )

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
    if (
      !active
      || active.events.length === 0
      || !hasLeaseRef.current
    ) return
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
    sessionRef.current = prepared.session
    void saveStudySession(prepared.session)
    void appApi.mutateKeepalive<StudySessionCommitReceipt>(
      `/api/study/sessions/${prepared.session.snapshot.session_id}/commit`,
      'POST',
      prepared.payload,
    ).then(async () => {
      await removeStudySessionIfMatches(
        prepared.session.scope_key,
        prepared.session.snapshot.session_id,
      )
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
        queryClient.invalidateQueries({ queryKey: ['stats'] }),
      ])
    }).catch(() => {
      // The pending batch remains durable in IndexedDB and can be retried.
    })
  }, [queryClient])

  useEffect(() => {
    const handlePageHide = () => flushOnExit()
    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted) window.location.reload()
    }
    window.addEventListener('pagehide', handlePageHide)
    window.addEventListener('pageshow', handlePageShow)
    return () => {
      window.removeEventListener('pagehide', handlePageHide)
      window.removeEventListener('pageshow', handlePageShow)
      flushOnExit()
    }
  }, [deckId, flushOnExit, userId])

  return {
    session,
    view,
    receipt,
    error: leaseState.error
      || (
        currentScopeKey
        && leaseState.key === currentScopeKey
        && leaseState.status === 'blocked'
          ? new Error('Phiên học đang được mở trong một tab khác. Tab này sẽ tự tiếp tục khi tab kia đóng.')
          : error
      ),
    isLoading: loading,
    isBusy: busy,
    prepareDecision,
    answer,
    commit,
  }
}
