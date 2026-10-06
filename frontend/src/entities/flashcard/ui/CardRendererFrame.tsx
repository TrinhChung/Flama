import { useEffect, useMemo, useRef, useState } from 'react'
import { resolveBackendUrl } from '@/config/env'
import { cn } from '@/lib/utils'
import type {
  CardRendererFrameProps,
  CardRendererSlotContext,
} from '../model/types'

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
const RENDERER_HOST_VERSION = 'renderer-media-url-v3'
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
    script.src = resolveBackendUrl(
      `/static/js/card_renderer_host.js?v=${RENDERER_HOST_VERSION}`,
    )
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
  fillHeight = false,
  className,
  slots,
  headerSlot,
  footerSlot,
  toolbarSlot,
  overlaySlot,
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

  const slotContext: CardRendererSlotContext = useMemo(
    () => ({
      cardId,
      noteId,
      side: activeSide,
      isBack: revealed,
      isRevealed: revealed,
      scope,
      scopeId,
      fieldValues,
      activeFacePayload: rawPayload,
    }),
    [cardId, noteId, activeSide, revealed, scope, scopeId, fieldValues, rawPayload],
  )

  const activeHeader = slots?.header ?? headerSlot ?? slots?.topToolbar
  const activeFooter = slots?.footer ?? footerSlot ?? slots?.bottomToolbar
  const activeToolbar = slots?.toolbar ?? toolbarSlot
  const activeOverlay = slots?.overlay ?? overlaySlot

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
      autoHeight: !fillHeight,
      fillHeight,
      enableLivePatch,
      mediaBaseUrl: resolveBackendUrl('/'),
    })
    controllerRef.current = controller

    return () => {
      if (controllerRef.current === controller) {
        controllerRef.current = null
      }
      controller.destroy()
    }
  }, [scriptLoaded, enableLivePatch, fillHeight])

  useEffect(() => {
    if (!active || !scriptLoaded) return
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
        fieldValues,
        fieldDefs,
      },
    })
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

  const viewport = (
    <>
      <iframe
        ref={iframeRef}
        title={revealed ? 'Mặt sau thẻ' : 'Mặt trước thẻ'}
        sandbox="allow-scripts"
        allow="autoplay"
        className={cn(
          'card-face study-card-frame w-full border-0 bg-transparent p-0 m-0 min-h-[240px]',
          fillHeight && 'h-full min-h-0',
        )}
      />

      {/* Floating Toolbar Slot */}
      {activeToolbar && (
        <div className="study-card-slot-toolbar absolute top-2.5 right-2.5 z-10 pointer-events-auto">
          {typeof activeToolbar === 'function' ? activeToolbar(slotContext) : activeToolbar}
        </div>
      )}

      {/* Overlay Slot */}
      {activeOverlay && (
        <div className="study-card-slot-overlay absolute inset-0 z-20 pointer-events-none flex items-center justify-center">
          <div className="pointer-events-auto">
            {typeof activeOverlay === 'function' ? activeOverlay(slotContext) : activeOverlay}
          </div>
        </div>
      )}

      {scriptFailed ? (
        slots?.errorFallback ? (
          slots.errorFallback('Không thể tải trình hiển thị thẻ.')
        ) : (
          <div className="study-card-content p-4 text-center text-sm text-muted-foreground">
            Không thể tải trình hiển thị thẻ.
          </div>
        )
      ) : null}
    </>
  )

  return (
    <div
      className={cn(
        'study-card-shell w-full relative min-h-[240px]',
        fillHeight && 'h-full min-h-0',
        (activeHeader || activeFooter) && 'flex flex-col',
        className,
      )}
    >
      {/* Header Slot */}
      {activeHeader && (
        <div className="study-card-slot-header w-full shrink-0 pb-2.5">
          {typeof activeHeader === 'function' ? activeHeader(slotContext) : activeHeader}
        </div>
      )}

      {/* Frame Container */}
      {activeHeader || activeFooter ? (
        <div className={cn('relative w-full min-h-[240px]', fillHeight && 'flex-1 min-h-0 h-full')}>
          {viewport}
        </div>
      ) : viewport}

      {/* Footer Slot */}
      {activeFooter && (
        <div className="study-card-slot-footer w-full shrink-0 pt-2.5">
          {typeof activeFooter === 'function' ? activeFooter(slotContext) : activeFooter}
        </div>
      )}
    </div>
  )
}
