import '@/shared/config/i18n'
import React, { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { AlignLeft, Code, LoaderCircle, Plus, RotateCcw, Tag, X } from 'lucide-react'
import { fieldValueEditorText, isArrayField, normalizeArrayFieldValues } from '@/lib/arrayField'
import { MediaFieldPreview, ArrayFieldInput, type ArrayViewMode } from '@/entities/flashcard'
import type { useBrowseState } from '../hooks/useBrowseState'

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
    noteTypes.find((nt) => nt.id === effectiveNoteTypeId) || noteTypes[0]
  const fields = (selectedNoteType?.field_defs || []).filter(
    (f) => f.name.trim().toLowerCase() !== 'stt',
  )

  const [editorArrayMode, setEditorArrayMode] = useState<ArrayViewMode>(browse.arrayViewMode || 'normal')

  useEffect(() => {
    if (browse.arrayViewMode) {
      setEditorArrayMode(browse.arrayViewMode)
    }
  }, [browse.arrayViewMode])

  const submitCreateCard = () => {
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
    const payloadFields: Record<string, string> = {}
    for (const [k, v] of Object.entries(editFieldValues)) {
      if (allowedNames.has(k) && v !== undefined && v !== null && String(v).trim() !== '') {
        payloadFields[k] = String(v)
      }
    }

    void createMutation.mutate({
      deck_id: editDeckId,
      note_type_id: noteTypeId,
      field_values: normalizeArrayFieldValues(payloadFields, fields),
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
          {/* View mode toggle: Normal lines vs Code (Array) */}
          <div className="flex items-center rounded-lg border border-border/60 bg-muted/40 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => {
                setEditorArrayMode('normal')
                browse.setArrayViewMode('normal')
              }}
              className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
                editorArrayMode === 'normal'
                  ? 'bg-background text-foreground shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              title={t('editor.view_mode_normal_tooltip', 'Chế độ xem thường')}
            >
              <AlignLeft className="size-3" />
              <span className="hidden sm:inline">{t('editor.view_mode_normal', 'Thường')}</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setEditorArrayMode('code')
                browse.setArrayViewMode('code')
              }}
              className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
                editorArrayMode === 'code'
                  ? 'bg-background text-foreground shadow-xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              title={t('editor.view_mode_code_tooltip', 'Chế độ xem code mảng JSON')}
            >
              <Code className="size-3" />
              <span className="hidden sm:inline">{t('editor.view_mode_code', 'Code')}</span>
            </button>
          </div>

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
          fields.map((field) => {
            const val = fieldValueEditorText(editFieldValues[field.name])
            const ft = (field.field_type || 'text').toLowerCase()

            // Media fields get a specialized preview/code editor.
            if (ft === 'image' || ft === 'audio' || ft === 'diagram') {
              return (
                <MediaFieldPreview
                  key={field.name}
                  fieldName={field.name}
                  fieldType={ft as 'image' | 'audio' | 'diagram'}
                  value={val}
                  onChange={(v) =>
                    setEditFieldValues((prev) => ({ ...prev, [field.name]: v }))
                  }
                  required={field.required}
                />
              )
            }

            if (isArrayField(ft)) {
              return (
                <ArrayFieldInput
                  key={field.name}
                  fieldName={field.name}
                  value={editFieldValues[field.name]}
                  onChange={(v) =>
                    setEditFieldValues((prev) => ({ ...prev, [field.name]: v }))
                  }
                  required={field.required}
                  mode={editorArrayMode}
                />
              )
            }

            const isMultiline =
              val.length > 50 ||
              val.includes('\n') ||
              field.name.toLowerCase().includes('meaning') ||
              field.name.toLowerCase().includes('example') ||
              field.name.toLowerCase().includes('sentence')

            return (
              <div key={field.name} className="space-y-1.5">
                <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {field.name} {field.required && <span className="text-destructive">*</span>}
                </Label>
                {isMultiline ? (
                  <Textarea
                    placeholder={`Nhập ${field.name}...`}
                    value={val}
                    onChange={(e) =>
                      setEditFieldValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                    }
                    className="min-h-20 text-xs sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50"
                  />
                ) : (
                  <Input
                    placeholder={`Nhập ${field.name}...`}
                    value={val}
                    onChange={(e) =>
                      setEditFieldValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                    }
                    className="h-9 text-xs sm:text-sm rounded-lg bg-muted/50"
                  />
                )}
              </div>
            )
          })
        )}

        {/* Tags management */}
        <div className="space-y-2">
          <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {t('editor.tags_label')}
          </Label>
          <div className="flex gap-1.5">
            <Input
              placeholder={t('editor.new_tag_placeholder')}
              value={newTagInput}
              onChange={(e) => setNewTagInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddTag()}
              className="h-8 rounded-lg text-xs bg-muted/50"
            />
            <Button
              size="sm"
              variant="outline"
              className="h-8 px-2.5 rounded-lg text-xs bg-muted/50 hover:bg-muted border-border"
              onClick={handleAddTag}
            >
              <Plus className="size-3.5" />
            </Button>
          </div>

          <div className="flex flex-wrap gap-1.5 pt-1.5">
            {editTags.length === 0 ? (
              <span className="text-[11px] text-muted-foreground italic">
                {t('editor.no_tags')}
              </span>
            ) : (
              editTags.map((tag) => (
                <Badge
                  key={tag}
                  variant="secondary"
                  className="gap-1 pl-1.5 pr-1 py-0.5 text-[11px] rounded-md font-semibold select-none group"
                >
                  <Tag className="size-2.5 opacity-60" />
                  <span>{tag}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveTag(tag)}
                    className="p-0.5 rounded-full hover:bg-muted-foreground/15 text-muted-foreground hover:text-foreground shrink-0"
                  >
                    <X className="size-2.5" />
                  </button>
                </Badge>
              ))
            )}
          </div>
        </div>
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
            disabled={createMutation.isPending || !editDeckId}
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
