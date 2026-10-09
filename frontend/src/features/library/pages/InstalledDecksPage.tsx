import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  HelpCircle,
  RotateCcw,
  Store,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Page, PageHeader } from '@/shared/components/Page'
import {
  EmptyState,
  PageError,
  PageLoading,
} from '@/shared/components/PageState'
import { SpotlightTour, type TourStep } from '@/shared/components/SpotlightTour'
import { ContextHelpButton } from '@/features/guide'
import { DeckCard, getCategoryBadgeStyle, type DeckCardItem } from '@/features/marketplace/components/DeckCard'
import { useTaxonomySchema } from '@/features/marketplace/hooks/useTaxonomySchema'
import { InstalledDecksFilterBar } from '../components/InstalledDecksFilterBar'

const DECKS_STORAGE_KEY = 'flama_installed_decks_spotlight_tour_v1'

const DECK_MAJOR_CATEGORIES = [
  'Tiếng Nhật',
  'Tiếng Anh',
  'Tiếng Trung',
  'Tiếng Hàn',
  'Công nghệ & IT',
  'Chứng chỉ',
  'Học thuật',
  'Tổng hợp',
]

export function InstalledDecksPage() {
  const { t } = useTranslation('library')
  const [tourOpen, setTourOpen] = useState(false)
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [category, setCategory] = useState('')
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'using_now' | 'installed' | 'owned' | 'update_available' | 'conflict'
  >('all')
  const [selectedDomain, setSelectedDomain] = useState('')
  const [selectedSubject, setSelectedSubject] = useState('')
  const [selectedFrameworkLevel, setSelectedFrameworkLevel] = useState('')
  const [selectedDifficulty, setSelectedDifficulty] = useState('')
  const [isFilterExpanded, setIsFilterExpanded] = useState(false)
  const searchInputRef = useRef<HTMLInputElement>(null)

  const {
    domains,
    subjectsByDomain,
    frameworksForSubject,
    difficulties,
  } = useTaxonomySchema('deck_marketplace_item')

  // Debounce search query
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(queryText.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [queryText])

  // Global '/' keyboard shortcut to focus search input
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (
        e.key === '/' &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault()
        searchInputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const query = useQuery({
    queryKey: ['installed-decks'],
    queryFn: () =>
      appApi.get<{ items: DeckCardItem[] }>(
        '/marketplace/installed-decks',
      ),
  })

  const items = query.data?.items || []

  // Subjects available under currently selected domain
  const availableSubjects = useMemo(() => {
    if (!selectedDomain) {
      return domains.flatMap((d) => subjectsByDomain(d.id))
    }
    return subjectsByDomain(selectedDomain)
  }, [selectedDomain, domains, subjectsByDomain])

  // Frameworks & levels available under currently selected subject
  const availableFrameworkLevels = useMemo(() => {
    if (!selectedSubject) {
      const jpFrameworks = frameworksForSubject('japanese')
      return jpFrameworks.flatMap((f) => f.levels)
    }
    const frameworks = frameworksForSubject(selectedSubject)
    return frameworks.flatMap((f) => f.levels)
  }, [selectedSubject, frameworksForSubject])

  const activeFilterCount = useMemo(() => {
    let count = 0
    if (selectedDomain) count++
    if (selectedSubject) count++
    if (selectedFrameworkLevel) count++
    if (selectedDifficulty) count++
    if (statusFilter !== 'all') count++
    return count
  }, [
    selectedDomain,
    selectedSubject,
    selectedFrameworkLevel,
    selectedDifficulty,
    statusFilter,
  ])

  const isFiltered = Boolean(queryText || category || activeFilterCount > 0)

  const handleResetFilters = () => {
    setQueryText('')
    setCategory('')
    setStatusFilter('all')
    setSelectedDomain('')
    setSelectedSubject('')
    setSelectedFrameworkLevel('')
    setSelectedDifficulty('')
  }

  // Filtered items computation
  const filteredItems = useMemo(() => {
    let list = items

    if (debouncedQuery) {
      const q = debouncedQuery.toLowerCase()
      list = list.filter(
        (item) =>
          item.title?.toLowerCase().includes(q) ||
          item.name?.toLowerCase().includes(q) ||
          item.description?.toLowerCase().includes(q) ||
          item.author?.username?.toLowerCase().includes(q) ||
          item.author?.account_name?.toLowerCase().includes(q),
      )
    }

    if (category) {
      list = list.filter(
        (item) => item.primary_category?.toLowerCase() === category.toLowerCase(),
      )
    }

    if (statusFilter === 'using_now') {
      list = list.filter((item) => item.install_bucket === 'using_now')
    } else if (statusFilter === 'installed') {
      list = list.filter((item) => item.install_bucket === 'installed')
    } else if (statusFilter === 'owned') {
      list = list.filter((item) => item.install_bucket === 'owned')
    } else if (statusFilter === 'update_available') {
      list = list.filter((item) => Boolean(item.update_available))
    } else if (statusFilter === 'conflict') {
      list = list.filter(
        (item) =>
          item.last_sync_status === 'conflict' ||
          Boolean(item.pending_conflict_count && item.pending_conflict_count > 0),
      )
    }

    if (selectedDomain) {
      list = list.filter(
        (item) =>
          (item as any).taxonomy_metadata?.domain === selectedDomain ||
          (item as any).domain === selectedDomain,
      )
    }

    if (selectedSubject) {
      list = list.filter(
        (item) =>
          (item as any).taxonomy_metadata?.subject === selectedSubject ||
          (item as any).subject === selectedSubject,
      )
    }

    if (selectedFrameworkLevel) {
      list = list.filter(
        (item) =>
          (item as any).taxonomy_metadata?.framework_level === selectedFrameworkLevel ||
          (item as any).framework_level === selectedFrameworkLevel,
      )
    }

    if (selectedDifficulty) {
      list = list.filter(
        (item) =>
          (item as any).taxonomy_metadata?.difficulty_band === selectedDifficulty ||
          (item as any).difficulty_band === selectedDifficulty,
      )
    }

    return list
  }, [
    items,
    debouncedQuery,
    category,
    statusFilter,
    selectedDomain,
    selectedSubject,
    selectedFrameworkLevel,
    selectedDifficulty,
  ])

  // Curated section grouping for installed decks when unfiltered
  const curatedSections = useMemo(() => {
    if (isFiltered || items.length < 5) {
      return null
    }

    const groups: Record<string, DeckCardItem[]> = {}
    items.forEach((it) => {
      const cat = it.primary_category || 'Tổng hợp'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(it)
    })

    const SECTION_THRESHOLD = 3
    const majorSections: { category: string; items: DeckCardItem[] }[] = []
    const otherItems: DeckCardItem[] = []

    Object.entries(groups).forEach(([cat, catItems]) => {
      if (catItems.length >= SECTION_THRESHOLD) {
        majorSections.push({ category: cat, items: catItems })
      } else {
        otherItems.push(...catItems)
      }
    })

    if (majorSections.length === 0) {
      return null
    }

    return {
      majorSections,
      otherItems,
    }
  }, [isFiltered, items])

  const tourSteps: TourStep[] = useMemo(() => {
    const steps: TourStep[] = [
      {
        target: '[data-tour="decks-header"]',
        title: t('tour.step1_title', { defaultValue: '📚 1. Quản Lý Bộ Thẻ Đã Cài' }),
        content: t('tour.step1_content', {
          defaultValue: 'Nơi quản lý toàn bộ các bộ thẻ (Decks) bạn đã cài đặt từ Marketplace hoặc do chính bạn sở hữu để bắt đầu ôn luyện.',
        }),
        placement: 'bottom',
      },
      {
        target: '[data-tour="marketplace-explore-btn"]',
        title: t('tour.step2_title', { defaultValue: '🛍️ 2. Khám Phá Kho Bộ Thẻ Marketplace' }),
        content: t('tour.step2_content', {
          defaultValue: 'Bấm vào đây để duyệt qua hàng trăm bộ thẻ từ vựng, ngữ pháp, Kanji... chất lượng cao do cộng đồng Flama chia sẻ.',
        }),
        placement: 'bottom',
      },
      {
        target: '[data-tour="installed-search-box"]',
        title: t('tour.step3_title', { defaultValue: '🔍 3. Tìm Kiếm & Lọc Bộ Thẻ' }),
        content: t('tour.step3_content', {
          defaultValue: 'Tìm kiếm nhanh theo tên deck, lọc theo danh mục, trình độ JLPT hoặc lọc theo trạng thái đang học/có bản cập nhật.',
        }),
        placement: 'bottom',
      },
    ]

    if (items.length > 0) {
      steps.push(
        {
          target: '[data-tour="deck-card-first"]',
          title: t('tour.step4_title_installed', { defaultValue: '🎴 4. Thông Tin Bộ Thẻ (Deck Card)' }),
          content: t('tour.step4_content_installed', {
            defaultValue: 'Hiển thị tiêu đề bộ thẻ, tên tác giả đóng góp, trạng thái học tập (Đang sử dụng / Đã cài) và mô tả vắn tắt.',
          }),
          placement: 'top',
        },
        {
          target: '[data-tour="deck-action-btn"]',
          title: t('tour.step5_title', { defaultValue: '🚀 5. Nút "Học Ngay" (Spaced Repetition)' }),
          content: t('tour.step5_content', {
            defaultValue: 'Bấm nút này để bắt đầu phiên ôn tập với thuật toán Lặp lại ngắt quãng thông minh (Anki SM-2 / FSRS) giúp ghi nhớ sâu và lâu bền.',
          }),
          placement: 'top',
        },
      )
    } else {
      steps.push({
        target: '[data-tour="installed-decks-grid"]',
        title: t('tour.step4_title_empty', { defaultValue: '📦 4. Khu Vực Bộ Thẻ Cá Nhân' }),
        content: t('tour.step4_content_empty', {
          defaultValue: 'Sau khi cài đặt bộ thẻ từ Marketplace, các bộ thẻ sẽ xuất hiện tại đây để bạn bắt đầu học và theo dõi tiến độ.',
        }),
        placement: 'top',
      })
    }

    return steps
  }, [items.length, t])

  // Auto-launch spotlight tour for first-time visitors with no installed decks
  useEffect(() => {
    if (query.isSuccess) {
      const completed = localStorage.getItem(DECKS_STORAGE_KEY)
      if (!completed && items.length === 0) {
        const timer = setTimeout(() => {
          setTourOpen(true)
        }, 500)
        return () => clearTimeout(timer)
      }
    }
  }, [query.isSuccess, items.length])

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
