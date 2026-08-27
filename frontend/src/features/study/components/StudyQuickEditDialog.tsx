import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { NativeSelect } from '@/components/ui/native-select'
import { LoaderCircle, Pencil, Plus, RotateCcw, Save, Tag, X } from 'lucide-react'
import { appApi } from '@/app/api'
import type { StudyContentArtifact, StudyTemplateArtifact } from '../types'
import type { CardDetailResponse } from '@/features/browse/hooks/useBrowseState'

export type StudyQuickEditDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  cardId?: string | null
  noteId?: string | null
  deckName?: string | null
  template?: StudyTemplateArtifact | null
  content?: StudyContentArtifact | null
  onCardUpdated: (cardId: string, newFieldValues: Record<string, string>) => void | Promise<void>
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
  const queryClient = useQueryClient()

  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [initialFieldValues, setInitialFieldValues] = useState<Record<string, string>>({})
  const [tags, setTags] = useState<string[]>([])
  const [initialTags, setInitialTags] = useState<string[]>([])
  const [newTagInput, setNewTagInput] = useState('')
  const [deckId, setDeckId] = useState<number | null>(null)
  const [initialDeckId, setInitialDeckId] = useState<number | null>(null)

  const isFormInitializedRef = useRef(false)

  // Query background card detail for full deck tree options and tags
  const cardDetailQuery = useQuery({
    queryKey: ['browse', 'card-detail', cardId],
    queryFn: () => appApi.get<CardDetailResponse>(`/browse/cards/${cardId}`),
    enabled: Boolean(open && cardId),
  })

  // Initialize immediately from available study session content (0ms latency)
  useEffect(() => {
    if (open && content && !isFormInitializedRef.current) {
      const baseValues = { ...(content.field_values || {}) }
      setFieldValues(baseValues)
      setInitialFieldValues(baseValues)
      isFormInitializedRef.current = true
    } else if (!open) {
      isFormInitializedRef.current = false
      setNewTagInput('')
    }
  }, [open, content])

  // Merge full detail once background query resolves
  useEffect(() => {
    if (cardDetailQuery.data && open) {
      const detail = cardDetailQuery.data
      const detailValues = detail.note.field_values || {}
      const detailTags = detail.note.tags || []
      const detailDeckId = detail.note.deck_id || null

      setFieldValues((current) => ({
        ...detailValues,
        ...current,
      }))
      setInitialFieldValues(detailValues)
      setTags(detailTags)
      setInitialTags(detailTags)
      setDeckId(detailDeckId)
      setInitialDeckId(detailDeckId)
    }
  }, [cardDetailQuery.data, open])

  const handleAddTag = useCallback(() => {
    const trimmed = newTagInput.trim()
    if (!trimmed || tags.includes(trimmed)) return
    setTags((prev) => [...prev, trimmed])
    setNewTagInput('')
  }, [newTagInput, tags])

  const handleRemoveTag = useCallback((tagToRemove: string) => {
    setTags((prev) => prev.filter((t) => t !== tagToRemove))
  }, [])

  const handleRevert = useCallback(() => {
    setFieldValues(initialFieldValues)
    setTags(initialTags)
    setDeckId(initialDeckId)
    setNewTagInput('')
  }, [initialFieldValues, initialTags, initialDeckId])

  const isDirty = (() => {
    if (!open || !cardId) return false
    if (deckId !== initialDeckId) return true
    if (JSON.stringify(tags) !== JSON.stringify(initialTags)) return true
    const currentKeys = Object.keys(fieldValues)
    const initialKeys = Object.keys(initialFieldValues)
    if (currentKeys.length !== initialKeys.length) return true
    for (const key of currentKeys) {
      if ((fieldValues[key] || '') !== (initialFieldValues[key] || '')) return true
    }
    return false
  })()

  // Save Mutation
  const updateMutation = useMutation({
    mutationFn: (payload: {
      field_values: Record<string, string>
      deck_id?: number
      tags?: string[]
    }) => appApi.mutate(`/browse/cards/${cardId}`, 'PATCH', payload),
    onSuccess: async () => {
      toast.success('Đã lưu thay đổi thẻ.')
      setInitialFieldValues(fieldValues)
      setInitialTags(tags)
      setInitialDeckId(deckId)

      if (cardId) {
        await onCardUpdated(cardId, fieldValues)
      }

      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      void queryClient.invalidateQueries({ queryKey: ['browse', 'card-detail', cardId] })

      onOpenChange(false)
    },
    onError: (error: Error) => {
      toast.error('Không thể lưu thẻ', { description: error.message })
    },
  })

  const handleSubmit = useCallback(() => {
    if (!isDirty || updateMutation.isPending || !cardId) return
    updateMutation.mutate({
      field_values: fieldValues,
      deck_id: deckId || undefined,
      tags,
    })
  }, [isDirty, updateMutation, cardId, fieldValues, deckId, tags])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  // Resolve fields definition: template field_defs > query fields > keys of fieldValues
  const fieldDefs = template?.field_defs && template.field_defs.length > 0
    ? template.field_defs
    : cardDetailQuery.data?.fields && cardDetailQuery.data.fields.length > 0
    ? cardDetailQuery.data.fields.map((f) => ({
        name: f.name,
        position: f.position,
        required: f.required,
        field_type: 'text',
      }))
    : Object.keys(fieldValues).map((name, index) => ({
        name,
        position: index,
        required: false,
        field_type: 'text',
      }))

  const deckList = cardDetailQuery.data?.decks || []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-2xl max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden bg-card border-border/80 shadow-2xl rounded-2xl"
        onKeyDown={handleKeyDown}
      >
        {/* Header */}
        <DialogHeader className="px-5 py-4 border-b border-border/60 bg-muted/20 shrink-0">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400 flex items-center justify-center shrink-0">
              <Pencil className="size-4" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold text-foreground flex items-center gap-2">
                Sửa nhanh thẻ
                {deckName && (
                  <Badge variant="outline" className="text-[11px] font-normal px-2 py-0">
                    {deckName}
                  </Badge>
                )}
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Chỉnh sửa các trường từ vựng và nội dung mà không làm gián đoạn phiên học.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Scrollable Form Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 min-h-0">
          {/* Destination Deck Selection (if available) */}
          {deckList.length > 0 && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Deck lưu trữ
              </Label>
              <NativeSelect
                value={deckId !== null ? String(deckId) : ''}
                onChange={(e) => setDeckId(Number(e.target.value))}
                className="h-9 text-xs sm:text-sm rounded-lg bg-muted/50"
              >
                {deckList.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.path || d.name}
                  </option>
                ))}
              </NativeSelect>
            </div>
          )}

          {/* Dynamic Note Fields */}
          {fieldDefs.map((field) => {
            const val = fieldValues[field.name] || ''
            const isMultiline =
              val.length > 60 ||
              val.includes('\n') ||
              field.name.toLowerCase().includes('meaning') ||
              field.name.toLowerCase().includes('example') ||
              field.name.toLowerCase().includes('sentence') ||
              field.name.toLowerCase().includes('notes')

            return (
              <div key={field.name} className="space-y-1.5">
                <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center justify-between">
                  <span>
                    {field.name} {field.required && <span className="text-destructive">*</span>}
                  </span>
                  {isMultiline && (
                    <span className="text-[10px] lowercase font-normal opacity-70">nhiều dòng</span>
                  )}
                </Label>
                {isMultiline ? (
                  <Textarea
                    value={val}
                    onChange={(e) =>
                      setFieldValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                    }
                    placeholder={`Nhập ${field.name}…`}
                    className="min-h-20 text-xs sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50 focus:bg-background transition-colors"
                  />
                ) : (
                  <Input
                    value={val}
                    onChange={(e) =>
                      setFieldValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                    }
                    placeholder={`Nhập ${field.name}…`}
                    className="h-9 text-xs sm:text-sm rounded-lg bg-muted/50 focus:bg-background transition-colors"
                  />
                )}
              </div>
            )
          })}

          {/* Tags management */}
          <div className="space-y-2 pt-2 border-t border-border/50">
            <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Tags (Nhãn)
            </Label>
            <div className="flex gap-1.5">
              <Input
                placeholder="Thêm tag mới…"
                value={newTagInput}
                onChange={(e) => setNewTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleAddTag()
                  }
                }}
                className="h-8 rounded-lg text-xs bg-muted/50"
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 px-2.5 rounded-lg text-xs bg-muted/50 hover:bg-muted border-border"
                onClick={handleAddTag}
              >
                <Plus className="size-3.5 mr-1" /> Thêm
              </Button>
            </div>

            <div className="flex flex-wrap gap-1.5 pt-1">
              {tags.length === 0 ? (
                <span className="text-[11px] text-muted-foreground italic">Chưa gắn tag nào</span>
              ) : (
                tags.map((t) => (
                  <Badge
                    key={t}
                    variant="secondary"
                    className="gap-1 pl-1.5 pr-1 py-0.5 text-[11px] rounded-md font-semibold select-none group"
                  >
                    <Tag className="size-2.5 opacity-60" />
                    <span>{t}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveTag(t)}
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

        {/* Footer Actions */}
        <DialogFooter className="px-5 py-3.5 border-t border-border/60 bg-muted/20 flex flex-row items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2">
            {isDirty && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-9 text-xs font-semibold rounded-lg text-muted-foreground hover:text-foreground"
                onClick={handleRevert}
                disabled={updateMutation.isPending}
              >
                <RotateCcw className="size-3.5 mr-1.5" /> Khôi phục
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-9 text-xs font-semibold rounded-lg"
              onClick={() => onOpenChange(false)}
              disabled={updateMutation.isPending}
            >
              Hủy
            </Button>

            <Button
              type="button"
              size="sm"
              className="h-9 text-xs font-bold rounded-lg shadow-sm bg-orange-600 hover:bg-orange-700 text-white dark:bg-orange-500 dark:hover:bg-orange-600"
              onClick={handleSubmit}
              disabled={!isDirty || updateMutation.isPending}
              title="Lưu thay đổi (Ctrl+Enter)"
            >
              {updateMutation.isPending ? (
                <LoaderCircle className="size-3.5 mr-1.5 animate-spin" />
              ) : (
                <Save className="size-3.5 mr-1.5" />
              )}
              Lưu thay đổi
              <kbd className="hidden sm:inline-block ml-1.5 rounded bg-black/20 dark:bg-white/20 px-1 py-0.2 text-[9px] font-mono font-medium">
                Ctrl+↵
              </kbd>
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
