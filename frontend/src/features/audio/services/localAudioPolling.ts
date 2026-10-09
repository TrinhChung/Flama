type LocalAudioPollingOptions<T> = {
  signal: AbortSignal
  intervalMs: number
  maxAttempts: number
  request: (signal: AbortSignal) => Promise<T>
  onResult: (result: T) => boolean | Promise<boolean>
  onExhausted?: () => void
}

/** Wait between settled requests so a slow desktop service never stacks polls. */
export function startLocalAudioPolling<T>({
  signal,
  intervalMs,
  maxAttempts,
  request,
  onResult,
  onExhausted,
}: LocalAudioPollingOptions<T>): void {
  if (signal.aborted) return

  let attempts = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  const stop = () => {
    clearTimeout(timer)
    signal.removeEventListener('abort', stop)
  }

  const poll = async () => {
    if (signal.aborted) return
    attempts++
    try {
      const result = await request(signal)
      if (signal.aborted) return
      const complete = await onResult(result)
      if (signal.aborted) return
      if (complete) {
        stop()
        return
      }
    } catch {
      // A failed request counts toward the same budget as an empty response.
      if (signal.aborted) return
    }

    if (attempts >= maxAttempts) {
      stop()
      onExhausted?.()
      return
    }
    timer = setTimeout(poll, intervalMs)
  }

  signal.addEventListener('abort', stop, { once: true })
  timer = setTimeout(poll, intervalMs)
}
