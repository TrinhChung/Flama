import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import { ApiError } from '@/shared/api/client'
import type {
  Rating,
  StudyMediaArtifact,
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
  acknowledgeStudySessionQuarantine,
  loadStudySessionWithDurability,
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
import { patchRenderContext } from '../renderer/clientRenderer'
import {
  useStudySessionLease,
  waitForNextOperationCheck,
} from './useStudySessionLease'

const openingRequests = new Map<string, Promise<StudySessionSnapshot>>()

type SessionMutationKind =
  | 'answer'
  | 'bootstrap'
  | 'commit'
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
    {
      scope: 'deck',
      scope_id: deckId,
      accepted_session_schema_versions: [
        'study-session.v3',
        'study-session.v2',
      ],
    },
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
  const mutationOwnerRef = useRef<SessionMutationOwner | null>(null)
  const mountedRef = useRef(true)
  const sessionRef = useRef<PersistedStudySession | null>(null)
  const sessionDurableRef = useRef(true)
  const exitFlushRef = useRef<string | null>(null)
  const recoveryAttemptRef = useRef<string | null>(null)

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
            if (serverSession.status !== 'open' || (serverSession.stale && active.events.length === 0)) {
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
    return session ? buildSessionView(session, now(), compositionFilter) : null
  }, [compositionFilter, now, session, tick])

  useEffect(() => {
    if (!session || !view?.card?.card_id) return
    if (session.active_card_id === view.card.card_id) return
    const controller = leaseControllerRef.current
    if (!controller || controller.signal.aborted || !hasLeaseRef.current) return
    void (async () => {
      const owner = await waitForMutation('selection-persist', controller)
      if (!owner) return
      beginLeaseWork(controller)
      try {
        if (!isCurrentLease(controller) || !hasLeaseRef.current) return
        const active = sessionRef.current
        if (!active) return
        const selectedCardId = buildSessionView(
          active,
          now(),
          compositionFilter,
        ).card?.card_id
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
    compositionFilter,
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
      const prepared = prepareCommit(active, options)
      if (isThisLease()) activateSession(prepared.session)
      sessionDurableRef.current = await saveStudySession(prepared.session)
      const result = await appApi.mutate<StudySessionCommitReceipt>(
        `/api/study/sessions/${prepared.session.snapshot.session_id}/commit`,
        'POST',
        prepared.payload,
      )
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
        const opened = await openSnapshot(userId, deckId)
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
          const result = caught.details
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
            const opened = await openSnapshot(userId, deckId)
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
  }, [busy, commit, hasLease, receipt, session, view])

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
        if (!active || active.events.length === 0) return
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
      const targetCards = current.snapshot.cards.filter(
        (c) => c.card_id === cardId || (options?.noteId && c.note_id === options.noteId),
      )
      if (targetCards.length === 0) return

      const updatedContents = { ...current.snapshot.contents }
      for (const card of targetCards) {
        const contentKey = card.content_key
        const template = current.snapshot.templates[card.template_key]
        const existingContent = updatedContents[contentKey]
        if (existingContent) {
        // Merge media assets
        const combinedMedia: StudyMediaArtifact[] = options?.media && options.media.length > 0
          ? [...options.media]
          : [...(existingContent.media || [])]

        // Synthesize any proxy URLs found in updatedFieldValues not yet in combinedMedia
        const existingProxyUrls = new Set(combinedMedia.map((m) => m.proxy_url))
        for (const [fieldName, val] of Object.entries(updatedFieldValues)) {
          if (typeof val === 'string') {
            const matches = val.match(/\/media\/proxy\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}/g)
            if (matches) {
              for (const pUrl of matches) {
                if (!existingProxyUrls.has(pUrl)) {
                  const assetId = pUrl.replace('/media/proxy/', '')
                  const lk = fieldName.toLowerCase()
                  const isAudio = lk.includes('audio') || lk.includes('sound') || lk.includes('voice')
                  combinedMedia.push({
                    id: assetId,
                    field_name: fieldName,
                    filename: `${assetId}`,
                    mime_type: isAudio ? 'audio/mpeg' : 'image/jpeg',
                    sha256: '',
                    proxy_url: pUrl,
                  })
                  existingProxyUrls.add(pUrl)
                }
              }
            }
          }
        }

        const nextRenderContext = patchRenderContext(
          existingContent.render_context || {},
          updatedFieldValues,
          template?.field_defs,
          combinedMedia,
        )
          updatedContents[contentKey] = {
            ...existingContent,
            field_values: {
              ...existingContent.field_values,
              ...updatedFieldValues,
            },
            render_context: nextRenderContext,
            media: combinedMedia,
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
    const controller = leaseControllerRef.current
    if (!controller || controller.signal.aborted || !hasLeaseRef.current) return
    const owner = await waitForMutation('template-update', controller)
    if (!owner) return
    beginLeaseWork(controller)
    try {
      if (!isCurrentLease(controller) || !hasLeaseRef.current) return
      const current = sessionRef.current
      if (!current) return

      const snapshot = current.snapshot
      const templateKeysToUpdate: string[] = []
      for (const [tplKey, tpl] of Object.entries(snapshot.templates)) {
        if (tpl && tpl.id === templateId) {
          templateKeysToUpdate.push(tplKey)
        }
      }
      if (templateKeysToUpdate.length === 0) return

    const versionNonce = Date.now().toString(36)
    const updatedTemplates = { ...snapshot.templates }
    const updatedCards = [...snapshot.cards]

    for (const oldKey of templateKeysToUpdate) {
      const existingTpl = updatedTemplates[oldKey]
      if (!existingTpl) continue
      const newVersion = `${existingTpl.version || 'v'}-${versionNonce}`
      const newKey = `${templateId}:${newVersion}`

      const newFrontSource = updated.front_source ?? updated.front_html ?? existingTpl.front_source
      const newBackSource = updated.back_source ?? updated.back_html ?? existingTpl.back_source
      const newSharedCss = updated.shared_css ?? existingTpl.shared_css

      updatedTemplates[newKey] = {
        ...existingTpl,
        version: newVersion,
        front_source: newFrontSource,
        back_source: newBackSource,
        shared_css: newSharedCss,
        front_inline_scripts: updated.front_inline_scripts ?? existingTpl.front_inline_scripts,
        back_inline_scripts: updated.back_inline_scripts ?? existingTpl.back_inline_scripts,
      }

      for (let i = 0; i < updatedCards.length; i++) {
        if (updatedCards[i].template_id === templateId || updatedCards[i].template_key === oldKey) {
          updatedCards[i] = {
            ...updatedCards[i],
            template_key: newKey,
          }
        }
      }

      if (oldKey !== newKey) {
        delete updatedTemplates[oldKey]
      }
    }

    const nextSession: PersistedStudySession = {
      ...current,
      snapshot: {
        ...snapshot,
        cards: updatedCards,
        templates: updatedTemplates,
      },
      updated_at_ms: Date.now(),
    }

      activateSession(nextSession)
      sessionDurableRef.current = await saveStudySession(nextSession)
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
    if (!force && (sessionRef.current?.events.length ?? 0) > 0) {
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
      const opened = await openSnapshot(userId, deckId)
      if (!isCurrentLease(controller) || !hasLeaseRef.current) return
      const next = createPersistedSession(opened)
      sessionDurableRef.current = await saveStudySession(next)
      if (!isCurrentLease(controller) || !hasLeaseRef.current) return
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
    const isUncommitted = session?.status === 'active' && Boolean(session?.events?.length)
    if (!isUncommitted || !session) return acc
    const batchDurationMs = session.events.reduce((sum, ev) => sum + (ev.duration_ms || 0), 0)
    const batchAgain = session.events.filter((ev) => ev.rating === 'again').length
    const batchHard = session.events.filter((ev) => ev.rating === 'hard').length
    const batchGood = session.events.filter((ev) => ev.rating === 'good').length
    const batchEasy = session.events.filter((ev) => ev.rating === 'easy').length
    return {
      total_reviews: acc.total_reviews + session.events.length,
      total_duration_ms: acc.total_duration_ms + batchDurationMs,
      again_count: acc.again_count + batchAgain,
      hard_count: acc.hard_count + batchHard,
      good_count: acc.good_count + batchGood,
      easy_count: acc.easy_count + batchEasy,
    }
  }, [session])

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
    canUndo,
    undo,
    prepareDecision,
    answer,
    commit,
    requestTakeover,
    forceTakeover,
    updateCardContent,
    updateTemplateContent,
    reloadSession,
  }
}
