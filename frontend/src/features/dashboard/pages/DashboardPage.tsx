import { useState } from 'react'
import {
  BarChartLine,
  BookOpen,
  Collection,
  Download,
  PlayCircle,
  PlusLg,
  Search,
  Upload,
} from '@/shared/components/Icons'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useBootstrap } from '@/shared/api/bootstrap'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useDashboard, useDashboardOverview } from '../api'
import { StudyHeatmap } from '@/shared/components/StudyHeatmap'
import { DeckTree } from '../components/DeckTree'
import { CreateDeckModal, DeckActionModal } from '../components/DeckModals'
import type { DeckNode, SelectedDeckAction } from '../types'

function findDeck(nodes: DeckNode[], deckId: number | null): DeckNode | null {
  if (deckId === null) return null
  for (const node of nodes) {
    if (node.id === deckId) return node
    const child = findDeck(node.children, deckId)
    if (child) return child
  }
  return null
}

export function DashboardPage() {
  const bootstrapQuery = useBootstrap()
  const dashboardQuery = useDashboard()
  const [year, setYear] = useState(() => new Date().getFullYear())
  const overviewQuery = useDashboardOverview(year)

  const [createOpened, setCreateOpened] = useState(false)
  const [selection, setSelection] = useState<SelectedDeckAction | null>(null)
  const [selectedDeckId, setSelectedDeckId] = useState<number | null>(null)

  if (bootstrapQuery.isPending || dashboardQuery.isPending) {
    return <PageLoading label="Đang tải dashboard…" />
  }
  if (!bootstrapQuery.data) {
    return <Page><PageError error={new Error('Không thể tải phiên đăng nhập.')} /></Page>
  }
  if (dashboardQuery.error) {
    return <Page><PageError error={dashboardQuery.error} /></Page>
  }

  const bootstrap = bootstrapQuery.data
  const dashboard = dashboardQuery.data
  const selectedDeck = findDeck(dashboard.decks, selectedDeckId)

  const studyUrl = selectedDeck?.study_url || bootstrap.links.study
  const statsUrl = selectedDeck ? `/statistics?deck_id=${selectedDeck.id}` : '/statistics'
  const browseUrl = selectedDeck ? `/browse?deck_id=${selectedDeck.id}` : bootstrap.links.browse
  const importUrl = selectedDeck
    ? `/flashcards/import?deck_id=${selectedDeck.id}`
    : '/flashcards/import'

  return (
    <Page className="anki-home max-w-[1200px] w-full mx-auto px-2 sm:px-4 py-2 sm:py-3 space-y-3 sm:space-y-6">
      {/* Shared Dashboard Toolbar */}
      <div className="dash-toolbar flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-2 sm:pb-3">
        {/* Left Navigation Tabs */}
        <div className="dash-toolbar__nav flex items-center gap-1 overflow-x-auto max-w-full py-0.5">
          <Link
            to="/dashboard"
            className="dash-tab inline-flex items-center gap-1.5 rounded-lg bg-orange-500/10 px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-bold text-orange-700 dark:text-orange-400 shrink-0"
          >
            <Collection className="size-3.5 sm:size-4" /> Decks
          </Link>

          <Link
            to={studyUrl}
            className="dash-tab inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
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
            className="dash-tab inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <Upload className="size-3.5 sm:size-4" /> Import
          </a>
        </div>

        {/* Right Actions */}
        <div className="dash-toolbar__actions flex items-center gap-1.5 sm:gap-2">
          <Button
            type="button"
            className="dash-btn dash-btn--primary text-xs font-bold bg-gradient-to-r from-primary to-orange-500 text-primary-foreground shadow-xs hover:opacity-95 h-8 px-2.5 sm:px-3"
            size="sm"
            onClick={() => setCreateOpened(true)}
          >
            <PlusLg className="size-3.5 sm:size-4 mr-1" /> Tạo Deck
          </Button>

          <Link
            to={browseUrl}
            className="dash-btn dash-btn--ghost inline-flex items-center gap-1.5 rounded-md border border-border/80 px-2.5 sm:px-3 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold hover:bg-muted"
          >
            <Search className="size-3.5 sm:size-4" /> Browse
          </Link>
        </div>
      </div>

      {/* Main Deck Board Container */}
      <section className="deck-board w-full rounded-xl sm:rounded-2xl border-0 sm:border border-border bg-card p-2.5 sm:p-6 shadow-none sm:shadow-sm">
        <header className="deck-board-head flex items-center justify-between border-b border-border/60 pb-2 sm:pb-3 mb-2">
          <div className="head-left">
            <h3 id="anki-decks-title" className="section-title text-lg sm:text-xl font-bold text-foreground">
              Deck
            </h3>
          </div>

          <div className="head-right hidden sm:grid sm:grid-cols-[repeat(3,64px)_30px] gap-2 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <span className="text-emerald-600">New</span>
            <span className="text-rose-600">Learn</span>
            <span className="text-orange-600">Due</span>
            <span className="settings-spacer" aria-hidden="true" />
          </div>
        </header>

        <div className="deck-list">
          {dashboard.decks.length ? (
            <DeckTree
              nodes={dashboard.decks}
              adminMode={dashboard.admin_mode}
              selectedDeckId={selectedDeckId}
              onSelect={(deck) => setSelectedDeckId((current) => (current === deck.id ? null : deck.id))}
              onAction={setSelection}
            />
          ) : (
            <div className="onboarding-panel flex flex-col items-center justify-center text-center p-8 rounded-2xl border-2 border-dashed border-orange-300 bg-orange-50/50 space-y-3">
              <div className="onboarding-icon text-4xl">📚</div>
              <h4 className="onboarding-title text-lg font-bold text-foreground">
                Chào mừng bạn đến với Flama!
              </h4>
              <p className="onboarding-desc text-sm text-muted-foreground max-w-md">
                Tài khoản của bạn chưa có deck nào.<br />
                Hãy vào <strong>Thư viện</strong> để tìm và cài bộ thẻ phù hợp với bạn.
              </p>
              <div className="onboarding-actions flex flex-wrap justify-center gap-3 pt-2">
                <Button asChild size="sm" className="bg-primary text-primary-foreground font-bold">
                  <Link to="/marketplace/decks">
                    <Download className="size-4 mr-1.5" /> Thư viện Deck
                  </Link>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <Link to="/marketplace/note-types">
                    <BookOpen className="size-4 mr-1.5" /> Thư viện Template
                  </Link>
                </Button>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Heatmap & Activity Statistics Section */}
      <StudyHeatmap
        overview={overviewQuery.data}
        loading={overviewQuery.isPending}
        year={year}
        onYearChange={setYear}
      />

      {/* Modals */}
      <CreateDeckModal
        opened={createOpened}
        onClose={() => setCreateOpened(false)}
        dashboard={dashboard}
      />
      <DeckActionModal
        selection={selection}
        onClose={() => setSelection(null)}
        dashboard={dashboard}
      />
    </Page>
  )
}
