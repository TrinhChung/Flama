import '@/shared/config/i18n'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Check,
  Layers,
  LoaderCircle,
  PenTool,
} from 'lucide-react'
import { BrowseStrokeSinglePreview } from './BrowseStrokeSinglePreview'
import { BrowseStrokeBatchForm } from './BrowseStrokeBatchForm'
import { useBrowseStrokeModal } from '../hooks/useBrowseStrokeModal'
import type { BrowseStrokeModalProps } from '../model/strokeModal'
export type { BrowseStrokeModalProps } from '../model/strokeModal'

export function BrowseStrokeModal(props: BrowseStrokeModalProps) {
  const {
    isOpen, onClose, mode, t, noteFieldNames, mediaTargetFieldNames,
    sourceField, setSourceField, targetField, setTargetField, locale, setLocale,
    overwrite, setOverwrite, copiedCode, sampleText, setSampleText,
    previewQuery, estimateQuery, batchMutation, handleApplySingle, handleCopyCode,
    selectedDeck, isMixedNoteTypes, summaryPending, targetCount,
  } = useBrowseStrokeModal(props)
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[95vw] sm:max-w-xl max-h-[92vh] flex flex-col overflow-hidden p-0 rounded-2xl border-border/60 shadow-2xl">
        <DialogHeader className="px-5 py-4 border-b bg-muted/20 text-left shrink-0">
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
            <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
              <PenTool className="size-4.5 shrink-0" />
            </div>
            <span>{t('stroke_modal.title')}</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground mt-0.5">
            {t('stroke_modal.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 text-xs">
          {/* Target summary badge */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-muted/50 border border-border/60">
            <span className="text-muted-foreground flex items-center gap-1.5 font-medium">
              <Layers className="size-3.5 text-primary" />
              <span>{t('stroke_modal.scope_label')}</span>
            </span>
            <Badge variant="secondary" className="font-bold text-xs">
              {typeof targetCount === 'number' ? t('stroke_modal.cards_count', { count: targetCount }) : targetCount}
            </Badge>
          </div>

          <BrowseStrokeBatchForm
            isMixedNoteTypes={isMixedNoteTypes}
            selectedDeck={selectedDeck}
            sourceField={sourceField}
            setSourceField={setSourceField}
            targetField={targetField}
            setTargetField={setTargetField}
            noteFieldNames={noteFieldNames}
            mediaTargetFieldNames={mediaTargetFieldNames}
            locale={locale}
            setLocale={setLocale}
            overwrite={overwrite}
            setOverwrite={setOverwrite}
            mode={mode}
            estimateQuery={estimateQuery}
          />

          <BrowseStrokeSinglePreview
            sourceField={sourceField}
            targetField={targetField}
            sampleText={sampleText}
            setSampleText={setSampleText}
            previewQuery={previewQuery}
            copiedCode={copiedCode}
            handleCopyCode={handleCopyCode}
          />
        </div>

        <DialogFooter className="m-0 px-4 sm:px-5 py-3.5 sm:py-4 pb-[calc(0.875rem+env(safe-area-inset-bottom,0px))] sm:pb-4 border-t border-border/60 bg-muted/20 flex flex-row items-center justify-end gap-2.5 sm:gap-3 shrink-0 rounded-b-2xl">
          <Button variant="outline" size="sm" onClick={onClose} className="h-9 text-xs rounded-xl shrink-0">
            {t('stroke_modal.close')}
          </Button>

          {mode === 'single' ? (
            <Button
              size="sm"
              onClick={handleApplySingle}
              disabled={!targetField || !previewQuery.data?.items?.length}
              className="h-9 text-xs font-bold rounded-xl gap-1.5 shadow-xs shrink-0"
            >
              <Check className="size-3.5" />
              <span>{t('stroke_modal.add_to_card')}</span>
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => batchMutation.mutate()}
              disabled={!targetField || batchMutation.isPending || isMixedNoteTypes || summaryPending}
              className="h-9 text-xs font-bold rounded-xl gap-1.5 shadow-xs shrink-0 max-w-[calc(100vw-120px)] sm:max-w-none"
            >
              {batchMutation.isPending ? (
                <>
                  <LoaderCircle className="size-3.5 animate-spin" />
                  <span className="truncate">
                    {t('stroke_modal.generating', {
                      eta: estimateQuery.data?.estimated_human ? `(${estimateQuery.data.estimated_human})` : '',
                    })}
                  </span>
                </>
              ) : (
                <>
                  <PenTool className="size-3.5" />
                  <span className="truncate">
                    {t('stroke_modal.generate_for_cards', {
                      target: typeof targetCount === 'number' ? t('stroke_modal.cards_count', { count: targetCount }) : targetCount,
                    })}
                  </span>
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
