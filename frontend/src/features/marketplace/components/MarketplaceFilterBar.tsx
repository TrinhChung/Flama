import React from 'react'
import {
  Flame,
  Loader2,
  Search,
  SlidersHorizontal,
  Star,
  X,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

type SortView = 'recommended' | 'newest' | 'popular'

interface MarketplaceFilterBarProps {
  queryText: string
  setQueryText: (val: string) => void
  searchInputRef: React.RefObject<HTMLInputElement | null>
  isFetching: boolean
  isPending: boolean
  isFilterExpanded: boolean
  setIsFilterExpanded: React.Dispatch<React.SetStateAction<boolean>>
  activeFilterCount: number
  view: SortView
  setView: (val: SortView) => void
  isFiltered: boolean
  onResetFilters: () => void
  selectedDomain: string
  setSelectedDomain: (val: string) => void
  selectedSubject: string
  setSelectedSubject: (val: string) => void
  selectedFrameworkLevel: string
  setSelectedFrameworkLevel: (val: string) => void
  selectedDifficulty: string
  setSelectedDifficulty: (val: string) => void
  pricingFilter: 'all' | 'free' | 'paid'
  setPricingFilter: (val: 'all' | 'free' | 'paid') => void
  domains: Array<{ id: string; label: string }>
  availableSubjects: Array<{ id: string; label: string }>
  availableFrameworkLevels: Array<{ id: string; label: string }>
  difficulties: Array<{ id: string; label: string }>
  category: string
  setCategory: (val: string) => void
  allCategories: string[]
}

export function MarketplaceFilterBar({
  queryText,
  setQueryText,
  searchInputRef,
  isFetching,
  isPending,
  isFilterExpanded,
  setIsFilterExpanded,
  activeFilterCount,
  view,
  setView,
  isFiltered,
  onResetFilters,
  selectedDomain,
  setSelectedDomain,
  selectedSubject,
  setSelectedSubject,
  selectedFrameworkLevel,
  setSelectedFrameworkLevel,
  selectedDifficulty,
  setSelectedDifficulty,
  pricingFilter,
  setPricingFilter,
  domains,
  availableSubjects,
  availableFrameworkLevels,
  difficulties,
  category,
  setCategory,
  allCategories,
}: MarketplaceFilterBarProps) {
  const { t } = useTranslation('marketplace')

  return (
    <Card className="border-border/80 bg-card/95 backdrop-blur-xs shadow-xs rounded-xl overflow-hidden">
      <CardContent className="p-3.5 sm:p-5 space-y-3.5">
        {/* Top Row: Search Input + Filter Toggle + Sorting Tabs */}
        <div className="flex flex-col sm:flex-row gap-3 sm:items-center justify-between">
          {/* Search Box with Kbd shortcut & Loader */}
          <div data-tour="market-search-box" className="relative flex-1">
            <Label htmlFor="marketplace-search" className="sr-only">
              Tìm kiếm học liệu
            </Label>
            <Input
              ref={searchInputRef}
              id="marketplace-search"
              className="pl-9 pr-14 text-xs sm:text-sm h-10 rounded-lg bg-background border-border/80 focus-visible:ring-2 focus-visible:ring-primary/30"
              placeholder={t('search_filter.placeholder_decks', { defaultValue: 'Tìm bộ thẻ, từ vựng, JLPT, tác giả…' })}
              value={queryText}
              onChange={(event) => setQueryText(event.currentTarget.value)}
            />
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />

            {/* Right Indicator: Loader or Clear Button or Kbd hint */}
            <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-1">
              {isFetching && !isPending ? (
                <Loader2 className="size-4 animate-spin text-primary mr-1" />
              ) : null}

              {queryText ? (
                <button
                  type="button"
                  onClick={() => {
                    setQueryText('')
                    searchInputRef.current?.focus()
                  }}
                  className="flex min-w-[36px] min-h-[36px] items-center justify-center rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                  aria-label={t('search_filter.clear_search', { defaultValue: 'Xóa từ khóa tìm kiếm' })}
                >
                  <X className="size-4" />
                </button>
              ) : (
                <kbd className="hidden sm:inline-flex h-5 items-center justify-center rounded-md border border-border/80 bg-muted px-1.5 text-[10px] font-medium text-muted-foreground shadow-2xs select-none mr-1">
                  /
                </kbd>
              )}
            </div>
          </div>

          {/* Filter Toggle, Sort Tabs & Reset Button */}
          <div data-tour="market-sort-tabs" className="flex items-center gap-2 shrink-0">
            <Button
              variant={isFilterExpanded || activeFilterCount > 0 ? 'default' : 'outline'}
              size="sm"
              onClick={() => setIsFilterExpanded((prev) => !prev)}
              className="h-10 px-3 text-xs font-semibold rounded-lg gap-1.5 shrink-0"
            >
              <SlidersHorizontal className="size-3.5" />
              <span>{t('search_filter.filter_btn', { defaultValue: 'Bộ lọc' })}</span>
              {activeFilterCount > 0 && (
                <span className="ml-0.5 inline-flex items-center justify-center size-4 text-[10px] font-bold rounded-full bg-primary-foreground text-primary">
                  {activeFilterCount}
                </span>
              )}
            </Button>

            <Tabs
              value={view}
              onValueChange={(value) => setView(value as SortView)}
              className="w-full sm:w-auto"
            >
              <TabsList className="grid grid-cols-3 w-full sm:w-auto h-10 p-1 rounded-lg bg-muted/60">
                <TabsTrigger
                  value="recommended"
                  className="text-xs font-semibold px-2 sm:px-3.5 py-1.5 rounded-md gap-1"
                >
                  <Star className="size-3 text-amber-500 fill-amber-400 shrink-0" />
                  <span className="truncate">{t('search_filter.tabs.recommended', { defaultValue: 'Đề xuất' })}</span>
                </TabsTrigger>
                <TabsTrigger
                  value="popular"
                  className="text-xs font-semibold px-2 sm:px-3.5 py-1.5 rounded-md gap-1"
                >
                  <Flame className="size-3 text-primary shrink-0" />
                  <span className="truncate">{t('search_filter.tabs.popular', { defaultValue: 'Phổ biến' })}</span>
                </TabsTrigger>
                <TabsTrigger
                  value="newest"
                  className="text-xs font-semibold px-2 sm:px-3.5 py-1.5 rounded-md"
                >
                  <span className="truncate">{t('search_filter.tabs.newest', { defaultValue: 'Mới nhất' })}</span>
                </TabsTrigger>
              </TabsList>
            </Tabs>

            {isFiltered ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-10 px-2.5 text-xs text-muted-foreground hover:text-foreground rounded-lg shrink-0"
                onClick={onResetFilters}
                title={t('search_filter.clear_all', { defaultValue: 'Xóa toàn bộ bộ lọc' })}
                aria-label={t('search_filter.clear_all', { defaultValue: 'Xóa toàn bộ bộ lọc' })}
              >
                <X className="size-4" />
                <span className="sr-only">Xóa bộ lọc</span>
              </Button>
            ) : null}
          </div>
        </div>

        {/* Expandable Advanced Taxonomy Filters Panel */}
        {isFilterExpanded && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2.5 p-3 rounded-xl bg-muted/30 border border-border/60 transition-all">
            {/* Domain Filter */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-muted-foreground">
                {t('search_filter.filter_drawer.domain_label', { defaultValue: 'Lĩnh vực (Domain)' })}
              </label>
              <Select
                value={selectedDomain || 'all'}
                onValueChange={(val) => {
                  setSelectedDomain(val === 'all' ? '' : val)
                  setSelectedSubject('')
                  setSelectedFrameworkLevel('')
                }}
              >
                <SelectTrigger className="h-8.5 text-xs bg-background">
                  <SelectValue placeholder={t('search_filter.filter_drawer.domain_all', { defaultValue: 'Tất cả lĩnh vực' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.filter_drawer.domain_all', { defaultValue: 'Tất cả lĩnh vực' })}</SelectItem>
                  {domains.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Subject Filter */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-muted-foreground">
                {t('search_filter.filter_drawer.subject_label', { defaultValue: 'Môn học (Subject)' })}
              </label>
              <Select
                value={selectedSubject || 'all'}
                onValueChange={(val) => {
                  setSelectedSubject(val === 'all' ? '' : val)
                  setSelectedFrameworkLevel('')
                }}
              >
                <SelectTrigger className="h-8.5 text-xs bg-background">
                  <SelectValue placeholder={t('search_filter.filter_drawer.subject_all', { defaultValue: 'Tất cả môn học' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.filter_drawer.subject_all', { defaultValue: 'Tất cả môn học' })}</SelectItem>
                  {availableSubjects.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Framework Level Filter */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-muted-foreground">
                {t('search_filter.filter_drawer.level_label', { defaultValue: 'Trình độ / Khung' })}
              </label>
              <Select
                value={selectedFrameworkLevel || 'all'}
                onValueChange={(val) => setSelectedFrameworkLevel(val === 'all' ? '' : val)}
              >
                <SelectTrigger className="h-8.5 text-xs bg-background">
                  <SelectValue placeholder={t('search_filter.filter_drawer.level_all', { defaultValue: 'Tất cả trình độ' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.filter_drawer.level_all', { defaultValue: 'Tất cả trình độ' })}</SelectItem>
                  {availableFrameworkLevels.map((l) => (
                    <SelectItem key={l.id} value={l.id}>
                      {l.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Difficulty Filter */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-muted-foreground">
                {t('search_filter.filter_drawer.difficulty_label', { defaultValue: 'Độ khó' })}
              </label>
              <Select
                value={selectedDifficulty || 'all'}
                onValueChange={(val) => setSelectedDifficulty(val === 'all' ? '' : val)}
              >
                <SelectTrigger className="h-8.5 text-xs bg-background">
                  <SelectValue placeholder={t('search_filter.filter_drawer.difficulty_all', { defaultValue: 'Tất cả độ khó' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.filter_drawer.difficulty_all', { defaultValue: 'Tất cả độ khó' })}</SelectItem>
                  {difficulties.map((diff) => (
                    <SelectItem key={diff.id} value={diff.id}>
                      {diff.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Pricing Filter */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-muted-foreground">
                {t('search_filter.filter_drawer.pricing_label', { defaultValue: 'Giá bán' })}
              </label>
              <Select
                value={pricingFilter}
                onValueChange={(val) => setPricingFilter(val as 'all' | 'free' | 'paid')}
              >
                <SelectTrigger className="h-8.5 text-xs bg-background">
                  <SelectValue placeholder={t('search_filter.filter_drawer.pricing_all', { defaultValue: 'Tất cả giá' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.filter_drawer.pricing_all', { defaultValue: 'Tất cả' })}</SelectItem>
                  <SelectItem value="free">{t('search_filter.filter_drawer.pricing_free', { defaultValue: 'Miễn phí' })}</SelectItem>
                  <SelectItem value="paid">{t('search_filter.filter_drawer.pricing_paid', { defaultValue: 'Trả phí' })}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        {/* Active Filter Badges */}
        {isFiltered && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-[11px] font-medium text-muted-foreground mr-1">
              {t('search_filter.active_filters.prefix', { defaultValue: 'Bộ lọc đang áp dụng:' })}
            </span>
            {queryText && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>{t('search_filter.active_filters.query', { query: queryText, defaultValue: `Từ khóa: "${queryText}"` })}</span>
                <button type="button" onClick={() => setQueryText('')} className="hover:text-destructive cursor-pointer">
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            {category && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>{t('search_filter.active_filters.category', { category, defaultValue: `Chủ đề: ${category}` })}</span>
                <button type="button" onClick={() => setCategory('')} className="hover:text-destructive cursor-pointer">
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            {selectedDomain && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>
                  {t('search_filter.active_filters.domain', {
                    label: domains.find((d) => d.id === selectedDomain)?.label || selectedDomain,
                    defaultValue: `Lĩnh vực: ${domains.find((d) => d.id === selectedDomain)?.label || selectedDomain}`,
                  })}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedDomain('')
                    setSelectedSubject('')
                    setSelectedFrameworkLevel('')
                  }}
                  className="hover:text-destructive cursor-pointer"
                >
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            {selectedSubject && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>
                  {t('search_filter.active_filters.subject', {
                    label: availableSubjects.find((s) => s.id === selectedSubject)?.label || selectedSubject,
                    defaultValue: `Môn: ${availableSubjects.find((s) => s.id === selectedSubject)?.label || selectedSubject}`,
                  })}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedSubject('')
                    setSelectedFrameworkLevel('')
                  }}
                  className="hover:text-destructive cursor-pointer"
                >
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            {selectedFrameworkLevel && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>
                  {t('search_filter.active_filters.level', {
                    label: availableFrameworkLevels.find((l) => l.id === selectedFrameworkLevel)?.label || selectedFrameworkLevel,
                    defaultValue: `Trình độ: ${availableFrameworkLevels.find((l) => l.id === selectedFrameworkLevel)?.label || selectedFrameworkLevel}`,
                  })}
                </span>
                <button type="button" onClick={() => setSelectedFrameworkLevel('')} className="hover:text-destructive cursor-pointer">
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            {selectedDifficulty && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>
                  {t('search_filter.active_filters.difficulty', {
                    label: difficulties.find((d) => d.id === selectedDifficulty)?.label || selectedDifficulty,
                    defaultValue: `Độ khó: ${difficulties.find((d) => d.id === selectedDifficulty)?.label || selectedDifficulty}`,
                  })}
                </span>
                <button type="button" onClick={() => setSelectedDifficulty('')} className="hover:text-destructive cursor-pointer">
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            {pricingFilter !== 'all' && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>
                  {t('search_filter.active_filters.pricing', {
                    label: pricingFilter === 'free' ? t('search_filter.filter_drawer.pricing_free', { defaultValue: 'Miễn phí' }) : t('search_filter.filter_drawer.pricing_paid', { defaultValue: 'Trả phí' }),
                    defaultValue: `Giá: ${pricingFilter === 'free' ? 'Miễn phí' : 'Trả phí'}`,
                  })}
                </span>
                <button type="button" onClick={() => setPricingFilter('all')} className="hover:text-destructive cursor-pointer">
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={onResetFilters}
              className="h-6 px-2 text-[11px] text-muted-foreground hover:text-destructive font-medium cursor-pointer"
            >
              {t('search_filter.clear_all', { defaultValue: 'Xóa tất cả' })}
            </Button>
          </div>
        )}

        {/* Bottom Row: Quick Category Pills with Horizontal Scroll & ARIA */}
        <div data-tour="market-categories" className="relative pt-2 border-t border-border/40">
          <div
            role="group"
            aria-label="Lọc theo danh mục chủ đề"
            className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-0.5 pr-8 touch-pan-x overscroll-x-contain"
            style={{ WebkitOverflowScrolling: 'touch' }}
          >
            <span className="text-[11px] font-semibold text-muted-foreground mr-1 shrink-0 uppercase tracking-wider">
              Chủ đề:
            </span>
            <button
              type="button"
              aria-pressed={category === ''}
              onClick={() => setCategory('')}
              className={`shrink-0 text-xs px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer ${
                category === ''
                  ? 'bg-primary text-primary-foreground shadow-2xs font-semibold ring-1 ring-primary/30'
                  : 'bg-muted/50 hover:bg-muted text-muted-foreground hover:text-foreground'
              }`}
            >
              {t('search_filter.all_categories', { defaultValue: 'Tất cả' })}
            </button>
            {allCategories.map((cat) => {
              const isSelected = category === cat
              return (
                <button
                  key={cat}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => setCategory(isSelected ? '' : cat)}
                  className={`shrink-0 text-xs px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-primary text-primary-foreground shadow-2xs font-semibold ring-1 ring-primary/30'
                      : 'bg-muted/50 hover:bg-muted text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {cat}
                </button>
              )
            })}
          </div>

          {/* Subtle Gradient Fade on Right for Scroll Indication */}
          <div className="pointer-events-none absolute right-0 top-2 bottom-0 w-8 bg-gradient-to-l from-card to-transparent" />
        </div>
      </CardContent>
    </Card>
  )
}
