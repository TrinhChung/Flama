import { useState } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowRight,
  faBolt,
  faBook,
  faBookBookmark,
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
import { Card, CardContent } from '@/components/ui/card'
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

interface GuideHomePageProps {
  searchQuery?: string
  onSearchChange?: (q: string) => void
}

export function GuideHomePage({ searchQuery: externalQuery, onSearchChange: externalOnChange }: GuideHomePageProps) {
  const [localQuery, setLocalQuery] = useState('')
  const searchQuery = externalQuery !== undefined ? externalQuery : localQuery
  const onSearchChange = externalOnChange || setLocalQuery

  const searchResults = searchQuery ? searchArticles(searchQuery) : []

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
            Toàn bộ tài liệu quy trình sử dụng Flama và cẩm nang giải quyết sự cố.
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
            placeholder="Tìm trong mục lục..."
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
              <p className="text-xs sm:text-sm font-semibold text-foreground">Không tìm thấy tài liệu phù hợp</p>
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

                return (
                  <Link
                    key={art.slug}
                    to={targetUrl}
                    className="flex items-start justify-between gap-3 p-3.5 hover:bg-muted/30 transition-colors group"
                  >
                    <div className="space-y-0.5 min-w-0">
                      <h4 className="text-xs sm:text-sm font-bold text-foreground group-hover:text-primary transition-colors flex items-center gap-2">
                        <span>{art.title}</span>
                      </h4>
                      <p className="text-xs text-muted-foreground line-clamp-1 leading-relaxed">
                        {art.shortDescription}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 pt-0.5">
                      {art.readTimeMinutes && (
                        <span className="text-[11px] text-muted-foreground whitespace-nowrap">
                          {art.readTimeMinutes} phút
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
          {GUIDE_CATEGORIES.map((cat, catIdx) => {
            const iconDef = CATEGORY_FA_ICONS[cat.iconName] || faBook
            const isTrouble = cat.slug === 'troubleshooting'
            const chapterNum = catIdx + 1

            return (
              <div key={cat.slug} className="p-4 sm:p-5 space-y-3">
                {/* Chapter Title Header */}
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md shrink-0">
                      {chapterNum < 10 ? `0${chapterNum}` : chapterNum}
                    </span>
                    <h2 className="text-sm sm:text-base font-bold text-foreground truncate flex items-center gap-2">
                      <FontAwesomeIcon
                        icon={iconDef}
                        className={`text-xs ${isTrouble ? 'text-amber-500' : 'text-primary'}`}
                      />
                      <span>{cat.title}</span>
                    </h2>
                  </div>

                  <span className="text-[11px] font-medium text-muted-foreground whitespace-nowrap shrink-0">
                    {cat.articles.length} bài
                  </span>
                </div>

                {/* Sub-articles Hierarchical List */}
                <div className="space-y-1.5 pl-2 sm:pl-3">
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
                        className="group flex flex-col sm:flex-row sm:items-baseline justify-between gap-1 sm:gap-2 py-1.5 px-2 rounded-lg hover:bg-muted/40 transition-colors"
                      >
                        <div className="flex items-baseline gap-2 min-w-0">
                          <span className="font-mono text-[11px] font-bold text-muted-foreground group-hover:text-primary transition-colors shrink-0">
                            {sectionNum}
                          </span>
                          <span className="text-xs sm:text-sm font-semibold text-foreground/90 group-hover:text-primary transition-colors truncate">
                            {art.title}
                          </span>
                        </div>

                        {/* Dotted Leader Line & Read Time */}
                        <div className="flex items-center gap-2 shrink-0 sm:self-center pl-6 sm:pl-0">
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
                      </Link>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}



