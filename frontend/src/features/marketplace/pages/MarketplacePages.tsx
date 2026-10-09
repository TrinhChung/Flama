import { useEffect, useMemo, useRef, useState } from 'react'
import {
  BookOpen,
  HelpCircle,
  Layers,
  Plus,
  RotateCcw,
  X,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { DeckCard } from '../components/DeckCard'
import { SharedNoteTypeCard } from '../components/card/SharedNoteTypeCard'
import { MarketplaceFilterBar } from '../components/MarketplaceFilterBar'
import { MarketplaceCuratedSection } from '../components/MarketplaceCuratedSection'

import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError } from '@/shared/components/PageState'
import { SpotlightTour, type TourStep } from '@/shared/components/SpotlightTour'
import { useTaxonomySchema } from '../hooks/useTaxonomySchema'

const MARKET_STORAGE_KEY = 'flama_marketplace_spotlight_tour_v1'

const getMarketTourSteps = (
  mode: 'decks' | 'note-types',
  hasItems: boolean,
  t: (key: any, opts?: any) => string,
): TourStep[] => {
  const steps: TourStep[] = [
    {
      target: '[data-tour="market-mode-switcher"]',
      title: t('tour.step1_title', { defaultValue: '🔄 1. Chuyển Đổi Kho Học Liệu' }),
      content: t('tour.step1_content', {
        defaultValue: 'Chuyển đổi linh hoạt giữa "Kho Bộ Thẻ" (các bộ flashcard hoàn chỉnh) và "Kho Loại Thẻ" (các mẫu giao diện NoteType).',
      }),
      placement: 'bottom',
    },
    {
      target: '[data-tour="market-publish-btn"]',
      title: mode === 'decks'
        ? t('tour.step2_title_decks', { defaultValue: '🚀 2. Đăng Tải Bộ Thẻ Của Bạn' })
        : t('tour.step2_title_notetypes', { defaultValue: '🚀 2. Tạo Mẫu Thẻ Mới' }),
      content: mode === 'decks'
        ? t('tour.step2_content_decks', {
            defaultValue: 'Chia sẻ bộ thẻ bạn đã biên soạn lên Marketplace để cộng đồng cùng học hoặc nhận đóng góp.',
          })
        : t('tour.step2_content_notetypes', {
            defaultValue: 'Tự tạo loại thẻ mới hoặc xuất bản NoteType của bạn lên Marketplace.',
          }),
      placement: 'bottom',
    },
    {
      target: '[data-tour="market-search-box"]',
      title: t('tour.step3_title', { defaultValue: '🔍 3. Tìm Kiếm Thông Minh' }),
      content: t('tour.step3_content', {
        defaultValue: 'Tìm kiếm nhanh theo tên bộ thẻ, trình độ JLPT (N5 - N1), từ vựng theo chủ đề, hoặc tên tác giả.',
      }),
      placement: 'bottom',
    },
    {
      target: '[data-tour="market-categories"]',
      title: t('tour.step4_title', { defaultValue: '🏷️ 4. Bộ Lọc Theo Chủ Đề' }),
      content: t('tour.step4_content', {
        defaultValue: 'Lọc nhanh theo các danh mục trọng tâm: JLPT N5, N4, N3, N2, N1, Từ vựng, Kanji, Giao tiếp, IT / Công nghệ...',
      }),
      placement: 'bottom',
    },
    {
      target: '[data-tour="market-sort-tabs"]',
      title: t('tour.step5_title', { defaultValue: '⚡ 5. Sắp Xếp Theo Nhu Cầu' }),
      content: t('tour.step5_content', {
        defaultValue: 'Xem các bộ thẻ được "Đề xuất" bởi thuật toán, "Phổ biến" nhiều lượt tải nhất, hoặc "Mới nhất" vừa đăng tải.',
      }),
      placement: 'bottom',
    },
  ]

  if (hasItems) {
    steps.push(
      {
        target: '[data-tour="market-card-first"]',
        title: t('tour.step6_title', { defaultValue: '🎴 6. Thông Tin Thẻ Học Liệu' }),
        content: t('tour.step6_content', {
          defaultValue: 'Mỗi thẻ hiển thị chủ đề, giá bán (Miễn phí/Trả phí), tên tác giả, điểm đánh giá sao ⭐ và số lượng thẻ.',
        }),
        placement: 'top',
      },
      {
        target: '[data-tour="market-action-btn"]',
        title: t('tour.step7_title', { defaultValue: '📥 7. Xem Chi Tiết & Cài Đặt' }),
        content: t('tour.step7_content', {
          defaultValue: 'Bấm để xem trước danh sách thẻ, xem giao diện thực tế và cài đặt (Overlay Sync) trực tiếp vào tài khoản của bạn để học ngay!',
        }),
        placement: 'top',
      },
    )
  }

  return steps
}

