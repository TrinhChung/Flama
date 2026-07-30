import { Link } from 'react-router-dom'
import {
  BarChartLine,
  Collection,
  PlayCircle,
  Search,
  Upload,
} from '@/shared/components/Icons'

type StudyHeaderToolbarProps = {
  deckName?: string | null
  deckId?: string | number | null
  cardId?: string | null
}

export function StudyHeaderToolbar({ deckName, deckId, cardId }: StudyHeaderToolbarProps) {
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

          <a
            href={importUrl}
            className="dash-tab hidden sm:inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <Upload className="size-3.5 sm:size-4" /> Import
          </a>

          <Link
            to={browseUrl}
            className="dash-tab inline-flex sm:hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <Search className="size-3.5" /> Browse
          </Link>
        </div>

        <div className="dash-toolbar__actions hidden sm:flex items-center gap-2 shrink-0">
          <Link
            to={browseUrl}
            className="dash-btn inline-flex items-center gap-1.5 rounded-md border border-border/80 px-2.5 sm:px-3 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold hover:bg-muted transition"
          >
            <Search className="size-3.5 sm:size-4" /> Browse
          </Link>
        </div>
      </div>

      {/* Deck context bar */}
      {deckName ? (
        <div className="deck-context-bar flex items-center gap-2 px-1 text-xs font-medium text-muted-foreground">
          <Collection className="size-3.5 text-orange-500 shrink-0" />
          <span className="truncate max-w-[480px] font-semibold text-foreground">
            {deckName}
          </span>
        </div>
      ) : null}
    </div>
  )
}
