import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import {
  Layers,
  LoaderCircle,
  Plus,
  RotateCcw,
  Save,
  Tag,
  Trash2,
  X,
} from 'lucide-react'
import type { useBrowseState } from '../hooks/useBrowseState'
import { statusLabel, statusVariant } from '../utils/formatter'

interface BrowseCardEditorProps {
  browse: ReturnType<typeof useBrowseState>
}

export function BrowseCardEditor({ browse }: BrowseCardEditorProps) {
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
    handleRevert,
    handleAddTag,
    handleRemoveTag,
    updateMutation,
    deleteMutation,
    mobileTab,
    setMobileTab,
  } = browse

  if (!activeCardId) {
    return (
      <div className="hidden lg:flex w-80 border-l border-border/60 flex-col items-center justify-center p-8 bg-muted/5 shrink-0 text-center">
        <Layers className="size-10 text-muted-foreground opacity-60 mb-2.5" />
        <h3 className="font-bold text-sm text-foreground">Chưa chọn thẻ</h3>
        <p className="text-xs text-muted-foreground max-w-44 mt-1 leading-relaxed">
          Nhấp vào bất kỳ thẻ nào trong bảng để xem chi tiết trường và thực hiện cập nhật.
        </p>
      </div>
    )
  }

  if (cardDetailQuery.isPending) {
    return (
      <div className="w-full lg:w-80 border-l border-border/60 p-4 space-y-4 shrink-0 bg-muted/10">
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

  return (
    <div className={`w-full lg:w-80 border-l border-border/60 flex flex-col bg-muted/5 shrink-0 h-full overflow-hidden ${mobileTab === 'editor' ? 'flex' : 'hidden lg:flex'}`}>
      {/* Editor Header */}
      <div className="px-4 py-3 border-b border-border/60 flex items-center justify-between bg-background shrink-0">
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant(detail.card.status)} className="text-[10px] px-1.5 py-0 font-semibold">
            {statusLabel(detail.card.status)}
          </Badge>
          <span className="text-xs font-bold text-foreground">Chi tiết Note</span>
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full" onClick={() => {
          setActiveCardId(null)
          setMobileTab('cards')
        }}>
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
            onChange={(e) => setEditDeckId(Number(e.target.value))}
            className="h-9 text-xs sm:text-sm rounded-lg"
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
                  className="min-h-20 text-xs sm:text-sm rounded-xl leading-relaxed resize-y"
                />
              ) : (
                <Input
                  value={val}
                  onChange={(e) =>
                    setEditFieldValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                  }
                  className="h-9 text-xs sm:text-sm rounded-lg"
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
              className="h-8 rounded-lg text-xs"
            />
            <Button size="sm" variant="outline" className="h-8 px-2.5 rounded-lg text-xs" onClick={handleAddTag}>
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
              className="flex-1 h-9 text-xs font-semibold rounded-lg"
              onClick={handleRevert}
              disabled={updateMutation.isPending}
            >
              <RotateCcw className="size-3.5 mr-1" /> Hủy
            </Button>
          )}

          <Button
            size="sm"
            className="flex-1 h-9 text-xs font-bold rounded-lg shadow-sm"
            onClick={() => {
              void updateMutation.mutate({
                field_values: editFieldValues,
                deck_id: editDeckId || undefined,
                tags: editTags,
              })
            }}
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
          className="w-full h-8 text-[11px] text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/25 rounded-lg"
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
