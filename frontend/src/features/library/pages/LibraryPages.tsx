import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  HelpCircle,
  Layers,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Sparkles,
  X,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
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

type NoteTypeItem = {
  id: string
  name: string
  description: string | null
  field_defs?: unknown[]
  templates?: unknown[]
  updated_at: string | null
}

function formatUpdatedAt(value: string | null) {
  if (!value) return 'Chưa có thời gian cập nhật'
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export function NoteTypesPage() {
  const query = useQuery({
    queryKey: ['note-types'],
    queryFn: () => appApi.get<{ items: NoteTypeItem[] }>('/note-types'),
  })

  if (query.isPending) return <PageLoading label="Đang tải loại thẻ…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="relative min-h-screen px-2.5 sm:px-6 py-4 sm:py-6">
      <AmbientBackground />
      <PageHeader
        title="Loại thẻ"
        description="Quản lý field, template và quy cách hiển thị flashcard."
      />
      {!query.data.items.length ? (
        <EmptyState
          title="Chưa có loại thẻ"
          description="Tạo note type đầu tiên hoặc cài một mẫu từ marketplace."
        />
      ) : (
        <div className="grid gap-3 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {query.data.items.map((item) => (
            <Card
              key={item.id}
              className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-md rounded-2xl"
            >
              <div className="flex flex-col flex-1 space-y-2">
                <div className="flex items-center justify-between gap-1.5 mb-1">
                  <Badge variant="secondary" className="px-2 py-0.5 text-xs font-semibold rounded-md">
                    <Layers className="mr-1 size-3 text-primary" />
                    {item.templates?.length || 0} template
                  </Badge>

                  <Badge variant="outline" className="px-2 py-0.5 text-xs font-semibold rounded-md">
                    {item.field_defs?.length || 0} field
                  </Badge>
                </div>

                <h3 className="text-sm sm:text-base font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug">
                  {item.name}
                </h3>

                <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
                  {item.description || 'Chưa có mô tả cho loại thẻ này.'}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-border/60 text-xs text-muted-foreground">
                Cập nhật {formatUpdatedAt(item.updated_at)}
              </div>
            </Card>
          ))}
        </div>
      )}
    </Page>
  )
}

