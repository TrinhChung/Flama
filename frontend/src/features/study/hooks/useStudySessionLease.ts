import { useCallback, useEffect, useRef, useState } from 'react'
import { holdStudyScopeLease } from '../session/studySessionLease'
import type { PersistedStudySession } from '../session/sessionStore'

export const HANDOFF_CHANNEL_PREFIX = 'flama-study-handoff:v1:'
export const HANDOFF_RESPONSE_TIMEOUT_MS = 8_000
export const HANDOFF_COMPLETION_TIMEOUT_MS = 30_000

export type LeaseState = {
  key: string | null
  status: 'checking' | 'blocked' | 'error' | 'held' | 'transferred'
  error: unknown
}

export type TakeoverState =
  | 'idle'
  | 'requesting'
  | 'waiting'
  | 'yielding'
  | 'unavailable'

export type HandoffMessage = {
  type:
    | 'handoff-accepted'
    | 'handoff-rejected'
    | 'handoff-request'
  requester_id: string
}

export function isHandoffMessage(value: unknown): value is HandoffMessage {
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

export function waitForNextOperationCheck() {
  return new Promise<void>((resolve) => window.setTimeout(resolve, 25))
}

export function createLeaseClientId() {
  return globalThis.crypto?.randomUUID?.()
    ?? `lease-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

interface UseStudySessionLeaseParams {
  currentScopeKey: string | null
  activateSession: (session: PersistedStudySession | null) => void
  sessionRef: React.MutableRefObject<PersistedStudySession | null>
  sessionDurableRef: React.MutableRefObject<boolean>
  setLoading: (loading: boolean) => void
}

export function useStudySessionLease({
  currentScopeKey,
  activateSession,
  sessionRef,
  sessionDurableRef,
  setLoading,
}: UseStudySessionLeaseParams) {
  const [leaseState, setLeaseState] = useState<LeaseState>({
    key: null,
    status: 'checking',
    error: null,
  })
  const [takeoverState, setTakeoverState] = useState<TakeoverState>('idle')
  const [leaseAttempt, setLeaseAttempt] = useState(0)

  const leaseWorkCountsRef = useRef(new WeakMap<AbortController, number>())
  const bootstrapStartedRef = useRef(new WeakSet<AbortController>())
  const ownedLeaseControllersRef = useRef(new WeakSet<AbortController>())
  const hasLeaseRef = useRef(false)
  const leaseControllerRef = useRef<AbortController | null>(null)
  const leaseChannelRef = useRef<BroadcastChannel | null>(null)
  const handoffTargetRef = useRef<string | null>(null)
  const requestOnBlockedRef = useRef(false)
  const takeoverTimerRef = useRef<number | null>(null)
  const [leaseClientId] = useState(createLeaseClientId)

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
    setLoading,
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
    sessionDurableRef,
    sessionRef,
    setLoading,
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

  const isCurrentLease = useCallback((controller: AbortController) => (
    leaseControllerRef.current === controller
    && !controller.signal.aborted
  ), [])

  return {
    leaseState,
    takeoverState,
    hasLease,
    hasLeaseRef,
    leaseControllerRef,
    bootstrapStartedRef,
    ownedLeaseControllersRef,
    beginLeaseWork,
    endLeaseWork,
    hasLeaseWork,
    releaseLeaseWhenIdle,
    requestTakeover,
    isCurrentLease,
  }
}
