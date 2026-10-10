import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faBolt,
  faBook,
  faBookBookmark,
  faChevronDown,
  faChevronRight,
  faGraduationCap,
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
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { GUIDE_CATEGORIES } from '../guideData'

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

interface GuideSidebarProps {
  activeCategorySlug?: string
  activeArticleSlug?: string
  searchQuery: string
  onSearchChange: (q: string) => void
  onItemClick?: () => void
}

export function GuideSidebar({
  activeCategorySlug,
  activeArticleSlug,
  searchQuery,
  onSearchChange,
  onItemClick,
}: GuideSidebarProps) {
  const { t } = useTranslation('guide')
  const [openCategories, setOpenCategories] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    GUIDE_CATEGORIES.forEach((c) => {
      initial[c.slug] = c.slug === activeCategorySlug || c.slug === 'getting-started' || c.slug === 'dashboard'
    })
    return initial
  })

  // When searching, auto open all categories with matching articles
  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return GUIDE_CATEGORIES
    const query = searchQuery.trim().toLowerCase()
    return GUIDE_CATEGORIES.map((cat) => ({
      ...cat,
      articles: cat.articles.filter(
        (art) =>
          art.title.toLowerCase().includes(query) ||
          art.shortDescription.toLowerCase().includes(query) ||
          cat.title.toLowerCase().includes(query),
      ),
    })).filter((cat) => cat.articles.length > 0)
  }, [searchQuery])

  const toggleCategory = (slug: string) => {
    setOpenCategories((prev) => ({
      ...prev,
      [slug]: !prev[slug],
    }))
  }

  return (
    <aside className="flex flex-col h-full bg-card rounded-2xl border border-border/80 p-3.5 space-y-3 shadow-2xs">
      {/* Search Bar */}
      <div className="relative">
        <FontAwesomeIcon
          icon={faMagnifyingGlass}
          className="text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 text-xs"
        />
        <Input
          type="search"
          placeholder={t('header.search_placeholder')}
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-8 pr-7 h-9 text-xs rounded-xl bg-background border-border/80 focus-visible:ring-primary"
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

      {/* Categories TOC Navigation */}
      <ScrollArea className="flex-1 pr-1 -mr-1 max-h-[calc(100vh-180px)]">
        <div className="space-y-1 pb-4">
          <Link
            to="/guide"
            onClick={onItemClick}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition-all mb-2 ${
              !activeCategorySlug && !activeArticleSlug
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-foreground hover:bg-muted/70'
            }`}
          >
            <FontAwesomeIcon icon={faBook} className="text-xs shrink-0" />
            <span>{t('sidebar.guide_home')}</span>
          </Link>

          {filteredCategories.map((cat) => {
            const iconDef = CATEGORY_FA_ICONS[cat.iconName] || faBook
            const isCatActive = activeCategorySlug === cat.slug
            const isOpen = Boolean(searchQuery.trim()) || (openCategories[cat.slug] ?? isCatActive)
            const isTrouble = cat.slug === 'troubleshooting'

            return (
              <div key={cat.slug} className="space-y-0.5 pt-1">
                {/* Category Header Button */}
                <button
                  type="button"
                  onClick={() => toggleCategory(cat.slug)}
                  className={`w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-xl text-xs font-bold transition-all text-left cursor-pointer group ${
                    isCatActive
                      ? 'text-primary bg-primary/10'
                      : isTrouble
                      ? 'text-amber-700 dark:text-amber-400 hover:bg-amber-500/10'
                      : 'text-foreground/90 hover:bg-muted/60'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FontAwesomeIcon
                      icon={iconDef}
                      className={`text-xs shrink-0 ${isTrouble ? 'text-amber-500' : 'text-primary'}`}
                    />
                    <span className="truncate">{cat.title}</span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Badge
                      variant="outline"
                      className="text-[10px] h-4 px-1 font-semibold text-muted-foreground border-border/60"
                    >
                      {cat.articles.length}
                    </Badge>
                    <FontAwesomeIcon
                      icon={isOpen ? faChevronDown : faChevronRight}
                      className="text-[9px] text-muted-foreground transition-transform"
                    />
                  </div>
                </button>

                {/* Sub-articles List */}
                {isOpen && (
                  <div className="pl-3.5 space-y-0.5 ml-2 border-l border-border/60 py-1">
                    {cat.articles.map((art) => {
                      const isArtActive =
                        activeArticleSlug === art.slug ||
                        (isCatActive && !activeArticleSlug && art.slug === cat.articles[0]?.slug)
                      const targetUrl =
                        cat.slug === 'getting-started' &&
                        (art.slug === 'getting-started' || art.slug === 'core-concepts')
                          ? `/guide/${art.slug}`
                          : `/guide/${cat.slug}/${art.slug}`

                      return (
                        <Link
                          key={art.slug}
                          to={targetUrl}
                          onClick={onItemClick}
                          className={`block px-2.5 py-1.5 rounded-lg text-[11px] transition-all truncate ${
                            isArtActive
                              ? 'bg-primary text-primary-foreground font-bold shadow-2xs'
                              : 'text-muted-foreground hover:text-foreground hover:bg-muted/50 font-medium'
                          }`}
                        >
                          {art.title}
                        </Link>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </ScrollArea>
    </aside>
  )
}

