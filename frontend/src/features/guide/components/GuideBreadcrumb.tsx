import { ChevronRight, Home } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { GuideCategory, GuideArticle } from '../types'

interface GuideBreadcrumbProps {
  category?: GuideCategory
  article?: GuideArticle
}

export function GuideBreadcrumb({ category, article }: GuideBreadcrumbProps) {
  return (
    <nav className="flex items-center gap-1.5 text-xs text-muted-foreground mb-4 flex-wrap" aria-label="Breadcrumb">
      <Link
        to="/guide"
        className="flex items-center gap-1 hover:text-primary transition-colors py-0.5 font-medium"
      >
        <Home className="size-3.5" />
        <span>Trung tâm Trợ giúp</span>
      </Link>

      {category && (
        <>
          <ChevronRight className="size-3.5 text-muted-foreground/50 shrink-0" />
          <Link
            to={`/guide/${category.slug}`}
            className="hover:text-primary transition-colors py-0.5 font-medium max-w-[200px] truncate"
          >
            {category.title}
          </Link>
        </>
      )}

      {article && (
        <>
          <ChevronRight className="size-3.5 text-muted-foreground/50 shrink-0" />
          <span className="font-semibold text-foreground max-w-[260px] truncate py-0.5">
            {article.title}
          </span>
        </>
      )}
    </nav>
  )
}
