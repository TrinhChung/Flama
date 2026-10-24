import '@/shared/config/i18n'
import React, { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import {
  LoaderCircle,
  PenTool,
  RotateCcw,
  Save,
  Trash2,
  X,
} from 'lucide-react'
import { serializeArrayFieldValues } from '@/entities/flashcard/fields'
import { NoteFieldEditor } from '@/entities/flashcard'
import { statusLabel, statusVariant } from '../utils/formatter'
import type { useBrowseState } from '../hooks/useBrowseState'
import { BrowseTagEditor } from './BrowseTagEditor'

export interface BrowseCardEditFormProps {
  browse: ReturnType<typeof useBrowseState>
  isMobile: boolean
  editorWidth: number
  onMouseDownResize: (e: React.MouseEvent) => void
}

export function BrowseCardEditForm({
  browse,
  isMobile,
  editorWidth,
  onMouseDownResize,
}: BrowseCardEditFormProps) {
  const { t } = useTranslation('browse')
  const {
    activeCardId,
    setActiveCardId,
    cardDetailQuery,
    editFieldValues,
    setEditFieldValues,
    editDeckId,
    setEditDeckId,
    editTags,
    newTagInput,
    setNewTagInput,
    decksQuery,
    isDirty,
    isCloneCard,
    canUploadMedia,
    handleRevert,
    handleAddTag,
    handleRemoveTag,
    updateMutation,
    deleteMutation,
    mobileTab,
    setMobileTab,
    setIsStrokeModalOpen,
    setStrokeModalMode,
    setStrokeModalCardId,
  } = browse

  const detail = cardDetailQuery.data
  const [invalidArrayFields, setInvalidArrayFields] = useState<Record<string, boolean>>({})
  const hasInvalidFields = detail?.fields.some((field) => invalidArrayFields[field.name]) ?? false
  const handleFieldChange = useCallback((fieldName: string, value: string) => {
    setEditFieldValues((prev) => ({ ...prev, [fieldName]: value }))
  }, [setEditFieldValues])
  const handleFieldValidityChange = useCallback((fieldName: string, valid: boolean) => {
    setInvalidArrayFields((previous) =>
      previous[fieldName] === !valid ? previous : { ...previous, [fieldName]: !valid })
  }, [])

  if (!detail) return null

  const deckList = decksQuery.data?.decks || []

  const submitUpdateCard = () => {
    if (!isDirty || updateMutation.isPending || hasInvalidFields) return
    const changedFields = Object.fromEntries(Object.entries(editFieldValues).filter(([name, value]) =>
      JSON.stringify(value) !== JSON.stringify(browse.initialFieldValues[name])))
    const fieldValues = serializeArrayFieldValues(changedFields, detail.fields)
    // A clone keeps its deck and tags; sending them back only risks a 400.
    void updateMutation.mutate(isCloneCard
      ? { field_values: fieldValues }
      : { field_values: fieldValues, deck_id: editDeckId || undefined, tags: editTags })
  }

  return (
    <div
      style={{ width: isMobile ? '100%' : `${editorWidth}px` }}
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault()
          submitUpdateCard()
        }
      }}
      className={`relative border-l border-border/60 flex flex-col bg-card shrink-0 h-full overflow-hidden ${
        mobileTab === 'editor' ? 'flex' : 'hidden lg:flex'
      }`}
    >
      {/* Resize Handle */}
      <div
        className="hidden lg:block absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/60 hover:w-1.5 transition-all bg-border/20 z-50"
        onMouseDown={onMouseDownResize}
      />
      {/* Editor Header */}
      <div className="px-4 py-3 border-b border-border/60 flex items-center justify-between bg-background shrink-0">
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant(detail.card.status)} className="text-[10px] px-1.5 py-0 font-semibold">
            {statusLabel(detail.card.status)}
          </Badge>
          <span className="text-xs font-bold text-foreground">{t('editor.note_detail_title')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-[11px] font-semibold gap-1 rounded-lg bg-muted/40 hover:bg-muted"
            title={t('editor.generate_stroke_tooltip')}
            onClick={() => {
              setStrokeModalMode('single')
              setStrokeModalCardId(activeCardId)
              setIsStrokeModalOpen(true)
            }}
          >
            <PenTool className="size-3 text-primary" />
            <span className="hidden sm:inline">{t('editor.generate_stroke')}</span>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-full"
            onClick={() => {
              setActiveCardId(null)
              setMobileTab('cards')
            }}
          >
            <X className="size-4" />
          </Button>
        </div>
      </div>

      {/* Editor Body Fields Scrollable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Destination Deck selection */}
        <div className="space-y-1.5">
          <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {t('editor.storage_deck')}
          </Label>
          <NativeSelect
            value={editDeckId !== null ? String(editDeckId) : ''}
            onChange={(e) => setEditDeckId(Number(e.target.value))}
            disabled={isCloneCard}
            title={isCloneCard ? t('editor.clone_locked_hint') : undefined}
            className="h-9 text-xs sm:text-sm rounded-lg bg-muted/50"
          >
            {deckList.map((d) => (
              <option key={d.id} value={d.id}>
                {d.path || d.name}
              </option>
            ))}
          </NativeSelect>
          {isCloneCard && (
            <p className="text-[11px] text-muted-foreground">{t('editor.clone_locked_hint')}</p>
          )}
        </div>

        {/* Dynamic Card fields */}
        {detail.fields.map((field) => (
          <NoteFieldEditor
            key={field.name}
            field={field}
            value={editFieldValues[field.name]}
            initialValue={detail.note.field_values[field.name]}
            onChange={handleFieldChange}
            onValidityChange={handleFieldValidityChange}
            mediaUploadDisabled={!canUploadMedia}
          />
        ))}

        {/* Tags management */}
        <BrowseTagEditor
          tags={editTags}
          newTagInput={newTagInput}
          onNewTagInputChange={setNewTagInput}
          onAddTag={handleAddTag}
          onRemoveTag={handleRemoveTag}
          disabled={isCloneCard}
          disabledReason={t('editor.clone_locked_hint')}
        />
      </div>

      {/* Editor Actions Footer sticky */}
      <div className="p-3 border-t border-border/60 bg-background flex flex-col gap-2 shrink-0">
        <div className="flex gap-2">
          {isDirty && (
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-9 text-xs font-semibold rounded-lg bg-background hover:bg-muted border-border"
              onClick={handleRevert}
              disabled={updateMutation.isPending}
            >
              <RotateCcw className="size-3.5 mr-1" /> {t('editor.cancel')}
            </Button>
          )}

          <Button
            size="sm"
            className="flex-1 h-9 text-xs font-bold rounded-lg shadow-sm disabled:bg-muted disabled:text-muted-foreground disabled:border disabled:border-border/50 disabled:shadow-none disabled:opacity-100"
            onClick={submitUpdateCard}
            disabled={!isDirty || updateMutation.isPending || hasInvalidFields}
          >
            {updateMutation.isPending ? (
              <LoaderCircle className="size-3.5 mr-1 animate-spin" />
            ) : (
              <Save className="size-3.5 mr-1" />
            )}
            {t('editor.save_card')}
          </Button>
        </div>

        <Button
          variant="outline"
          size="sm"
          className="w-full h-8 text-[11px] text-destructive hover:text-white hover:bg-destructive border-destructive/40 hover:border-destructive bg-background rounded-lg transition-all"
          onClick={() => {
            if (window.confirm(t('editor.confirm_delete'))) {
              void deleteMutation.mutate(detail.card.card_id)
            }
          }}
          disabled={deleteMutation.isPending}
        >
          <Trash2 className="size-3.5 mr-1.5" /> {t('editor.delete_card')}
        </Button>
      </div>
    </div>
  )
}
