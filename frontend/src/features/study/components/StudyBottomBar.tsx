import { Eye, Maximize2, Minimize2, Pencil, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'

type Rating = 'again' | 'hard' | 'good' | 'easy'

type IntervalsPreview = Record<Rating, { label?: string }>

type StudyBottomBarProps = {
  cardId?: string | null
  revealed: boolean
  canEdit?: boolean
  newCount?: number
  learnCount?: number
  dueCount?: number
  intervalsPreview?: IntervalsPreview
  isFullscreen?: boolean
  submitting?: boolean
  onReveal: () => void
  onAnswer: (rating: Rating) => void
  onEdit: () => void
  onToggleFullscreen: () => void
}

export function StudyBottomBar({
  cardId,
  revealed,
  canEdit = false,
  newCount = 0,
  learnCount = 0,
  dueCount = 0,
  intervalsPreview,
  isFullscreen = false,
  submitting = false,
  onReveal,
  onAnswer,
  onEdit,
  onToggleFullscreen,
}: StudyBottomBarProps) {
  if (!cardId) return null

  return (
    <div className="study-bottom-bar fixed bottom-0 left-0 right-0 z-40 bg-background/90 dark:bg-zinc-950/90 backdrop-blur-md border-t border-border/80 shadow-lg py-3 px-4 md:px-8">
      <div className="max-w-6xl mx-auto flex items-center justify-between gap-4 md:gap-8">
        {/* Left Side: Edit Button (Generous width & matching height) */}
        <div className="w-36 sm:w-44 flex items-center justify-start shrink-0">
          {canEdit ? (
            <Button
              type="button"
              variant="outline"
              onClick={onEdit}
              className="h-11 px-4 rounded-xl border-border/80 bg-card hover:bg-accent text-foreground text-xs sm:text-sm font-semibold gap-2 shadow-xs transition-all hover:border-orange-400/60"
              title="Sửa thẻ hiện tại (phím E)"
            >
              <Pencil className="size-4 text-orange-500" />
              <span>Sửa thẻ</span>
              <kbd className="hidden sm:inline-block ml-1 rounded bg-muted-foreground/15 px-1.5 py-0.5 text-[10px] font-mono font-medium text-muted-foreground">
                E
              </kbd>
            </Button>
          ) : null}
        </div>

        {/* Center Zone: Zero Height Shift Layout */}
        <div className="flex-1 flex flex-col items-center justify-center min-w-0 max-w-2xl mx-auto">
          {!revealed ? (
            <div className="flex items-center gap-3 w-full justify-center">
              {/* Soft Pill Badge Counters */}
              <div className="study-counters-line hidden lg:flex items-center gap-1.5 text-xs whitespace-nowrap mr-2">
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

              {/* Reveal Answer Button (Clean solid primary, no heavy gradient) */}
              <Button
                type="button"
                onClick={onReveal}
                className="h-12 w-full max-w-md bg-primary hover:bg-primary/95 text-primary-foreground font-bold text-sm sm:text-base rounded-xl shadow-sm hover:shadow-primary/20 transition-all duration-150 gap-2"
              >
                <Eye className="size-4.5" />
                <span>Hiện đáp án</span>
                <kbd className="hidden sm:inline-block ml-1.5 rounded bg-white/20 px-1.5 py-0.5 text-[11px] font-mono font-medium text-primary-foreground">
                  Space
                </kbd>
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-4 gap-2.5 w-full h-12 items-stretch">
              {/* Again Button */}
              <Button
                type="button"
                variant="outline"
                disabled={submitting}
                onClick={() => onAnswer('again')}
                className="h-12 rounded-xl border-rose-200 dark:border-rose-900/60 bg-rose-500/10 text-rose-700 dark:text-rose-300 hover:bg-rose-500/20 hover:border-rose-300 transition-all duration-150 shadow-xs flex flex-col items-center justify-center p-1"
              >
                <div className="flex items-center gap-1 text-xs sm:text-sm font-bold">
                  <RotateCcw className="size-3" />
                  <span>Học lại</span>
                  <span className="text-[10px] opacity-60 ml-0.5">1</span>
                </div>
                {intervalsPreview?.again?.label ? (
                  <span className="text-[10px] font-normal text-muted-foreground leading-tight">
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
                className="h-12 rounded-xl border-amber-200 dark:border-amber-900/60 bg-amber-500/10 text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 hover:border-amber-300 transition-all duration-150 shadow-xs flex flex-col items-center justify-center p-1"
              >
                <div className="flex items-center gap-1 text-xs sm:text-sm font-bold">
                  <span>Khó</span>
                  <span className="text-[10px] opacity-60 ml-0.5">2</span>
                </div>
                {intervalsPreview?.hard?.label ? (
                  <span className="text-[10px] font-normal text-muted-foreground leading-tight">
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
                className="h-12 rounded-xl border-blue-200 dark:border-blue-900/60 bg-blue-500/10 text-blue-700 dark:text-blue-300 hover:bg-blue-500/20 hover:border-blue-300 transition-all duration-150 shadow-xs flex flex-col items-center justify-center p-1"
              >
                <div className="flex items-center gap-1 text-xs sm:text-sm font-bold">
                  <span>Tốt</span>
                  <span className="text-[10px] opacity-60 ml-0.5">3</span>
                </div>
                {intervalsPreview?.good?.label ? (
                  <span className="text-[10px] font-normal text-muted-foreground leading-tight">
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
                className="h-12 rounded-xl border-emerald-200 dark:border-emerald-900/60 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/20 hover:border-emerald-300 transition-all duration-150 shadow-xs flex flex-col items-center justify-center p-1"
              >
                <div className="flex items-center gap-1 text-xs sm:text-sm font-bold">
                  <span>Dễ</span>
                  <span className="text-[10px] opacity-60 ml-0.5">4</span>
                </div>
                {intervalsPreview?.easy?.label ? (
                  <span className="text-[10px] font-normal text-muted-foreground leading-tight">
                    {intervalsPreview.easy.label}
                  </span>
                ) : null}
              </Button>
            </div>
          )}
        </div>

        {/* Right Side: Fullscreen Toggle (Generous width & matching height) */}
        <div className="w-36 sm:w-44 flex items-center justify-end shrink-0">
          <Button
            type="button"
            variant="outline"
            onClick={onToggleFullscreen}
            className="h-11 px-4 rounded-xl border-border/80 bg-card hover:bg-accent text-foreground text-xs sm:text-sm font-semibold gap-2 shadow-xs transition-all hover:border-orange-400/60"
            title="Bật/tắt toàn màn hình (phím F)"
          >
            {isFullscreen ? (
              <Minimize2 className="size-4 text-orange-500" />
            ) : (
              <Maximize2 className="size-4 text-orange-500" />
            )}
            <span>{isFullscreen ? 'Thoát' : 'Toàn màn hình'}</span>
            <kbd className="hidden sm:inline-block ml-1 rounded bg-muted-foreground/15 px-1.5 py-0.5 text-[10px] font-mono font-medium text-muted-foreground">
              F
            </kbd>
          </Button>
        </div>
      </div>
    </div>
  )
}
