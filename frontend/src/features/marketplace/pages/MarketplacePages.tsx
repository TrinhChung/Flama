import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  BookOpen,
  Download,
  Eye,
  Flame,
  HelpCircle,
  Layers,
  Loader2,
  Plus,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Sparkles,
  Star,
  X,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { DeckCard } from '../components/DeckCard'

import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
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
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError } from '@/shared/components/PageState'
import { SpotlightTour, type TourStep } from '@/shared/components/SpotlightTour'
import { useTaxonomySchema } from '../hooks/useTaxonomySchema'

const MARKET_STORAGE_KEY = 'flama_marketplace_spotlight_tour_v1'

const getMarketTourSteps = (mode: 'decks' | 'note-types', hasItems: boolean): TourStep[] => {
  const steps: TourStep[] = [
    {
      target: '[data-tour="market-mode-switcher"]',
      title: '🔄 1. Chuyển Đổi Kho Học Liệu',
      content:
        'Chuyển đổi linh hoạt giữa "Kho Bộ Thẻ" (các bộ flashcard hoàn chỉnh) và "Kho Loại Thẻ" (các mẫu giao diện NoteType).',
      placement: 'bottom',
    },
    {
      target: '[data-tour="market-publish-btn"]',
      title: mode === 'decks' ? '🚀 2. Đăng Tải Bộ Thẻ Của Bạn' : '🚀 2. Tạo Mẫu Thẻ Mới',
      content:
        mode === 'decks'
          ? 'Chia sẻ bộ thẻ bạn đã biên soạn lên Marketplace để cộng đồng cùng học hoặc nhận đóng góp.'
          : 'Tự tạo loại thẻ mới hoặc xuất bản NoteType của bạn lên Marketplace.',
      placement: 'bottom',
    },
    {
      target: '[data-tour="market-search-box"]',
      title: '🔍 3. Tìm Kiếm Thông Minh',
      content:
        'Tìm kiếm nhanh theo tên bộ thẻ, trình độ JLPT (N5 - N1), từ vựng theo chủ đề, hoặc tên tác giả.',
      placement: 'bottom',
    },
    {
      target: '[data-tour="market-categories"]',
      title: '🏷️ 4. Bộ Lọc Theo Chủ Đề',
      content:
        'Lọc nhanh theo các danh mục trọng tâm: JLPT N5, N4, N3, N2, N1, Từ vựng, Kanji, Giao tiếp, IT / Công nghệ...',
      placement: 'bottom',
    },
    {
      target: '[data-tour="market-sort-tabs"]',
      title: '⚡ 5. Sắp Xếp Theo Nhu Cầu',
      content:
        'Xem các bộ thẻ được "Đề xuất" bởi thuật toán, "Phổ biến" nhiều lượt tải nhất, hoặc "Mới nhất" vừa đăng tải.',
      placement: 'bottom',
    },
  ]

  if (hasItems) {
    steps.push(
      {
        target: '[data-tour="market-card-first"]',
        title: '🎴 6. Thông Tin Thẻ Học Liệu',
        content:
          'Mỗi thẻ hiển thị chủ đề, giá bán (Miễn phí/Trả phí), tên tác giả, điểm đánh giá sao ⭐ và số lượng thẻ.',
        placement: 'top',
      },
      {
        target: '[data-tour="market-action-btn"]',
        title: '📥 7. Xem Chi Tiết & Cài Đặt',
        content:
          'Bấm để xem trước danh sách thẻ, xem giao diện thực tế và cài đặt (Overlay Sync) trực tiếp vào tài khoản của bạn để học ngay!',
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
    () => getMarketTourSteps(mode, (marketQuery.data?.items.length ?? 0) > 0),
    [mode, marketQuery.data?.items.length],
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
        title={mode === 'decks' ? 'Kho Bộ Thẻ Cộng Đồng' : 'Kho Mẫu Thẻ (Note Types)'}
        description={
          mode === 'decks'
            ? 'Khám phá, chia sẻ và tải về các bộ flashcard tiếng Nhật chất lượng từ cộng đồng.'
            : 'Các mẫu hiển thị Flashcard chuẩn đẹp, tối ưu hóa giao diện học Kanji, Từ vựng và Ngữ pháp.'
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
              <span className="hidden xs:inline">Tour </span>Hướng Dẫn
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
                  Bộ Thẻ
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
                  Loại Thẻ
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
                {mode === 'decks' ? 'Deck đã cài' : 'Loại thẻ của tôi'}
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
                {mode === 'decks' ? 'Đăng tải bộ thẻ' : 'Tạo loại thẻ'}
              </Link>
            </Button>

          </div>
        }
      />

      {/* Streamlined Search & Filter Bar */}
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
                placeholder="Tìm bộ thẻ, từ vựng, JLPT, tác giả…"
                value={queryText}
                onChange={(event) => setQueryText(event.currentTarget.value)}
              />
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />

              {/* Right Indicator: Loader or Clear Button or Kbd hint */}
              <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-1">
                {marketQuery.isFetching && !marketQuery.isPending ? (
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
                    aria-label="Xóa từ khóa tìm kiếm"
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
                <span>Bộ lọc</span>
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
                    <span className="truncate">Đề xuất</span>
                  </TabsTrigger>
                  <TabsTrigger
                    value="popular"
                    className="text-xs font-semibold px-2 sm:px-3.5 py-1.5 rounded-md gap-1"
                  >
                    <Flame className="size-3 text-primary shrink-0" />
                    <span className="truncate">Phổ biến</span>
                  </TabsTrigger>
                  <TabsTrigger
                    value="newest"
                    className="text-xs font-semibold px-2 sm:px-3.5 py-1.5 rounded-md"
                  >
                    <span className="truncate">Mới nhất</span>
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              {isFiltered ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-10 px-2.5 text-xs text-muted-foreground hover:text-foreground rounded-lg shrink-0"
                  onClick={handleResetFilters}
                  title="Xóa toàn bộ bộ lọc"
                  aria-label="Xóa toàn bộ bộ lọc"
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
                <label className="text-[11px] font-semibold text-muted-foreground">Lĩnh vực (Domain)</label>
                <Select
                  value={selectedDomain || 'all'}
                  onValueChange={(val) => {
                    setSelectedDomain(val === 'all' ? '' : val)
                    setSelectedSubject('')
                    setSelectedFrameworkLevel('')
                  }}
                >
                  <SelectTrigger className="h-8.5 text-xs bg-background">
                    <SelectValue placeholder="Tất cả lĩnh vực" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tất cả lĩnh vực</SelectItem>
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
                <label className="text-[11px] font-semibold text-muted-foreground">Môn học (Subject)</label>
                <Select
                  value={selectedSubject || 'all'}
                  onValueChange={(val) => {
                    setSelectedSubject(val === 'all' ? '' : val)
                    setSelectedFrameworkLevel('')
                  }}
                >
                  <SelectTrigger className="h-8.5 text-xs bg-background">
                    <SelectValue placeholder="Tất cả môn học" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tất cả môn học</SelectItem>
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
                <label className="text-[11px] font-semibold text-muted-foreground">Trình độ / Khung</label>
                <Select
                  value={selectedFrameworkLevel || 'all'}
                  onValueChange={(val) => setSelectedFrameworkLevel(val === 'all' ? '' : val)}
                >
                  <SelectTrigger className="h-8.5 text-xs bg-background">
                    <SelectValue placeholder="Tất cả trình độ" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tất cả trình độ</SelectItem>
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
                <label className="text-[11px] font-semibold text-muted-foreground">Độ khó</label>
                <Select
                  value={selectedDifficulty || 'all'}
                  onValueChange={(val) => setSelectedDifficulty(val === 'all' ? '' : val)}
                >
                  <SelectTrigger className="h-8.5 text-xs bg-background">
                    <SelectValue placeholder="Tất cả độ khó" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tất cả độ khó</SelectItem>
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
                <label className="text-[11px] font-semibold text-muted-foreground">Giá bán</label>
                <Select
                  value={pricingFilter}
                  onValueChange={(val) => setPricingFilter(val as 'all' | 'free' | 'paid')}
                >
                  <SelectTrigger className="h-8.5 text-xs bg-background">
                    <SelectValue placeholder="Tất cả giá" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tất cả</SelectItem>
                    <SelectItem value="free">Miễn phí</SelectItem>
                    <SelectItem value="paid">Trả phí</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {/* Active Filter Badges */}
          {isFiltered && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[11px] font-medium text-muted-foreground mr-1">Bộ lọc đang áp dụng:</span>
              {queryText && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                  <span>Từ khóa: "{queryText}"</span>
                  <button type="button" onClick={() => setQueryText('')} className="hover:text-destructive cursor-pointer">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {category && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                  <span>Chủ đề: {category}</span>
                  <button type="button" onClick={() => setCategory('')} className="hover:text-destructive cursor-pointer">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {selectedDomain && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                  <span>Lĩnh vực: {domains.find((d) => d.id === selectedDomain)?.label || selectedDomain}</span>
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
                  <span>Môn: {availableSubjects.find((s) => s.id === selectedSubject)?.label || selectedSubject}</span>
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
                  <span>Trình độ: {availableFrameworkLevels.find((l) => l.id === selectedFrameworkLevel)?.label || selectedFrameworkLevel}</span>
                  <button type="button" onClick={() => setSelectedFrameworkLevel('')} className="hover:text-destructive cursor-pointer">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {selectedDifficulty && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                  <span>Độ khó: {difficulties.find((d) => d.id === selectedDifficulty)?.label || selectedDifficulty}</span>
                  <button type="button" onClick={() => setSelectedDifficulty('')} className="hover:text-destructive cursor-pointer">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {pricingFilter !== 'all' && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2">
                  <span>Giá: {pricingFilter === 'free' ? 'Miễn phí' : 'Trả phí'}</span>
                  <button type="button" onClick={() => setPricingFilter('all')} className="hover:text-destructive cursor-pointer">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResetFilters}
                className="h-6 px-2 text-[11px] text-muted-foreground hover:text-destructive font-medium cursor-pointer"
              >
                Xóa tất cả
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
                Tất cả
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

      {/* Results Header / Summary */}
      {!marketQuery.isPending && marketQuery.data?.items.length ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
          <span className="font-medium">
            Hiển thị{' '}
            <strong className="text-foreground font-semibold tabular-nums">
              {totalCount}
            </strong>{' '}
            học liệu {isFiltered ? 'phù hợp với bộ lọc' : ''}
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
                ? 'Không tìm thấy học liệu phù hợp'
                : 'Kho học liệu cộng đồng hiện đang trống'
            }
            description={
              isFiltered
                ? 'Thử thay đổi từ khóa tìm kiếm, chọn chủ đề khác hoặc sắp xếp lại danh sách.'
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
                <X className="mr-1.5 size-3.5" /> Xóa bộ lọc hiện tại
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
                  {mode === 'decks' ? 'Đăng tải bộ thẻ ngay' : 'Tạo loại thẻ ngay'}
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
                        ({section.items.length} bộ thẻ)
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCategory(section.category)}
                      className="h-8 text-xs font-semibold text-primary hover:text-primary hover:bg-primary/10 gap-1 rounded-lg cursor-pointer"
                    >
                      <span>Xem tất cả {section.category}</span>
                      <ArrowRight className="size-3.5" />
                    </Button>
                  </div>
                  <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {section.items.slice(0, 4).map((item, index) => (
                      <DeckCard
                        key={item.id}
                        item={item}
                        variant="marketplace"
                        dataTour={index === 0 ? 'market-card-first' : undefined}
                        actionDataTour={index === 0 ? 'market-action-btn' : undefined}
                      />
                    ))}
                  </div>
                </div>
              ))}

              {curatedSections.otherItems.length > 0 && (
                <div className="space-y-3.5">
                  <div className="flex items-center justify-between border-b border-border/50 pb-2">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-foreground">Học liệu & Chủ đề khác</h3>
                      <span className="text-xs font-semibold text-muted-foreground">
                        ({curatedSections.otherItems.length} bộ thẻ)
                      </span>
                    </div>
                  </div>
                  <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {curatedSections.otherItems.map((item) => (
                      <DeckCard
                        key={item.id}
                        item={item}
                        variant="marketplace"
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
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
            {marketQuery.data.items.map((item, index) => {
              const itemTitle = item.name || item.title || 'Mẫu thẻ không tên'
              const detailUrl = `/marketplace/note-types/${item.id}`
              const authorName =
                item.author?.account_name || item.author?.username || 'Cộng đồng Flama'
              const authorInitial = authorName.charAt(0).toUpperCase()

              return (
                <Card
                  key={item.id}
                  data-tour={index === 0 ? 'market-card-first' : undefined}
                  className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/40 hover:shadow-md rounded-2xl"
                >
                  <div className="flex flex-col flex-1 space-y-3">
                    <div className="flex items-center justify-between gap-1.5">
                      <Badge
                        variant="outline"
                        className={`px-2.5 py-0.5 text-xs font-semibold rounded-md truncate max-w-[65%] border ${getCategoryBadgeStyle(
                          item.primary_category,
                        )}`}
                      >
                        {item.primary_category || 'Chung'}
                      </Badge>
                      <span
                        className={`inline-flex items-center gap-1 rounded-md px-2.5 py-0.5 text-xs font-semibold ${
                          item.pricing_mode === 'free'
                            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20'
                            : 'bg-primary/10 text-primary border border-primary/20'
                        }`}
                      >
                        {item.pricing_mode === 'free' ? (
                          <Sparkles className="size-3" />
                        ) : null}
                        {item.price_display}
                      </span>
                    </div>

                    <h3 className="text-sm sm:text-base font-bold tracking-tight text-foreground line-clamp-2 leading-snug">
                      <Link
                        to={detailUrl}
                        className="hover:text-primary hover:underline transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
                      >
                        {itemTitle}
                      </Link>
                    </h3>

                    {item.author?.username ? (
                      <Link
                        to={`/profile/${item.author.username}`}
                        className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-primary transition-colors group/author"
                      >
                        <div className="flex size-5 sm:size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] ring-1 ring-primary/20 group-hover/author:ring-primary">
                          {authorInitial}
                        </div>
                        <span className="font-medium text-foreground/80 group-hover/author:text-primary truncate">
                          {authorName}
                        </span>
                      </Link>
                    ) : (
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <div className="flex size-5 sm:size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] ring-1 ring-primary/20">
                          {authorInitial}
                        </div>
                        <span className="font-medium text-foreground/80 truncate">
                          {authorName}
                        </span>
                      </div>
                    )}

                    <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
                      {item.description || 'Chưa có mô tả chi tiết cho loại thẻ này.'}
                    </p>
                  </div>

                  <div className="mt-4 pt-3.5 border-t border-border/60 space-y-3">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1 font-semibold text-foreground">
                        <Star className="size-3.5 fill-amber-400 text-amber-500" />
                        <span className="tabular-nums">
                          {(item.rating_avg || 0).toFixed(1)}
                          {item.rating_count ? (
                            <span className="text-[11px] font-normal text-muted-foreground ml-0.5">
                              ({item.rating_count})
                            </span>
                          ) : null}
                        </span>
                      </span>

                      <span className="inline-flex items-center gap-1">
                        <Download className="size-3.5 text-primary" />
                        <span className="tabular-nums">
                          {(item.install_count || 0).toLocaleString('vi-VN')} lượt
                        </span>
                      </span>
                    </div>

                    <Button
                      variant="outline"
                      size="sm"
                      asChild
                      data-tour={index === 0 ? 'market-action-btn' : undefined}
                      className="w-full h-9 text-xs font-semibold rounded-xl hover:bg-primary hover:text-primary-foreground hover:border-primary transition-all"
                    >
                      <Link to={detailUrl}>
                        <Eye className="mr-1.5 size-3.5" />
                        Xem chi tiết
                        <ArrowRight className="ml-1 size-3.5 transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    </Button>
                  </div>
                </Card>
              )
            })}
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
