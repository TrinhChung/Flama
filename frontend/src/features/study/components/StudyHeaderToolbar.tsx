import { Link } from 'react-router-dom'
import {
  BarChartLine,
  Collection,
  PlayCircle,
  Search,
  Upload,
} from '@/shared/components/Icons'
import {
  AlertTriangle,
  BookOpen,
  MoreVertical,
  Pencil,
  RotateCcw,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { StudyModeSelector } from './StudyModeSelector'
import type { AppliedComposition } from '../types'

type StudyHeaderToolbarProps = {
  deckName?: string | null
  deckId?: string | number | null
  cardId?: string | null
  canEdit?: boolean
  onEdit?: () => void
  onReload?: () => void
  newCount?: number
  learnCount?: number
  dueCount?: number
  compositions?: AppliedComposition[]
  selectedCompositionId?: string | null
  onSelectComposition?: (compositionId: string | null) => void
}

export function StudyHeaderToolbar({
  deckName,
  deckId,
  cardId,
  canEdit = false,
  onEdit,
  onReload,
  newCount = 0,
  learnCount = 0,
  dueCount = 0,
  compositions,
  selectedCompositionId,
  onSelectComposition,
}: StudyHeaderToolbarProps) {

  const statsUrl = deckId ? `/statistics?deck_id=${deckId}` : '/statistics'
  const browseUrl = deckId
    ? cardId
      ? `/browse?deck_id=${deckId}&card_id=${cardId}`
      : `/browse?deck_id=${deckId}`
    : cardId
      ? `/browse?card_id=${cardId}`
      : '/browse'
  const importUrl = deckId ? `/flashcards/import?deck_id=${deckId}` : '/flashcards/import'
  const studyUrl = deckId ? `/study?deck_id=${deckId}` : '/study'

  const hasCounters = newCount > 0 || learnCount > 0 || dueCount > 0

  return (
    <div className="study-header-container w-full space-y-2">
      {/* Dashboard & Study Toolbar */}
      <div className="dash-toolbar flex items-center justify-between gap-2 border-b border-border/60 pb-2 sm:pb-3">
        <div className="dash-toolbar__nav flex items-center gap-1 overflow-x-auto max-w-full py-0.5">
          <Link
            to="/dashboard"
            className="dash-tab inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <Collection className="size-3.5 sm:size-4" /> Decks
          </Link>

          <Link
            to={studyUrl}
            className="dash-tab inline-flex items-center gap-1.5 rounded-lg bg-orange-500/10 px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-bold text-orange-700 dark:text-orange-400 shrink-0"
          >
            <PlayCircle className="size-3.5 sm:size-4" /> Study
          </Link>

          <Link
            to={statsUrl}
            className="dash-tab inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <BarChartLine className="size-3.5 sm:size-4" /> Stats
          </Link>

          <Link
            to={importUrl}
            className="dash-tab hidden sm:inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <Upload className="size-3.5 sm:size-4" /> Import
          </Link>
        </div>

        <div className="dash-toolbar__actions flex items-center gap-1.5 sm:gap-2 shrink-0">
          {canEdit && onEdit ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onEdit}
              className="dash-btn inline-flex items-center gap-1.5 rounded-md border border-border/80 px-2 sm:px-2.5 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold hover:bg-muted transition text-foreground"
              title="Sửa nhanh thẻ hiện tại (phím E)"
              aria-label="Sửa nhanh thẻ hiện tại"
            >
              <Pencil className="size-3.5 text-orange-500 shrink-0" />
              <span className="hidden sm:inline">Sửa thẻ</span>
              <kbd className="hidden md:inline-block ml-0.5 rounded bg-muted-foreground/15 px-1 py-0.2 text-[9px] font-mono font-medium text-muted-foreground">
                E
              </kbd>
            </Button>
          ) : null}

          <Link
            to={browseUrl}
            className="dash-btn hidden sm:inline-flex items-center gap-1.5 rounded-md border border-border/80 px-2.5 sm:px-3 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold hover:bg-muted transition"
          >
            <Search className="size-3.5 sm:size-4" /> Browse
          </Link>

          {/* Three-dot dropdown menu for shortcuts, troubleshooting, and mobile access */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="size-7 sm:size-8 p-0 rounded-md border-border/80 hover:bg-muted text-muted-foreground hover:text-foreground transition shrink-0"
                aria-label="Thêm tùy chọn và trợ giúp"
                title="Thêm tùy chọn và trợ giúp"
              >
                <MoreVertical className="size-3.5 sm:size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 p-1.5 rounded-xl shadow-lg border-border/80">
              <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground px-2 py-1">
                Tùy chọn & Trợ giúp
              </DropdownMenuLabel>

              <DropdownMenuItem asChild className="rounded-lg p-2 cursor-pointer focus:bg-primary/10 focus:text-primary">
                <Link to={browseUrl} className="flex items-center gap-2.5 w-full">
                  <Search className="size-3.5 text-muted-foreground shrink-0" />
                  <span className="text-xs font-medium">Duyệt thẻ (Browse)</span>
                </Link>
              </DropdownMenuItem>

              <DropdownMenuItem asChild className="rounded-lg p-2 cursor-pointer focus:bg-primary/10 focus:text-primary">
                <Link to={importUrl} className="flex items-center gap-2.5 w-full">
                  <Upload className="size-3.5 text-muted-foreground shrink-0" />
                  <span className="text-xs font-medium">Nhập dữ liệu (Import)</span>
                </Link>
              </DropdownMenuItem>

              {onReload ? (
                <DropdownMenuItem
                  onClick={onReload}
                  className="rounded-lg p-2 cursor-pointer focus:bg-primary/10 focus:text-primary"
                >
                  <div className="flex items-center gap-2.5 w-full">
                    <RotateCcw className="size-3.5 text-muted-foreground shrink-0" />
                    <span className="text-xs font-medium">Tải lại phiên học</span>
                  </div>
                </DropdownMenuItem>
              ) : null}

              <DropdownMenuSeparator className="my-1" />

              <DropdownMenuItem asChild className="rounded-lg p-2 cursor-pointer focus:bg-primary/10 focus:text-primary">
                <Link to="/guide/study/shortcuts" className="flex items-start gap-2.5 w-full">
                  <BookOpen className="size-3.5 text-muted-foreground shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-foreground">Phím tắt & Hướng dẫn</div>
                    <div className="text-[11px] text-muted-foreground line-clamp-1">Bảng phím tắt & cách chấm điểm</div>
                  </div>
                </Link>
              </DropdownMenuItem>

              <DropdownMenuItem asChild className="rounded-lg p-2 cursor-pointer focus:bg-amber-500/10 focus:text-amber-600 dark:focus:text-amber-400">
                <Link to="/guide/troubleshooting/dashboard-study" className="flex items-start gap-2.5 w-full">
                  <AlertTriangle className="size-3.5 text-amber-500 shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-foreground">Khắc phục sự cố</div>
                    <div className="text-[11px] text-muted-foreground line-clamp-1">Sự cố trong phòng học</div>
                  </div>
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Deck context bar, Counters & Mode Selector */}
      {deckName || hasCounters || (compositions && compositions.length > 1) ? (
        <div className="deck-context-bar space-y-1.5 px-1 text-xs font-medium text-muted-foreground">
          {/* Main Context Line: Deck Name (Left) & Queue Counters (Right) */}
          <div className="flex items-center justify-between gap-2 min-w-0">
            {deckName ? (
              <div className="flex items-center gap-1.5 min-w-0 flex-1">
                <Collection className="size-3.5 text-orange-500 shrink-0" />
                <span
                  className="truncate font-semibold text-foreground text-xs sm:text-sm"
                  title={deckName}
                >
                  {deckName}
                </span>
              </div>
            ) : (
              <div className="flex-1" />
            )}

            {/* Persistent Soft Pill Badges - Visible on both faces, mobile & desktop */}
            {hasCounters ? (
              <div
                className="study-counters-line flex items-center gap-1 sm:gap-1.5 text-xs whitespace-nowrap shrink-0"
                role="status"
                aria-label={`Bộ đếm: Mới ${newCount}, Đang học ${learnCount}, Đến hạn ${dueCount}`}
              >
                <span
                  className="inline-flex items-center gap-1 sm:gap-1.5 rounded-full bg-emerald-500/10 px-1.5 sm:px-2.5 py-0.5 sm:py-1 font-bold text-[11px] sm:text-xs text-emerald-600 dark:text-emerald-400"
                  title={`Thẻ mới: ${newCount}`}
                >
                  <span className="size-1.5 rounded-full bg-emerald-500 shrink-0" />
                  <span>Mới {newCount}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 sm:gap-1.5 rounded-full bg-amber-500/10 px-1.5 sm:px-2.5 py-0.5 sm:py-1 font-bold text-[11px] sm:text-xs text-amber-600 dark:text-amber-400"
                  title={`Thẻ đang học: ${learnCount}`}
                >
                  <span className="size-1.5 rounded-full bg-amber-500 shrink-0" />
                  <span>Học {learnCount}</span>
                </span>
                <span
                  className="inline-flex items-center gap-1 sm:gap-1.5 rounded-full bg-rose-500/10 px-1.5 sm:px-2.5 py-0.5 sm:py-1 font-bold text-[11px] sm:text-xs text-rose-600 dark:text-rose-400"
                  title={`Thẻ đến hạn cần ôn: ${dueCount}`}
                >
                  <span className="size-1.5 rounded-full bg-rose-500 shrink-0" />
                  <span>Hạn {dueCount}</span>
                </span>
              </div>
            ) : null}
          </div>

          {/* Sub-row for StudyModeSelector (only if note type has multiple templates) */}
          {compositions && compositions.length > 1 && onSelectComposition ? (
            <div className="w-full overflow-x-auto pt-0.5">
              <StudyModeSelector
                compositions={compositions}
                selectedCompositionId={selectedCompositionId}
                onSelectComposition={onSelectComposition}
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
