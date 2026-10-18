import '@/shared/config/i18n'
import React, { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { LoaderCircle, Pencil, PenTool, RotateCcw, Save } from 'lucide-react'
import { BrowseStrokeModal } from '@/features/browse/components/BrowseStrokeModal'
import { StudyQuickEditFields } from './StudyQuickEditFields'
import { StudyQuickEditTags } from './StudyQuickEditTags'
import { useStudyQuickEditForm } from '../hooks/useStudyQuickEditForm'
import type { StudyContentArtifact, StudyMediaArtifact, StudyTemplateArtifact } from '../types'

export type StudyQuickEditDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  cardId?: string | null
  noteId?: string | null
  deckName?: string | null
  template?: StudyTemplateArtifact | null
  content?: StudyContentArtifact | null
  onCardUpdated: (
    cardId: string,
    newFieldValues: Record<string, unknown>,
    options?: { media?: StudyMediaArtifact[]; noteId?: string | null },
  ) => void | Promise<void>
}

export function StudyQuickEditDialog({
  open,
  onOpenChange,
  cardId,
  deckName,
  template,
  content,
  onCardUpdated,
}: StudyQuickEditDialogProps) {
  const { t } = useTranslation('study')
  const [isStrokeModalOpen, setIsStrokeModalOpen] = useState(false)

  const {
    fieldValues,
    setFieldValues,
    tags,
    newTagInput,
    setNewTagInput,
    deckId,
    setDeckId,
    handleAddTag,
    handleRemoveTag,
    handleRevert,
    handleApplyStrokes,
    isDirty,
    isDetailReady,
    hasInvalidFields,
    handleFieldValidityChange,
    mediaResolver,
    handleSubmit,
    isSubmitting,
    fieldDefs,
    deckList,
  } = useStudyQuickEditForm({
    open,
    cardId,
    template,
    content,
    onCardUpdated,
    onClose: () => onOpenChange(false),
  })

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  const handleFieldValueChange = useCallback((fieldName: string, value: string) => {
    setFieldValues((prev) => ({ ...prev, [fieldName]: value }))
  }, [setFieldValues])

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className="w-[calc(100%-1rem)] sm:w-full sm:max-w-2xl max-h-[92dvh] sm:max-h-[88vh] flex flex-col p-0 gap-0 overflow-hidden bg-card border-border/80 shadow-2xl rounded-2xl"
          onKeyDown={handleKeyDown}
        >
          {/* Header */}
          <DialogHeader className="px-3.5 pt-3.5 pb-3.5 sm:px-5 sm:pt-4 sm:pb-4 border-b border-border/60 bg-muted/20 shrink-0">
            <div className="flex items-center justify-between gap-2 sm:gap-3 pr-9 sm:pr-8">
              <div className="flex items-center gap-2 min-w-0">
                <div className="size-7 sm:size-8 rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400 flex items-center justify-center shrink-0">
                  <Pencil className="size-3.5 sm:size-4" />
                </div>
                <div className="min-w-0">
                  <DialogTitle className="text-sm sm:text-base font-bold text-foreground flex items-center gap-1.5 sm:gap-2 truncate">
                    <span>{t('quick_edit.title')}</span>
                    {deckName && (
                      <Badge variant="outline" className="text-[10px] sm:text-[11px] font-normal px-1.5 sm:px-2 py-0 shrink-0 truncate max-w-[120px] sm:max-w-xs">
                        {deckName}
                      </Badge>
                    )}
                  </DialogTitle>
                  <DialogDescription className="text-[11px] sm:text-xs text-muted-foreground mt-0.5 truncate hidden sm:block">
                    {t('quick_edit.description')}
                  </DialogDescription>
                </div>
              </div>

              <div className="flex items-center gap-1.5 shrink-0 my-auto">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 px-2 sm:px-2.5 text-xs font-semibold gap-1.5 rounded-lg bg-background/80 hover:bg-muted shrink-0 border-border/80 shadow-2xs"
                  title={t('quick_edit.generate_stroke_tooltip')}
                  onClick={() => setIsStrokeModalOpen(true)}
                >
                  <PenTool className="size-3.5 text-primary" />
                  <span className="hidden sm:inline">{t('quick_edit.generate_stroke')}</span>
                </Button>
              </div>
            </div>
          </DialogHeader>

          {/* Scrollable Form Body */}
          <div className="flex-1 overflow-y-auto overscroll-contain p-3.5 sm:p-5 space-y-3.5 sm:space-y-4 min-h-0 pb-6 sm:pb-8">
            <StudyQuickEditFields
              deckList={deckList}
              deckId={deckId}
              onDeckChange={setDeckId}
              fieldDefs={fieldDefs}
              fieldValues={fieldValues}
              onFieldValueChange={handleFieldValueChange}
              onFieldValidityChange={handleFieldValidityChange}
              resolveMediaUrl={mediaResolver}
            />

            <StudyQuickEditTags
              tags={tags}
              newTagInput={newTagInput}
              onNewTagInputChange={setNewTagInput}
              onAddTag={handleAddTag}
              onRemoveTag={handleRemoveTag}
            />
          </div>

          {/* Footer Actions */}
          <DialogFooter className="m-0 px-3.5 py-3 sm:px-5 sm:py-4 pb-[calc(0.75rem+env(safe-area-inset-bottom,0px))] sm:pb-4 border-t border-border/60 bg-muted/20 flex flex-row items-center justify-between gap-2 sm:gap-3 shrink-0 rounded-b-2xl">
            <div className="flex items-center gap-1.5 sm:gap-2">
              {isDirty && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-10 sm:h-9 px-2.5 sm:px-3 text-xs font-semibold rounded-lg text-muted-foreground hover:text-foreground shrink-0"
                  onClick={handleRevert}
                  disabled={isSubmitting}
                >
                  <RotateCcw className="size-3.5 sm:mr-1.5" />
                  <span className="hidden sm:inline">{t('quick_edit.revert')}</span>
                </Button>
              )}
            </div>

            <div className="flex items-center gap-2 flex-1 sm:flex-initial justify-end">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-10 sm:h-9 px-3.5 sm:px-4 text-xs font-semibold rounded-lg shrink-0"
                onClick={() => onOpenChange(false)}
                disabled={isSubmitting}
              >
                {t('quick_edit.cancel')}
              </Button>

              <Button
                type="button"
                size="sm"
                className="h-10 sm:h-9 px-4 text-xs font-bold rounded-lg shadow-sm bg-orange-600 hover:bg-orange-700 text-white dark:bg-orange-500 dark:hover:bg-orange-600 flex-1 sm:flex-initial justify-center"
                onClick={handleSubmit}
                disabled={!isDetailReady || !isDirty || isSubmitting || hasInvalidFields}
                title={t('quick_edit.save_tooltip')}
              >
                {isSubmitting ? (
                  <LoaderCircle className="size-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Save className="size-3.5 mr-1.5" />
                )}
                {t('quick_edit.save_changes')}
                <kbd className="hidden sm:inline-block ml-1.5 rounded bg-black/20 dark:bg-white/20 px-1 py-0.2 text-[9px] font-mono font-medium">
                  Ctrl+↵
                </kbd>
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {isStrokeModalOpen && (
        <BrowseStrokeModal
          isOpen={isStrokeModalOpen}
          onClose={() => setIsStrokeModalOpen(false)}
          mode="single"
          cardId={cardId}
          deckName={deckName}
          fields={fieldDefs}
          fieldValues={fieldValues}
          onApply={handleApplyStrokes}
        />
      )}
    </>
  )
}
