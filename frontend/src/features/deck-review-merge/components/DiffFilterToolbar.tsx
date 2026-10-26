import { useState, useEffect, type ChangeEvent } from 'react'
import {
  CheckSquare,
  Square,
  Layers,
  RotateCcw,
  PlusCircle,
  Edit3,
  Trash2,
  AlertTriangle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { SearchInput } from '@/shared/ui'
import type { DiffChangeFilter } from '@/entities/card-diff'
import type { DiffFilterToolbarProps } from '../model/types'

export function DiffFilterToolbar({
  filters,
  summary,
  groups,
  visibleCount,
  selectedCount,
  onFiltersChange,
  onToggleSelectAllVisible,
  className = '',
}: DiffFilterToolbarProps) {
  const [searchVal, setSearchVal] = useState(filters.searchQuery)

  // Sync internal search value if parent updates filters
  useEffect(() => {
    setSearchVal(filters.searchQuery)
  }, [filters.searchQuery])

  // Debounced search propagation
  useEffect(() => {
    const handler = setTimeout(() => {
      if (searchVal !== filters.searchQuery) {
        onFiltersChange({ ...filters, searchQuery: searchVal })
      }
    }, 200)

    return () => clearTimeout(handler)
  }, [searchVal, filters, onFiltersChange])

  const handleSelectNoteType = (e: ChangeEvent<HTMLSelectElement>) => {
    onFiltersChange({ ...filters, noteTypeId: e.target.value })
  }

  const handleSelectChangeType = (type: DiffChangeFilter) => {
    onFiltersChange({ ...filters, changeType: type })
  }

  const handleResetFilters = () => {
    setSearchVal('')
    onFiltersChange({
      changeType: 'all',
      noteTypeId: 'all',
      searchQuery: '',
    })
  }

  const hasActiveFilters =
    filters.changeType !== 'all' ||
    filters.noteTypeId !== 'all' ||
    filters.searchQuery.trim().length > 0

  const isAllVisibleSelected = visibleCount > 0 && selectedCount >= visibleCount

  return (
    <div
      className={`space-y-3 p-3 sm:p-4 rounded-2xl border border-border/80 bg-card shadow-xs transition-colors ${className}`}
      data-testid="diff-filter-toolbar"
    >
      {/* Top row: Search, Note Type Dropdown, and Global Select All */}
      <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
        <div className="flex flex-1 flex-wrap items-center gap-2 sm:gap-3 min-w-[280px]">
          {/* Search Bar */}
          <div className="w-full sm:w-72">
            <SearchInput
              value={searchVal}
              onChange={(e) => setSearchVal(e.target.value)}
              onClear={() => setSearchVal('')}
              placeholder="Tìm kiếm từ vựng, hán tự, nghĩa..."
              size="sm"
              aria-label="Tìm kiếm nội dung thẻ"
            />
          </div>

          {/* Note Type Selector */}
          <div className="flex items-center gap-1.5 max-w-full">
            <label htmlFor="note-type-filter" className="sr-only">
              Lọc theo Loại thẻ
            </label>
            <div className="relative inline-flex items-center max-w-full">
              <Layers className="pointer-events-none absolute left-2.5 size-3.5 text-muted-foreground" />
              <select
                id="note-type-filter"
                value={filters.noteTypeId}
                onChange={handleSelectNoteType}
                className="h-8 pl-8 pr-3 text-xs rounded-lg border border-border bg-background text-foreground font-medium hover:border-border/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer max-w-full truncate"
                aria-label="Chọn loại thẻ"
              >
                <option value="all">Tất cả Loại thẻ ({summary.totalNotes})</option>
                {groups.map((group) => (
                  <option key={group.noteTypeId} value={group.noteTypeId}>
                    {group.noteTypeName} ({group.totalCount})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Reset Filters CTA if any filter is active */}
          {hasActiveFilters && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleResetFilters}
              className="h-8 sm:h-7 min-h-[38px] sm:min-h-[28px] text-xs text-muted-foreground hover:text-foreground gap-1 px-2"
              title="Đặt lại bộ lọc"
            >
              <RotateCcw className="size-3" />
              <span>Đặt lại</span>
            </Button>
          )}
        </div>

        {/* Global Select All Visible */}
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onToggleSelectAllVisible}
            disabled={visibleCount === 0}
            className="h-8 sm:h-7 min-h-[38px] sm:min-h-[28px] text-xs gap-1.5 font-medium"
            aria-label={
              isAllVisibleSelected
                ? 'Bỏ chọn tất cả thẻ đang hiển thị'
                : 'Chọn tất cả thẻ đang hiển thị'
            }
          >
            {isAllVisibleSelected ? (
              <CheckSquare className="size-3.5 text-primary" />
            ) : (
              <Square className="size-3.5 text-muted-foreground" />
            )}
            <span>
              {isAllVisibleSelected ? 'Bỏ chọn tất cả' : 'Chọn tất cả'} ({visibleCount})
            </span>
          </Button>
        </div>
      </div>

      {/* Bottom row: Change Type Filter Pills */}
      <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-border/50">
        <span className="text-[11px] font-semibold text-muted-foreground mr-1">Loại thay đổi:</span>

        {/* All */}
        <button
          type="button"
          onClick={() => handleSelectChangeType('all')}
          className={`inline-flex items-center gap-1.5 h-8 sm:h-7 min-h-[38px] sm:min-h-[28px] px-2.5 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
            filters.changeType === 'all'
              ? 'bg-primary text-primary-foreground border-primary shadow-2xs'
              : 'bg-card text-muted-foreground border-border/70 hover:bg-muted hover:text-foreground'
          }`}
          aria-pressed={filters.changeType === 'all'}
        >
          <span>Tất cả</span>
          <Badge
            variant="secondary"
            className={`text-[10px] h-4 px-1.5 font-mono ${
              filters.changeType === 'all'
                ? 'bg-primary-foreground/20 text-primary-foreground'
                : 'bg-muted text-muted-foreground'
            }`}
          >
            {summary.totalNotes}
          </Badge>
        </button>

        {/* Added */}
        <button
          type="button"
          onClick={() => handleSelectChangeType('added')}
          className={`inline-flex items-center gap-1.5 h-8 sm:h-7 min-h-[38px] sm:min-h-[28px] px-2.5 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
            filters.changeType === 'added'
              ? 'bg-emerald-600 text-white border-emerald-600 shadow-2xs'
              : 'bg-card text-emerald-700 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10'
          }`}
          aria-pressed={filters.changeType === 'added'}
        >
          <PlusCircle className="size-3 shrink-0" />
          <span>Thêm mới</span>
          <Badge
            variant="secondary"
            className={`text-[10px] h-4 px-1.5 font-mono ${
              filters.changeType === 'added'
                ? 'bg-white/20 text-white'
                : 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300'
            }`}
          >
            {summary.addedCount}
          </Badge>
        </button>

        {/* Modified */}
        <button
          type="button"
          onClick={() => handleSelectChangeType('modified')}
          className={`inline-flex items-center gap-1.5 h-8 sm:h-7 min-h-[38px] sm:min-h-[28px] px-2.5 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
            filters.changeType === 'modified'
              ? 'bg-amber-500 text-amber-950 font-bold border-amber-600 shadow-2xs'
              : 'bg-card text-amber-800 dark:text-amber-300 border-amber-500/30 hover:bg-amber-500/10'
          }`}
          aria-pressed={filters.changeType === 'modified'}
        >
          <Edit3 className="size-3 shrink-0" />
          <span>Đã sửa</span>
          <Badge
            variant="secondary"
            className={`text-[10px] h-4 px-1.5 font-mono ${
              filters.changeType === 'modified'
                ? 'bg-amber-950/20 text-amber-950 font-bold'
                : 'bg-amber-500/15 text-amber-800 dark:text-amber-300'
            }`}
          >
            {summary.modifiedCount}
          </Badge>
        </button>

        {/* Removed */}
        <button
          type="button"
          onClick={() => handleSelectChangeType('removed')}
          className={`inline-flex items-center gap-1.5 h-8 sm:h-7 min-h-[38px] sm:min-h-[28px] px-2.5 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
            filters.changeType === 'removed'
              ? 'bg-rose-600 text-white border-rose-600 shadow-2xs'
              : 'bg-card text-rose-700 dark:text-rose-400 border-rose-500/30 hover:bg-rose-500/10'
          }`}
          aria-pressed={filters.changeType === 'removed'}
        >
          <Trash2 className="size-3 shrink-0" />
          <span>Đã xóa</span>
          <Badge
            variant="secondary"
            className={`text-[10px] h-4 px-1.5 font-mono ${
              filters.changeType === 'removed'
                ? 'bg-white/20 text-white'
                : 'bg-rose-500/15 text-rose-800 dark:text-rose-300'
            }`}
          >
            {summary.removedCount}
          </Badge>
        </button>

        {/* Conflict (if any) */}
        {summary.conflictCount > 0 && (
          <button
            type="button"
            onClick={() => handleSelectChangeType('conflict')}
            className={`inline-flex items-center gap-1.5 h-8 sm:h-7 min-h-[38px] sm:min-h-[28px] px-2.5 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
              filters.changeType === 'conflict'
                ? 'bg-amber-500 text-amber-950 font-bold border-amber-600 shadow-2xs'
                : 'bg-card text-amber-700 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/10'
            }`}
            aria-pressed={filters.changeType === 'conflict'}
          >
            <AlertTriangle className="size-3 shrink-0" />
            <span>Xung đột</span>
            <Badge
              variant="secondary"
              className={`text-[10px] h-4 px-1.5 font-mono ${
                filters.changeType === 'conflict'
                  ? 'bg-amber-950/20 text-amber-950 font-bold'
                  : 'bg-amber-500/15 text-amber-800 dark:text-amber-300'
              }`}
            >
              {summary.conflictCount}
            </Badge>
          </button>
        )}
      </div>
    </div>
  )
}
