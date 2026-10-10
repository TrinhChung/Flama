import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBolt,
  faBook,
  faBookBookmark,
  faChevronDown,
  faChevronRight,
  faClock,
  faGraduationCap,
  faListUl,
  faMagnifyingGlass,
  faRightLeft,
  faRobot,
  faStore,
  faTableColumns,
  faTriangleExclamation,
  faVolumeHigh,
  faWallet,
  faXmark,
} from '@fortawesome/free-solid-svg-icons'
import type { IconDefinition } from '@fortawesome/free-solid-svg-icons'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { GUIDE_CATEGORIES, searchArticles } from '../guideData'

const CATEGORY_FA_ICONS: Record<string, IconDefinition> = {
  Zap: faBolt,
  LayoutDashboard: faTableColumns,
  GraduationCap: faGraduationCap,
  Search: faMagnifyingGlass,
  NotebookTabs: faBookBookmark,
  Store: faStore,
  ArrowRightLeft: faRightLeft,
  Bot: faRobot,
  AudioLines: faVolumeHigh,
  Wallet: faWallet,
  AlertTriangle: faTriangleExclamation,
}

type CategoryFilter = 'all' | 'foundation' | 'features' | 'troubleshooting'

interface GuideHomePageProps {
  searchQuery?: string
  onSearchChange?: (q: string) => void
}

