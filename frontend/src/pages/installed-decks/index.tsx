import {
  ArrowRight,
  HelpCircle,
  RotateCcw,
  Store,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Page, PageHeader } from '@/shared/components/Page'
import {
  EmptyState,
  PageError,
  PageLoading,
} from '@/shared/components/PageState'
import { SpotlightTour } from '@/shared/components/SpotlightTour'
import { ContextHelpButton } from '@/features/guide'
import { DeckCard, getCategoryBadgeStyle } from '@/entities/marketplace-deck'
import { InstalledDecksFilterBar } from '@/features/library'

import { useInstalledDecks } from './hooks/useInstalledDecks'

export function InstalledDecksPage() {
  const { t, tourOpen, setTourOpen, queryText, setQueryText, category, setCategory, statusFilter, setStatusFilter, selectedDomain, setSelectedDomain, selectedSubject, setSelectedSubject, selectedFrameworkLevel, setSelectedFrameworkLevel, selectedDifficulty, setSelectedDifficulty, isFilterExpanded, setIsFilterExpanded, searchInputRef, domains, difficulties, query, items, availableSubjects, availableFrameworkLevels, activeFilterCount, isFiltered, handleResetFilters, filteredItems, curatedSections, tourSteps, DECK_MAJOR_CATEGORIES, DECKS_STORAGE_KEY } = useInstalledDecks()

  if (query.isPending) {
    return <PageLoading label={t('summary.empty_desc', { defaultValue: 'Đang tải deck đã cài…' })} />
  }

  if (query.error) {
    return (
      <Page>
        <PageError error={query.error} />
      </Page>
    )
  }

  return (
    <Page size="wide" className="relative min-h-screen px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />
      <div data-tour="decks-header">
        <PageHeader
          title={t('header.title', { defaultValue: 'Deck đã cài' })}
          description={t('header.description', { defaultValue: 'Quản lý và tiếp tục học các bộ deck bạn đã cài từ Marketplace hoặc sở hữu.' })}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setTourOpen(true)}
                className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl"
              >
                <HelpCircle className="size-3.5 mr-1.5 text-primary" />
                {t('header.btn_tour', { defaultValue: 'Tour Hướng Dẫn' })}
              </Button>
              <ContextHelpButton
                guidePath="/guide/marketplace/installed-overlay"
                guideTitle="Cơ chế Clone Overlay & Cập nhật Deck"
                label={t('header.btn_help', { defaultValue: 'Trợ giúp' })}
              />
              <Button
                size="sm"
                data-tour="marketplace-explore-btn"
                className="h-8 sm:h-9 px-3.5 rounded-xl font-bold text-xs sm:text-sm shadow-xs"
                asChild
              >
                <Link to="/marketplace/decks" className="inline-flex items-center gap-1.5">
                  <Store className="size-3.5" />
                  <span>{t('header.btn_explore', { defaultValue: 'Khám phá Marketplace' })}</span>
                  <ArrowRight className="size-3.5" />
                </Link>
              </Button>
            </div>
          }
        />
      </div>

      {/* Unified Search & Filter Control Center */}
      <InstalledDecksFilterBar
        queryText={queryText}
        setQueryText={setQueryText}
        searchInputRef={searchInputRef}
        isFilterExpanded={isFilterExpanded}
        setIsFilterExpanded={setIsFilterExpanded}
        activeFilterCount={activeFilterCount}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        isFiltered={isFiltered}
        onResetFilters={handleResetFilters}
        selectedDomain={selectedDomain}
        setSelectedDomain={setSelectedDomain}
        selectedSubject={selectedSubject}
        setSelectedSubject={setSelectedSubject}
        selectedFrameworkLevel={selectedFrameworkLevel}
        setSelectedFrameworkLevel={setSelectedFrameworkLevel}
        selectedDifficulty={selectedDifficulty}
        setSelectedDifficulty={setSelectedDifficulty}
        domains={domains}
        availableSubjects={availableSubjects}
        availableFrameworkLevels={availableFrameworkLevels}
        difficulties={difficulties}
        category={category}
        setCategory={setCategory}
        allCategories={DECK_MAJOR_CATEGORIES}
      />

      {/* Results Header / Summary */}
      {items.length > 0 ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
          <span className="font-medium">
            {t('summary.results_count', {
              filtered: filteredItems.length,
              total: items.length,
              suffix: isFiltered ? t('summary.suffix_filtered', { defaultValue: 'phù hợp với bộ lọc' }) : t('summary.suffix_installed', { defaultValue: 'đã cài' }),
              defaultValue: `Hiển thị ${filteredItems.length} / ${items.length} bộ deck ${isFiltered ? 'phù hợp với bộ lọc' : 'đã cài'}`,
            })}
          </span>
        </div>
      ) : null}

      {!items.length ? (
        <div data-tour="installed-decks-grid">
          <EmptyState
            title={t('summary.empty_title', { defaultValue: 'Chưa cài deck nào' })}
            description={t('summary.empty_desc', { defaultValue: 'Khám phá marketplace và cài một deck để bắt đầu học.' })}
          />
        </div>
      ) : !filteredItems.length ? (
        <div className="py-8">
          <EmptyState
            title={t('summary.no_match_title', { defaultValue: 'Không tìm thấy bộ deck phù hợp' })}
            description={t('summary.no_match_desc', { defaultValue: 'Thử thay đổi từ khóa tìm kiếm hoặc xóa các tiêu chí lọc hiện tại.' })}
          />
          <div className="flex justify-center mt-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleResetFilters}
              className="rounded-xl text-xs font-semibold"
            >
              <RotateCcw className="mr-1.5 size-3.5" /> {t('summary.btn_reset_filters', { defaultValue: 'Xóa bộ lọc hiện tại' })}
            </Button>
          </div>
        </div>
      ) : curatedSections ? (
        <div className="space-y-8">
          {curatedSections.majorSections.map((section) => (
            <div key={section.category} className="space-y-3.5">
              <div className="flex items-center justify-between border-b border-border/50 pb-2">
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={`px-2.5 py-0.5 text-xs font-bold rounded-md ${getCategoryBadgeStyle(
                      section.category,
                    )}`}
                  >
                    {section.category}
                  </Badge>
                  <span className="text-xs font-semibold text-muted-foreground">
                    {t('curated.deck_count', { count: section.items.length, defaultValue: `(${section.items.length} bộ deck)` })}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCategory(section.category)}
                  className="h-8 text-xs font-semibold text-primary hover:text-primary hover:bg-primary/10 gap-1 rounded-xl cursor-pointer"
                >
                  <span>{t('curated.view_all', { category: section.category, defaultValue: `Xem tất cả ${section.category}` })}</span>
                  <ArrowRight className="size-3.5" />
                </Button>
              </div>
              <div className="grid gap-3 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {section.items.slice(0, 4).map((item, index) => (
                  <DeckCard
                    key={item.id}
                    item={item}
                    variant="installed"
                    dataTour={index === 0 ? 'deck-card-first' : undefined}
                    actionDataTour={index === 0 ? 'deck-action-btn' : undefined}
                  />
                ))}
              </div>
            </div>
          ))}

          {curatedSections.otherItems.length > 0 && (
            <div className="space-y-3.5">
              <div className="flex items-center justify-between border-b border-border/50 pb-2">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-foreground">{t('curated.other_heading', { defaultValue: 'Bộ thẻ & Chủ đề khác' })}</h3>
                  <span className="text-xs font-semibold text-muted-foreground">
                    {t('curated.deck_count', { count: curatedSections.otherItems.length, defaultValue: `(${curatedSections.otherItems.length} bộ deck)` })}
                  </span>
                </div>
              </div>
              <div className="grid gap-3 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {curatedSections.otherItems.map((item) => (
                  <DeckCard
                    key={item.id}
                    item={item}
                    variant="installed"
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="grid gap-3 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredItems.map((item, index) => (
            <DeckCard
              key={item.id}
              item={item}
              variant="installed"
              dataTour={index === 0 ? 'deck-card-first' : undefined}
              actionDataTour={index === 0 ? 'deck-action-btn' : undefined}
            />
          ))}
        </div>
      )}

      {/* Interactive Spotlight Tour for Installed Decks */}
      <SpotlightTour
        steps={tourSteps}
        isOpen={tourOpen}
        onClose={() => {
          localStorage.setItem(DECKS_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
        onComplete={() => {
          localStorage.setItem(DECKS_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
      />
    </Page>
  )
}
