import { useEffect, useRef, useState } from 'react'

declare global {
  interface Window {
    FlamaCardRendererHost?: {
      createRendererFrameController: (
        iframeEl: HTMLIFrameElement,
        options?: Record<string, unknown>,
      ) => {
        render: (payload: unknown, options?: Record<string, unknown>) => void
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
}

let scriptLoadPromise: Promise<void> | null = null

function ensureRendererScript(): Promise<void> {
  if (window.FlamaCardRendererHost) {
    return Promise.resolve()
  }
  if (scriptLoadPromise) {
    return scriptLoadPromise
  }
  scriptLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = '/static/js/card_renderer_host.js'
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
  fieldDefs = [],
  fieldValues = {},
}: CardRendererFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const controllerRef = useRef<ReturnType<
    NonNullable<typeof window.FlamaCardRendererHost>['createRendererFrameController']
  > | null>(null)
  const [scriptLoaded, setScriptLoaded] = useState(Boolean(window.FlamaCardRendererHost))

  useEffect(() => {
    let mounted = true
    ensureRendererScript()
      .then(() => {
        if (mounted) setScriptLoaded(true)
      })
      .catch(() => {
        if (mounted) setScriptLoaded(false)
      })
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    const iframeEl = iframeRef.current
    if (!iframeEl) return
    const host = window.FlamaCardRendererHost
    if (!host) return

    if (!controllerRef.current) {
      controllerRef.current = host.createRendererFrameController(iframeEl, {
        minHeight: 240,
        autoHeight: true,
      })
    }

    const activeSide = revealed ? 'back' : 'front'
    const rawPayload = revealed
      ? backPayload || backHtml || ''
      : frontPayload || frontHtml || ''

    const normalizedPayload = host.normalizeRendererSidePayload(
      rawPayload || { html: '' },
    )
    const payloadForFrame = normalizedPayload.html.trim()
      ? normalizedPayload
      : { html: host.createNoticeHtml('Không có nội dung thẻ.') }

    controllerRef.current.render(payloadForFrame, {
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
      revealOnReady: {
        side: activeSide,
        reason: revealed ? 'show_answer' : 'load_card',
      },
    })
  }, [
    scriptLoaded,
    revealed,
    cardId,
    noteId,
    frontPayload,
    backPayload,
    frontHtml,
    backHtml,
    scope,
    scopeId,
    fieldDefs,
    fieldValues,
  ])

  const rawFallbackHtml = revealed ? backHtml || '' : frontHtml || ''

  return (
    <div className="study-card-shell w-full relative min-h-[240px]">
      <iframe
        ref={iframeRef}
        title={revealed ? 'Mặt sau thẻ' : 'Mặt trước thẻ'}
        sandbox="allow-scripts"
        className="card-face study-card-frame w-full border-0 bg-transparent p-0 m-0 min-h-[240px]"
      />
      {!scriptLoaded && rawFallbackHtml ? (
        <div
          className="study-card-content p-4 text-center flex flex-col justify-center items-center"
          dangerouslySetInnerHTML={{ __html: rawFallbackHtml }}
        />
      ) : null}
    </div>
  )
}
