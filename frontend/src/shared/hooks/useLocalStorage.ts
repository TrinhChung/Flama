import { useCallback, useEffect, useState } from 'react'

export interface UseLocalStorageOptions<T> {
  serializer?: (value: T) => string
  deserializer?: (value: string) => T
  syncTabs?: boolean
  onError?: (error: unknown) => void
}

/**
 * Safely reads a value from localStorage with fallback.
 */
export function safeLocalStorageGet<T>(
  key: string,
  fallback: T,
  deserializer: (raw: string) => T = JSON.parse,
): T {
  if (typeof window === 'undefined' || !window.localStorage) {
    return fallback
  }

  try {
    const item = window.localStorage.getItem(key)
    if (item === null) return fallback
    return deserializer(item)
  } catch (error) {
    console.warn(`[safeLocalStorageGet] Failed to read key "${key}":`, error)
    return fallback
  }
}

/**
 * Safely writes a value to localStorage, preventing QuotaExceeded or Private Mode crashes.
 */
export function safeLocalStorageSet<T>(
  key: string,
  value: T,
  serializer: (val: T) => string = JSON.stringify,
): boolean {
  if (typeof window === 'undefined' || !window.localStorage) {
    return false
  }

  try {
    window.localStorage.setItem(key, serializer(value))
    return true
  } catch (error) {
    console.warn(`[safeLocalStorageSet] Failed to write key "${key}":`, error)
    return false
  }
}

/**
 * Safely removes a key from localStorage.
 */
export function safeLocalStorageRemove(key: string): boolean {
  if (typeof window === 'undefined' || !window.localStorage) {
    return false
  }

  try {
    window.localStorage.removeItem(key)
    return true
  } catch (error) {
    console.warn(`[safeLocalStorageRemove] Failed to remove key "${key}":`, error)
    return false
  }
}

/**
 * Type-safe, crash-resistant React hook for persistent localStorage state.
 */
export function useLocalStorage<T>(
  key: string,
  initialValue: T,
  options?: UseLocalStorageOptions<T>,
): [T, (value: T | ((val: T) => T)) => void, () => void] {
  const {
    serializer = JSON.stringify,
    deserializer = JSON.parse,
    syncTabs = true,
    onError,
  } = options || {}

  const [storedValue, setStoredValue] = useState<T>(() => {
    return safeLocalStorageGet(key, initialValue, deserializer)
  })

  const setValue = useCallback(
    (value: T | ((val: T) => T)) => {
      setStoredValue((prev) => {
        const nextValue = value instanceof Function ? value(prev) : value
        const success = safeLocalStorageSet(key, nextValue, serializer)
        if (!success && onError) {
          onError(new Error(`Failed to save key "${key}" to localStorage`))
        }
        return nextValue
      })
    },
    [key, serializer, onError],
  )

  const removeValue = useCallback(() => {
    safeLocalStorageRemove(key)
    setStoredValue(initialValue)
  }, [key, initialValue])

  // Cross-tab synchronization
  useEffect(() => {
    if (!syncTabs || typeof window === 'undefined') return

    const handleStorageEvent = (event: StorageEvent) => {
      if (event.key !== key || event.storageArea !== window.localStorage) return

      if (event.newValue === null) {
        setStoredValue(initialValue)
      } else {
        try {
          setStoredValue(deserializer(event.newValue))
        } catch (err) {
          onError?.(err)
          setStoredValue(initialValue)
        }
      }
    }

    window.addEventListener('storage', handleStorageEvent)
    return () => window.removeEventListener('storage', handleStorageEvent)
  }, [key, initialValue, deserializer, syncTabs, onError])

  return [storedValue, setValue, removeValue]
}
