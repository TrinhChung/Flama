import { useState, useEffect } from 'react'
import { useParams, useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
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
    <Page className="w-full max-w-7xl px-4 lg:px-8 py-4 space-y-6">
      {/* Mobile Top Bar with category drawer trigger */}
      <div className="flex items-center justify-between lg:hidden pb-2 border-b border-border/70">
        <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" size="sm" className="gap-2 rounded-xl text-xs font-semibold">
              <Menu className="size-4" />
              <span>Mục Lục Hướng Dẫn</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-80 p-3 pt-8">
            <GuideSidebar
              activeCategorySlug={category?.slug}
              activeArticleSlug={article?.slug}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              onItemClick={() => setMobileMenuOpen(false)}
            />
          </SheetContent>
        </Sheet>

        <span className="text-xs font-bold text-muted-foreground truncate max-w-[200px]">
          {article ? article.title : 'Trung Tâm Trợ Giúp'}
        </span>
      </div>

      {/* Main Grid: Left Sidebar (Desktop) + Right Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Desktop Left Sidebar (3 cols) */}
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
