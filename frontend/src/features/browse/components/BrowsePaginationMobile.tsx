import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface BrowsePaginationMobileProps {
  page: number
  pages: number
  setPage: (page: number | ((prev: number) => number)) => void
}

export function BrowsePaginationMobile({
  page,
  pages,
  setPage,
}: BrowsePaginationMobileProps) {
  const { t } = useTranslation('browse')

  return (
    <div className="flex sm:hidden items-center justify-between w-full gap-1">
      <div className="flex items-center gap-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 w-7 p-0 rounded-lg text-muted-foreground hover:text-foreground disabled:opacity-30"
          disabled={page <= 1}
          onClick={() => setPage(1)}
          aria-label={t('pagination.first_page_aria')}
          title={t('pagination.first_page')}
        >
          <ChevronsLeft className="size-3.5" />
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 w-7 p-0 rounded-lg text-muted-foreground hover:text-foreground disabled:opacity-30"
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          aria-label={t('pagination.prev_page_aria')}
          title={t('pagination.prev_page')}
        >
          <ChevronLeft className="size-3.5" />
        </Button>
      </div>

      {/* Mobile Page indicator pill */}
      <div className="flex items-center gap-1 px-2.5 h-7 rounded-lg bg-card border border-border/70 text-xs font-semibold shadow-2xs">
        <span className="text-primary font-bold">{page}</span>
        <span className="text-muted-foreground font-normal">/</span>
        <span className="text-muted-foreground font-mono">{pages}</span>
      </div>

      <div className="flex items-center gap-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 w-7 p-0 rounded-lg text-muted-foreground hover:text-foreground disabled:opacity-30"
          disabled={page >= pages}
          onClick={() => setPage((p) => Math.min(pages, p + 1))}
          aria-label={t('pagination.next_page_aria')}
          title={t('pagination.next_page')}
        >
          <ChevronRight className="size-3.5" />
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 w-7 p-0 rounded-lg text-muted-foreground hover:text-foreground disabled:opacity-30"
          disabled={page >= pages}
          onClick={() => setPage(pages)}
          aria-label={t('pagination.last_page_aria')}
          title={t('pagination.last_page')}
        >
          <ChevronsRight className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}
