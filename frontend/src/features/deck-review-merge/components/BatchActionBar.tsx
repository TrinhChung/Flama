import { CheckCircle2, XCircle, X, Loader2, CheckSquare } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { BatchActionBarProps } from '../model/types'

export function BatchActionBar({
  selectedCount,
  totalCount,
  onApprove,
  onReject,
  onClear,
  isProcessing = false,
  className = '',
}: BatchActionBarProps) {
  if (selectedCount === 0) return null

  return (
    <div
      role="region"
      aria-label="Thao tác hàng loạt"
      className={`sticky bottom-3 z-30 flex flex-wrap items-center justify-between gap-3 p-3 sm:px-4 rounded-2xl border border-border/80 bg-background/95 backdrop-blur-md shadow-lg transition-all animate-in fade-in slide-in-from-bottom-2 ${className}`}
      data-testid="batch-action-bar"
    >
      {/* Left: Selected counter */}
      <div className="flex items-center gap-2 min-w-0">
        <div className="flex items-center justify-center size-7 rounded-lg bg-primary/10 text-primary shrink-0">
          <CheckSquare className="size-4" />
        </div>
        <div className="text-xs sm:text-sm truncate">
          <span className="font-semibold text-foreground">
            Đã chọn {selectedCount.toLocaleString()}
          </span>
          <span className="text-muted-foreground ml-1">
            / {totalCount.toLocaleString()} thẻ
          </span>
        </div>
        <Badge variant="outline" className="text-[10px] h-5 font-mono ml-1 hidden sm:inline-flex">
          {Math.round((selectedCount / (totalCount || 1)) * 100)}%
        </Badge>
      </div>

      {/* Right: Actions */}
      <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 w-full sm:w-auto">
        {/* Approve Selected */}
        <Button
          type="button"
          size="sm"
          onClick={onApprove}
          disabled={isProcessing}
          className="h-9 sm:h-8 min-h-[38px] sm:min-h-[32px] text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 shadow-xs cursor-pointer flex-1 sm:flex-initial justify-center"
          data-testid="batch-approve-btn"
        >
          {isProcessing ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <CheckCircle2 className="size-3.5" />
          )}
          <span>Chấp nhận đã chọn ({selectedCount})</span>
        </Button>

        {/* Reject Selected */}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onReject}
          disabled={isProcessing}
          className="h-9 sm:h-8 min-h-[38px] sm:min-h-[32px] text-xs font-semibold text-rose-700 hover:text-rose-800 dark:text-rose-400 border-rose-500/30 dark:border-rose-500/30 hover:bg-rose-500/10 gap-1.5 cursor-pointer flex-1 sm:flex-initial justify-center"
          data-testid="batch-reject-btn"
        >
          {isProcessing ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <XCircle className="size-3.5" />
          )}
          <span>Từ chối đã chọn ({selectedCount})</span>
        </Button>

        {/* Clear selection */}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onClear}
          disabled={isProcessing}
          className="h-9 sm:h-8 min-h-[38px] sm:min-h-[32px] text-xs text-muted-foreground hover:text-foreground gap-1 px-2.5 cursor-pointer shrink-0"
          data-testid="batch-clear-btn"
          title="Bỏ chọn tất cả"
        >
          <X className="size-3.5" />
          <span className="hidden sm:inline">Bỏ chọn</span>
        </Button>
      </div>
    </div>
  )
}
