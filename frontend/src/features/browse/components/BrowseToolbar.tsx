import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Search, Sliders, ChevronDown, Trash2, Volume2, PenTool } from 'lucide-react'
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
    setIsTtsModalOpen,
    setLocalAudioEngineId,
    setLocalAudioDefaultVoiceId,
    setLocalAudioTargetCardIds,
    setIsLocalAudioModalOpen,
    setIsStrokeModalOpen,
    setStrokeModalMode,
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

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-8 rounded-lg text-xs gap-1 bg-muted/50">
                  <span>Thao tác hàng loạt</span>
                  <ChevronDown className="size-3 opacity-60" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                {/* Stroke Diagram Generation Trigger */}
                <DropdownMenuItem
                  onClick={() => {
                    setStrokeModalMode('batch')
                    setIsStrokeModalOpen(true)
                  }}
                  className="flex items-center gap-2 font-medium cursor-pointer"
                >
                  <PenTool className="size-4 text-primary shrink-0" />
                  <span>Tạo nét Kanji/Hanzi</span>
                </DropdownMenuItem>

                {/* Voice Generation Trigger */}
                <DropdownMenuItem
                  onClick={() => setIsTtsModalOpen(true)}
                  className="flex items-center gap-2 font-medium cursor-pointer"
                >
                  <Volume2 className="size-4 text-primary shrink-0" />
                  <span>Tạo audio VoiceVox</span>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => {
                    setLocalAudioEngineId('voicevox')
                    setLocalAudioDefaultVoiceId('3')
                    setLocalAudioTargetCardIds(selectedCards)
                    setIsLocalAudioModalOpen(true)
                  }}
                  className="flex items-center justify-between font-medium cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <Volume2 className="size-4 text-emerald-600 shrink-0" />
                    <span>Tạo audio local</span>
                  </div>
                  <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 border-emerald-200">
                    Local
                  </Badge>
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => {
                    if (window.confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn ${selectedCards.length} thẻ đã chọn?`)) {
                      bulkDeleteMutation.mutate(selectedCards)
                    }
                  }}
                  disabled={bulkDeleteMutation.isPending}
                  className="flex items-center gap-2 text-destructive focus:text-destructive focus:bg-destructive/10 font-medium cursor-pointer"
                >
                  <Trash2 className="size-4 shrink-0" />
                  <span>Xóa thẻ vĩnh viễn</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
      </div>
    </div>
  )
}
