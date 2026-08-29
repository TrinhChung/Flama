import { useState } from 'react'
import {
  AlertTriangle,
  ArrowRightLeft,
  AudioLines,
  BookOpen,
  Bot,
  ChevronDown,
  ChevronRight,
  GraduationCap,
  LayoutDashboard,
  NotebookTabs,
  Search,
  Store,
  Wallet,
  X,
  Zap,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { GUIDE_CATEGORIES } from '../guideData'

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  Zap,
  LayoutDashboard,
  GraduationCap,
  Search,
  NotebookTabs,
  Store,
  ArrowRightLeft,
  Bot,
  AudioLines,
  Wallet,
  AlertTriangle,
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
  const [openCategories, setOpenCategories] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    GUIDE_CATEGORIES.forEach((c) => {
      // Default open if active category, or open the first few
      initial[c.slug] = c.slug === activeCategorySlug || c.slug === 'getting-started' || c.slug === 'dashboard'
    })
    return initial
  })

  const toggleCategory = (slug: string) => {
    setOpenCategories((prev) => ({
      ...prev,
      [slug]: !prev[slug],
    }))
  }

  return (
    <aside className="flex flex-col h-full bg-card/40 rounded-2xl border border-border/70 p-3.5 space-y-3">
      {/* Search Bar */}
      <div className="relative">
        <Search className="size-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
        <Input
          type="search"
          placeholder="Tìm kiếm tài liệu..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9 pr-8 h-9 text-xs rounded-xl bg-background/80 focus-visible:ring-primary"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>

      {/* Categories Navigation */}
      <ScrollArea className="flex-1 pr-1 -mr-1">
        <div className="space-y-1 pb-4">
          <Link
            to="/guide"
            onClick={onItemClick}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all mb-2 ${
              !activeCategorySlug && !activeArticleSlug
                ? 'bg-primary text-primary-foreground shadow-xs'
                : 'text-foreground hover:bg-muted/70'
            }`}
          >
            <BookOpen className="size-4 shrink-0" />
            <span>Trang Chủ Trợ Giúp</span>
          </Link>

          {GUIDE_CATEGORIES.map((cat) => {
            const IconComp = CATEGORY_ICONS[cat.iconName] || BookOpen
            const isCatActive = activeCategorySlug === cat.slug
            const isOpen = openCategories[cat.slug] ?? isCatActive
            const isTrouble = cat.slug === 'troubleshooting'

            return (
              <div key={cat.slug} className="space-y-0.5 pt-1">
                {/* Category Header Button */}
                <button
                  type="button"
                  onClick={() => toggleCategory(cat.slug)}
                  className={`w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-xs font-bold transition-all text-left group ${
                    isCatActive
                      ? 'text-primary bg-primary/10'
                      : isTrouble
                      ? 'text-amber-700 dark:text-amber-400 hover:bg-amber-500/10'
                      : 'text-foreground/80 hover:bg-muted/60'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <IconComp className={`size-3.5 shrink-0 ${isTrouble ? 'text-amber-500' : 'text-primary/80'}`} />
                    <span className="truncate">{cat.title}</span>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Badge
                      variant="outline"
                      className="text-[10px] h-4 px-1 font-semibold text-muted-foreground border-border/60"
                    >
                      {cat.articles.length}
                    </Badge>
                    {isOpen ? (
                      <ChevronDown className="size-3.5 text-muted-foreground transition-transform" />
                    ) : (
                      <ChevronRight className="size-3.5 text-muted-foreground transition-transform" />
                    )}
                  </div>
                </button>

                {/* Sub-articles List */}
                {isOpen && (
                  <div className="pl-4 space-y-0.5 ml-2 border-l border-border/60 py-1">
                    {cat.articles.map((art) => {
                      const isArtActive = activeArticleSlug === art.slug || (isCatActive && !activeArticleSlug && art.slug === cat.articles[0]?.slug)
                      const targetUrl = cat.slug === 'getting-started' && (art.slug === 'getting-started' || art.slug === 'core-concepts')
                        ? `/guide/${art.slug}`
                        : `/guide/${cat.slug}/${art.slug}`

                      return (
                        <Link
                          key={art.slug}
                          to={targetUrl}
                          onClick={onItemClick}
                          className={`block px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all truncate ${
                            isArtActive
                              ? 'bg-primary text-primary-foreground font-semibold shadow-xs'
                              : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
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
