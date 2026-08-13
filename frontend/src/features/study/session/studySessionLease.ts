export type StudyLeaseHandlers = {
  onBlocked: () => void
  onAcquired: () => void
}

function waitForAbort(signal: AbortSignal) {
  if (signal.aborted) return Promise.resolve()
  return new Promise<void>((resolve) => {
    signal.addEventListener('abort', () => resolve(), { once: true })
  })
}

export async function holdStudyScopeLease(
  lockManager: LockManager | undefined,
  lockName: string,
  signal: AbortSignal,
  handlers: StudyLeaseHandlers,
) {
  if (!lockManager) {
    handlers.onAcquired()
    await waitForAbort(signal)
    return
  }

  const acquiredImmediately = await lockManager.request(
    lockName,
    { mode: 'exclusive', ifAvailable: true, signal },
    async (lock) => {
      if (!lock) return false
      handlers.onAcquired()
      await waitForAbort(signal)
      return true
    },
  )
  if (acquiredImmediately || signal.aborted) return

  handlers.onBlocked()
  await lockManager.request(
    lockName,
    { mode: 'exclusive', signal },
    async () => {
      handlers.onAcquired()
      await waitForAbort(signal)
    },
  )
}
