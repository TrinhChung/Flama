import React from 'react'
import {
  Search,
  SlidersHorizontal,
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

interface InstalledDecksFilterBarProps {
  queryText: string
  setQueryText: (val: string) => void
  searchInputRef: React.RefObject<HTMLInputElement | null>
  isFilterExpanded: boolean
  setIsFilterExpanded: React.Dispatch<React.SetStateAction<boolean>>
  activeFilterCount: number
  statusFilter: 'all' | 'using_now' | 'installed' | 'owned' | 'update_available' | 'conflict'
  setStatusFilter: (val: 'all' | 'using_now' | 'installed' | 'owned' | 'update_available' | 'conflict') => void
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
  domains: Array<{ id: string; label: string }>
  availableSubjects: Array<{ id: string; label: string }>
  availableFrameworkLevels: Array<{ id: string; label: string }>
  difficulties: Array<{ id: string; label: string }>
  category: string
  setCategory: (val: string) => void
  allCategories: string[]
}

export function InstalledDecksFilterBar({
  queryText,
  setQueryText,
  searchInputRef,
  isFilterExpanded,
  setIsFilterExpanded,
  activeFilterCount,
  statusFilter,
  setStatusFilter,
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
  domains,
  availableSubjects,
  availableFrameworkLevels,
  difficulties,
  category,
  setCategory,
  allCategories,
}: InstalledDecksFilterBarProps) {
  const { t } = useTranslation('library')

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'using_now':
        return t('search_filter.advanced.status_using_now', { defaultValue: 'Đang sử dụng' })
      case 'installed':
        return t('search_filter.advanced.status_installed', { defaultValue: 'Đã cài đặt' })
      case 'owned':
        return t('search_filter.advanced.status_owned', { defaultValue: 'Deck của bạn' })
      case 'update_available':
        return t('search_filter.advanced.status_update_available', { defaultValue: 'Có bản cập nhật' })
      case 'conflict':
        return t('search_filter.advanced.status_conflict', { defaultValue: 'Có xung đột' })
      default:
        return status
    }
  }

  return (
    <Card className="border-border/80 bg-card/95 backdrop-blur-xs shadow-xs rounded-xl overflow-hidden">
      <CardContent className="p-3.5 sm:p-5 space-y-3.5">
        {/* Top Row: Search Input + Filter Toggle + Status Tabs */}
        <div className="flex flex-col sm:flex-row gap-3 sm:items-center justify-between">
          {/* Search Box with Kbd hint */}
          <div data-tour="installed-decks-search" className="relative flex-1">
            <Label htmlFor="installed-search" className="sr-only">
              Tìm kiếm deck đã cài
            </Label>
            <Input
              ref={searchInputRef}
              id="installed-search"
              className="pl-9 pr-14 text-xs sm:text-sm h-10 rounded-lg bg-background border-border/80 focus-visible:ring-2 focus-visible:ring-primary/30"
              placeholder={t('search_filter.placeholder', { defaultValue: "Tìm kiếm deck đã cài theo tên, tác giả... (Nhấn '/' để tìm nhanh)" })}
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
            />
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />

            {/* Clear Button or Kbd hint */}
            <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-1">
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

          {/* Filter Toggle + Status Tabs + Reset */}
          <div className="flex items-center gap-2 shrink-0">
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
              value={statusFilter === 'using_now' || statusFilter === 'update_available' ? statusFilter : 'all'}
              onValueChange={(val) => setStatusFilter(val as any)}
              className="w-full sm:w-auto"
            >
              <TabsList className="grid grid-cols-3 w-full sm:w-auto h-10 p-1 rounded-lg bg-muted/60">
                <TabsTrigger
                  value="all"
                  className="text-xs font-semibold px-2 sm:px-3.5 py-1.5 rounded-md"
                >
                  {t('search_filter.tabs.all', { defaultValue: 'Tất cả' })}
                </TabsTrigger>
                <TabsTrigger
                  value="using_now"
                  className="text-xs font-semibold px-2 sm:px-3.5 py-1.5 rounded-md"
                >
                  {t('search_filter.tabs.using_now', { defaultValue: 'Đang dùng' })}
                </TabsTrigger>
                <TabsTrigger
                  value="update_available"
                  className="text-xs font-semibold px-2 sm:px-3.5 py-1.5 rounded-md"
                >
                  {t('search_filter.tabs.update_available', { defaultValue: 'Có bản mới' })}
                </TabsTrigger>
              </TabsList>
            </Tabs>

            {isFiltered ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-10 px-2.5 text-xs text-muted-foreground hover:text-foreground rounded-lg shrink-0"
                onClick={onResetFilters}
                title={t('search_filter.clear_all', { defaultValue: 'Xóa tất cả' })}
                aria-label={t('search_filter.clear_all', { defaultValue: 'Xóa tất cả' })}
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
            {/* Status Filter */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-muted-foreground">
                {t('search_filter.advanced.status_label', { defaultValue: 'Trạng thái deck' })}
              </label>
              <Select
                value={statusFilter}
                onValueChange={(val) => setStatusFilter(val as any)}
              >
                <SelectTrigger className="h-8.5 text-xs bg-background">
                  <SelectValue placeholder={t('search_filter.advanced.status_all', { defaultValue: 'Tất cả trạng thái' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.advanced.status_all', { defaultValue: 'Tất cả trạng thái' })}</SelectItem>
                  <SelectItem value="using_now">{t('search_filter.advanced.status_using_now', { defaultValue: 'Đang sử dụng' })}</SelectItem>
                  <SelectItem value="installed">{t('search_filter.advanced.status_installed', { defaultValue: 'Đã cài đặt' })}</SelectItem>
                  <SelectItem value="owned">{t('search_filter.advanced.status_owned', { defaultValue: 'Deck của bạn' })}</SelectItem>
                  <SelectItem value="update_available">{t('search_filter.advanced.status_update_available', { defaultValue: 'Có bản cập nhật' })}</SelectItem>
                  <SelectItem value="conflict">{t('search_filter.advanced.status_conflict', { defaultValue: 'Có xung đột' })}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Domain Filter */}
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-muted-foreground">
                {t('search_filter.advanced.domain_label', { defaultValue: 'Lĩnh vực (Domain)' })}
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
                  <SelectValue placeholder={t('search_filter.advanced.domain_all', { defaultValue: 'Tất cả lĩnh vực' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.advanced.domain_all', { defaultValue: 'Tất cả lĩnh vực' })}</SelectItem>
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
                {t('search_filter.advanced.subject_label', { defaultValue: 'Môn học (Subject)' })}
              </label>
              <Select
                value={selectedSubject || 'all'}
                onValueChange={(val) => {
                  setSelectedSubject(val === 'all' ? '' : val)
                  setSelectedFrameworkLevel('')
                }}
              >
                <SelectTrigger className="h-8.5 text-xs bg-background">
                  <SelectValue placeholder={t('search_filter.advanced.subject_all', { defaultValue: 'Tất cả môn học' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.advanced.subject_all', { defaultValue: 'Tất cả môn học' })}</SelectItem>
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
                {t('search_filter.advanced.level_label', { defaultValue: 'Trình độ / Khung' })}
              </label>
              <Select
                value={selectedFrameworkLevel || 'all'}
                onValueChange={(val) => setSelectedFrameworkLevel(val === 'all' ? '' : val)}
              >
                <SelectTrigger className="h-8.5 text-xs bg-background">
                  <SelectValue placeholder={t('search_filter.advanced.level_all', { defaultValue: 'Tất cả trình độ' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.advanced.level_all', { defaultValue: 'Tất cả trình độ' })}</SelectItem>
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
                {t('search_filter.advanced.difficulty_label', { defaultValue: 'Độ khó' })}
              </label>
              <Select
                value={selectedDifficulty || 'all'}
                onValueChange={(val) => setSelectedDifficulty(val === 'all' ? '' : val)}
              >
                <SelectTrigger className="h-8.5 text-xs bg-background">
                  <SelectValue placeholder={t('search_filter.advanced.difficulty_all', { defaultValue: 'Tất cả độ khó' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('search_filter.advanced.difficulty_all', { defaultValue: 'Tất cả độ khó' })}</SelectItem>
                  {difficulties.map((diff) => (
                    <SelectItem key={diff.id} value={diff.id}>
                      {diff.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        {/* Active Filter Badges */}
        {isFiltered && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-[11px] font-medium text-muted-foreground mr-1">
              {t('search_filter.active.prefix', { defaultValue: 'Bộ lọc đang áp dụng:' })}
            </span>
            {queryText && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>{t('search_filter.active.query', { query: queryText, defaultValue: `Từ khóa: "${queryText}"` })}</span>
                <button type="button" onClick={() => setQueryText('')} className="hover:text-destructive cursor-pointer">
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            {category && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>{t('search_filter.active.category', { category, defaultValue: `Chủ đề: ${category}` })}</span>
                <button type="button" onClick={() => setCategory('')} className="hover:text-destructive cursor-pointer">
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            {statusFilter !== 'all' && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>{t('search_filter.active.status', { status: getStatusLabel(statusFilter), defaultValue: `Trạng thái: ${getStatusLabel(statusFilter)}` })}</span>
                <button type="button" onClick={() => setStatusFilter('all')} className="hover:text-destructive cursor-pointer">
                  <X className="size-3" />
                </button>
              </Badge>
            )}
            {selectedDomain && (
              <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                <span>
                  {t('search_filter.active.domain', {
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
                  {t('search_filter.active.subject', {
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
                  {t('search_filter.active.level', {
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
                  {t('search_filter.active.difficulty', {
                    label: difficulties.find((d) => d.id === selectedDifficulty)?.label || selectedDifficulty,
                    defaultValue: `Độ khó: ${difficulties.find((d) => d.id === selectedDifficulty)?.label || selectedDifficulty}`,
                  })}
                </span>
                <button type="button" onClick={() => setSelectedDifficulty('')} className="hover:text-destructive cursor-pointer">
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
        <div data-tour="installed-decks-categories" className="relative pt-2 border-t border-border/40">
          <div
            role="group"
            aria-label="Lọc theo danh mục chủ đề"
            className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-0.5 pr-8 touch-pan-x overscroll-x-contain"
            style={{ WebkitOverflowScrolling: 'touch' }}
          >
            <span className="text-[11px] font-semibold text-muted-foreground mr-1 shrink-0 uppercase tracking-wider">
              {t('categories.title', { defaultValue: 'Chủ đề:' })}
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
              {t('categories.all', { defaultValue: 'Tất cả' })}
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
