import { useState, useEffect } from 'react'
import { useParams, useLocation } from 'react-router-dom'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faBars, faBookOpen } from '@fortawesome/free-solid-svg-icons'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet'
import { Page } from '@/shared/components/Page'
import { GuideSidebar } from '../components/GuideSidebar'
import { GuideHomePage } from '../components/GuideHomePage'
import { GuideArticleRenderer } from '../components/GuideArticleRenderer'
import { getArticleBySlug } from '../guideData'

export function GuidePage() {
  const params = useParams<{ categorySlug?: string; articleSlug?: string }>()
  const location = useLocation()
  const [searchQuery, setSearchQuery] = useState('')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  // Scroll to top on navigation
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [location.pathname])

  const { categorySlug, articleSlug } = params

  // Check if we are at root /guide (no params)
  const isHome = !categorySlug && !articleSlug

  // Resolve active article and category
  const { category, article } = isHome
    ? {}
    : getArticleBySlug(categorySlug || '', articleSlug)

  return (
    <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-3 sm:py-5 space-y-6">
      {/* Mobile Top Bar with TOC drawer trigger */}
      <div className="flex items-center justify-between lg:hidden pb-3 border-b border-border/80">
        <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="sm" className="gap-2 rounded-xl text-xs font-bold border-border/80 shadow-2xs">
              <FontAwesomeIcon icon={faBars} className="text-xs" />
              <span>Mục Lục Hướng Dẫn</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-80 p-3 pt-8 bg-card border-r border-border/80">
            <GuideSidebar
              activeCategorySlug={category?.slug}
              activeArticleSlug={article?.slug}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              onItemClick={() => setMobileMenuOpen(false)}
            />
          </SheetContent>
        </Sheet>

        <span className="text-xs font-bold text-muted-foreground truncate max-w-[200px] flex items-center gap-1.5">
          <FontAwesomeIcon icon={faBookOpen} className="text-primary text-[11px]" />
          <span>{article ? article.title : 'Trung Tâm Trợ Giúp'}</span>
        </span>
      </div>

      {/* Main Grid: Left TOC Sidebar (Desktop) + Right Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 xl:gap-8 items-start">
        {/* Desktop Left Sidebar (3-4 cols) */}
        <div className="hidden lg:block lg:col-span-4 xl:col-span-3 sticky top-20">
          <GuideSidebar
            activeCategorySlug={category?.slug}
            activeArticleSlug={article?.slug}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
          />
        </div>

        {/* Content Area (8-9 cols) */}
        <main className="lg:col-span-8 xl:col-span-9 min-w-0">
          {isHome ? (
            <GuideHomePage
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
            />
          ) : article ? (
            <GuideArticleRenderer
              article={article}
              category={category}
            />
          ) : (
            <GuideHomePage
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
            />
          )}
        </main>
      </div>
    </Page>
  )
}

