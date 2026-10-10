import { useCallback, useEffect, useState } from 'react'
import { useBlocker } from 'react-router-dom'
import type { PersistedStudySession } from '../session/sessionStore'

export type UseStudyNavigationBlockerOptions = {
  session: PersistedStudySession | null
  commit: (options: { reason: 'manual_exit' }) => Promise<unknown>
  discard?: () => Promise<unknown> | unknown
}

export function useStudyNavigationBlocker({
  session,
  commit,
  discard,
}: UseStudyNavigationBlockerOptions) {
  const uncommittedCount = session?.events?.length ?? 0
  const isSessionActive = session?.status === 'active'
  const hasUncommittedWork = Boolean(isSessionActive && uncommittedCount > 0)
  const [isExiting, setIsExiting] = useState(false)

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      hasUncommittedWork && currentLocation.pathname !== nextLocation.pathname,
  )

  useEffect(() => {
    if (!hasUncommittedWork) return
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [hasUncommittedWork])

  const handleSaveAndExit = useCallback(async () => {
    if (!session) {
      blocker.proceed?.()
      return
    }
    setIsExiting(true)
    try {
      await commit({ reason: 'manual_exit' })
      blocker.proceed?.()
    } catch (err) {
      console.error('Failed to commit study session before exit:', err)
      blocker.proceed?.()
    } finally {
      setIsExiting(false)
    }
  }, [blocker, commit, session])

  const handleDiscardAndExit = useCallback(async () => {
    try {
      await discard?.()
    } catch (err) {
      console.error('Failed to discard study session before exit:', err)
    } finally {
      blocker.proceed?.()
    }
  }, [blocker, discard])

  const handleContinueStudy = useCallback(() => {
    blocker.reset?.()
  }, [blocker])

  return {
    blocker,
    uncommittedCount,
    hasUncommittedWork,
    isExiting,
    handleSaveAndExit,
    handleDiscardAndExit,
    handleContinueStudy,
  }
}
