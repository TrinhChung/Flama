import React, { useState, useRef, useCallback, useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import {
  Layers,
  LoaderCircle,
  PenTool,
  Plus,
  RotateCcw,
  Save,
  Tag,
  Trash2,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import type { useBrowseState } from '../hooks/useBrowseState'
import { statusLabel, statusVariant } from '../utils/formatter'
import { MediaFieldPreview } from './MediaFieldPreview'

interface BrowseCardEditorProps {
  browse: ReturnType<typeof useBrowseState>
}

export function BrowseCardEditor({ browse }: BrowseCardEditorProps) {
  const {
    activeCardId,
    setActiveCardId,
    isCreatingCard,
    createNoteTypeId,
    setCreateNoteTypeId,
    noteTypesQuery,
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
    handleRevert,
    handleStartCreateCard,
    handleCancelCreate,
    createMutation,
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

  const [editorWidth, setEditWidth] = useState(() => {
    try {
      const saved = localStorage.getItem('flama:browse:editor-width')
      if (saved) return Number(saved)
    } catch {}
    return 320 // default width
  })
  const isResizing = useRef(false)
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth < 768
    }
    return false
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    const media = window.matchMedia('(max-width: 767px)')
    const listener = () => setIsMobile(media.matches)
    media.addEventListener('change', listener)
    return () => media.removeEventListener('change', listener)
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isResizing.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isResizing.current) return
      const newWidth = window.innerWidth - moveEvent.clientX
      const minWidth = 280
      const maxWidth = Math.min(800, window.innerWidth * 0.6)
      if (newWidth >= minWidth && newWidth <= maxWidth) {
        setEditWidth(newWidth)
        try {
          localStorage.setItem('flama:browse:editor-width', String(newWidth))
        } catch {}
      }
    }

    const handleMouseUp = () => {
      isResizing.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
  }, [])

  if (!activeCardId && !isCreatingCard) {
    return (
      <div
        style={{ width: `${editorWidth}px` }}
        className="hidden lg:flex border-l border-border/60 flex-col items-center justify-center p-8 bg-card shrink-0 text-center relative"
      >
        {/* Resize Handle */}
        <div
          className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/60 hover:w-1.5 transition-all bg-border/20 z-50"
          onMouseDown={handleMouseDown}
        />
        <Layers className="size-10 text-muted-foreground opacity-60 mb-2.5" />
        <h3 className="font-bold text-sm text-foreground">Chưa chọn thẻ</h3>
        <p className="text-xs text-muted-foreground max-w-48 mt-1 leading-relaxed">
          Nhấp vào bất kỳ thẻ nào trong bảng để xem chi tiết trường hoặc bấm thêm thẻ để tạo mới.
        </p>
        <Button
          size="sm"
          className="mt-4 text-xs font-semibold rounded-lg gap-1.5 bg-primary text-primary-foreground hover:opacity-95 shadow-xs"
          onClick={handleStartCreateCard}
        >
          <Plus className="size-3.5" />
          <span>Thêm thẻ mới</span>
        </Button>
      </div>
    )
  }

  if (isCreatingCard) {
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
      (f) => f.name.trim().toLowerCase() !== 'stt'
    )

    const submitCreateCard = () => {
      if (!editDeckId) {
        toast.error('Vui lòng chọn deck lưu trữ')
        return
      }
      const noteTypeId = effectiveNoteTypeId || selectedNoteType?.id
      if (!noteTypeId) {
        toast.error('Vui lòng chọn mẫu thẻ')
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
        field_values: payloadFields,
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
          onMouseDown={handleMouseDown}
        />
        {/* Editor Header */}
        <div className="px-4 py-3 border-b border-border/60 flex items-center justify-between bg-background shrink-0">
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
              Thẻ mới
            </Badge>
            <span className="text-xs font-bold text-foreground">Tạo thẻ mới</span>
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

        {/* Editor Body Fields Scrollable */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {/* Destination Deck selection */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Deck lưu trữ</Label>
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
              {noteTypesQuery.isPending ? 'Đang tải mẫu thẻ...' : 'Mẫu thẻ này chưa có trường nào.'}
            </div>
          ) : (
            fields.map((field) => {
              const val = editFieldValues[field.name] || ''
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
            <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Tags (Nhãn)</Label>
            <div className="flex gap-1.5">
              <Input
                placeholder="Tag mới…"
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
                <span className="text-[11px] text-muted-foreground italic">Chưa gắn tag nào</span>
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
              <RotateCcw className="size-3.5 mr-1" /> Hủy
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
              Tạo thẻ
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (cardDetailQuery.isPending) {
    return (
      <div
        style={{ width: isMobile ? '100%' : `${editorWidth}px` }}
        className={`border-l border-border/60 p-4 space-y-4 shrink-0 bg-card relative flex flex-col h-full ${
          mobileTab === 'editor' ? 'flex' : 'hidden lg:flex'
        }`}
      >
        {/* Resize Handle */}
        <div
          className="hidden lg:block absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/60 hover:w-1.5 transition-all bg-border/20 z-50"
          onMouseDown={handleMouseDown}
        />
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-muted rounded w-2/3" />
          <div className="h-4 bg-muted rounded w-1/3" />
          <div className="space-y-4 pt-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-1.5">
                <div className="h-3 bg-muted rounded w-1/4" />
                <div className="h-16 bg-muted rounded-xl" />
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const detail = cardDetailQuery.data
  if (!detail) return null

  const deckList = detail.decks || decksQuery.data?.decks || []

  const submitUpdateCard = () => {
    if (!isDirty || updateMutation.isPending) return
    void updateMutation.mutate({
      field_values: editFieldValues,
      deck_id: editDeckId || undefined,
      tags: editTags,
    })
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
        onMouseDown={handleMouseDown}
      />
      {/* Editor Header */}
      <div className="px-4 py-3 border-b border-border/60 flex items-center justify-between bg-background shrink-0">
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant(detail.card.status)} className="text-[10px] px-1.5 py-0 font-semibold">
            {statusLabel(detail.card.status)}
          </Badge>
          <span className="text-xs font-bold text-foreground">Chi tiết Note</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-[11px] font-semibold gap-1 rounded-lg bg-muted/40 hover:bg-muted"
            title="Tạo sơ đồ thứ tự nét Kanji & Hanzi cho thẻ này"
            onClick={() => {
              setStrokeModalMode('single')
              setStrokeModalCardId(activeCardId)
              setIsStrokeModalOpen(true)
            }}
          >
            <PenTool className="size-3 text-primary" />
            <span className="hidden sm:inline">Tạo nét</span>
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full" onClick={() => {
            setActiveCardId(null)
            setMobileTab('cards')
          }}>
            <X className="size-4" />
          </Button>
        </div>
      </div>

      {/* Editor Body Fields Scrollable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Destination Deck selection */}
        <div className="space-y-1.5">
          <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Deck lưu trữ</Label>
          <NativeSelect
            value={editDeckId !== null ? String(editDeckId) : ''}
            onChange={(e) => setEditDeckId(Number(e.target.value))}
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
        {detail.fields.map((field) => {
          const val = editFieldValues[field.name] || ''
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

          const isMultiline = val.length > 50 || val.includes('\n') || field.name.toLowerCase().includes('meaning')

          return (
            <div key={field.name} className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {field.name} {field.required && <span className="text-destructive">*</span>}
              </Label>
              {isMultiline ? (
                <Textarea
                  value={val}
                  onChange={(e) =>
                    setEditFieldValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                  }
                  className="min-h-20 text-xs sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50"
                />
              ) : (
                <Input
                  value={val}
                  onChange={(e) =>
                    setEditFieldValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                  }
                  className="h-9 text-xs sm:text-sm rounded-lg bg-muted/50"
                />
              )}
            </div>
          )
        })}

        {/* Tags management */}
        <div className="space-y-2">
          <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Tags (Nhãn)</Label>
          <div className="flex gap-1.5">
            <Input
              placeholder="Tag mới…"
              value={newTagInput}
              onChange={(e) => setNewTagInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAddTag()}
              className="h-8 rounded-lg text-xs bg-muted/50"
            />
            <Button size="sm" variant="outline" className="h-8 px-2.5 rounded-lg text-xs bg-muted/50 hover:bg-muted border-border" onClick={handleAddTag}>
              <Plus className="size-3.5" />
            </Button>
          </div>

          <div className="flex flex-wrap gap-1.5 pt-1.5">
            {editTags.length === 0 ? (
              <span className="text-[11px] text-muted-foreground italic">Chưa gắn tag nào</span>
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
              <RotateCcw className="size-3.5 mr-1" /> Hủy
            </Button>
          )}

          <Button
            size="sm"
            className="flex-1 h-9 text-xs font-bold rounded-lg shadow-sm disabled:bg-muted disabled:text-muted-foreground disabled:border disabled:border-border/50 disabled:shadow-none disabled:opacity-100"
            onClick={submitUpdateCard}
            disabled={!isDirty || updateMutation.isPending}
          >
            {updateMutation.isPending ? (
              <LoaderCircle className="size-3.5 mr-1 animate-spin" />
            ) : (
              <Save className="size-3.5 mr-1" />
            )}
            Lưu thẻ
          </Button>
        </div>

        <Button
          variant="outline"
          size="sm"
          className="w-full h-8 text-[11px] text-destructive hover:text-white hover:bg-destructive border-destructive/40 hover:border-destructive bg-background rounded-lg transition-all"
          onClick={() => {
            if (window.confirm('Bạn có chắc chắn muốn xóa vĩnh viễn thẻ này? Thao tác này không thể hoàn tác.')) {
              void deleteMutation.mutate(detail.card.card_id)
            }
          }}
          disabled={deleteMutation.isPending}
        >
          <Trash2 className="size-3.5 mr-1.5" /> Xóa thẻ vĩnh viễn
        </Button>
      </div>
    </div>
  )
}
