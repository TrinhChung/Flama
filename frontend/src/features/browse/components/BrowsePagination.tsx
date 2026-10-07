import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Check, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { BrowsePaginationMobile } from './BrowsePaginationMobile'
import { BrowsePaginationControls } from './BrowsePaginationControls'

export interface BrowsePaginationProps {
  page: number
  setPage: (page: number | ((prev: number) => number)) => void
  perPage: number
  handlePerPageChange: (perPage: number) => void
  total: number
  pages: number
  selectedCount?: number
}

function getPageItems(current: number, total: number): (number | 'ellipsis-start' | 'ellipsis-end')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  if (current <= 4) {
    return [1, 2, 3, 4, 5, 'ellipsis-end', total]
  }

  if (current >= total - 3) {
    return [1, 'ellipsis-start', total - 4, total - 3, total - 2, total - 1, total]
  }

  return [1, 'ellipsis-start', current - 1, current, current + 1, 'ellipsis-end', total]
}

export function BrowsePagination({
  page,
  setPage,
  perPage,
  handlePerPageChange,
  total,
  pages,
  selectedCount = 0,
}: BrowsePaginationProps) {
  const { t } = useTranslation('browse')

  if (total <= 0) return null

  const startItem = (page - 1) * perPage + 1
  const endItem = Math.min(page * perPage, total)
  const pageItems = getPageItems(page, pages)

  return (
    <footer
      aria-label={t('pagination.aria_label')}
      className="shrink-0 flex flex-col sm:flex-row items-center justify-between gap-2.5 sm:gap-4 border-t border-border/60 bg-muted/15 px-3 py-2.5 sm:px-4 sm:py-2 mt-auto"
    >
      {/* Left: Summary Metrics & Per Page Selector */}
      <div className="flex items-center justify-between sm:justify-start gap-3 w-full sm:w-auto text-xs text-muted-foreground font-medium">
        <div className="flex items-center gap-1.5 truncate">
          <span>
            {t('pagination.showing_range', {
              start: startItem,
              end: endItem,
              total,
            })}
          </span>

          {selectedCount > 0 && (
            <Badge
              variant="secondary"
              className="text-[10px] px-1.5 py-0 font-bold bg-primary/15 text-primary rounded-full shrink-0 ml-1"
            >
              {t('pagination.selected_count', { count: selectedCount })}
            </Badge>
          )}
        </div>

        {/* Per-Page Dropdown Selector */}
        <div className="flex items-center gap-1.5 shrink-0 ml-auto sm:ml-2">
          <span className="hidden md:inline text-[11px] text-muted-foreground font-medium">
            {t('pagination.per_page_label')}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 px-2 text-xs font-semibold rounded-lg border-border/70 bg-card hover:bg-muted/60 text-foreground flex items-center gap-1.5 shadow-2xs cursor-pointer transition-all"
                aria-label={t('pagination.select_rows_per_page')}
              >
                <span>{t('pagination.rows_count', { count: perPage })}</span>
                <ChevronDown className="size-3 text-muted-foreground opacity-70" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-32 min-w-28 p-1 rounded-xl shadow-lg border-border/80">
              <DropdownMenuLabel className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground px-2 py-1">
                {t('pagination.rows_per_page')}
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="my-1" />
              {[20, 50, 100, 200, 500].map((count) => {
                const isSelected = perPage === count
                return (
                  <DropdownMenuItem
                    key={count}
                    onClick={() => handlePerPageChange(count)}
                    className={`flex items-center justify-between text-xs font-medium cursor-pointer py-1.5 px-2 rounded-lg transition-colors ${
                      isSelected ? 'bg-primary/10 text-primary font-bold' : 'text-foreground hover:bg-muted/60'
                    }`}
                  >
                    <span>{t('pagination.rows_count', { count })}</span>
                    {isSelected && <Check className="size-3.5 text-primary shrink-0" />}
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Right: Responsive Navigation Controls */}
      {pages > 1 && (
        <div className="flex items-center justify-center sm:justify-end gap-1 sm:gap-1.5 w-full sm:w-auto">
          {/* Mobile View: Compact Prev / Next / Direct Indicator */}
          <BrowsePaginationMobile
            page={page}
            pages={pages}
            setPage={setPage}
          />

          {/* Desktop View: Full rich pagination with first, prev, numbers, ellipsis, next, last, jump */}
          <BrowsePaginationControls
            page={page}
            pages={pages}
            setPage={setPage}
            pageItems={pageItems}
          />
        </div>
      )}
    </footer>
  )
}
