import { Eye, Maximize2, Minimize2, Pencil, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Rating } from '../types'

type IntervalsPreview = Record<Rating, { label?: string }>

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
            {!revealed ? (
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
            ) : (
              <div className="grid grid-cols-4 gap-1.5 sm:gap-2.5 w-full h-11 sm:h-12 items-stretch">
                {/* Again Button */}
                <Button
                  type="button"
                  variant="outline"
                  disabled={submitting}
                  onClick={() => onAnswer('again')}
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
                  onClick={() => onAnswer('hard')}
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
                  onClick={() => onAnswer('good')}
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
                  onClick={() => onAnswer('easy')}
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
            )}
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