export function GuideHomePage({ searchQuery: externalQuery, onSearchChange: externalOnChange }: GuideHomePageProps) {
  const { t } = useTranslation('guide')
  const [localQuery, setLocalQuery] = useState('')
  const [activeFilter, setActiveFilter] = useState<CategoryFilter>('all')
  const [collapsedChapters, setCollapsedChapters] = useState<Record<string, boolean>>({})

  const searchQuery = externalQuery !== undefined ? externalQuery : localQuery
  const onSearchChange = externalOnChange || setLocalQuery

  const searchResults = searchQuery ? searchArticles(searchQuery) : []

  // Filter categories based on active tab
  const displayedCategories = useMemo(() => {
    if (activeFilter === 'foundation') {
      return GUIDE_CATEGORIES.filter((c) => ['getting-started', 'dashboard'].includes(c.slug))
    }
    if (activeFilter === 'features') {
      return GUIDE_CATEGORIES.filter(
        (c) =>
          !['getting-started', 'dashboard', 'troubleshooting'].includes(c.slug),
      )
    }
    if (activeFilter === 'troubleshooting') {
      return GUIDE_CATEGORIES.filter((c) => c.slug === 'troubleshooting')
    }
    return GUIDE_CATEGORIES
  }, [activeFilter])

  const totalArticleCount = useMemo(() => {
    return GUIDE_CATEGORIES.reduce((acc, cat) => acc + cat.articles.length, 0)
  }, [])

  const toggleChapter = (slug: string) => {
    setCollapsedChapters((prev) => ({
      ...prev,
      [slug]: !prev[slug],
    }))
  }

  const toggleAllChapters = (collapse: boolean) => {
    const next: Record<string, boolean> = {}
    GUIDE_CATEGORIES.forEach((cat) => {
      next[cat.slug] = collapse
    })
    setCollapsedChapters(next)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Streamlined Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-border/80">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <FontAwesomeIcon icon={faListUl} className="text-primary text-lg" />
            <span>Mục Lục Hướng Dẫn &amp; Cẩm Nang</span>
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Tổng hợp {GUIDE_CATEGORIES.length} chương mục &bull; {totalArticleCount} bài viết hướng dẫn và quy trình giải quyết sự cố.
          </p>
        </div>

        {/* Compact Search Bar */}
        <div className="relative w-full sm:w-72 shrink-0">
          <FontAwesomeIcon
            icon={faMagnifyingGlass}
            className="text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 text-xs"
          />
          <Input
            type="search"
            placeholder={t('header.search_placeholder')}
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-8 pr-7 h-9 text-xs rounded-xl bg-card border-border/80 focus-visible:ring-primary shadow-2xs"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5"
            >
              <FontAwesomeIcon icon={faXmark} className="text-xs" />
            </button>
          )}
        </div>
      </div>

      {/* Filter Tabs & Quick Jump Toolbar */}
      {!searchQuery && (
        <div className="flex flex-wrap items-center justify-between gap-2.5 pt-0.5">
          <div className="flex flex-wrap items-center gap-1.5 bg-muted/30 p-1 rounded-xl border border-border/70 text-xs">
            <button
              type="button"
              onClick={() => setActiveFilter('all')}
              className={`px-3 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
                activeFilter === 'all'
                  ? 'bg-card text-foreground shadow-2xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {t('header.all_categories')} ({totalArticleCount})
            </button>
            <button
              type="button"
              onClick={() => setActiveFilter('foundation')}
              className={`px-3 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
                activeFilter === 'foundation'
                  ? 'bg-card text-foreground shadow-2xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Khởi đầu &amp; Nền tảng (6)
            </button>
            <button
              type="button"
              onClick={() => setActiveFilter('features')}
              className={`px-3 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
                activeFilter === 'features'
                  ? 'bg-card text-foreground shadow-2xs'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Học tập &amp; Tính năng (7)
            </button>
            <button
              type="button"
              onClick={() => setActiveFilter('troubleshooting')}
              className={`px-3 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
                activeFilter === 'troubleshooting'
                  ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 shadow-2xs font-bold'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              Sửa lỗi (4)
            </button>
          </div>

          {/* Quick Collapse / Expand Buttons */}
          <div className="flex items-center gap-1.5 text-[11px]">
            <button
              type="button"
              onClick={() => toggleAllChapters(false)}
              className="text-muted-foreground hover:text-primary transition-colors font-medium px-2 py-1"
            >
              Mở rộng tất cả
            </button>
            <span className="text-border">&bull;</span>
            <button
              type="button"
              onClick={() => toggleAllChapters(true)}
              className="text-muted-foreground hover:text-primary transition-colors font-medium px-2 py-1"
            >
              Thu gọn
            </button>
          </div>
        </div>
      )}

      {/* Search Results Mode */}
      {searchQuery ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
            <span>Tìm thấy <strong>{searchResults.length}</strong> bài viết khớp với "{searchQuery}"</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSearchChange('')}
              className="h-7 px-2 text-xs rounded-lg hover:text-foreground"
            >
              Xóa tìm kiếm
            </Button>
          </div>

          {searchResults.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border/80 p-8 text-center text-muted-foreground space-y-1 bg-card/40">
              <p className="text-xs sm:text-sm font-semibold text-foreground">{t('header.search_empty', { query: searchQuery })}</p>
              <p className="text-xs">Thử tìm bằng các từ khóa ngắn như: deck, SRS, phím tắt, yomitan, audio, payos...</p>
            </div>
          ) : (
            <div className="rounded-2xl border border-border/80 bg-card divide-y divide-border/60 shadow-2xs overflow-hidden">
              {searchResults.map((art) => {
                const targetUrl =
                  art.categorySlug === 'getting-started' &&
                  (art.slug === 'getting-started' || art.slug === 'core-concepts')
                    ? `/guide/${art.slug}`
                    : `/guide/${art.categorySlug}/${art.slug}`
                const categoryTitle = GUIDE_CATEGORIES.find((c) => c.slug === art.categorySlug)?.title

                return (
                  <Link
                    key={art.slug}
                    to={targetUrl}
                    className="flex items-start justify-between gap-3 p-3.5 hover:bg-muted/30 transition-colors group"
                  >
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-2">
                        {categoryTitle && (
                          <Badge variant="outline" className="text-[10px] h-4 px-1 font-semibold text-muted-foreground border-border/60">
                            {categoryTitle}
                          </Badge>
                        )}
                        <h4 className="text-xs sm:text-sm font-bold text-foreground group-hover:text-primary transition-colors truncate">
                          {art.title}
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-1 leading-relaxed pl-0.5">
                        {art.shortDescription}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 pt-0.5">
                      {art.readTimeMinutes && (
                        <span className="text-[11px] text-muted-foreground whitespace-nowrap">
                          {t('header.read_time', { minutes: art.readTimeMinutes })}
                        </span>
                      )}
                      <FontAwesomeIcon icon={faChevronRight} className="text-[10px] text-muted-foreground/60 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                    </div>
                  </Link>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        /* Hierarchical Book Table of Contents */
        <div className="rounded-2xl border border-border/80 bg-card shadow-2xs divide-y divide-border/60 overflow-hidden">
          {displayedCategories.map((cat) => {
            const originalIndex = GUIDE_CATEGORIES.findIndex((c) => c.slug === cat.slug)
            const chapterNum = originalIndex + 1
            const iconDef = CATEGORY_FA_ICONS[cat.iconName] || faBook
            const isTrouble = cat.slug === 'troubleshooting'
            const isCollapsed = collapsedChapters[cat.slug] ?? false

            return (
              <div key={cat.slug} className="p-4 sm:p-5 space-y-3">
                {/* Chapter Title Header with Click-to-toggle */}
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => toggleChapter(cat.slug)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      toggleChapter(cat.slug)
                    }
                  }}
                  className="flex items-center justify-between gap-3 cursor-pointer group select-none"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md shrink-0">
                      {chapterNum < 10 ? `0${chapterNum}` : chapterNum}
                    </span>
                    <h2 className="text-sm sm:text-base font-bold text-foreground truncate flex items-center gap-2 group-hover:text-primary transition-colors">
                      <FontAwesomeIcon
                        icon={iconDef}
                        className={`text-xs ${isTrouble ? 'text-amber-500' : 'text-primary'}`}
                      />
                      <span>{cat.title}</span>
                    </h2>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[11px] font-medium text-muted-foreground whitespace-nowrap">
                      {cat.articles.length} bài
                    </span>
                    <FontAwesomeIcon
                      icon={isCollapsed ? faChevronRight : faChevronDown}
                      className="text-[10px] text-muted-foreground group-hover:text-foreground transition-transform"
                    />
                  </div>
                </div>

                {/* Sub-articles Hierarchical List */}
                {!isCollapsed && (
                  <div className="space-y-1 pl-1 sm:pl-2 pt-0.5">
                    {cat.articles.map((art, artIdx) => {
                      const targetUrl =
                        cat.slug === 'getting-started' &&
                        (art.slug === 'getting-started' || art.slug === 'core-concepts')
                          ? `/guide/${art.slug}`
                          : `/guide/${cat.slug}/${art.slug}`
                      const sectionNum = `${chapterNum}.${artIdx + 1}`

                      return (
                        <Link
                          key={art.slug}
                          to={targetUrl}
                          className="group block py-2 px-2.5 rounded-xl hover:bg-muted/40 transition-all"
                        >
                          <div className="flex items-baseline justify-between gap-2">
                            <div className="flex items-baseline gap-2 min-w-0">
                              <span className="font-mono text-[11px] font-bold text-muted-foreground group-hover:text-primary transition-colors shrink-0">
                                {sectionNum}
                              </span>
                              <span className="text-xs sm:text-sm font-semibold text-foreground/90 group-hover:text-primary transition-colors truncate">
                                {art.title}
                              </span>
                            </div>

                            {/* Dotted Leader Line & Read Time */}
                            <div className="flex items-center gap-2 shrink-0 self-center">
                              <div className="hidden sm:block w-12 border-b border-dotted border-border/80 group-hover:border-primary/40 transition-colors" />
                              {art.readTimeMinutes && (
                                <span className="text-[11px] text-muted-foreground flex items-center gap-1">
                                  <FontAwesomeIcon icon={faClock} className="text-[9px] opacity-70" />
                                  <span>{art.readTimeMinutes}p</span>
                                </span>
                              )}
                              <FontAwesomeIcon
                                icon={faChevronRight}
                                className="text-[9px] text-muted-foreground/40 group-hover:text-primary group-hover:translate-x-0.5 transition-all"
                              />
                            </div>
                          </div>

                          {/* 1-Line Clean Subtitle Description */}
                          <p className="text-[11px] text-muted-foreground line-clamp-1 mt-0.5 pl-6">
                            {art.shortDescription}
                          </p>
                        </Link>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}




