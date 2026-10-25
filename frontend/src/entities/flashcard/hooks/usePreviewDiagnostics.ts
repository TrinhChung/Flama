import { useCallback, useEffect, useRef, useState } from 'react'
import type { RendererDiagnostic } from '../model/types'

interface PreviewDiagnosticsOptions {
  cardId: string
  candidateHash?: string
  frontPayload?: unknown
  backPayload?: unknown
  frontHtml?: string
  backHtml?: string
  onDiagnostic?: (diagnostic: RendererDiagnostic) => void
}

/** Reports carry text only. A card cannot turn a diagnostic into a host action. */
export function usePreviewDiagnostics({
  cardId, candidateHash, frontPayload, backPayload, frontHtml, backHtml, onDiagnostic,
}: PreviewDiagnosticsOptions) {
  const [diagnostics, setDiagnostics] = useState<RendererDiagnostic[]>([])
  const callbackRef = useRef(onDiagnostic)
  callbackRef.current = onDiagnostic
  const identityRef = useRef({ cardId, candidateHash })
  identityRef.current = { cardId, candidateHash }

  useEffect(() => {
    setDiagnostics([])
  }, [cardId, candidateHash, frontPayload, backPayload, frontHtml, backHtml])

  const reportDiagnostic = useCallback((diagnostic: RendererDiagnostic) => {
    const current = identityRef.current
    if (diagnostic.cardId && diagnostic.cardId !== current.cardId) return
    if (diagnostic.candidateHash && diagnostic.candidateHash !== current.candidateHash) return
    const bounded = { ...diagnostic, message: diagnostic.message.slice(0, 1000) }
    setDiagnostics((items) => {
      if (items.length >= 20 || items.some((item) => item.code === bounded.code && item.side === bounded.side && item.message === bounded.message)) return items
      return [...items, bounded]
    })
    callbackRef.current?.(bounded)
  }, [])

  return { diagnostics, reportDiagnostic }
}
