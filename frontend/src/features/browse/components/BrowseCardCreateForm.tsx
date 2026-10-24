import React, { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { LoaderCircle, Plus, RotateCcw, X } from 'lucide-react'
import { fieldValueEditorText, serializeArrayFieldValues } from '@/entities/flashcard/fields'
import { NoteFieldEditor } from '@/entities/flashcard'
import type { useBrowseState } from '../hooks/useBrowseState'
import { BrowseTagEditor } from './BrowseTagEditor'

export interface BrowseCardCreateFormProps {
  browse: ReturnType<typeof useBrowseState>
  isMobile: boolean
  editorWidth: number
  onMouseDownResize: (e: React.MouseEvent) => void
}

export function BrowseCardCreateForm({
  browse,
  isMobile,
  editorWidth,
  onMouseDownResize,
}: BrowseCardCreateFormProps) {
  const { t } = useTranslation('browse')
  const {
    noteTypesQuery,
    decksQuery,
    editDeckId,
    setEditDeckId,
    createNoteTypeId,
    setCreateNoteTypeId,
    editFieldValues,
    setEditFieldValues,
    editTags,
    newTagInput,
    setNewTagInput,
    handleAddTag,
    handleRemoveTag,
    handleCancelCreate,
    createMutation,
    mobileTab,
    setMobileTab,
  } = browse

  const noteTypes = noteTypesQuery.data?.items || []
  const deckList = decksQuery.data?.decks || []
  const currentDeck = deckList.find((d) => d.id === editDeckId)
  const deckNoteTypeId = currentDeck?.note_type_id
  const effectiveNoteTypeId =
    deckNoteTypeId ||
    createNoteTypeId ||
    noteTypes.find((nt) => nt.field_defs?.some((f) => f.name.toLowerCase() === 'word'))?.id ||
    noteTypes.find((nt) => !nt.field_defs?.some((f) => f.name.toLowerCase() === 'stt'))?.id ||
    noteTypes[0]?.id
  const selectedNoteType =
    noteTypes.find((nt) => nt.id === effectiveNoteTypeId)
  const fields = (selectedNoteType?.field_defs || []).filter(
    (f) => f.name.trim().toLowerCase() !== 'stt',
  )
  const [invalidArrayFields, setInvalidArrayFields] = useState<Record<string, boolean>>({})
  const hasInvalidFields = fields.some((field) => invalidArrayFields[`${effectiveNoteTypeId}:${field.name}`])
  const handleFieldChange = useCallback((fieldName: string, value: string) => {
    setEditFieldValues((prev) => ({ ...prev, [fieldName]: value }))
  }, [setEditFieldValues])
  const handleFieldValidityChange = useCallback((fieldName: string, valid: boolean) => {
    setInvalidArrayFields((previous) => {
      const key = `${effectiveNoteTypeId}:${fieldName}`
      return previous[key] === !valid ? previous : { ...previous, [key]: !valid }
    })
  }, [effectiveNoteTypeId])

  const submitCreateCard = () => {
    if (createMutation.isPending || hasInvalidFields || fields.length === 0) return
    if (!editDeckId) {
      toast.error(t('editor.select_deck_error'))
      return
    }
    const noteTypeId = effectiveNoteTypeId || selectedNoteType?.id
    if (!noteTypeId) {
      toast.error(t('editor.select_template_error'))
      return
    }
    // Only send fields defined in the selected Note Type
    const allowedNames = new Set(fields.map((f) => f.name))
    const payloadFields: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(editFieldValues)) {
      if (allowedNames.has(k) && v !== undefined && v !== null && fieldValueEditorText(v).trim() !== '') {
        payloadFields[k] = v
      }
    }

    void createMutation.mutate({
      deck_id: editDeckId,
      note_type_id: noteTypeId,
      field_values: serializeArrayFieldValues(payloadFields, fields),
      tags: editTags,
    })
  }

  return (
    <div
      style={{ width: isMobile ? '100%' : `${editorWidth}px` }}
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault()
          submitCreateCard()
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
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
            {t('editor.badge_new_card')}
          </Badge>
          <span className="text-xs font-bold text-foreground">{t('editor.create_card_title')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-full"
            onClick={() => {
              handleCancelCreate()
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
            onChange={(e) => {
              const newDeckId = Number(e.target.value)
              setEditDeckId(newDeckId)
              const targetDeck = deckList.find((d) => d.id === newDeckId)
              if (targetDeck?.note_type_id) {
                setCreateNoteTypeId(targetDeck.note_type_id)
              }
            }}
            className="h-9 text-xs sm:text-sm rounded-lg bg-muted/50"
          >
            {deckList.map((d) => (
              <option key={d.id} value={d.id}>
                {d.path || d.name}
              </option>
            ))}
          </NativeSelect>
        </div>

        {/* Dynamic Card fields */}
        {fields.length === 0 ? (
          <div className="text-xs text-muted-foreground italic py-2">
            {noteTypesQuery.isPending ? t('editor.loading_template') : t('editor.no_fields_in_template')}
          </div>
        ) : (
          fields.map((field) => (
            <NoteFieldEditor
              key={`${effectiveNoteTypeId}:${field.name}`}
              field={field}
              value={editFieldValues[field.name]}
              onChange={handleFieldChange}
              onValidityChange={handleFieldValidityChange}
              placeholder={`Nhập ${field.name}...`}
            />
          ))
        )}

        {/* Tags management */}
        <BrowseTagEditor
          tags={editTags}
          newTagInput={newTagInput}
          onNewTagInputChange={setNewTagInput}
          onAddTag={handleAddTag}
          onRemoveTag={handleRemoveTag}
        />
      </div>

      {/* Editor Actions Footer */}
      <div className="p-3 border-t border-border/60 bg-background flex flex-col gap-2 shrink-0">
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 h-9 text-xs font-semibold rounded-lg bg-background hover:bg-muted border-border"
            onClick={() => {
              handleCancelCreate()
              setMobileTab('cards')
            }}
            disabled={createMutation.isPending}
          >
            <RotateCcw className="size-3.5 mr-1" /> {t('editor.cancel')}
          </Button>

          <Button
            size="sm"
            className="flex-1 h-9 text-xs font-bold rounded-lg shadow-sm bg-primary text-primary-foreground hover:opacity-95 disabled:opacity-50"
            onClick={submitCreateCard}
            disabled={createMutation.isPending || !editDeckId || fields.length === 0 || hasInvalidFields}
          >
            {createMutation.isPending ? (
              <LoaderCircle className="size-3.5 mr-1 animate-spin" />
            ) : (
              <Plus className="size-3.5 mr-1" />
            )}
            {t('editor.create_button')}
          </Button>
        </div>
      </div>
    </div>
  )
}
