import { useState, type FormEvent } from 'react'
import {
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  MoreHorizontal,
} from 'lucide-react'
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
  const [jumpPage, setJumpPage] = useState('')

  if (total <= 0) return null

  const startItem = (page - 1) * perPage + 1
  const endItem = Math.min(page * perPage, total)

  const handleJumpSubmit = (e: FormEvent) => {
    e.preventDefault()
    const target = parseInt(jumpPage.trim(), 10)
    if (!isNaN(target)) {
      const bounded = Math.max(1, Math.min(pages, target))
      setPage(bounded)
      setJumpPage('')
    }
  }

  const pageItems = getPageItems(page, pages)

  return (
    <footer
      aria-label="Điều hướng phân trang"
      className="shrink-0 flex flex-col sm:flex-row items-center justify-between gap-2.5 sm:gap-4 border-t border-border/60 bg-muted/15 px-3 py-2.5 sm:px-4 sm:py-2 mt-auto"
    >
      {/* Left: Summary Metrics & Per Page Selector */}
      <div className="flex items-center justify-between sm:justify-start gap-3 w-full sm:w-auto text-xs text-muted-foreground font-medium">
        <div className="flex items-center gap-1.5 truncate">
          <span>
            Hiển thị{' '}
            <strong className="text-foreground font-bold tabular-nums">
              {startItem}–{endItem}
            </strong>{' '}
            trên{' '}
            <strong className="text-foreground font-bold tabular-nums">
              {total}
            </strong>{' '}
            thẻ
          </span>

          {selectedCount > 0 && (
            <Badge
              variant="secondary"
              className="text-[10px] px-1.5 py-0 font-bold bg-primary/15 text-primary rounded-full shrink-0 ml-1"
            >
              {selectedCount} đã chọn
            </Badge>
          )}
        </div>

        {/* Per-Page Dropdown Selector */}
        <div className="flex items-center gap-1.5 shrink-0 ml-auto sm:ml-2">
          <span className="hidden md:inline text-[11px] text-muted-foreground font-medium">Mỗi trang:</span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 px-2 text-xs font-semibold rounded-lg border-border/70 bg-card hover:bg-muted/60 text-foreground flex items-center gap-1.5 shadow-2xs cursor-pointer transition-all"
                aria-label="Chọn số dòng trên một trang"
              >
                <span>{perPage} dòng</span>
                <ChevronDown className="size-3 text-muted-foreground opacity-70" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-32 min-w-28 p-1 rounded-xl shadow-lg border-border/80">
              <DropdownMenuLabel className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground px-2 py-1">
                Số dòng / trang
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
                    <span>{count} dòng</span>
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
          <div className="flex sm:hidden items-center justify-between w-full gap-1">
            <div className="flex items-center gap-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 w-7 p-0 rounded-lg text-muted-foreground hover:text-foreground disabled:opacity-30"
                disabled={page <= 1}
                onClick={() => setPage(1)}
                aria-label="Về trang đầu"
                title="Trang đầu"
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
                aria-label="Trang trước"
                title="Trang trước"
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
                aria-label="Trang sau"
                title="Trang sau"
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
                aria-label="Đến trang cuối"
                title="Trang cuối"
              >
                <ChevronsRight className="size-3.5" />
              </Button>
            </div>
          </div>

          {/* Desktop View: Full rich pagination with first, prev, numbers, ellipsis, next, last, jump */}
          <div className="hidden sm:flex items-center gap-1">
            {/* First Page */}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0 rounded-lg text-muted-foreground hover:text-foreground disabled:opacity-30"
              disabled={page <= 1}
              onClick={() => setPage(1)}
              aria-label="Về trang đầu"
              title="Trang đầu (1)"
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
              aria-label="Trang trước"
              title="Trang trước"
            >
              <ChevronLeft className="size-3.5" />
              <span className="hidden md:inline">Trước</span>
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
                    aria-label={`Trang ${item}`}
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
              aria-label="Trang sau"
              title="Trang sau"
            >
              <span className="hidden md:inline">Sau</span>
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
              aria-label="Đến trang cuối"
              title={`Trang cuối (${pages})`}
            >
              <ChevronsRight className="size-3.5" />
            </Button>

            {/* Quick Jump Input (when pages >= 6) */}
            {pages >= 6 && (
              <form onSubmit={handleJumpSubmit} className="hidden lg:flex items-center gap-1.5 ml-1.5 pl-1.5 border-l border-border/60">
                <span className="text-[11px] text-muted-foreground">Đến:</span>
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
                  aria-label="Nhập số trang muốn chuyển tới"
                  className="h-7 w-12 text-center text-xs rounded-lg border border-border/70 bg-card hover:border-primary/40 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono tabular-nums shadow-2xs [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                />
              </form>
            )}
          </div>
        </div>
      )}
    </footer>
  )
}
