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
  updateCardFieldValuesInSessions,
} from '../session/sessionStore'
import type {
  PersistedStudySession,
  StudyCommitReason,
} from '../session/sessionStore'
import {
  useStudySessionLease,
  waitForNextOperationCheck,
} from './useStudySessionLease'

const openingRequests = new Map<string, Promise<StudySessionSnapshot>>()

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

export function useStudySession(deckId: string | null, compositionFilter?: string | null) {
  const queryClient = useQueryClient()
  const bootstrapQuery = useBootstrap()
  const userId = bootstrapQuery.data?.user?.id ?? null
  const [session, setSession] = useState<PersistedStudySession | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(Boolean(deckId))
  const [busy, setBusy] = useState(false)
  const [receipt, setReceipt] = useState<StudySessionCommitReceipt | null>(null)
  const [tick, setTick] = useState(0)

  const clockRef = useRef<{
    serverAtMs: number
    performanceAtMs: number
  } | null>(null)
  const operationRef = useRef(false)
  const sessionRef = useRef<PersistedStudySession | null>(null)
  const sessionDurableRef = useRef(true)
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
    isCurrentLease,
  } = useStudySessionLease({
    currentScopeKey,
    activateSession,
    sessionRef,
    sessionDurableRef,
    setLoading,
  })

  // Bootstrap session data
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
    const isThisLease = () => isCurrentLease(controller)

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
        if (!isThisLease()) return
        if (loaded.quarantine) {
          throw new Error(
            `Phiên học đã lưu không tương thích (${loaded.quarantine.reason}) và đã được cách ly. Tải lại trang để mở một phiên mới; dữ liệu cũ vẫn được giữ để chẩn đoán.`,
          )
        }
        const expiresAt = restored
          ? Date.parse(restored.snapshot.expires_at)
          : 0
        let active = restored
        if (active && expiresAt <= Date.now()) {
          await removeStudySessionIfMatches(
            key,
            active.snapshot.session_id,
          )
          if (!isThisLease()) return
          active = null
        }
        if (active) {
          const activeSessionId = active.snapshot.session_id
          try {
            const serverSession = await appApi.get<StudySessionStatus>(
              `/api/study/sessions/${activeSessionId}`,
            )
            if (!isThisLease()) return
            if (serverSession.status !== 'open') {
              await removeStudySessionIfMatches(
                key,
                activeSessionId,
              )
              if (!isThisLease()) return
              active = null
            }
          } catch (caught) {
            if (!isThisLease()) return
            if (caught instanceof ApiError && caught.code === 'SESSION_NOT_FOUND') {
              await removeStudySessionIfMatches(
                key,
                activeSessionId,
              )
              if (!isThisLease()) return
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
          if (!isThisLease()) return
          active = createPersistedSession(opened)
          sessionDurableRef.current = await saveStudySession(active)
          if (!isThisLease()) return
        }
        if (hasLeaseRef.current) activateSession(active)
      } catch (caught) {
        if (isThisLease() && hasLeaseRef.current) setError(caught)
      } finally {
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
    return session ? buildSessionView(session, now(), compositionFilter) : null
  }, [compositionFilter, now, session, tick])

  useEffect(() => {
    if (!session || !view?.card?.card_id) return
    if (session.active_card_id !== view.card.card_id) {
      const nextSession: PersistedStudySession = {
        ...session,
        active_card_id: view.card.card_id,
        updated_at_ms: Date.now(),
      }
      activateSession(nextSession)
      void saveStudySession(nextSession)
    }
  }, [activateSession, session, view?.card?.card_id])

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
    if (!active || !controller || controller.signal.aborted || !hasLeaseRef.current) {
      throw new Error('Study session lease is not held by this window.')
    }
    setBusy(true)
    operationRef.current = true
    beginLeaseWork(controller)
    try {
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
      operationRef.current = false
      endLeaseWork(controller)
      setBusy(false)
    }
  }, [activateSession, beginLeaseWork, endLeaseWork, hasLeaseRef, leaseControllerRef])

  const undo = useCallback(async (): Promise<string | null> => {
    const active = sessionRef.current
    const controller = leaseControllerRef.current
    if (!active || !controller || controller.signal.aborted || !hasLeaseRef.current) {
      throw new Error('Study session lease is not held by this window.')
    }
    setBusy(true)
    operationRef.current = true
    beginLeaseWork(controller)
    try {
      const undoResult = undoLocalAnswer(active)
      if (!undoResult) return null
      activateSession(undoResult.session)
      sessionDurableRef.current = await saveStudySession(undoResult.session)
      return undoResult.undoneCardId
    } finally {
      operationRef.current = false
      endLeaseWork(controller)
      setBusy(false)
    }
  }, [activateSession, beginLeaseWork, endLeaseWork, hasLeaseRef, leaseControllerRef])

  const commit = useCallback(async (options?: {
    reason?: StudyCommitReason
    resumeAfterCommit?: boolean
  }) => {
    const active = sessionRef.current
    const controller = leaseControllerRef.current
    if (
      !active
      || !controller
      || controller.signal.aborted
      || !hasLeaseRef.current
      || userId === null
      || !deckId
    ) {
      throw new Error('Study session lease is not held by this window.')
    }
    const isThisLease = () => isCurrentLease(controller)
    setBusy(true)
    operationRef.current = true
    beginLeaseWork(controller)
    try {
      const prepared = prepareCommit(active, options)
      if (isThisLease()) activateSession(prepared.session)
      sessionDurableRef.current = await saveStudySession(prepared.session)
      const result = await appApi.mutate<StudySessionCommitReceipt>(
        `/api/study/sessions/${prepared.session.snapshot.session_id}/commit`,
        'POST',
        prepared.payload,
      )
      if (!isThisLease()) return result
      const reconciled = applyCommitReceipt(prepared.session, result)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
        queryClient.invalidateQueries({ queryKey: ['stats'] }),
      ])
      if (!isThisLease()) return result
      if (prepared.session.resume_after_commit) {
        const opened = await openSnapshot(userId, deckId)
        if (!isThisLease()) return result
        const next = createPersistedSession(opened)
        sessionDurableRef.current = await saveStudySession(next)
        if (!isThisLease()) return result
        activateSession(next)
        setReceipt(null)
      } else {
        await removeStudySessionIfMatches(
          prepared.session.scope_key,
          prepared.session.snapshot.session_id,
        )
        if (!isThisLease()) return result
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
          const result = caught.details
          const reconciled = applyCommitReceipt(pending, result)
          await Promise.all([
            queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] }),
            queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] }),
            queryClient.invalidateQueries({ queryKey: ['stats'] }),
          ])
          if (!isThisLease()) return result
          if (pending.resume_after_commit) {
            const opened = await openSnapshot(userId, deckId)
            if (!isThisLease()) return result
            const next = createPersistedSession(opened)
            sessionDurableRef.current = await saveStudySession(next)
            if (!isThisLease()) return result
            activateSession(next)
            setReceipt(null)
          } else {
            await removeStudySessionIfMatches(
              pending.scope_key,
              pending.snapshot.session_id,
            )
            if (!isThisLease()) return result
            activateSession(reconciled)
            setReceipt(result)
          }
          return result
        }
      }
      if (isThisLease() && hasLeaseRef.current) setError(caught)
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
    hasLeaseRef,
    isCurrentLease,
    leaseControllerRef,
    queryClient,
    userId,
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
  }, [beginLeaseWork, endLeaseWork, leaseControllerRef, ownedLeaseControllersRef, queryClient])

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
    options?: { noteId?: string | null; skipBroadcast?: boolean },
  ) => {
    const current = sessionRef.current
    if (!current) return
    const targetCards = current.snapshot.cards.filter(
      (c) => c.card_id === cardId || (options?.noteId && c.note_id === options.noteId),
    )
    if (targetCards.length === 0) return

    const updatedContents = { ...current.snapshot.contents }
    for (const card of targetCards) {
      const contentKey = card.content_key
      const existingContent = updatedContents[contentKey]
      if (existingContent) {
        updatedContents[contentKey] = {
          ...existingContent,
          field_values: {
            ...existingContent.field_values,
            ...updatedFieldValues,
          },
        }
      }
    }

    const nextSession: PersistedStudySession = {
      ...current,
      snapshot: {
        ...current.snapshot,
        contents: updatedContents,
      },
      updated_at_ms: Date.now(),
    }

    activateSession(nextSession)
    try {
      sessionDurableRef.current = await saveStudySession(nextSession)
    } catch {
      // Retain in-memory copy
    }
    if (!options?.skipBroadcast) {
      await updateCardFieldValuesInSessions(cardId, updatedFieldValues, { noteId: options?.noteId })
    }
  }, [activateSession])

  // Synchronize card content updates in real-time (from Browse, Note Modal, or other tabs)
  useEffect(() => {
    const handleSync = (detail: { cardId?: string; noteId?: string | null; fieldValues?: Record<string, string> }) => {
      if (!detail?.cardId || !detail?.fieldValues) return
      void updateCardContent(detail.cardId, detail.fieldValues, {
        noteId: detail.noteId,
        skipBroadcast: true,
      })
    }

    const handleWindowCustomEvent = (event: Event) => {
      const customEvent = event as CustomEvent
      handleSync(customEvent.detail)
    }

    window.addEventListener('flama_study_card_updated', handleWindowCustomEvent)

    let broadcastChannel: BroadcastChannel | null = null
    try {
      broadcastChannel = new BroadcastChannel('flama_study_sync_channel')
      broadcastChannel.onmessage = (event) => {
        if (event.data?.type === 'CARD_UPDATED') {
          handleSync({
            cardId: event.data.cardId,
            noteId: event.data.noteId,
            fieldValues: event.data.fieldValues,
          })
        }
      }
    } catch {}

    return () => {
      window.removeEventListener('flama_study_card_updated', handleWindowCustomEvent)
      if (broadcastChannel) {
        broadcastChannel.close()
      }
    }
  }, [updateCardContent])

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
    updateCardContent,
  }
}
