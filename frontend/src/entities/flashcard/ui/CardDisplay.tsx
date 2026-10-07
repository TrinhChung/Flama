import { useMemo } from 'react'
import { cn } from '@/lib/utils'
import { CardRendererFrame } from './CardRendererFrame'
import type {
  CardDisplayProps,
  CardRendererSlotContext,
} from '../model/types'

const EMPTY_FIELD_DEFS: unknown[] = []
const EMPTY_FIELD_VALUES: Record<string, string> = {}

/**
 * Shared, fixed-viewport card display used by Study, NoteType editor, and Marketplace.
 * Both faces remain mounted so flipping a card does not rebuild its template.
 * Supports Abstract Slots projection for extensibility.
 */
export function CardDisplay({
  cardId,
  noteId,
  side,
  frontPayload,
  backPayload,
  frontHtml,
  backHtml,
  scope = 'deck',
  scopeId,
  fieldDefs = EMPTY_FIELD_DEFS,
  fieldValues = EMPTY_FIELD_VALUES,
  enableLivePatch = true,
  className,
  slots,
  headerSlot,
  footerSlot,
  toolbarSlot,
  overlaySlot,
}: CardDisplayProps) {
  const isBack = side === 'back'
  const activeSide = isBack ? 'back' : 'front'
  const activePayload = isBack
    ? backPayload || backHtml
    : frontPayload || frontHtml

  const slotContext: CardRendererSlotContext = useMemo(
    () => ({
      cardId,
      noteId,
      side: activeSide,
      isBack,
      isRevealed: isBack,
      scope,
      scopeId,
      fieldValues,
      activeFacePayload: activePayload,
    }),
    [cardId, noteId, activeSide, isBack, scope, scopeId, fieldValues, activePayload],
  )

  const activeHeader = slots?.header ?? headerSlot ?? slots?.topToolbar
  const activeFooter = slots?.footer ?? footerSlot ?? slots?.bottomToolbar
  const activeToolbar = slots?.toolbar ?? toolbarSlot
  const activeOverlay = slots?.overlay ?? overlaySlot

  const hasContent = Boolean(
    frontPayload !== undefined ||
    backPayload !== undefined ||
    frontHtml ||
    backHtml,
  )

  if (!hasContent && slots?.emptyState) {
    return (
      <div className={cn('study-card-shell relative h-full min-h-[240px] w-full min-w-0 overflow-hidden flex items-center justify-center', className)}>
        {typeof slots.emptyState === 'function' ? slots.emptyState(slotContext) : slots.emptyState}
      </div>
    )
  }

  const viewport = (
    <>
      {/* Front Face Frame */}
      <div
        className={cn('h-full min-h-0 w-full', isBack && 'hidden')}
        aria-hidden={isBack}
      >
        <CardRendererFrame
          key={`front:${cardId || ''}`}
          cardId={cardId}
          noteId={noteId}
          revealed={false}
          active={!isBack}
          frontPayload={frontPayload}
          frontHtml={frontHtml}
          scope={scope}
          scopeId={scopeId}
          fieldDefs={fieldDefs}
          fieldValues={fieldValues}
          enableLivePatch={enableLivePatch}
          fillHeight
        />
      </div>

      {/* Back Face Frame */}
      <div
        className={cn('h-full min-h-0 w-full', !isBack && 'hidden')}
        aria-hidden={!isBack}
      >
        <CardRendererFrame
          key={`back:${cardId || ''}`}
          cardId={cardId}
          noteId={noteId}
          revealed
          active={isBack}
          backPayload={backPayload}
          backHtml={backHtml}
          scope={scope}
          scopeId={scopeId}
          fieldDefs={fieldDefs}
          fieldValues={fieldValues}
          enableLivePatch={enableLivePatch}
          fillHeight
        />
      </div>

      {/* 3. Floating Toolbar Slot Zone */}
      {activeToolbar && (
        <div className="study-card-slot-toolbar absolute top-2.5 right-2.5 z-10 pointer-events-auto">
          {typeof activeToolbar === 'function' ? activeToolbar(slotContext) : activeToolbar}
        </div>
      )}

      {/* 4. Overlay Slot Zone */}
      {activeOverlay && (
        <div className="study-card-slot-overlay absolute inset-0 z-20 pointer-events-none flex items-center justify-center">
          <div className="pointer-events-auto">
            {typeof activeOverlay === 'function' ? activeOverlay(slotContext) : activeOverlay}
          </div>
        </div>
      )}
    </>
  )

  return (
    <div
      className={cn(
        'study-card-shell relative h-full min-h-[240px] w-full min-w-0 overflow-hidden',
        (activeHeader || activeFooter) && 'flex flex-col',
        className,
      )}
    >
      {/* 1. Header Slot Zone */}
      {activeHeader && (
        <div className="study-card-slot-header w-full shrink-0 pb-2.5">
          {typeof activeHeader === 'function' ? activeHeader(slotContext) : activeHeader}
        </div>
      )}

      {/* 2. Central Dual-Face Viewport */}
      {activeHeader || activeFooter ? (
        <div className={cn('relative w-full h-full min-h-[240px] min-w-0 overflow-hidden', (activeHeader || activeFooter) && 'flex-1 min-h-0')}>
          {viewport}
        </div>
      ) : viewport}

      {/* 5. Footer Slot Zone */}
      {activeFooter && (
        <div className="study-card-slot-footer w-full shrink-0 pt-2.5">
          {typeof activeFooter === 'function' ? activeFooter(slotContext) : activeFooter}
        </div>
      )}
    </div>
  )
}
