import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Search, Sliders, Trash2, Plus, AlertTriangle } from 'lucide-react'
import type { useBrowseState } from '../hooks/useBrowseState'

interface BrowseToolbarProps {
  browse: ReturnType<typeof useBrowseState>
}

export function BrowseToolbar({ browse }: BrowseToolbarProps) {
  const {
    queryText,
    setQueryText,
    statusFilter,
    setStatusFilter,
    selectedCards,
    selectedDeck,
    bulkDeleteMutation,
    handleStartCreateCard,
  } = browse

  return (
    <div className="flex flex-col sm:flex-row gap-2.5 p-3 border-b border-border/60 bg-background shrink-0">
      {/* Search Bar Input */}
      <div className="relative flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder="Tìm từ vựng, cách đọc, ý nghĩa..."
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          className="pl-9 h-9 rounded-xl text-xs sm:text-sm bg-muted/50"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Add Card Button */}
        <Button
          type="button"
          size="sm"
          onClick={handleStartCreateCard}
          className="h-8 rounded-lg text-xs font-bold gap-1 bg-primary text-primary-foreground hover:opacity-95 shadow-xs shrink-0"
        >
          <Plus className="size-3.5" />
          <span>Thêm thẻ</span>
        </Button>

        {/* Status filter dropdown mapping */}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-semibold">
          <Sliders className="size-3.5 text-muted-foreground" />
          <NativeSelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-8 py-0 pl-2 pr-6 text-xs rounded-lg bg-muted/50"
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="new">Mới (New)</option>
            <option value="learning">Đang học (Learn)</option>
            <option value="review">Đến hạn (Due)</option>
          </NativeSelect>
        </div>

        {/* Selected Deck indicator when no individual cards are ticked */}
        {selectedCards.length === 0 && selectedDeck && (
          <div className="flex items-center gap-1.5 animate-in fade-in slide-in-from-right-3">
            <Badge variant="outline" className="text-xs font-semibold px-2.5 py-1 rounded-lg gap-1.5 bg-muted/40 border-border/80 text-foreground">
              <span className="text-muted-foreground font-normal">Đang chọn:</span>
              <span className="font-bold text-foreground truncate max-w-36 sm:max-w-60">{selectedDeck.name}</span>
              <span className="text-muted-foreground font-medium">({selectedDeck.counts?.total ?? 0} thẻ)</span>
            </Badge>

            {selectedDeck.has_mixed_note_types ? (
              <Badge
                variant="outline"
                className="text-[11px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/30 gap-1 px-2 py-0.5"
                title={`Bộ deck chứa nhiều loại Note Type khác nhau: ${selectedDeck.note_type_names?.join(', ')}`}
              >
                <AlertTriangle className="size-3 shrink-0" />
                <span>Nhiều Note Type ({selectedDeck.note_type_names?.length || selectedDeck.note_type_ids?.length || 2})</span>
              </Badge>
            ) : selectedDeck.note_type_name ? (
              <Badge
                variant="outline"
                className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/30 px-2 py-0.5"
              >
                <span>Mẫu: {selectedDeck.note_type_name}</span>
              </Badge>
            ) : null}
          </div>
        )}

        {/* Selected cards Bulk actions */}
        {selectedCards.length > 0 && (
          <div className="flex items-center gap-1.5 animate-in fade-in slide-in-from-right-3">
            <Badge variant="secondary" className="text-xs font-semibold px-2 py-0.5 rounded-md">
              Đã chọn: {selectedCards.length} thẻ
            </Badge>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                if (window.confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn ${selectedCards.length} thẻ đã chọn?`)) {
                  bulkDeleteMutation.mutate(selectedCards)
                }
              }}
              disabled={bulkDeleteMutation.isPending}
              className="h-8 rounded-lg text-xs gap-1.5 text-destructive hover:bg-destructive/10 hover:text-destructive border-destructive/30 bg-background"
            >
              <Trash2 className="size-3.5 shrink-0" />
              <span>Xóa {selectedCards.length} thẻ</span>
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
