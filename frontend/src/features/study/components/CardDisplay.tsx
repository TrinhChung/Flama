import { cn } from '@/lib/utils'
import { CardRendererFrame } from './CardRendererFrame'

type CardDisplayProps = {
  cardId?: string | null
  noteId?: string | null
  side: 'front' | 'back'
  frontPayload?: unknown
  backPayload?: unknown
  frontHtml?: string
  backHtml?: string
  scope?: string
  scopeId?: string | null
  fieldDefs?: unknown[]
  fieldValues?: Record<string, string>
  enableLivePatch?: boolean
  className?: string
}

const EMPTY_FIELD_DEFS: unknown[] = []
const EMPTY_FIELD_VALUES: Record<string, string> = {}

/**
 * Shared, fixed-viewport card display used by Study and live previews.
 * Both faces remain mounted so flipping a card does not rebuild its template.
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
}: CardDisplayProps) {
  const isBack = side === 'back'

  return (
    <div
      className={cn(
        'study-card-shell relative h-full min-h-[240px] w-full min-w-0 overflow-hidden',
        className,
      )}
    >
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
    </div>
  )
}
