import { Maximize2, Minimize2, Pencil, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Rating } from '../types'
import {
  ReviewInteractionControls,
  type IntervalsPreview,
} from '../interactions/ReviewInteractionControls'

type StudyBottomBarProps = {
  cardId?: string | null
  revealed: boolean
  canEdit?: boolean
  canUndo?: boolean
  newCount?: number
  learnCount?: number
  dueCount?: number
  intervalsPreview?: IntervalsPreview
  isFullscreen?: boolean
  submitting?: boolean
  onReveal: () => void
  onAnswer: (rating: Rating) => void
  onUndo?: () => void
  onEdit: () => void
  onToggleFullscreen: () => void
}

export function StudyBottomBar({
  cardId,
  revealed,
  canEdit = false,
  canUndo = false,
  newCount = 0,
  learnCount = 0,
  dueCount = 0,
  intervalsPreview,
  isFullscreen = false,
  submitting = false,
  onReveal,
  onAnswer,
  onUndo,
  onEdit,
  onToggleFullscreen,
}: StudyBottomBarProps) {
  if (!cardId) return null

  return (
    <>
      {/* Mobile Floating Undo Button (FAB) - Floating in left thumb zone above bottom bar */}
      {onUndo && canUndo ? (
        <div className="sm:hidden fixed bottom-[calc(4.75rem+env(safe-area-inset-bottom,0px))] left-3.5 z-50 animate-in fade-in zoom-in-90 duration-150">
          <Button
            type="button"
            variant="outline"
            onClick={onUndo}
            disabled={submitting}
            className="size-11 rounded-full border-blue-300/80 dark:border-blue-800/80 bg-background/95 dark:bg-zinc-900/95 backdrop-blur-md shadow-lg text-blue-600 dark:text-blue-400 hover:bg-accent flex items-center justify-center p-0 transition-all duration-150 active:scale-90 hover:border-blue-400"
            title="Hoàn tác đánh giá trước (Ctrl+Z)"
            aria-label="Hoàn tác đánh giá trước"
          >
            <RotateCcw className="size-5 shrink-0" />
          </Button>
        </div>
      ) : null}

      {/* Mobile Floating Edit Button (FAB) - Floating in right thumb zone above bottom bar */}
      {canEdit ? (
        <div className="sm:hidden fixed bottom-[calc(4.75rem+env(safe-area-inset-bottom,0px))] right-3.5 z-50 animate-in fade-in zoom-in-90 duration-150">
          <Button
            type="button"
            variant="outline"
            onClick={onEdit}
            disabled={submitting}
            className="size-11 rounded-full border-orange-300/80 dark:border-orange-800/80 bg-background/95 dark:bg-zinc-900/95 backdrop-blur-md shadow-lg text-orange-600 dark:text-orange-400 hover:bg-accent flex items-center justify-center p-0 transition-all duration-150 active:scale-90 hover:border-orange-400"
            title="Sửa nhanh thẻ (phím E)"
            aria-label="Sửa nhanh thẻ"
          >
            <Pencil className="size-5 shrink-0" />
          </Button>
        </div>
      ) : null}

      {/* Main Bottom Bar */}
      <div className="study-bottom-bar fixed bottom-0 left-0 right-0 z-40 bg-background/95 dark:bg-zinc-950/95 backdrop-blur-md border-t border-border/80 shadow-lg py-2 sm:py-3 px-2.5 sm:px-4 md:px-8 pb-[calc(0.5rem+env(safe-area-inset-bottom,0px))]">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-1.5 sm:gap-4 md:gap-8">
          {/* Left Side: Desktop Undo & Edit Buttons (Hidden on mobile to give 100% width to rating buttons) */}
          <div className="hidden sm:flex items-center justify-start shrink-0 sm:w-36 md:w-44 gap-1.5 sm:gap-2">
            {onUndo ? (
              <Button
                type="button"
                variant="outline"
                onClick={onUndo}
                disabled={submitting || !canUndo}
                className="h-10 sm:h-11 px-2.5 sm:px-3.5 rounded-xl border-border/80 bg-card hover:bg-accent text-foreground text-xs sm:text-sm font-semibold gap-1.5 sm:gap-2 shadow-xs transition-all hover:border-blue-400/60 disabled:opacity-40"
                title="Hoàn tác đánh giá trước (phím Ctrl+Z hoặc Z)"
              >
                <RotateCcw className="size-4 text-blue-500 shrink-0" />
                <span className="hidden sm:inline">Hoàn tác</span>
                <kbd className="hidden md:inline-block ml-1 rounded bg-muted-foreground/15 px-1.5 py-0.5 text-[10px] font-mono font-medium text-muted-foreground">
                  Ctrl+Z
                </kbd>
              </Button>
            ) : null}

            {canEdit ? (
              <Button
                type="button"
                variant="outline"
                onClick={onEdit}
                className="h-10 sm:h-11 px-2.5 sm:px-4 rounded-xl border-border/80 bg-card hover:bg-accent text-foreground text-xs sm:text-sm font-semibold gap-1.5 sm:gap-2 shadow-xs transition-all hover:border-orange-400/60"
                title="Sửa thẻ hiện tại (phím E)"
              >
                <Pencil className="size-4 text-orange-500 shrink-0" />
                <span className="hidden sm:inline">Sửa thẻ</span>
                <kbd className="hidden md:inline-block ml-1 rounded bg-muted-foreground/15 px-1.5 py-0.5 text-[10px] font-mono font-medium text-muted-foreground">
                  E
                </kbd>
              </Button>
            ) : null}
          </div>

          {/* Center Zone: Full width on mobile, centered max-w-2xl on desktop */}
          <div className="w-full sm:flex-1 flex flex-col items-center justify-center min-w-0 max-w-2xl mx-auto px-0">
            <ReviewInteractionControls
              revealed={revealed}
              submitting={submitting}
              newCount={newCount}
              learnCount={learnCount}
              dueCount={dueCount}
              intervalsPreview={intervalsPreview}
              onReveal={onReveal}
              onAnswer={onAnswer}
            />
          </div>

          {/* Right Side: Desktop Fullscreen Toggle (Hidden on mobile) */}
          <div className="hidden sm:flex items-center justify-end shrink-0 sm:w-36 md:w-44">
            <Button
              type="button"
              variant="outline"
              onClick={onToggleFullscreen}
              className="h-10 sm:h-11 px-2.5 sm:px-4 rounded-xl border-border/80 bg-card hover:bg-accent text-foreground text-xs sm:text-sm font-semibold gap-1.5 sm:gap-2 shadow-xs transition-all hover:border-orange-400/60"
              title="Bật/tắt toàn màn hình (phím F)"
            >
              {isFullscreen ? (
                <Minimize2 className="size-4 text-orange-500 shrink-0" />
              ) : (
                <Maximize2 className="size-4 text-orange-500 shrink-0" />
              )}
              <span className="hidden sm:inline">{isFullscreen ? 'Thoát' : 'Toàn màn hình'}</span>
              <kbd className="hidden md:inline-block ml-1 rounded bg-muted-foreground/15 px-1.5 py-0.5 text-[10px] font-mono font-medium text-muted-foreground">
                F
              </kbd>
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}
