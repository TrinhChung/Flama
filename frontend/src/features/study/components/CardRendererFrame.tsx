import { useEffect, useRef, useState } from 'react'
import { resolveBackendUrl } from '@/config/env'

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

type CardRendererFrameProps = {
  cardId?: string | null
  noteId?: string | null
  revealed: boolean
  frontPayload?: unknown
  backPayload?: unknown
  frontHtml?: string
  backHtml?: string
  scope?: string
  scopeId?: string | null
  fieldDefs?: unknown[]
  fieldValues?: Record<string, string>
  active?: boolean
  enableLivePatch?: boolean
}

let scriptLoadPromise: Promise<void> | null = null
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
    script.src = resolveBackendUrl('/static/js/card_renderer_host.js')
    script.async = true
    script.onload = () => resolve()
    script.onerror = (err) => {
      scriptLoadPromise = null
      reject(err)
    }
    document.body.appendChild(script)
  })
  return scriptLoadPromise
}

export function CardRendererFrame({
  cardId,
  noteId,
  revealed,
  frontPayload,
  backPayload,
  frontHtml,
  backHtml,
  scope = 'deck',
  scopeId,
  fieldDefs = EMPTY_FIELD_DEFS,
  fieldValues = EMPTY_FIELD_VALUES,
  active = true,
  enableLivePatch = false,
}: CardRendererFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const controllerRef = useRef<ReturnType<
    NonNullable<typeof window.FlamaCardRendererHost>['createRendererFrameController']
  > | null>(null)
  const [scriptLoaded, setScriptLoaded] = useState(Boolean(window.FlamaCardRendererHost))
  const [scriptFailed, setScriptFailed] = useState(false)
  const activeSide = revealed ? 'back' : 'front'
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
      autoHeight: true,
      enableLivePatch,
    })
    controllerRef.current = controller

    return () => {
      if (controllerRef.current === controller) {
        controllerRef.current = null
      }
      controller.destroy()
    }
  }, [scriptLoaded, enableLivePatch])

  useEffect(() => {
    if (!scriptLoaded) return
    const controller = controllerRef.current
    const host = window.FlamaCardRendererHost
    if (!controller || !host) return
    const normalizedPayload = host.normalizeRendererSidePayload(
      rawPayload || { html: '' },
    )
    const payloadForFrame = normalizedPayload.html.trim()
      ? normalizedPayload
      : { html: host.createNoticeHtml('Không có nội dung thẻ.') }

    controller.render(payloadForFrame, {
      padding: '12px',
      background: 'transparent',
      color: 'initial',
      config: {
        mode: 'shared_deck_preview',
        side: activeSide,
        scope,
        scopeId: scopeId || '',
      },
      context: {
        cardId: cardId || '',
        noteId: noteId || '',
        fieldValues,
        fieldDefs,
      },
    })
  }, [
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
  ])

  return (
    <div className="study-card-shell w-full relative min-h-[240px]">
      <iframe
        ref={iframeRef}
        title={revealed ? 'Mặt sau thẻ' : 'Mặt trước thẻ'}
        sandbox="allow-scripts"
        className="card-face study-card-frame w-full border-0 bg-transparent p-0 m-0 min-h-[240px]"
      />
      {scriptFailed ? (
        <div className="study-card-content p-4 text-center text-sm text-muted-foreground">
          Không thể tải trình hiển thị thẻ.
        </div>
      ) : null}
    </div>
  )
}
