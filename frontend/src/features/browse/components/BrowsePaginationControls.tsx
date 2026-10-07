import '@/shared/config/i18n'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  MoreHorizontal,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface BrowsePaginationControlsProps {
  page: number
  pages: number
  setPage: (page: number | ((prev: number) => number)) => void
  pageItems: (number | 'ellipsis-start' | 'ellipsis-end')[]
}

export function BrowsePaginationControls({
  page,
  pages,
  setPage,
  pageItems,
}: BrowsePaginationControlsProps) {
  const { t } = useTranslation('browse')
  const [jumpPage, setJumpPage] = useState('')

  const handleJumpSubmit = (e: FormEvent) => {
    e.preventDefault()
    const target = parseInt(jumpPage.trim(), 10)
    if (!isNaN(target)) {
      const bounded = Math.max(1, Math.min(pages, target))
      setPage(bounded)
      setJumpPage('')
    }
  }

  return (
    <div className="hidden sm:flex items-center gap-1">
      {/* First Page */}
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

      {/* Previous Page */}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-7 px-2 gap-1 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground disabled:opacity-30"
        disabled={page <= 1}
        onClick={() => setPage((p) => Math.max(1, p - 1))}
        aria-label={t('pagination.prev_page_aria')}
        title={t('pagination.prev_page')}
      >
        <ChevronLeft className="size-3.5" />
        <span className="hidden md:inline">{t('pagination.prev_page')}</span>
      </Button>

      {/* Numbered Page Buttons with Smart Ellipsis */}
      <div className="flex items-center gap-0.5">
        {pageItems.map((item, idx) => {
          if (typeof item === 'string') {
            return (
              <span
                key={`${item}-${idx}`}
                className="flex size-7 items-center justify-center text-muted-foreground/60 select-none"
                aria-hidden="true"
              >
                <MoreHorizontal className="size-3.5" />
              </span>
            )
          }

          const isActive = item === page
          return (
            <Button
              key={item}
              type="button"
              variant={isActive ? 'default' : 'ghost'}
              size="sm"
              className={`h-7 min-w-7 px-1.5 text-xs font-semibold rounded-lg tabular-nums cursor-pointer transition-all ${
                isActive
                  ? 'bg-primary text-primary-foreground font-bold shadow-xs hover:bg-primary/90'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/60'
              }`}
              onClick={() => setPage(item)}
              aria-current={isActive ? 'page' : undefined}
              aria-label={t('pagination.page_item_aria', { page: item })}
            >
              {item}
            </Button>
          )
        })}
      </div>

      {/* Next Page */}
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-7 px-2 gap-1 rounded-lg text-xs font-medium text-muted-foreground hover:text-foreground disabled:opacity-30"
        disabled={page >= pages}
        onClick={() => setPage((p) => Math.min(pages, p + 1))}
        aria-label={t('pagination.next_page_aria')}
        title={t('pagination.next_page')}
      >
        <span className="hidden md:inline">{t('pagination.next_page')}</span>
        <ChevronRight className="size-3.5" />
      </Button>

      {/* Last Page */}
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

      {/* Quick Jump Input (when pages >= 6) */}
      {pages >= 6 && (
        <form onSubmit={handleJumpSubmit} className="hidden lg:flex items-center gap-1.5 ml-1.5 pl-1.5 border-l border-border/60">
          <span className="text-[11px] text-muted-foreground">{t('pagination.jump_label')}</span>
          <input
            type="number"
            min={1}
            max={pages}
            value={jumpPage}
            placeholder={String(page)}
            onChange={(e) => setJumpPage(e.target.value)}
            onBlur={() => {
              if (jumpPage.trim()) {
                const target = parseInt(jumpPage.trim(), 10)
                if (!isNaN(target)) {
                  setPage(Math.max(1, Math.min(pages, target)))
                }
                setJumpPage('')
              }
            }}
            aria-label={t('pagination.jump_input_aria')}
            className="h-7 w-12 text-center text-xs rounded-lg border border-border/70 bg-card hover:border-primary/40 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono tabular-nums shadow-2xs [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
          />
        </form>
      )}
    </div>
  )
}