export function InstalledDecksPage() {
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
        title: '📚 1. Quản Lý Bộ Thẻ Đã Cài',
        content:
          'Nơi quản lý toàn bộ các bộ thẻ (Decks) bạn đã cài đặt từ Marketplace hoặc do chính bạn sở hữu để bắt đầu ôn luyện.',
        placement: 'bottom',
      },
      {
        target: '[data-tour="marketplace-explore-btn"]',
        title: '🛍️ 2. Khám Phá Kho Bộ Thẻ Marketplace',
        content:
          'Bấm vào đây để duyệt qua hàng trăm bộ thẻ từ vựng, ngữ pháp, Kanji... chất lượng cao do cộng đồng Flama chia sẻ.',
        placement: 'bottom',
      },
      {
        target: '[data-tour="installed-search-box"]',
        title: '🔍 3. Tìm Kiếm & Lọc Bộ Thẻ',
        content:
          'Tìm kiếm nhanh theo tên deck, lọc theo danh mục, trình độ JLPT hoặc lọc theo trạng thái đang học/có bản cập nhật.',
        placement: 'bottom',
      },
    ]

    if (items.length > 0) {
      steps.push(
        {
          target: '[data-tour="deck-card-first"]',
          title: '🎴 4. Thông Tin Bộ Thẻ (Deck Card)',
          content:
            'Hiển thị tiêu đề bộ thẻ, tên tác giả đóng góp, trạng thái học tập (Đang sử dụng / Đã cài) và mô tả vắn tắt.',
          placement: 'top',
        },
        {
          target: '[data-tour="deck-action-btn"]',
          title: '🚀 5. Nút "Học Ngay" (Spaced Repetition)',
          content:
            'Bấm nút này để bắt đầu phiên ôn tập với thuật toán Lặp lại ngắt quãng thông minh (Anki SM-2 / FSRS) giúp ghi nhớ sâu và lâu bền.',
          placement: 'top',
        },
      )
    } else {
      steps.push({
        target: '[data-tour="installed-decks-grid"]',
        title: '📦 4. Khu Vực Bộ Thẻ Cá Nhân',
        content:
          'Sau khi cài đặt bộ thẻ từ Marketplace, các bộ thẻ sẽ xuất hiện tại đây để bạn bắt đầu học và theo dõi tiến độ.',
        placement: 'top',
      })
    }

    return steps
  }, [items.length])

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

  if (query.isPending) return <PageLoading label="Đang tải deck đã cài…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="relative min-h-screen px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />
      <div data-tour="decks-header">
        <PageHeader
          title="Deck đã cài"
          description="Quản lý và tiếp tục học các bộ deck bạn đã cài từ Marketplace hoặc sở hữu."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setTourOpen(true)}
                className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl"
              >
                <HelpCircle className="size-3.5 mr-1.5 text-primary" />
                Tour Hướng Dẫn
              </Button>
              <ContextHelpButton
                guidePath="/guide/marketplace/installed-overlay"
                guideTitle="Cơ chế Clone Overlay & Cập nhật Deck"
                label="Trợ giúp"
              />
              <Button
                size="sm"
                data-tour="marketplace-explore-btn"
                className="h-8 sm:h-9 px-3.5 rounded-xl font-bold text-xs sm:text-sm shadow-xs"
                asChild
              >
                <Link to="/marketplace/decks" className="inline-flex items-center gap-1.5">
                  <Sparkles className="size-3.5" />
                  <span>Khám phá Marketplace</span>
                  <ArrowRight className="size-3.5" />
                </Link>
              </Button>
            </div>
          }
        />
      </div>

      {/* Unified Search & Filter Control Center matching Marketplace */}
      <Card data-tour="installed-search-box" className="border-border/80 bg-card shadow-xs rounded-2xl overflow-hidden">
        <CardContent className="p-3 sm:p-4 space-y-3">
          <div className="flex flex-col sm:flex-row gap-2.5 items-stretch sm:items-center justify-between">
            {/* Search Box with Hotkey indicator */}
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
              <Input
                ref={searchInputRef}
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                placeholder="Tìm kiếm deck đã cài theo tên, tác giả... (Nhấn '/' để tìm nhanh)"
                className="pl-9 pr-12 h-10 text-xs sm:text-sm bg-muted/40 border-border/70 rounded-xl focus-visible:bg-background transition-all"
              />
              <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center gap-1">
                {queryText ? (
                  <button
                    type="button"
                    onClick={() => setQueryText('')}
                    className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
                    aria-label="Xóa từ khóa tìm kiếm"
                  >
                    <X className="size-4" />
                  </button>
                ) : (
                  <kbd className="hidden sm:inline-flex h-5 items-center justify-center rounded-md border border-border/80 bg-muted px-1.5 text-[10px] font-medium text-muted-foreground select-none">
                    /
                  </kbd>
                )}
              </div>
            </div>

            {/* Filter Toggle & Status Tabs */}
            <div className="flex items-center gap-2 shrink-0 flex-wrap sm:flex-nowrap">
              <Button
                variant={isFilterExpanded || activeFilterCount > 0 ? 'default' : 'outline'}
                size="sm"
                onClick={() => setIsFilterExpanded((prev) => !prev)}
                className="h-10 px-3 text-xs font-semibold rounded-xl gap-1.5 shrink-0"
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
                value={statusFilter}
                onValueChange={(val) => setStatusFilter(val as any)}
                className="w-full sm:w-auto"
              >
                <TabsList className="grid grid-cols-3 sm:flex sm:flex-wrap h-10 p-1 rounded-xl bg-muted/60">
                  <TabsTrigger
                    value="all"
                    className="text-xs font-semibold px-2 sm:px-3 py-1.5 rounded-lg"
                  >
                    Tất cả
                  </TabsTrigger>
                  <TabsTrigger
                    value="using_now"
                    className="text-xs font-semibold px-2 sm:px-3 py-1.5 rounded-lg"
                  >
                    Đang dùng
                  </TabsTrigger>
                  <TabsTrigger
                    value="update_available"
                    className="text-xs font-semibold px-2 sm:px-3 py-1.5 rounded-lg text-primary"
                  >
                    Có bản mới
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              {isFiltered ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-10 px-2.5 text-xs text-muted-foreground hover:text-foreground rounded-xl shrink-0"
                  onClick={handleResetFilters}
                  title="Xóa toàn bộ bộ lọc"
                  aria-label="Xóa toàn bộ bộ lọc"
                >
                  <X className="size-4" />
                </Button>
              ) : null}
            </div>
          </div>

          {/* Expandable Advanced Taxonomy Filters */}
          {isFilterExpanded && (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2.5 p-3 rounded-xl bg-muted/30 border border-border/60 transition-all">
              {/* Status Select */}
              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-muted-foreground">Trạng thái deck</label>
                <Select
                  value={statusFilter}
                  onValueChange={(val) => setStatusFilter(val as any)}
                >
                  <SelectTrigger className="h-8.5 text-xs bg-background rounded-lg">
                    <SelectValue placeholder="Tất cả trạng thái" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tất cả trạng thái</SelectItem>
                    <SelectItem value="using_now">Đang sử dụng</SelectItem>
                    <SelectItem value="installed">Đã cài đặt</SelectItem>
                    <SelectItem value="owned">Deck của bạn</SelectItem>
                    <SelectItem value="update_available">Có bản cập nhật</SelectItem>
                    <SelectItem value="conflict">Có xung đột</SelectItem>
                  </SelectContent>
                </Select>
              </div>

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
                  <SelectTrigger className="h-8.5 text-xs bg-background rounded-lg">
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
                  <SelectTrigger className="h-8.5 text-xs bg-background rounded-lg">
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
                  <SelectTrigger className="h-8.5 text-xs bg-background rounded-lg">
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
                  <SelectTrigger className="h-8.5 text-xs bg-background rounded-lg">
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
            </div>
          )}

          {/* Active Filter Badges */}
          {isFiltered && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[11px] font-medium text-muted-foreground mr-1">Bộ lọc đang áp dụng:</span>
              {queryText && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2 rounded-md">
                  <span>Từ khóa: "{queryText}"</span>
                  <button type="button" onClick={() => setQueryText('')} className="hover:text-destructive cursor-pointer">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {category && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2 rounded-md">
                  <span>Chủ đề: {category}</span>
                  <button type="button" onClick={() => setCategory('')} className="hover:text-destructive cursor-pointer">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {statusFilter !== 'all' && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2 rounded-md">
                  <span>
                    Trạng thái:{' '}
                    {statusFilter === 'using_now'
                      ? 'Đang sử dụng'
                      : statusFilter === 'installed'
                        ? 'Đã cài đặt'
                        : statusFilter === 'owned'
                          ? 'Deck của bạn'
                          : statusFilter === 'update_available'
                            ? 'Có bản cập nhật'
                            : 'Có xung đột'}
                  </span>
                  <button type="button" onClick={() => setStatusFilter('all')} className="hover:text-destructive cursor-pointer">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {selectedDomain && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2 rounded-md">
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
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2 rounded-md">
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
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2 rounded-md">
                  <span>Trình độ: {availableFrameworkLevels.find((l) => l.id === selectedFrameworkLevel)?.label || selectedFrameworkLevel}</span>
                  <button type="button" onClick={() => setSelectedFrameworkLevel('')} className="hover:text-destructive cursor-pointer">
                    <X className="size-3" />
                  </button>
                </Badge>
              )}
              {selectedDifficulty && (
                <Badge variant="secondary" className="gap-1 text-xs py-0.5 px-2 rounded-md">
                  <span>Độ khó: {difficulties.find((d) => d.id === selectedDifficulty)?.label || selectedDifficulty}</span>
                  <button type="button" onClick={() => setSelectedDifficulty('')} className="hover:text-destructive cursor-pointer">
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

          {/* Quick Category Pills with Horizontal Scroll */}
          <div className="relative pt-2 border-t border-border/40">
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
              {DECK_MAJOR_CATEGORIES.map((cat) => {
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
            <div className="pointer-events-none absolute right-0 top-2 bottom-0 w-8 bg-gradient-to-l from-card to-transparent" />
          </div>
        </CardContent>
      </Card>

      {/* Results Header / Summary */}
      {items.length > 0 ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
          <span className="font-medium">
            Hiển thị{' '}
            <strong className="text-foreground font-semibold tabular-nums">
              {filteredItems.length}
            </strong>{' '}
            / {items.length} bộ deck {isFiltered ? 'phù hợp với bộ lọc' : 'đã cài'}
          </span>
        </div>
      ) : null}

      {!items.length ? (
        <div data-tour="installed-decks-grid">
          <EmptyState
            title="Chưa cài deck nào"
            description="Khám phá marketplace và cài một deck để bắt đầu học."
          />
        </div>
      ) : !filteredItems.length ? (
        <div className="py-8">
          <EmptyState
            title="Không tìm thấy bộ deck phù hợp"
            description="Thử thay đổi từ khóa tìm kiếm hoặc xóa các tiêu chí lọc hiện tại."
          />
          <div className="flex justify-center mt-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleResetFilters}
              className="rounded-xl text-xs font-semibold"
            >
              <RotateCcw className="mr-1.5 size-3.5" /> Xóa bộ lọc hiện tại
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
                    ({section.items.length} bộ deck)
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCategory(section.category)}
                  className="h-8 text-xs font-semibold text-primary hover:text-primary hover:bg-primary/10 gap-1 rounded-xl cursor-pointer"
                >
                  <span>Xem tất cả {section.category}</span>
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
                  <h3 className="text-sm font-bold text-foreground">Bộ thẻ & Chủ đề khác</h3>
                  <span className="text-xs font-semibold text-muted-foreground">
                    ({curatedSections.otherItems.length} bộ deck)
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


