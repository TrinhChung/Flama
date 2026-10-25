import '@/shared/config/i18n'
import { useState, type ReactNode } from 'react'
import { Eye, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Card, NativeSelect, NativeSelectOption } from '@/shared/ui'
import { cn } from '@/shared/lib'
import type { CardRendererSlots, RendererDiagnostic, RendererReadyEvent } from '../model/types'
import { CardDisplay } from './CardDisplay'
import { usePreviewDiagnostics } from '../hooks/usePreviewDiagnostics'
import { CardSideToggle, type CardSide } from './CardSideToggle'

export interface CardPreviewTemplateOption {
  id: string
  name: string
}

export interface CardPreviewPanelProps {
  cardId: string
  side?: CardSide
  onSideChange?: (side: CardSide) => void
  templates?: CardPreviewTemplateOption[]
  selectedTemplateId?: string
  onSelectTemplate?: (id: string) => void
  frontPayload?: unknown
  backPayload?: unknown
  frontHtml?: string
  backHtml?: string
  scope?: string
  scopeId?: string
  fieldDefs?: Array<{ id: string; name: string; field_type: string; position: number }>
  candidateHash?: string
  mediaBaseUrl?: string
  fieldValues?: Record<string, unknown>
  onDiagnostic?: (diagnostic: RendererDiagnostic) => void
  onReady?: (event: RendererReadyEvent) => void
  isLoading?: boolean
  error?: string | null
  title?: string
  subtitle?: string
  /** Extra controls rendered before the side switch (e.g. a sample data button). */
  headerActions?: ReactNode
  className?: string
  /** Fixed viewport height when the panel is not filling its parent. */
  containerHeightClass?: string
  /** Extra classes for the card viewport (e.g. a white card background). */
  viewportClassName?: string
  /**
   * Fill the parent's height (workspace panes). Below `lg` the viewport keeps a
   * screen-relative height so the stacked mobile layout stays usable.
   */
  fill?: boolean
  showSideSelector?: boolean
  slots?: CardRendererSlots
}

/**
 * Shared live card preview: title, optional template picker, front/back switch
 * and a sandboxed CardDisplay. The renderer is laid out on an absolutely
 * positioned layer so its `h-full` chain always resolves to the viewport size,
 * whichever flex or block parent hosts the panel.
 */
export function CardPreviewPanel({
  cardId,
  side: controlledSide,
  onSideChange,
  templates = [],
  selectedTemplateId,
  onSelectTemplate,
  frontPayload,
  backPayload,
  frontHtml,
  backHtml,
  scope = 'note_type_live_preview',
  scopeId,
  fieldDefs,
  candidateHash,
  mediaBaseUrl,
  fieldValues,
  onDiagnostic,
  onReady,
  isLoading = false,
  error = null,
  title,
  subtitle,
  headerActions,
  className,
  containerHeightClass = 'h-[clamp(14rem,40vh,30rem)] min-h-[240px]',
  viewportClassName,
  fill = false,
  showSideSelector = true,
  slots,
}: CardPreviewPanelProps) {
  const { t } = useTranslation('common')
  const { diagnostics, reportDiagnostic } = usePreviewDiagnostics({
    cardId, candidateHash, frontPayload, backPayload, frontHtml, backHtml, onDiagnostic,
  })
  const [internalSide, setInternalSide] = useState<CardSide>('front')
  const activeSide = controlledSide ?? internalSide
  const displayTitle = title ?? t('card_preview.title')
  const displaySubtitle = subtitle ?? t('card_preview.subtitle')
  const hasContent = frontPayload !== undefined || backPayload !== undefined || Boolean(frontHtml) || Boolean(backHtml)
  const changeSide = (next: CardSide) => {
    if (onSideChange) onSideChange(next)
    else setInternalSide(next)
  }

  return (
    <Card className={cn('p-4 sm:p-5 border border-border/80 shadow-xs flex flex-col rounded-2xl min-w-0', fill ? 'h-full min-h-0' : 'flex-1', className)}>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 mb-3 min-h-[32px]">
        <div className="flex min-w-0 items-center gap-2">
          <div className="p-2 rounded-xl bg-primary/10 text-primary shrink-0">
            <Eye className="size-4" />
          </div>
          <div className="min-w-0">
            <h4 className="text-sm font-bold text-foreground">{displayTitle}</h4>
            {displaySubtitle && <span className="text-[10px] text-muted-foreground block">{displaySubtitle}</span>}
          </div>
          {isLoading && (
            <span className="text-xs text-primary font-semibold animate-pulse ml-2 flex items-center gap-1">
              <Loader2 className="size-3 animate-spin shrink-0" /> {t('card_preview.updating')}
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 sm:ml-auto">
          {headerActions}
          {templates.length > 1 && onSelectTemplate && (
            <NativeSelect
              aria-label={t('card_preview.template_select')}
              value={selectedTemplateId || templates[0]?.id}
              onChange={(event) => onSelectTemplate(event.target.value)}
              className="h-8 text-xs font-medium flex-1 sm:w-36 rounded-xl bg-background"
            >
              {templates.map((template) => (
                <NativeSelectOption key={template.id} value={template.id}>
                  {template.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          )}
          {showSideSelector && <CardSideToggle side={activeSide} onSideChange={changeSide} />}
        </div>
      </div>

      <div
        data-slot="card-preview-viewport"
        className={cn(
          'relative w-full overflow-hidden rounded-xl border border-border/80 bg-muted/30 dark:bg-muted/10',
          fill ? 'h-[60svh] min-h-72 lg:h-auto lg:min-h-64 lg:flex-1' : cn('flex-auto', containerHeightClass),
          viewportClassName,
        )}
      >
        <div className="absolute inset-3">
          {error ? (
            <div role="alert" className="flex h-full items-center justify-center p-6 text-center text-sm text-destructive">
              {error}
            </div>
          ) : hasContent ? (
            <CardDisplay
              cardId={cardId}
              side={activeSide}
              frontPayload={frontPayload}
              backPayload={backPayload}
              frontHtml={frontHtml}
              backHtml={backHtml}
              scope={scope}
              scopeId={scopeId}
              fieldDefs={fieldDefs}
              fieldValues={fieldValues}
              candidateHash={candidateHash}
              mediaBaseUrl={mediaBaseUrl}
              onDiagnostic={reportDiagnostic}
              onReady={onReady}
              slots={slots}
            />
          ) : (
            <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
              {t('card_preview.preparing')}
            </div>
          )}
        </div>
      </div>
      {diagnostics.length > 0 && (
        <div role="status" aria-live="polite" className="mt-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
          <p className="font-semibold">{t('card_preview.runtime_errors', { defaultValue: 'Lỗi khi chạy bản xem trước' })}</p>
          <ul className="mt-1 space-y-1 break-words">
            {diagnostics.map((diagnostic, index) => (
              <li key={index}>{diagnostic.side === 'back' ? t('card_preview.back') : t('card_preview.front')} · {diagnostic.code}: {diagnostic.message}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}
