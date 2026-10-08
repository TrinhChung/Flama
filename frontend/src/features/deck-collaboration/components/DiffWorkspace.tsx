import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import '@/shared/config/i18n'
import type {
  DiffChangeFilter,
  DiffFilters,
  DiffItem,
  DiffSummary,
} from '../types'
import { DiffFilterBar } from './diff/DiffFilterBar'
import { DiffRow } from './diff/DiffRow'

export type DiffWorkspaceProps = {
  summary: DiffSummary
  items: DiffItem[]
  filters: DiffFilters
  onFiltersChange: (filters: DiffFilters) => void
  isFetching?: boolean
  isFetchingMore?: boolean
  hasMore?: boolean
  onLoadMore?: () => void
  hasPrevious?: boolean
  onPrevious?: () => void
  pageLabel?: string
  emptyTitle?: string
  emptyDescription?: string
  headerAction?: ReactNode
}

export function DiffWorkspace({
  summary,
  items,
  filters,
  onFiltersChange,
  isFetching = false,
  isFetchingMore = false,
  hasMore = false,
  onLoadMore,
  hasPrevious = false,
  onPrevious,
  pageLabel,
  emptyTitle,
  emptyDescription,
  headerAction,
}: DiffWorkspaceProps) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const [searchDraft, setSearchDraft] = useState(filters.query)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    setSearchDraft(filters.query)
  }, [filters.query])

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const query = searchDraft.trim()
    if (query === filters.query) return
    setExpandedId(null)
    onFiltersChange({ ...filters, query })
  }

  function selectFilter(changeType: DiffChangeFilter) {
    if (changeType === filters.changeType) return
    setExpandedId(null)
    onFiltersChange({ ...filters, changeType })
  }

  const effectiveEmptyTitle = emptyTitle ?? t('diff.empty_title', 'Không có thay đổi')
  const effectiveEmptyDescription = emptyDescription ?? t('diff.empty_desc', 'Không có mục nào khớp với bộ lọc hiện tại.')

  return (
    <section className="space-y-4" aria-label={t('diff.aria_label', 'So sánh thay đổi')}>
      <DiffFilterBar
        summary={summary}
        filters={filters}
        searchDraft={searchDraft}
        onSearchDraftChange={setSearchDraft}
        onSelectFilter={selectFilter}
        onSubmitSearch={submitSearch}
        isFetching={isFetching}
        isFetchingMore={isFetchingMore}
        headerAction={headerAction}
      />

      {!items.length && !isFetching ? (
        <div className="rounded-2xl border border-dashed bg-muted/20 px-6 py-14 text-center">
          <h3 className="font-semibold">{effectiveEmptyTitle}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{effectiveEmptyDescription}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <DiffRow
              key={item.id}
              item={item}
              expanded={expandedId === item.id}
              onToggle={() => setExpandedId((current) => (current === item.id ? null : item.id))}
            />
          ))}
        </div>
      )}

      <p className="sr-only" role="status" aria-live="polite">
        {isFetching
          ? t('diff.loading_status', 'Đang tải thay đổi.')
          : t('diff.showing_status', {
              count: items.length.toLocaleString(locale),
              defaultValue: `Đang hiển thị ${items.length.toLocaleString(locale)} thay đổi.`,
            })}
      </p>

      {hasPrevious || hasMore ? (
        <nav
          className="flex items-center justify-center gap-2 pt-2"
          aria-label={t('diff.pagination_aria_label', 'Phân trang thay đổi')}
        >
          <Button
            type="button"
            variant="outline"
            disabled={!hasPrevious || isFetchingMore}
            onClick={onPrevious}
          >
            {t('diff.btn_prev', 'Trang trước')}
          </Button>
          {pageLabel ? (
            <span className="px-2 text-xs text-muted-foreground">{pageLabel}</span>
          ) : null}
          <Button
            type="button"
            variant="outline"
            disabled={!hasMore || isFetchingMore}
            onClick={onLoadMore}
          >
            {isFetchingMore ? <LoaderCircle className="size-4 animate-spin" /> : null}
            {t('diff.btn_next', 'Trang tiếp')}
          </Button>
        </nav>
      ) : null}
    </section>
  )
}
