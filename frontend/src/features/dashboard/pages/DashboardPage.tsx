import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
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
import { Compass, Target } from 'lucide-react'
import { StudyHeatmap } from '@/shared/components/StudyHeatmap'
import { ContextHelpButton } from '@/features/guide'
import { DeckTree } from '../components/DeckTree'
import { CreateDeckModal, DeckActionModal } from '../components/DeckModals'
import { findDeck, useDashboardPage } from '../hooks/useDashboardPage'
import {
  DashboardSpotlightTour,
  OnboardingHeroCard,
  OnboardingModal,
  useOnboarding,
} from '@/features/onboarding'

export function DashboardPage() {
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

  const [tourOpen, setTourOpen] = useState(false)

  const hasDecks = Boolean(dashboardQuery.data?.decks?.length)
  const onboarding = useOnboarding(hasDecks)

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
        <div
          data-tour="dash-toolbar-nav"
          className="dash-toolbar__nav flex items-center gap-1 overflow-x-auto max-w-full py-0.5"
        >
          <Link
            to="/dashboard"
            className="dash-tab inline-flex items-center gap-1.5 rounded-lg bg-orange-500/10 px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-bold text-orange-700 dark:text-orange-400 shrink-0"
          >
            <Collection className="size-3.5 sm:size-4" /> Decks
          </Link>

          {selectedDeck ? (
            <Link
              to={selectedDeck.study_url}
              data-tour="dash-study-action"
              className="dash-tab inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
            >
              <PlayCircle className="size-3.5 sm:size-4" /> Study
            </Link>
          ) : (
            <button
              type="button"
              disabled
              data-tour="dash-study-action"
              title="Vui lòng chọn một deck để học"
              className="dash-tab inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3.5 py-1.5 sm:py-2 text-[11px] sm:text-xs font-semibold text-muted-foreground/40 cursor-not-allowed opacity-50 shrink-0 select-none"
            >
              <PlayCircle className="size-3.5 sm:size-4" /> Study
            </button>
          )}

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

          <Link
            to={browseUrl}
            className="dash-tab inline-flex sm:hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold text-muted-foreground hover:bg-muted hover:text-foreground transition shrink-0"
          >
            <Search className="size-3.5" /> Browse
          </Link>
        </div>

        {/* Right Actions */}
        <div className="dash-toolbar__actions flex items-center gap-1.5 sm:gap-2 shrink-0">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            data-tour="dash-tour-btn"
            onClick={() => setTourOpen(true)}
            className="h-8 px-2 sm:px-3 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted rounded-xl"
            title="Xem hướng dẫn sử dụng Dashboard"
          >
            <Compass className="size-3.5 sm:size-4 sm:mr-1.5 text-orange-500" />
            <span className="hidden sm:inline">Tour Hướng Dẫn</span>
          </Button>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onboarding.openOnboarding(1)}
            className="h-8 px-2 sm:px-3 text-[11px] sm:text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted rounded-xl hidden md:inline-flex"
            title="Tùy chỉnh mục tiêu cá nhân hóa"
          >
            <Target className="size-3.5 sm:size-4 sm:mr-1.5 text-primary" />
            <span>Mục Tiêu</span>
          </Button>

          <ContextHelpButton
            guidePath="/guide/dashboard/deck-grouping"
            guideTitle="Mẹo gom nhóm bộ thẻ bằng ::"
            troubleshootPath="/guide/troubleshooting/dashboard-study"
            troubleshootTitle="Số lượng thẻ hiển thị chưa đúng?"
            label="Trợ giúp"
            variant="outline"
            size="xs"
          />

          <Button
            type="button"
            data-tour="dash-create-btn"
            className="dash-btn dash-btn--primary text-xs font-bold bg-gradient-to-r from-primary to-orange-500 text-primary-foreground shadow-xs hover:opacity-95 h-8 px-2 sm:px-3 hidden sm:inline-flex rounded-xl"
            size="sm"
            onClick={() => setCreateOpened(true)}
          >
            <PlusLg className="size-3.5 sm:size-4 sm:mr-1" />
            <span>Tạo Deck</span>
          </Button>

          <Link
            to={browseUrl}
            className="dash-btn dash-btn--ghost hidden sm:inline-flex items-center gap-1.5 rounded-xl border border-border/80 px-2.5 sm:px-3 py-1 sm:py-1.5 text-[11px] sm:text-xs font-semibold hover:bg-muted"
          >
            <Search className="size-3.5 sm:size-4" /> Browse
          </Link>
        </div>
      </div>

      {/* Onboarding Hero / Personalization Banner */}
      <OnboardingHeroCard
        preferences={onboarding.preferences}
        onOpenPreferences={() => onboarding.openOnboarding(1)}
        onOpenCreateDeck={() => setCreateOpened(true)}
        onStartTour={() => setTourOpen(true)}
        hasDecks={hasDecks}
      />

      {/* Main Deck Board Container */}
      <section
        data-tour="dash-deck-board"
        className="deck-board w-full rounded-xl sm:rounded-2xl border-0 sm:border border-border bg-card p-2.5 sm:p-6 shadow-none sm:shadow-sm"
      >
        <header className="deck-board-head flex items-center justify-between border-b border-border/60 pb-2 sm:pb-3 mb-2">
          <div className="head-left flex items-center justify-between w-full sm:w-auto">
            <h3 id="anki-decks-title" className="section-title text-lg sm:text-xl font-bold text-foreground">
              Deck
            </h3>
            <Button
              type="button"
              data-tour="dash-create-btn"
              className="dash-btn dash-btn--primary text-xs font-bold bg-gradient-to-r from-primary to-orange-500 text-primary-foreground shadow-xs hover:opacity-95 h-7 px-2.5 sm:hidden rounded-lg"
              size="sm"
              onClick={() => setCreateOpened(true)}
            >
              <PlusLg className="size-3.5 mr-1" />
              <span>Tạo Deck</span>
            </Button>
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
              onSelect={(deck) => setSelectedDeckId(deck.id)}
              onActivate={(deck) => navigate(deck.study_url)}
              onAction={setSelection}
              onMoveDeck={handleMoveDeck}
            />
          ) : (
            <div className="onboarding-panel flex flex-col items-center justify-center text-center p-8 rounded-2xl border-2 border-dashed border-border/80 bg-card/60 dark:bg-card/40 hover:border-primary/40 transition-colors space-y-3">
              <div className="onboarding-icon text-4xl">📚</div>
              <h4 className="onboarding-title text-lg font-bold text-foreground">
                Chào mừng bạn đến với Flama!
              </h4>
              <p className="onboarding-desc text-sm text-muted-foreground max-w-md">
                Tài khoản của bạn chưa có deck nào.<br />
                Hãy khám phá các bộ thẻ đề xuất hoặc vào <strong>Thư viện</strong> để bắt đầu học ngay.
              </p>
              <div className="onboarding-actions flex flex-wrap justify-center gap-3 pt-2">
                <Button
                  size="sm"
                  onClick={() => onboarding.openOnboarding(3)}
                  className="bg-primary text-primary-foreground font-bold shadow-xs"
                >
                  <Download className="size-4 mr-1.5" /> Bộ Thẻ Đề Xuất
                </Button>
                <Button
                  asChild
                  variant="outline"
                  size="sm"
                  data-tour="dash-marketplace-link"
                  className="font-semibold"
                >
                  <Link to="/marketplace/decks">
                    <Download className="size-4 mr-1.5" /> Thư viện Marketplace
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
      <div data-tour="dash-heatmap-section">
        <StudyHeatmap
          overview={overviewQuery.data}
          loading={overviewQuery.isPending}
          year={year}
          onYearChange={setYear}
        />
      </div>

      {/* Modals & Tours */}
      <OnboardingModal
        onboarding={onboarding}
        onStartDashboardTour={() => setTourOpen(true)}
      />

      <DashboardSpotlightTour
        isOpen={tourOpen}
        onClose={() => setTourOpen(false)}
        hasDecks={hasDecks}
      />

      <CreateDeckModal
        opened={createOpened}
        onClose={() => setCreateOpened(false)}
        dashboard={dashboard}
        selectedDeck={selectedDeck}
      />

      <DeckActionModal
        selection={selection}
        onClose={() => setSelection(null)}
        dashboard={dashboard}
      />
    </Page>
  )
}
