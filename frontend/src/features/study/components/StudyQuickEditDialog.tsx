import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
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
import { LoaderCircle, Pencil, PenTool, Plus, RotateCcw, Save, Tag, X } from 'lucide-react'
import { appApi } from '@/app/api'
import { resolveBackendUrl } from '@/config/env'
import { MediaFieldPreview } from '@/features/browse/components/MediaFieldPreview'
import { BrowseStrokeModal } from '@/features/browse/components/BrowseStrokeModal'
import type { StudyContentArtifact, StudyMediaArtifact, StudyTemplateArtifact } from '../types'
import type { CardDetailResponse } from '@/features/browse/hooks/useBrowseState'

type UpdateCardResponse = {
  success: boolean
  row?: unknown
  detail?: CardDetailResponse
}

function inferFieldType(
  rawFieldType?: string | null,
  fieldName?: string,
  fieldValue?: string,
): 'image' | 'audio' | 'diagram' | 'text' {
  const ft = (rawFieldType || '').trim().toLowerCase()
  if (ft === 'image' || ft === 'audio' || ft === 'diagram') {
    return ft
  }

  const name = (fieldName || '').trim().toLowerCase()
  if (
    name === 'audio' ||
    name === 'sound' ||
    name === 'voice' ||
    name.endsWith('_audio') ||
    name.endsWith(' audio') ||
    name.endsWith('_sound') ||
    name.endsWith(' sound')
  ) {
    return 'audio'
  }

  if (
    name === 'image' ||
    name === 'picture' ||
    name === 'photo' ||
    name === 'diagram' ||
    name === 'illustration' ||
    name.endsWith('_image') ||
    name.endsWith(' image') ||
    name.endsWith('_photo') ||
    name.endsWith(' photo') ||
    name.endsWith('_picture') ||
    name.endsWith(' picture')
  ) {
    return 'image'
  }

  const val = (fieldValue || '').trim()
  if (val.startsWith('[sound:') || /\.(mp3|wav|ogg|opus|m4a|aac|flac)(\?.*)?$/i.test(val)) {
    return 'audio'
  }
  if (/\.(png|jpe?g|webp|gif|svg|avif)(\?.*)?$/i.test(val)) {
    return 'image'
  }

  return 'text'
}

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
    newFieldValues: Record<string, string>,
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
  const queryClient = useQueryClient()

  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [initialFieldValues, setInitialFieldValues] = useState<Record<string, string>>({})
  const [tags, setTags] = useState<string[]>([])
  const [initialTags, setInitialTags] = useState<string[]>([])
  const [newTagInput, setNewTagInput] = useState('')
  const [deckId, setDeckId] = useState<number | null>(null)
  const [initialDeckId, setInitialDeckId] = useState<number | null>(null)
  const [isStrokeModalOpen, setIsStrokeModalOpen] = useState(false)

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
      setIsStrokeModalOpen(false)
    }
  }, [open, content])

  const handleApplyStrokes = useCallback((targetFieldName: string, urls: string) => {
    setFieldValues((prev) => ({
      ...prev,
      [targetFieldName]: urls,
    }))
  }, [])

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

  // Media resolver map: maps filename or relative reference to fully resolved proxy URL
  const mediaMap = useMemo(() => {
    const map = new Map<string, string>()
    if (cardDetailQuery.data?.media_assets) {
      for (const asset of cardDetailQuery.data.media_assets) {
        if (asset.filename && asset.url) {
          map.set(asset.filename.toLowerCase(), resolveBackendUrl(asset.url))
        }
      }
    }
    if (content?.media) {
      for (const m of content.media) {
        if (m.filename && m.proxy_url) {
          map.set(m.filename.toLowerCase(), resolveBackendUrl(m.proxy_url))
        }
      }
    }
    return map
  }, [cardDetailQuery.data?.media_assets, content?.media])

  const mediaResolver = useCallback(
    (rawRef: string) => {
      return mediaMap.get(rawRef.toLowerCase())
    },
    [mediaMap],
  )

  // Save Mutation
  const updateMutation = useMutation({
    mutationFn: (payload: {
      field_values: Record<string, string>
      deck_id?: number
      tags?: string[]
    }) => appApi.mutate<UpdateCardResponse>(`/browse/cards/${cardId}`, 'PATCH', payload),
    onSuccess: async (data) => {
      toast.success('Đã lưu thay đổi thẻ.')
      const committedFieldValues = data?.detail?.note?.field_values || fieldValues
      setInitialFieldValues(committedFieldValues)
      setFieldValues(committedFieldValues)
      setInitialTags(tags)
      setInitialDeckId(deckId)

      if (cardId) {
        const mediaAssets: StudyMediaArtifact[] = (data?.detail?.media_assets || []).map((asset) => ({
          id: asset.id,
          field_name: asset.field_name || '',
          filename: asset.filename || '',
          mime_type: asset.mime_type || '',
          sha256: '',
          proxy_url: asset.url,
        }))
        const options = {
          media: mediaAssets.length > 0 ? mediaAssets : undefined,
          noteId: data?.detail?.note?.id != null ? String(data.detail.note.id) : undefined,
        }
        if (options.media || options.noteId) {
          await onCardUpdated(cardId, committedFieldValues, options)
        } else {
          await onCardUpdated(cardId, committedFieldValues)
        }
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

  // Resolve fields definition:
  // 1. Prefer cardDetailQuery.data.fields (authoritative backend definition with clone overlay & note type types)
  // 2. Fallback to template?.field_defs (immediate 0ms study session cache)
  // 3. Fallback to keys in fieldValues
  const fieldDefs = useMemo(() => {
    const rawDefs =
      cardDetailQuery.data?.fields && cardDetailQuery.data.fields.length > 0
        ? cardDetailQuery.data.fields
        : template?.field_defs && template.field_defs.length > 0
        ? template.field_defs
        : Object.keys(fieldValues).map((name, index) => ({
            name,
            position: index,
            required: false,
            field_type: 'text',
          }))

    return rawDefs.map((f, index) => {
      const val = initialFieldValues[f.name] || fieldValues[f.name] || ''
      const detectedType = inferFieldType(f.field_type, f.name, val)
      return {
        name: f.name,
        position: f.position ?? index,
        required: Boolean(f.required),
        field_type: detectedType,
      }
    })
  }, [cardDetailQuery.data?.fields, template?.field_defs, fieldValues, initialFieldValues])

  const deckList = cardDetailQuery.data?.decks || []

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[calc(100%-1rem)] sm:w-full sm:max-w-2xl max-h-[92dvh] sm:max-h-[88vh] flex flex-col p-0 gap-0 overflow-hidden bg-card border-border/80 shadow-2xl rounded-2xl"
        onKeyDown={handleKeyDown}
      >
        {/* Header */}
        <DialogHeader className="px-3.5 py-3 sm:px-5 sm:py-4 border-b border-border/60 bg-muted/20 shrink-0">
          <div className="flex items-center justify-between gap-2 sm:gap-3 pr-9 sm:pr-8">
            <div className="flex items-center gap-2 min-w-0">
              <div className="size-7 sm:size-8 rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400 flex items-center justify-center shrink-0">
                <Pencil className="size-3.5 sm:size-4" />
              </div>
              <div className="min-w-0">
                <DialogTitle className="text-sm sm:text-base font-bold text-foreground flex items-center gap-1.5 sm:gap-2 truncate">
                  <span>Sửa nhanh thẻ</span>
                  {deckName && (
                    <Badge variant="outline" className="text-[10px] sm:text-[11px] font-normal px-1.5 sm:px-2 py-0 shrink-0 truncate max-w-[120px] sm:max-w-xs">
                      {deckName}
                    </Badge>
                  )}
                </DialogTitle>
                <DialogDescription className="text-[11px] sm:text-xs text-muted-foreground mt-0.5 truncate hidden xs:block">
                  Chỉnh sửa các trường từ vựng và nội dung mà không làm gián đoạn phiên học.
                </DialogDescription>
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 px-2 sm:px-2.5 text-xs font-semibold gap-1.5 rounded-lg bg-background/80 hover:bg-muted shrink-0 border-border/80 shadow-2xs"
              title="Tạo sơ đồ thứ tự nét Kanji & Hanzi cho thẻ này"
              onClick={() => setIsStrokeModalOpen(true)}
            >
              <PenTool className="size-3.5 text-primary" />
              <span className="hidden sm:inline">Tạo nét</span>
            </Button>
          </div>
        </DialogHeader>

        {/* Scrollable Form Body */}
        <div className="flex-1 overflow-y-auto overscroll-contain p-3.5 sm:p-5 space-y-3.5 sm:space-y-4 min-h-0 pb-6 sm:pb-8">
          {/* Destination Deck Selection (if available) */}
          {deckList.length > 0 && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Deck lưu trữ
              </Label>
              <NativeSelect
                value={deckId !== null ? String(deckId) : ''}
                onChange={(e) => setDeckId(Number(e.target.value))}
                className="h-10 sm:h-9 text-base sm:text-sm rounded-lg bg-muted/50"
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
            const ft = field.field_type

            if (ft === 'image' || ft === 'audio' || ft === 'diagram') {
              return (
                <MediaFieldPreview
                  key={field.name}
                  fieldName={field.name}
                  fieldType={ft}
                  value={val}
                  onChange={(v) =>
                    setFieldValues((prev) => ({ ...prev, [field.name]: v }))
                  }
                  required={field.required}
                  resolveUrl={mediaResolver}
                />
              )
            }

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
                    className="min-h-20 text-base sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50 focus:bg-background transition-colors"
                  />
                ) : (
                  <Input
                    value={val}
                    onChange={(e) =>
                      setFieldValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                    }
                    placeholder={`Nhập ${field.name}…`}
                    className="h-10 sm:h-9 text-base sm:text-sm rounded-lg bg-muted/50 focus:bg-background transition-colors"
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
                className="h-10 sm:h-8 rounded-lg text-base sm:text-xs bg-muted/50 flex-1"
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-10 sm:h-8 px-3.5 sm:px-2.5 rounded-lg text-xs font-semibold bg-muted/50 hover:bg-muted border-border shrink-0"
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
                    className="gap-1 pl-2 sm:pl-1.5 pr-1.5 sm:pr-1 py-1 sm:py-0.5 text-xs sm:text-[11px] rounded-md font-semibold select-none group"
                  >
                    <Tag className="size-3 sm:size-2.5 opacity-60" />
                    <span>{t}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveTag(t)}
                      className="p-1 sm:p-0.5 rounded-full hover:bg-muted-foreground/15 text-muted-foreground hover:text-foreground shrink-0"
                    >
                      <X className="size-3 sm:size-2.5" />
                    </button>
                  </Badge>
                ))
              )}
            </div>
          </div>
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
                disabled={updateMutation.isPending}
              >
                <RotateCcw className="size-3.5 sm:mr-1.5" />
                <span className="hidden xs:inline">Khôi phục</span>
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
              disabled={updateMutation.isPending}
            >
              Hủy
            </Button>

            <Button
              type="button"
              size="sm"
              className="h-10 sm:h-9 px-4 text-xs font-bold rounded-lg shadow-sm bg-orange-600 hover:bg-orange-700 text-white dark:bg-orange-500 dark:hover:bg-orange-600 flex-1 sm:flex-initial justify-center"
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
  </>
  )
}
