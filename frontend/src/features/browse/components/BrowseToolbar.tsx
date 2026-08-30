import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { Search, Sliders, Trash2, Plus } from 'lucide-react'
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
