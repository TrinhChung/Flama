import { useCallback, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
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
import { StudyHeatmap } from '@/shared/components/StudyHeatmap'
import { DeckTree } from '../components/DeckTree'
import { CreateDeckModal, DeckActionModal } from '../components/DeckModals'
import { findDeck, useDashboardPage } from '../hooks/useDashboardPage'
import type { DeckNode } from '../types'

export function DashboardPage() {
  const { t } = useTranslation('dashboard')
  const navigate = useNavigate()
  const {
    bootstrapQuery,
    dashboardQuery,
    overviewQuery,
    year,
    setYear,
    createOpened,
    setCreateOpened,
    selection,
    setSelection,
    selectedDeckId,
    setSelectedDeckId,
    handleMoveDeck,
  } = useDashboardPage()

  const handleSelectDeck = useCallback((deck: DeckNode) => {
    setSelectedDeckId(deck.id)
  }, [setSelectedDeckId])

  const handleActivateDeck = useCallback((deck: DeckNode) => {
    navigate(deck.study_url)
  }, [navigate])

  const handleCloseCreate = useCallback(() => {
    setCreateOpened(false)
  }, [setCreateOpened])

  const handleCloseAction = useCallback(() => {
    setSelection(null)
  }, [setSelection])

  const dashboardData = dashboardQuery.data
  const selectedDeck = useMemo(() => {
    if (!dashboardData) return null
    return findDeck(dashboardData.decks, selectedDeckId)
  }, [dashboardData, selectedDeckId])

  if (bootstrapQuery.isPending || dashboardQuery.isPending) {
    return <PageLoading label={t('page.loading')} />
  }
  if (!bootstrapQuery.data) {
    return <Page><PageError error={new Error(t('page.auth_error'))} /></Page>
  }
  if (dashboardQuery.error) {
    return <Page><PageError error={dashboardQuery.error} /></Page>
  }

  const bootstrap = bootstrapQuery.data
  const dashboard = dashboardQuery.data

  const statsUrl = selectedDeck ? `/statistics?deck_id=${selectedDeck.id}` : '/statistics'
  const browseUrl = selectedDeck ? `/browse?deck_id=${selectedDeck.id}` : bootstrap.links.browse
  const importUrl = selectedDeck
    ? `/flashcards/import?deck_id=${selectedDeck.id}`
    : '/flashcards/import'

  return (
    <Page className="anki-home relative max-w-[1200px] w-full mx-auto px-2 sm:px-4 py-2 sm:py-3 space-y-3 sm:space-y-6">
      <AmbientBackground />

      {/* Shared Dashboard Toolbar */}
      <div className="dash-toolbar flex items-center justify-between gap-2 border-b border-border/60 pb-2 sm:pb-3">
        {/* Left Navigation Tabs */}
        <div className="dash-toolbar__nav flex items-center gap-1 overflow-x-auto max-w-full py-0.5">
          <Link
            to="/dashboard"
            className="dash-tab inline-flex items-center gap-1.5 rounded-lg bg-orange-500/10 px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-bold text-orange-700 dark:text-orange-400 shrink-0"
          >
            <Collection className="size-3.5 sm:size-4" /> {t('toolbar.tabs.decks')}
          </Link>

          {selectedDeck ? (
            <Link
              to={selectedDeck.study_url}
              className="dash-tab inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
            >
              <PlayCircle className="size-3.5 sm:size-4" /> {t('toolbar.tabs.study')}
            </Link>
          ) : (
            <button
              type="button"
              disabled
              title={t('toolbar.tabs.study_disabled_tooltip')}
              className="dash-tab inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground/40 cursor-not-allowed opacity-50 shrink-0 select-none"
            >
              <PlayCircle className="size-3.5 sm:size-4" /> {t('toolbar.tabs.study')}
            </button>
          )}

          <Link
            to={statsUrl}
            className="dash-tab inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <BarChartLine className="size-3.5 sm:size-4" /> {t('toolbar.tabs.stats')}
          </Link>

          <Link
            to={importUrl}
            className="dash-tab hidden sm:inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <Upload className="size-3.5 sm:size-4" /> {t('toolbar.tabs.import')}
          </Link>

          <Link
            to={browseUrl}
            className="dash-tab inline-flex sm:hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <Search className="size-3.5" /> {t('toolbar.tabs.browse')}
          </Link>
        </div>

        {/* Right Actions */}
        <div className="dash-toolbar__actions flex items-center gap-1.5 sm:gap-2 shrink-0">
          <Button
            type="button"
            className="dash-btn dash-btn--primary text-xs font-bold bg-gradient-to-r from-primary to-orange-500 text-primary-foreground shadow-xs hover:opacity-95 h-8 px-2 sm:px-3 hidden sm:inline-flex"
            size="sm"
            onClick={() => setCreateOpened(true)}
          >
            <PlusLg className="size-3.5 sm:size-4 sm:mr-1" />
            <span>{t('toolbar.actions.create_deck')}</span>
          </Button>

          <Link
            to={browseUrl}
            className="dash-btn dash-btn--ghost hidden sm:inline-flex items-center gap-1.5 rounded-md border border-border/80 px-2.5 sm:px-3 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold hover:bg-muted"
          >
            <Search className="size-3.5 sm:size-4" /> {t('toolbar.actions.browse')}
          </Link>
        </div>
      </div>

      {/* Main Deck Board Container */}
      <section className="deck-board w-full rounded-xl sm:rounded-2xl border-0 sm:border border-border bg-card p-2.5 sm:p-6 shadow-none sm:shadow-sm">
        <header className="deck-board-head flex items-center justify-between border-b border-border/60 pb-2 sm:pb-3 mb-2">
          <div className="head-left flex items-center justify-between w-full sm:w-auto">
            <h3 id="anki-decks-title" className="section-title text-lg sm:text-xl font-bold text-foreground">
              {t('deck_board.title')}
            </h3>
            <Button
              type="button"
              className="dash-btn dash-btn--primary text-xs font-bold bg-gradient-to-r from-primary to-orange-500 text-primary-foreground shadow-xs hover:opacity-95 h-7 px-2.5 sm:hidden"
              size="sm"
              onClick={() => setCreateOpened(true)}
            >
              <PlusLg className="size-3.5 mr-1" />
              <span>{t('deck_board.create_deck')}</span>
            </Button>
          </div>

          <div className="head-right hidden sm:grid sm:grid-cols-[repeat(3,64px)_30px] gap-2 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <span className="text-emerald-600">{t('deck_board.columns.new')}</span>
            <span className="text-rose-600">{t('deck_board.columns.learn')}</span>
            <span className="text-orange-600">{t('deck_board.columns.due')}</span>
            <span className="settings-spacer" aria-hidden="true" />
          </div>
        </header>

        <div className="deck-list">
          {dashboard.decks.length ? (
            <DeckTree
              nodes={dashboard.decks}
              adminMode={dashboard.admin_mode}
              selectedDeckId={selectedDeckId}
              onSelect={handleSelectDeck}
              onActivate={handleActivateDeck}
              onAction={setSelection}
              onMoveDeck={handleMoveDeck}
            />
          ) : (
            <div className="onboarding-panel flex flex-col items-center justify-center text-center p-8 rounded-2xl border-2 border-dashed border-orange-300 bg-orange-50/50 space-y-3">
              <div className="onboarding-icon text-4xl">📚</div>
              <h4 className="onboarding-title text-lg font-bold text-foreground">
                {t('deck_board.empty_state.title')}
              </h4>
              <p className="onboarding-desc text-sm text-muted-foreground max-w-md">
                {t('deck_board.empty_state.desc_line1')}<br />
                {t('deck_board.empty_state.desc_line2_prefix')}<strong>{t('deck_board.empty_state.desc_line2_bold')}</strong>{t('deck_board.empty_state.desc_line2_suffix')}
              </p>
              <div className="onboarding-actions flex flex-wrap justify-center gap-3 pt-2">
                <Button asChild size="sm" className="bg-primary text-primary-foreground font-bold">
                  <Link to="/marketplace/decks">
                    <Download className="size-4 mr-1.5" /> {t('deck_board.empty_state.btn_marketplace_decks')}
                  </Link>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <Link to="/marketplace/note-types">
                    <BookOpen className="size-4 mr-1.5" /> {t('deck_board.empty_state.btn_marketplace_templates')}
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
        loading={overviewQuery.isPending || overviewQuery.isPlaceholderData}
        year={year}
        onYearChange={setYear}
      />

      {/* Modals */}
      <CreateDeckModal
        opened={createOpened}
        onClose={handleCloseCreate}
        dashboard={dashboard}
        selectedDeck={selectedDeck}
      />
      <DeckActionModal
        selection={selection}
        onClose={handleCloseAction}
        dashboard={dashboard}
      />
    </Page>
  )
}
