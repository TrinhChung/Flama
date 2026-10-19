import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * Hook that debounces a value by delayMs.
 * Only updates the debounced value after the specified delay has passed with no new updates.
 */
export function useDebounce<T>(value: T, delayMs = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delayMs)

    return () => {
      clearTimeout(timer)
    }
  }, [value, delayMs])

  return debouncedValue
}

/**
 * Hook that debounces a callback function by delayMs.
 * Returns a stable memoized function that cancels previous invocations.
 */
export function useDebouncedCallback<Args extends unknown[]>(
  callback: (...args: Args) => void,
  delayMs = 300,
): {
  (...args: Args): void
  cancel: () => void
} {
  const callbackRef = useRef(callback)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  const cancel = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const debouncedFn = useCallback(
    (...args: Args) => {
      cancel()
      timerRef.current = setTimeout(() => {
        callbackRef.current(...args)
        timerRef.current = null
      }, delayMs)
    },
    [cancel, delayMs],
  )

  useEffect(() => {
    return cancel
  }, [cancel])

  return Object.assign(debouncedFn, { cancel })
}
