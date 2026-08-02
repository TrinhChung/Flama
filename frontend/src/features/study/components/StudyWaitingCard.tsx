import { Clock3, Layers3, LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'

type StudyWaitingCardProps = {
  deckName?: string | null
  counts: { new: number; learning: number; due: number }
  nowMs: number
  pendingLearningCount: number
  nextEligibleAtMs: number | null
  nextDueAtMs: number | null
  isBusy: boolean
  onCommit: () => void
}

function formatRemaining(seconds: number) {
  if (seconds <= 0) return 'đang tải lại thẻ'
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes <= 0) return `${remainingSeconds} giây`
  return `${minutes} phút ${remainingSeconds.toString().padStart(2, '0')} giây`
}

export function StudyWaitingCard({
  deckName,
  counts,
  nowMs,
  pendingLearningCount,
  nextEligibleAtMs,
  nextDueAtMs,
  isBusy,
  onCommit,
}: StudyWaitingCardProps) {
  const remainingSeconds = nextEligibleAtMs === null
    ? 0
    : Math.max(0, Math.ceil((nextEligibleAtMs - nowMs) / 1000))

  return (
    <div className="w-full max-w-xl mx-auto py-6 px-4">
      <div className="rounded-2xl border border-amber-200/80 dark:border-amber-900/50 bg-card p-6 sm:p-8 space-y-6 text-center shadow-xs">
        <div className="inline-flex items-center justify-center size-12 rounded-xl bg-amber-500/10 border border-amber-200 dark:border-amber-900/50 text-amber-600 dark:text-amber-400 mx-auto">
          <Clock3 className="size-6" />
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium text-muted-foreground">
            {deckName || 'Phiên học'}
          </div>
          <h2 className="text-2xl font-bold text-foreground tracking-tight">
            Đang chờ lượt học lại
          </h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
            Phiên học vẫn đang mở. Các thẻ này chưa hoàn thành learning step
            và sẽ tự xuất hiện lại khi vào cửa sổ học sớm.
          </p>
        </div>

        <div
          className="rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-500/10 p-4"
          aria-live="polite"
        >
          <div className="text-sm font-semibold text-amber-700 dark:text-amber-300">
            Tiếp tục sau {formatRemaining(remainingSeconds)}
          </div>
          {nextDueAtMs !== null ? (
            <div className="mt-1 text-xs text-muted-foreground">
              Mốc ôn danh nghĩa: {new Date(nextDueAtMs).toLocaleTimeString('vi-VN')}
            </div>
          ) : null}
        </div>

        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="rounded-xl border border-border/60 bg-muted/20 p-3">
            <span className="block text-muted-foreground">Mới</span>
            <strong className="text-base text-foreground">{counts.new}</strong>
          </div>
          <div className="rounded-xl border border-border/60 bg-muted/20 p-3">
            <span className="block text-amber-600 dark:text-amber-400">
              Đang học
            </span>
            <strong className="text-base text-foreground">
              {Math.max(counts.learning, pendingLearningCount)}
            </strong>
          </div>
          <div className="rounded-xl border border-border/60 bg-muted/20 p-3">
            <span className="block text-muted-foreground">Đến hạn</span>
            <strong className="text-base text-foreground">{counts.due}</strong>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <Layers3 className="size-4" />
            <span>Còn {pendingLearningCount} thẻ chờ learning step</span>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={isBusy}
            onClick={onCommit}
            className="w-full sm:w-auto"
          >
            <LogOut className="size-4 mr-2" />
            Kết thúc lúc này
          </Button>
        </div>
      </div>
    </div>
  )
}
