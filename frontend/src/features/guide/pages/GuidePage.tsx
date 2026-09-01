import { useEffect } from 'react'
import { useParams, useLocation } from 'react-router-dom'
import { Page } from '@/shared/components/Page'
import { GuideHomePage } from '../components/GuideHomePage'
import { GuideArticleRenderer } from '../components/GuideArticleRenderer'
import { getArticleBySlug } from '../guideData'

export function GuidePage() {
  const params = useParams<{ categorySlug?: string; articleSlug?: string }>()
  const location = useLocation()

  // Scroll to top on navigation
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [location.pathname])

  const { categorySlug, articleSlug } = params

  // Check if we are at root /guide (no params) or category index
  const isHome = !categorySlug && !articleSlug

  // Resolve active article and category
  const { category, article } = isHome
    ? {}
    : getArticleBySlug(categorySlug || '', articleSlug)

  return (
    <Page className="w-full max-w-5xl px-3 sm:px-6 py-4 sm:py-6">
      {isHome ? (
        <GuideHomePage />
      ) : article ? (
        <GuideArticleRenderer
          article={article}
          category={category}
        />
      ) : (
        <GuideHomePage />
      )}
    </Page>
  )
}


