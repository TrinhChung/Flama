import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import type { Rating } from '../types'
import type {
  StudySessionCommitReceipt,
  StudySessionSnapshot,
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
import type { PersistedStudySession } from '../session/sessionStore'

const openingRequests = new Map<string, Promise<StudySessionSnapshot>>()

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
  const [hasLease, setHasLease] = useState(true)
  const [receipt, setReceipt] = useState<StudySessionCommitReceipt | null>(null)
  const [tick, setTick] = useState(0)
  const clockRef = useRef<{
    serverAtMs: number
    performanceAtMs: number
  } | null>(null)
  const operationRef = useRef(false)
  const sessionRef = useRef<PersistedStudySession | null>(null)
  const hasLeaseRef = useRef(true)
  const exitFlushRef = useRef<string | null>(null)
  const recoveryAttemptRef = useRef<string | null>(null)

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
    if (!deckId || userId === null) {
      activateSession(null)
      setLoading(Boolean(deckId))
      return
    }
    let cancelled = false
    const key = scopeKey(userId, 'deck', deckId)
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
  }, [activateSession, deckId, userId])

  useEffect(() => {
    if (!session) return
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [session])

  useEffect(() => {
    const sessionId = session?.snapshot.session_id
    if (!sessionId || !navigator.locks) {
      hasLeaseRef.current = true
      setHasLease(true)
      return
    }
    let release: (() => void) | null = null
    let disposed = false
    void navigator.locks.request(
      `flama-study:${sessionId}`,
      { mode: 'exclusive', ifAvailable: true },
      async (lock) => {
        if (!lock) {
          if (!disposed) {
            hasLeaseRef.current = false
            setHasLease(false)
          }
          return
        }
        if (!disposed) {
          hasLeaseRef.current = true
          setHasLease(true)
        }
        await new Promise<void>((resolve) => {
          release = resolve
        })
      },
    ).catch(() => {
      if (!disposed) {
        hasLeaseRef.current = true
        setHasLease(true)
      }
    })
    return () => {
      disposed = true
      release?.()
    }
  }, [session?.snapshot.session_id])

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
    options: { resumeAfterCommit?: boolean } = {},
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
      const prepared = prepareCommit(active, { resumeAfterCommit })
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
      setError(caught)
      throw caught
    } finally {
      operationRef.current = false
      setBusy(false)
    }
  }, [activateSession, deckId, queryClient, userId])

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
    error: !hasLease
      ? new Error('Phiên học đang được mở trong một tab khác.')
      : error,
    isLoading: loading,
    isBusy: busy,
    prepareDecision,
    answer,
    commit,
  }
}
