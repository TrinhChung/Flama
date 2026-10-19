import { useCallback, useEffect, useRef, useState } from 'react'

export interface UseCopyToClipboardOptions {
  resetTimeout?: number
  onSuccess?: (text: string) => void
  onError?: (error: Error) => void
}

export interface UseCopyToClipboardReturn {
  copy: (text: string) => Promise<boolean>
  isCopied: boolean
  copiedText: string | null
  error: Error | null
}

/**
 * Robust copy-to-clipboard hook with fallback for non-secure contexts.
 */
export function useCopyToClipboard(
  options: UseCopyToClipboardOptions = {},
): UseCopyToClipboardReturn {
  const { resetTimeout = 2000, onSuccess, onError } = options

  const [copiedText, setCopiedText] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearTimer = useCallback(() => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }, [])

  useEffect(() => {
    return clearTimer
  }, [clearTimer])

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      clearTimer()
      setError(null)

      if (!text) {
        setCopiedText(null)
        return false
      }

      // 1. Try modern Navigator Clipboard API
      if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(text)
          setCopiedText(text)
          onSuccess?.(text)

          if (resetTimeout > 0) {
            timeoutRef.current = setTimeout(() => {
              setCopiedText(null)
            }, resetTimeout)
          }

          return true
        } catch (err) {
          // Continue to fallback
        }
      }

      // 2. Fallback to document.execCommand('copy')
      try {
        if (typeof document === 'undefined') {
          throw new Error('Document is not available for clipboard copy.')
        }

        const textArea = document.createElement('textarea')
        textArea.value = text
        textArea.style.position = 'fixed'
        textArea.style.left = '-9999px'
        textArea.style.top = '-9999px'
        textArea.setAttribute('readonly', '')
        document.body.appendChild(textArea)
        textArea.select()

        const successful = document.execCommand('copy')
        document.body.removeChild(textArea)

        if (!successful) {
          throw new Error('Failed to copy text using execCommand.')
        }

        setCopiedText(text)
        onSuccess?.(text)

        if (resetTimeout > 0) {
          timeoutRef.current = setTimeout(() => {
            setCopiedText(null)
          }, resetTimeout)
        }

        return true
      } catch (err) {
        const copyError = err instanceof Error ? err : new Error(String(err))
        setError(copyError)
        onError?.(copyError)
        setCopiedText(null)
        return false
      }
    },
    [clearTimer, resetTimeout, onSuccess, onError],
  )

  return {
    copy,
    isCopied: copiedText !== null,
    copiedText,
    error,
  }
}
