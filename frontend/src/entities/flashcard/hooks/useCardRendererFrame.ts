import { useEffect, useRef, useState } from 'react'
import { resolveBackendUrl } from '@/shared/config/env'
import type { CardRendererFrameProps, RendererDiagnostic, RendererReadyEvent } from '../model/types'

declare global {
  interface Window {
    FlamaCardRendererHost?: {
      createRendererFrameController: (
        iframeEl: HTMLIFrameElement,
        options?: Record<string, unknown>,
      ) => {
        render: (payload: unknown, options?: Record<string, unknown>) => void
        reveal: (payload?: Record<string, unknown>) => void
        destroy: () => void
      }
      normalizeRendererSidePayload: (payload: unknown) => {
        html: string
        allowed_media_urls: string[]
        allowed_audio_urls: string[]
      }
      createNoticeHtml: (message: string) => string
    }
  }
}

let scriptLoadPromise: Promise<void> | null = null
const RENDERER_HOST_VERSION = 'renderer-diagnostics-v5'
const EMPTY_FIELD_DEFS: unknown[] = []
const EMPTY_FIELD_VALUES: Record<string, string> = {}

function ensureRendererScript(): Promise<void> {
  if (window.FlamaCardRendererHost) {
    return Promise.resolve()
  }
  if (scriptLoadPromise) {
    return scriptLoadPromise
  }
  scriptLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    const timeout = window.setTimeout(() => {
      scriptLoadPromise = null
      script.remove()
      reject(new Error('Card renderer host load timed out.'))
    }, 8000)
    script.src = resolveBackendUrl(
      `/static/js/card_renderer_host.js?v=${RENDERER_HOST_VERSION}`,
    )
    script.async = true
    script.onload = () => {
      window.clearTimeout(timeout)
      if (window.FlamaCardRendererHost) resolve()
      else {
        scriptLoadPromise = null
        reject(new Error('Card renderer host did not initialize.'))
      }
    }
    script.onerror = (err) => {
      window.clearTimeout(timeout)
      scriptLoadPromise = null
      script.remove()
      reject(err)
    }
    document.body.appendChild(script)
  })
  return scriptLoadPromise
}

export function useCardRendererFrame({
  cardId, noteId, revealed, frontPayload, backPayload, frontHtml, backHtml,
  scope = 'deck', scopeId, fieldDefs = EMPTY_FIELD_DEFS,
  fieldValues = EMPTY_FIELD_VALUES, active = true, enableLivePatch = false,
  fillHeight = false, candidateHash, mediaBaseUrl, onDiagnostic, onReady,
}: CardRendererFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const controllerRef = useRef<ReturnType<
    NonNullable<typeof window.FlamaCardRendererHost>['createRendererFrameController']
  > | null>(null)
  const lastRenderRef = useRef<readonly unknown[] | null>(null)
  const [scriptLoaded, setScriptLoaded] = useState(Boolean(window.FlamaCardRendererHost))
  const [scriptFailed, setScriptFailed] = useState(false)
  const activeSide: 'front' | 'back' = revealed ? 'back' : 'front'
  const callbackRef = useRef({ onDiagnostic, onReady })
  callbackRef.current = { onDiagnostic, onReady }
  const identityRef = useRef<RendererReadyEvent>({ cardId: cardId || '', candidateHash, side: activeSide })
  identityRef.current = { cardId: cardId || '', candidateHash, side: activeSide }
  const rawPayload = revealed
    ? backPayload || backHtml || ''
    : frontPayload || frontHtml || ''

  useEffect(() => {
    let mounted = true
    ensureRendererScript()
      .then(() => {
        if (mounted) {
          setScriptLoaded(true)
          setScriptFailed(false)
        }
      })
      .catch(() => {
        if (mounted) {
          setScriptLoaded(false)
          setScriptFailed(true)
          callbackRef.current.onDiagnostic?.({
            code: 'RENDERER_HOST_LOAD_FAILED', stage: 'host',
            message: 'Không thể tải trình hiển thị thẻ.', ...identityRef.current,
          })
        }
      })
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    if (!scriptLoaded) return
    const iframeEl = iframeRef.current
    if (!iframeEl) return
    const host = window.FlamaCardRendererHost
    if (!host) return

    const controller = host.createRendererFrameController(iframeEl, {
      minHeight: 240,
      autoHeight: !fillHeight,
      fillHeight,
      enableLivePatch,
      mediaBaseUrl: mediaBaseUrl || resolveBackendUrl('/'),
      onError: (diagnostic: RendererDiagnostic) => {
        if (callbackRef.current.onDiagnostic) callbackRef.current.onDiagnostic(diagnostic)
        else console.warn('Flama card renderer:', diagnostic.message)
      },
      onReady: (event: RendererReadyEvent) => callbackRef.current.onReady?.(event),
    })
    controllerRef.current = controller
    lastRenderRef.current = null

    return () => {
      if (controllerRef.current === controller) {
        controllerRef.current = null
        lastRenderRef.current = null
      }
      controller.destroy()
    }
  }, [scriptLoaded, enableLivePatch, fillHeight, mediaBaseUrl])

  useEffect(() => {
    if (!active || !scriptLoaded) return
    const controller = controllerRef.current
    const host = window.FlamaCardRendererHost
    if (!controller || !host) return
    // Both faces stay mounted. Merely showing an unchanged face again must
    // retain its interactive DOM state; data/source changes still render.
    const renderInputs = [
      controller, rawPayload, activeSide, cardId, noteId, scope, scopeId,
      fieldDefs, fieldValues, enableLivePatch, fillHeight, candidateHash, mediaBaseUrl,
    ]
    if (lastRenderRef.current?.every((value, index) => Object.is(value, renderInputs[index]))) return
    const normalizedPayload = host.normalizeRendererSidePayload(
      rawPayload || { html: '' },
    )
    const payloadForFrame = normalizedPayload.html.trim()
      ? normalizedPayload
      : { html: host.createNoticeHtml('Không có nội dung thẻ.') }

    controller.render(payloadForFrame, {
      padding: fillHeight ? '0' : '12px',
      background: 'transparent',
      color: 'initial',
      config: {
        mode: scope,
        side: activeSide,
        scope,
        scopeId: scopeId || '',
      },
      context: {
        cardId: cardId || '',
        noteId: noteId || '',
        candidateHash: candidateHash || '',
        fieldValues,
        fieldDefs,
      },
    })
    lastRenderRef.current = renderInputs
  }, [
    active,
    scriptLoaded,
    activeSide,
    cardId,
    noteId,
    rawPayload,
    scope,
    scopeId,
    fieldDefs,
    fieldValues,
    enableLivePatch,
    fillHeight,
    candidateHash,
    mediaBaseUrl,
  ])

  useEffect(() => {
    if (!active || !scriptLoaded) return
    controllerRef.current?.reveal({
      side: activeSide,
      reason: revealed ? 'show_answer' : 'load_card',
    })
  }, [
    active,
    scriptLoaded,
    activeSide,
    revealed,
    cardId,
    noteId,
    rawPayload,
    fieldDefs,
    fieldValues,
    enableLivePatch,
    fillHeight,
    candidateHash,
    mediaBaseUrl,
  ])

  return { iframeRef, scriptFailed, activeSide, rawPayload }
}
