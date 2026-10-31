import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { TourStep } from '@/shared/components/SpotlightTour'
import { useTaxonomySchema } from '@/features/marketplace'
import { getInstalledDecks } from '@/features/library'
import type { DeckCardItem } from '@/entities/marketplace-deck'

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

export function useInstalledDecks() {
  const { t } = useTranslation('library')
  const [tourOpen, setTourOpen] = useState(false)
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [category, setCategory] = useState('')
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'using_now' | 'installed' | 'owned'
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
      getInstalledDecks(),
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
          defaultValue: 'Tìm kiếm nhanh theo tên deck, lọc theo danh mục, trình độ JLPT hoặc trạng thái đang học.',
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

  return { t, tourOpen, setTourOpen, queryText, setQueryText, category, setCategory, statusFilter, setStatusFilter, selectedDomain, setSelectedDomain, selectedSubject, setSelectedSubject, selectedFrameworkLevel, setSelectedFrameworkLevel, selectedDifficulty, setSelectedDifficulty, isFilterExpanded, setIsFilterExpanded, searchInputRef, domains, difficulties, query, items, availableSubjects, availableFrameworkLevels, activeFilterCount, isFiltered, handleResetFilters, filteredItems, curatedSections, tourSteps, DECK_MAJOR_CATEGORIES, DECKS_STORAGE_KEY }
}