type MarketplaceItem = {
  id: string
  title?: string
  name?: string
  description: string | null
  primary_category: string | null
  rating_avg: number
  rating_count?: number
  install_count: number
  card_count?: number
  note_count?: number
  lesson_count?: number
  total_decks?: number
  has_subdecks?: boolean
  price_display: string
  pricing_mode: string
  is_installed: boolean
  installed_deck_id?: number | null
  badges?: string[]
  tags?: string[]
  author: {
    username?: string
    account_name?: string
  } | null
}

type SortView = 'recommended' | 'newest' | 'popular'

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

const NOTETYPE_MAJOR_CATEGORIES = [
  'Từ vựng',
  'Ngữ pháp',
  'Kanji / Hán tự',
  'Đục lỗ (Cloze)',
  'Code & IT',
  'Hỏi đáp (Q&A)',
  'Mẫu chuẩn',
]

function getCategoryBadgeStyle(categoryName: string | null | undefined) {
  if (!categoryName) return 'bg-muted text-muted-foreground border-border/60'
  const lower = categoryName.toLowerCase()
  if (lower.includes('ielts') || lower.includes('toeic') || lower.includes('vstep') || lower.includes('tiếng anh')) {
    return 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20'
  }
  if (lower.includes('topik') || lower.includes('tiếng hàn')) {
    return 'bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/20'
  }
  if (lower.includes('hsk') || lower.includes('tiếng trung') || lower.includes('tocfl')) {
    return 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/20'
  }
  if (lower.includes('aws') || lower.includes('azure') || lower.includes('it') || lower.includes('công nghệ') || lower.includes('code')) {
    return 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20'
  }
  if (lower.includes('n5') || lower.includes('n4')) {
    return 'bg-sky-500/10 text-sky-700 dark:text-sky-400 border-sky-500/20'
  }
  if (lower.includes('n3')) {
    return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20'
  }
  if (lower.includes('n2') || lower.includes('n1') || lower.includes('tiếng nhật')) {
    return 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20'
  }
  if (lower.includes('kanji') || lower.includes('hán tự')) {
    return 'bg-primary/10 text-primary border-primary/20'
  }
  if (lower.includes('thpt') || lower.includes('y dược') || lower.includes('học thuật')) {
    return 'bg-teal-500/10 text-teal-700 dark:text-teal-400 border-teal-500/20'
  }
  if (lower.includes('ngữ pháp') || lower.includes('cloze') || lower.includes('đục lỗ')) {
    return 'bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border-indigo-500/20'
  }
  if (lower.includes('hỏi đáp') || lower.includes('q&a') || lower.includes('mẫu chuẩn') || lower.includes('từ vựng')) {
    return 'bg-cyan-500/10 text-cyan-700 dark:text-cyan-400 border-cyan-500/20'
  }
  return 'bg-muted text-muted-foreground border-border/60'
}

function MarketplaceSkeletonGrid() {
  return (
    <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 8 }).map((_, index) => (
        <Card
          key={index}
          className="flex flex-col justify-between overflow-hidden border-border/70 bg-card p-4 sm:p-5 rounded-xl space-y-4 shadow-xs"
        >
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-20 rounded-md" />
              <Skeleton className="h-5 w-16 rounded-md" />
            </div>
            <Skeleton className="h-6 w-4/5 rounded-md" />
            <div className="flex items-center gap-2">
              <Skeleton className="size-5 rounded-full" />
              <Skeleton className="h-4 w-24 rounded-md" />
            </div>
            <Skeleton className="h-10 w-full rounded-md" />
          </div>
          <div className="space-y-3 pt-3 border-t border-border/50">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-12 rounded-md" />
              <Skeleton className="h-4 w-20 rounded-md" />
            </div>
            <Skeleton className="h-9 w-full rounded-lg" />
          </div>
        </Card>
      ))}
    </div>
  )
}

