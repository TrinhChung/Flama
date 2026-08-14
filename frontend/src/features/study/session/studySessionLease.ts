export type StudyLeaseHandlers = {
  onBlocked: () => void
  onAcquired: () => void
  onLost?: (error: unknown) => void
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
    throw new Error(
      'Trình duyệt không hỗ trợ khóa phiên học an toàn. Hãy mở ứng dụng bằng HTTPS trên một trình duyệt hiện đại rồi thử lại.',
    )
  }

  type RequestResult = 'acquired' | 'cancelled' | 'lost' | 'unavailable'

  const requestAndHold = async (
    requestOptions: LockOptions,
  ): Promise<RequestResult> => {
    let acquired = false
    try {
      return await lockManager.request(
        lockName,
        requestOptions,
        async (lock) => {
          if (!lock) return 'unavailable'
          if (signal.aborted) return 'cancelled'
          acquired = true
          handlers.onAcquired()
          await waitForAbort(signal)
          return 'acquired'
        },
      )
    } catch (caught) {
      if (acquired && !signal.aborted) {
        handlers.onLost?.(caught)
        return 'lost'
      }
      if (signal.aborted) return 'cancelled'
      throw caught
    }
  }

  if (signal.aborted) return
  // Web Locks also forbids combining `ifAvailable` with `signal`. Probe first
  // without a signal, then use an abortable queued request only when blocked.
  const immediateResult = await requestAndHold({
    mode: 'exclusive',
    ifAvailable: true,
  })
  if (immediateResult !== 'unavailable' || signal.aborted) return

  handlers.onBlocked()
  await requestAndHold({ mode: 'exclusive', signal })
}
