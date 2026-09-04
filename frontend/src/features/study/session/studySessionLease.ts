export const LEASE_EPOCH_PREFIX = 'flama-study-lease-epoch:'

export function getLeaseEpoch(scopeKey: string): number {
  try {
    const raw = globalThis.localStorage?.getItem(`${LEASE_EPOCH_PREFIX}${scopeKey}`)
    const parsed = raw ? parseInt(raw, 10) : 1
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1
  } catch {
    return 1
  }
}

export function incrementLeaseEpoch(scopeKey: string): number {
  const next = getLeaseEpoch(scopeKey) + 1
  try {
    globalThis.localStorage?.setItem(`${LEASE_EPOCH_PREFIX}${scopeKey}`, String(next))
  } catch {}
  return next
}

export function getStudyLockName(scopeKey: string, epoch: number = 1): string {
  if (epoch <= 1) {
    return `flama-study:${scopeKey}`
  }
  return `flama-study:${scopeKey}:epoch:${epoch}`
}

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
