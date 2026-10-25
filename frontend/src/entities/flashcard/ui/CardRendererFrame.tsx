import { useMemo } from 'react'
import { useCardRendererFrame } from '../hooks/useCardRendererFrame'
import { cn } from '@/shared/lib'
import type {
  CardRendererFrameProps,
  CardRendererSlotContext,
} from '../model/types'

const EMPTY_FIELD_DEFS: unknown[] = []
const EMPTY_FIELD_VALUES: Record<string, string> = {}

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
  candidateHash,
  mediaBaseUrl,
  onDiagnostic,
  onReady,
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
  const { iframeRef, scriptFailed, activeSide, rawPayload } = useCardRendererFrame({
    cardId, noteId, revealed, frontPayload, backPayload, frontHtml, backHtml,
    scope, scopeId, fieldDefs, fieldValues, active, enableLivePatch, fillHeight,
    candidateHash, mediaBaseUrl, onDiagnostic, onReady,
  })

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