function MarketplacePage({ mode }: { mode: 'decks' | 'note-types' }) {
  const { t } = useTranslation('marketplace')
  const [view, setView] = useState<SortView>('recommended')
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [category, setCategory] = useState('')
  const [selectedDomain, setSelectedDomain] = useState('')
  const [selectedSubject, setSelectedSubject] = useState('')
  const [selectedFrameworkLevel, setSelectedFrameworkLevel] = useState('')
  const [selectedDifficulty, setSelectedDifficulty] = useState('')
  const [pricingFilter, setPricingFilter] = useState<'all' | 'free' | 'paid'>('all')
  const [isFilterExpanded, setIsFilterExpanded] = useState(false)
  const [tourOpen, setTourOpen] = useState(false)
  const searchInputRef = useRef<HTMLInputElement>(null)

  const {
    domains,
    subjectsByDomain,
    frameworksForSubject,
    difficulties,
  } = useTaxonomySchema(mode === 'decks' ? 'deck_marketplace_item' : 'note_type')

  const endpoint =
    mode === 'decks' ? '/api/shared/decks' : '/api/shared/note-types'
  const sort =
    view === 'recommended' ? 'top_rated' : view === 'newest' ? 'newest' : 'popular'

  // Debounce search query
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(queryText.trim()), 250)
    return () => window.clearTimeout(timer)
  }, [queryText])

  // Global keyboard shortcut: Press '/' to focus search input
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

  const marketQuery = useQuery({
    queryKey: [
      'marketplace',
      mode,
      debouncedQuery,
      category,
      selectedDomain,
      selectedSubject,
      selectedFrameworkLevel,
      selectedDifficulty,
      pricingFilter,
      sort,
    ],
    queryFn: () =>
      appApi.get<{ items: MarketplaceItem[] }>(endpoint, {
        q: debouncedQuery,
        category: category || undefined,
        domain: selectedDomain || undefined,
        subject: selectedSubject || undefined,
        framework_level: selectedFrameworkLevel || undefined,
        difficulty_band: selectedDifficulty || undefined,
        pricing_mode: pricingFilter !== 'all' ? pricingFilter : undefined,
        sort,
      }),
  })

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

  // Major categories selection based on mode (clean high-level topics only)
  const allCategories = useMemo(() => {
    return mode === 'decks' ? DECK_MAJOR_CATEGORIES : NOTETYPE_MAJOR_CATEGORIES
  }, [mode])

  const activeFilterCount = useMemo(() => {
    let count = 0
    if (selectedDomain) count++
    if (selectedSubject) count++
    if (selectedFrameworkLevel) count++
    if (selectedDifficulty) count++
    if (pricingFilter !== 'all') count++
    return count
  }, [selectedDomain, selectedSubject, selectedFrameworkLevel, selectedDifficulty, pricingFilter])

  const isFiltered = Boolean(queryText || category || activeFilterCount > 0)
  const totalCount = marketQuery.data?.items.length ?? 0

  const handleResetFilters = () => {
    setQueryText('')
    setCategory('')
    setSelectedDomain('')
    setSelectedSubject('')
    setSelectedFrameworkLevel('')
    setSelectedDifficulty('')
    setPricingFilter('all')
  }

  const tourSteps = useMemo(
    () => getMarketTourSteps(mode, (marketQuery.data?.items.length ?? 0) > 0, t),
    [mode, marketQuery.data?.items.length, t],
  )

  // Curated section grouping when browsing all items without active filters
  const curatedSections = useMemo(() => {
    if (isFiltered || mode !== 'decks' || !marketQuery.data?.items) {
      return null
    }
    const items = marketQuery.data.items
    if (items.length < 5) {
      return null
    }

    const groups: Record<string, MarketplaceItem[]> = {}
    items.forEach((it) => {
      const cat = it.primary_category || 'Tổng hợp'
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(it)
    })

    const SECTION_THRESHOLD = 3
    const majorSections: { category: string; items: MarketplaceItem[] }[] = []
    const otherItems: MarketplaceItem[] = []

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
  }, [isFiltered, mode, marketQuery.data?.items])

  // Auto-launch marketplace spotlight tour for first-time visitors
  useEffect(() => {
    if (marketQuery.isSuccess) {
      const completed = localStorage.getItem(MARKET_STORAGE_KEY)
      if (!completed) {
        const timer = setTimeout(() => {
          setTourOpen(true)
        }, 500)
        return () => clearTimeout(timer)
      }
    }
  }, [marketQuery.isSuccess])

  return (
    <Page className="space-y-6 relative px-3 sm:px-6 lg:px-8 py-4 sm:py-6">
      <AmbientBackground intensity="subtle" />

      {/* Flama Header with Mode Switcher & Publish CTA */}
      <PageHeader
        title={
          mode === 'decks'
            ? t('header.title_decks', { defaultValue: 'Kho Bộ Thẻ Cộng Đồng' })
            : t('header.title_notetypes', { defaultValue: 'Chợ Cấu trúc thẻ' })
        }
        description={
          mode === 'decks'
            ? t('header.desc_decks', { defaultValue: 'Khám phá, chia sẻ và tải về các bộ flashcard tiếng Nhật chất lượng từ cộng đồng.' })
            : t('header.desc_notetypes', { defaultValue: 'Khám phá các cấu trúc thẻ Flashcard tối ưu cho học tập, hỗ trợ trường tùy biến và nhiều giao diện thẻ.' })
        }
        actions={
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-start sm:justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setTourOpen(true)}
              className="h-8 sm:h-9 px-2.5 sm:px-3 text-xs font-semibold rounded-xl shrink-0"
            >
              <HelpCircle className="size-3.5 mr-1.5 text-primary shrink-0" />
              <span className="hidden xs:inline">{t('header.tour_btn_prefix', { defaultValue: 'Tour ' })}</span>
              {t('header.tour_btn', { defaultValue: 'Hướng Dẫn' })}
            </Button>

            <div data-tour="market-mode-switcher" className="inline-flex rounded-xl border border-border/80 bg-muted/40 p-0.5 sm:p-1 shadow-2xs shrink-0">
              <Button
                variant={mode === 'decks' ? 'default' : 'ghost'}
                size="sm"
                asChild
                className="h-7 sm:h-8 px-2.5 sm:px-3 text-xs font-semibold rounded-lg transition-all"
              >
                <Link to="/marketplace/decks">
                  <BookOpen className="mr-1 sm:mr-1.5 size-3.5 shrink-0" />
                  {t('header.tab_decks', { defaultValue: 'Bộ Thẻ' })}
                </Link>
              </Button>
              <Button
                variant={mode === 'note-types' ? 'default' : 'ghost'}
                size="sm"
                asChild
                className="h-7 sm:h-8 px-2.5 sm:px-3 text-xs font-semibold rounded-lg transition-all"
              >
                <Link to="/marketplace/note-types">
                  <Layers className="mr-1 sm:mr-1.5 size-3.5 shrink-0" />
                  {t('header.tab_notetypes', { defaultValue: 'Cấu trúc thẻ' })}
                </Link>
              </Button>
            </div>

            <Button
              variant="outline"
              size="sm"
              asChild
              className="h-8 sm:h-9 px-2.5 sm:px-3 text-xs font-semibold rounded-lg shrink-0"
            >
              <Link to={mode === 'decks' ? '/installed-decks' : '/note-types'}>
                {mode === 'decks'
                  ? t('card.installed', { defaultValue: 'Bộ thẻ đã cài' })
                  : t('header.my_notetypes', { defaultValue: 'Cấu trúc thẻ của tôi' })}
              </Link>
            </Button>

            <Button
              variant="default"
              size="sm"
              asChild
              data-tour="market-publish-btn"
              className="h-8 sm:h-9 px-3 sm:px-3.5 text-xs font-bold rounded-lg shadow-xs shrink-0"
            >
              <Link
                to={
                  mode === 'decks'
                    ? '/marketplace/decks/publish'
                    : '/marketplace/note-types/publish'
                }
              >
                <Plus className="mr-1 sm:mr-1.5 size-3.5 shrink-0" />
                {mode === 'decks'
                  ? t('header.btn_publish_deck', { defaultValue: 'Đăng tải bộ thẻ' })
                  : t('header.btn_create_notetype', { defaultValue: 'Tạo Cấu trúc thẻ' })}
              </Link>
            </Button>
          </div>
        }
      />

      {/* Streamlined Search & Filter Bar */}
      <MarketplaceFilterBar
        mode={mode}
        queryText={queryText}
        setQueryText={setQueryText}
        searchInputRef={searchInputRef}
        isFetching={marketQuery.isFetching}
        isPending={marketQuery.isPending}
        isFilterExpanded={isFilterExpanded}
        setIsFilterExpanded={setIsFilterExpanded}
        activeFilterCount={activeFilterCount}
        view={view}
        setView={setView}
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
        pricingFilter={pricingFilter}
        setPricingFilter={setPricingFilter}
        domains={domains}
        availableSubjects={availableSubjects}
        availableFrameworkLevels={availableFrameworkLevels}
        difficulties={difficulties}
        category={category}
        setCategory={setCategory}
        allCategories={allCategories}
      />

      {/* Results Header / Summary */}
      {!marketQuery.isPending && marketQuery.data?.items.length ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
          <span className="font-medium">
            Hiển thị{' '}
            <strong className="text-foreground font-semibold tabular-nums">
              {totalCount}
            </strong>{' '}
            {mode === 'note-types' ? 'cấu trúc thẻ' : 'bộ thẻ'} {isFiltered ? 'phù hợp với bộ lọc' : ''}
          </span>
        </div>
      ) : null}

      {/* States */}
      {marketQuery.isPending ? <MarketplaceSkeletonGrid /> : null}
      {marketQuery.error ? (
        <div className="space-y-3 py-4">
          <PageError error={marketQuery.error} />
          <div className="flex justify-center">
            <Button
              variant="outline"
              size="sm"
              onClick={() => marketQuery.refetch()}
              className="rounded-lg text-xs font-semibold"
            >
              <RotateCcw className="mr-1.5 size-3.5" /> Thử tải lại
            </Button>
          </div>
        </div>
      ) : null}

      {marketQuery.data && !marketQuery.data.items.length ? (
        <div className="py-8">
          <EmptyState
            title={
              isFiltered
                ? t('search_filter.empty_search.title', { defaultValue: 'Không tìm thấy học liệu phù hợp' })
                : mode === 'note-types'
                  ? 'Chợ Cấu trúc thẻ hiện đang trống'
                  : 'Kho bộ thẻ cộng đồng hiện đang trống'
            }
            description={
              isFiltered
                ? t('search_filter.empty_search.desc', { defaultValue: 'Thử thay đổi từ khóa tìm kiếm, chọn chủ đề khác hoặc sắp xếp lại danh sách.' })
                : mode === 'note-types'
                  ? 'Hãy là người đầu tiên chia sẻ cấu trúc thẻ Flashcard cho cộng đồng Flama!'
                  : 'Hãy là người đầu tiên đóng góp và chia sẻ bộ thẻ tiếng Nhật cho cộng đồng Flama!'
            }
          />
          <div className="flex justify-center mt-4 gap-2">
            {isFiltered ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setQueryText('')
                  setCategory('')
                }}
                className="rounded-lg text-xs font-semibold"
              >
                <X className="mr-1.5 size-3.5" /> {t('search_filter.empty_search.btn_reset', { defaultValue: 'Xóa bộ lọc hiện tại' })}
              </Button>
            ) : (
              <Button
                size="sm"
                asChild
                className="rounded-lg text-xs font-bold shadow-xs"
              >
                <Link
                  to={
                    mode === 'decks'
                      ? '/marketplace/decks/publish'
                      : '/marketplace/note-types/publish'
                  }
                >
                  <Plus className="mr-1.5 size-3.5" />
                  {mode === 'decks'
                    ? t('header.btn_publish_deck', { defaultValue: 'Đăng tải bộ thẻ ngay' })
                    : t('header.btn_create_notetype', { defaultValue: 'Tạo Cấu trúc thẻ ngay' })}
                </Link>
              </Button>
            )}
          </div>
        </div>
      ) : null}

      {/* Item Card Grid / Section Blocks */}
      {marketQuery.data?.items.length ? (
        mode === 'decks' ? (
          curatedSections ? (
            <MarketplaceCuratedSection
              curatedSections={curatedSections}
              getCategoryBadgeStyle={getCategoryBadgeStyle}
              onSelectCategory={(cat) => setCategory(cat)}
            />
          ) : (
            <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {marketQuery.data.items.map((item, index) => (
                <DeckCard
                  key={item.id}
                  item={item}
                  variant="marketplace"
                  dataTour={index === 0 ? 'market-card-first' : undefined}
                  actionDataTour={index === 0 ? 'market-action-btn' : undefined}
                />
              ))}
            </div>
          )
        ) : (
          <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {marketQuery.data.items.map((item, index) => (
              <SharedNoteTypeCard
                key={item.id}
                item={item}
                index={index}
                getCategoryBadgeStyle={getCategoryBadgeStyle}
              />
            ))}
          </div>
        )
      ) : null}

      {/* Interactive Spotlight Tour for Marketplace */}
      <SpotlightTour
        steps={tourSteps}
        isOpen={tourOpen}
        onClose={() => {
          localStorage.setItem(MARKET_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
        onComplete={() => {
          localStorage.setItem(MARKET_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
      />
    </Page>
  )
}

export function SharedDecksPage() {
  return <MarketplacePage mode="decks" />
}

export function SharedNoteTypesPage() {
  return <MarketplacePage mode="note-types" />
}

export { SharedDeckDetailPage } from './SharedDeckDetailPage'
export { SharedNoteTypeDetailPage } from './SharedNoteTypeDetailPage'
export { PaymentResultPage } from './PaymentResultPage'
