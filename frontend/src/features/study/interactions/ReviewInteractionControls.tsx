import { Eye, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Rating } from '../types'
import { resolveReviewAction, type ReviewAction, type ReviewRating } from './reviewInteraction'

export type IntervalsPreview = Record<Rating, { label?: string }>

export type ReviewInteractionControlsProps = {
  revealed: boolean
  submitting?: boolean
  newCount?: number
  learnCount?: number
  dueCount?: number
  intervalsPreview?: IntervalsPreview
  onReveal: () => void
  onAnswer?: (rating: Rating) => void
  onReviewAction?: (action: ReviewAction) => void
}

export function ReviewInteractionControls({
  revealed,
  submitting = false,
  newCount = 0,
  learnCount = 0,
  dueCount = 0,
  intervalsPreview,
  onReveal,
  onAnswer,
  onReviewAction,
}: ReviewInteractionControlsProps) {
  const handleRatingClick = (rating: ReviewRating) => {
    if (submitting) return
    if (onReviewAction) {
      onReviewAction(resolveReviewAction(rating))
    }
    if (onAnswer) {
      onAnswer(rating)
    }
  }

  if (!revealed) {
    return (
      <div className="flex items-center gap-2 sm:gap-3 w-full justify-center">
        {/* Soft Pill Badge Counters (visible on XL screens) */}
        <div className="study-counters-line hidden xl:flex items-center gap-1.5 text-xs whitespace-nowrap mr-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 font-bold text-emerald-600 dark:text-emerald-400">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Mới {newCount}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 font-bold text-amber-600 dark:text-amber-400">
            <span className="size-1.5 rounded-full bg-amber-500" />
            Học {learnCount}
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 px-2.5 py-1 font-bold text-rose-600 dark:text-rose-400">
            <span className="size-1.5 rounded-full bg-rose-500" />
            Hạn {dueCount}
          </span>
        </div>

        {/* Reveal Answer Button */}
        <Button
          type="button"
          disabled={submitting}
          onClick={onReveal}
          className="h-11 sm:h-12 w-full max-w-md bg-primary hover:bg-primary/95 text-primary-foreground font-bold text-sm sm:text-base rounded-xl shadow-sm hover:shadow-primary/20 transition-all duration-150 gap-1.5 sm:gap-2"
        >
          <Eye className="size-4 sm:size-4.5 shrink-0" />
          <span>Hiện đáp án</span>
          <kbd className="hidden sm:inline-block ml-1.5 rounded bg-white/20 px-1.5 py-0.5 text-[11px] font-mono font-medium text-primary-foreground">
            Space
          </kbd>
        </Button>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-4 gap-1.5 sm:gap-2.5 w-full h-11 sm:h-12 items-stretch">
      {/* Again Button */}
      <Button
        type="button"
        variant="outline"
        disabled={submitting}
        onClick={() => handleRatingClick('again')}
        className="h-11 sm:h-12 rounded-lg sm:rounded-xl border-rose-200 dark:border-rose-900/60 bg-rose-500/10 text-rose-700 dark:text-rose-300 hover:bg-rose-500/20 hover:border-rose-300 transition-all duration-150 shadow-xs flex flex-col items-center justify-center px-1 py-0.5"
      >
        <div className="flex items-center justify-center gap-0.5 sm:gap-1 text-[12px] sm:text-sm font-bold leading-tight">
          <RotateCcw className="size-3 hidden xs:inline-block" />
          <span className="truncate">Học lại</span>
          <span className="hidden sm:inline text-[10px] opacity-60 ml-0.5">1</span>
        </div>
        {intervalsPreview?.again?.label ? (
          <span className="text-[10px] sm:text-[11px] font-medium text-muted-foreground leading-none mt-0.5 truncate max-w-full">
            {intervalsPreview.again.label}
          </span>
        ) : null}
      </Button>

      {/* Hard Button */}
      <Button
        type="button"
        variant="outline"
        disabled={submitting}
        onClick={() => handleRatingClick('hard')}
        className="h-11 sm:h-12 rounded-lg sm:rounded-xl border-amber-200 dark:border-amber-900/60 bg-amber-500/10 text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 hover:border-amber-300 transition-all duration-150 shadow-xs flex flex-col items-center justify-center px-1 py-0.5"
      >
        <div className="flex items-center justify-center gap-0.5 sm:gap-1 text-[12px] sm:text-sm font-bold leading-tight">
          <span className="truncate">Khó</span>
          <span className="hidden sm:inline text-[10px] opacity-60 ml-0.5">2</span>
        </div>
        {intervalsPreview?.hard?.label ? (
          <span className="text-[10px] sm:text-[11px] font-medium text-muted-foreground leading-none mt-0.5 truncate max-w-full">
            {intervalsPreview.hard.label}
          </span>
        ) : null}
      </Button>

      {/* Good Button */}
      <Button
        type="button"
        variant="outline"
        disabled={submitting}
        onClick={() => handleRatingClick('good')}
        className="h-11 sm:h-12 rounded-lg sm:rounded-xl border-blue-200 dark:border-blue-900/60 bg-blue-500/10 text-blue-700 dark:text-blue-300 hover:bg-blue-500/20 hover:border-blue-300 transition-all duration-150 shadow-xs flex flex-col items-center justify-center px-1 py-0.5"
      >
        <div className="flex items-center justify-center gap-0.5 sm:gap-1 text-[12px] sm:text-sm font-bold leading-tight">
          <span className="truncate">Tốt</span>
          <span className="hidden sm:inline text-[10px] opacity-60 ml-0.5">3</span>
        </div>
        {intervalsPreview?.good?.label ? (
          <span className="text-[10px] sm:text-[11px] font-medium text-muted-foreground leading-none mt-0.5 truncate max-w-full">
            {intervalsPreview.good.label}
          </span>
        ) : null}
      </Button>

      {/* Easy Button */}
      <Button
        type="button"
        variant="outline"
        disabled={submitting}
        onClick={() => handleRatingClick('easy')}
        className="h-11 sm:h-12 rounded-lg sm:rounded-xl border-emerald-200 dark:border-emerald-900/60 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/20 hover:border-emerald-300 transition-all duration-150 shadow-xs flex flex-col items-center justify-center px-1 py-0.5"
      >
        <div className="flex items-center justify-center gap-0.5 sm:gap-1 text-[12px] sm:text-sm font-bold leading-tight">
          <span className="truncate">Dễ</span>
          <span className="hidden sm:inline text-[10px] opacity-60 ml-0.5">4</span>
        </div>
        {intervalsPreview?.easy?.label ? (
          <span className="text-[10px] sm:text-[11px] font-medium text-muted-foreground leading-none mt-0.5 truncate max-w-full">
            {intervalsPreview.easy.label}
          </span>
        ) : null}
      </Button>
    </div>
  )
}
