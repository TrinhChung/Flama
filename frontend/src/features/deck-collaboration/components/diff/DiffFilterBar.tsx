import { type FormEvent, type ReactNode } from 'react'
import { LoaderCircle, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import '@/shared/config/i18n'
import type { DiffChangeFilter, DiffFilters, DiffSummary } from '../../types'

type DiffFilterBarProps = {
  summary: DiffSummary
  filters: DiffFilters
  searchDraft: string
  onSearchDraftChange: (value: string) => void
  onSelectFilter: (filter: DiffChangeFilter) => void
  onSubmitSearch: (event: FormEvent<HTMLFormElement>) => void
  isFetching?: boolean
  isFetchingMore?: boolean
  headerAction?: ReactNode
}

export function DiffFilterBar({
  summary,
  filters,
  searchDraft,
  onSearchDraftChange,
  onSelectFilter,
  onSubmitSearch,
  isFetching = false,
  isFetchingMore = false,
  headerAction,
}: DiffFilterBarProps) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  const filterOptions: Array<{
    value: DiffChangeFilter
    label: string
    summaryKey: keyof Pick<
      DiffSummary,
      'total' | 'added' | 'modified' | 'removed' | 'conflicts'
    >
  }> = [
    { value: 'all', label: t('diff.filter_all', 'Tất cả'), summaryKey: 'total' },
    { value: 'added', label: t('diff.filter_added', 'Thêm'), summaryKey: 'added' },
    { value: 'modified', label: t('diff.filter_modified', 'Sửa'), summaryKey: 'modified' },
    { value: 'removed', label: t('diff.filter_removed', 'Xóa'), summaryKey: 'removed' },
    { value: 'conflict', label: t('diff.filter_conflict', 'Xung đột'), summaryKey: 'conflicts' },
  ]

  return (
    <div className="sticky top-0 z-10 space-y-3 rounded-2xl border bg-background/95 p-3 shadow-sm backdrop-blur sm:p-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {filterOptions.map((filter) => {
            const selected = filter.value === filters.changeType
            return (
              <button
                key={filter.value}
                type="button"
                aria-pressed={selected}
                onClick={() => onSelectFilter(filter.value)}
                className={cn(
                  'rounded-xl border px-3 py-2 text-left transition-colors',
                  selected
                    ? 'border-primary/50 bg-primary/10 text-primary'
                    : 'bg-card hover:bg-muted/60',
                )}
              >
                <span className="block text-[11px] font-medium text-muted-foreground">
                  {filter.label}
                </span>
                <span className="text-lg font-bold tabular-nums">
                  {summary[filter.summaryKey].toLocaleString(locale)}
                </span>
              </button>
            )
          })}
        </div>
        {headerAction}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <form onSubmit={onSubmitSearch} className="flex w-full max-w-xl gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchDraft}
              onChange={(event) => onSearchDraftChange(event.target.value)}
              className="pl-9"
              placeholder={t('diff.search_placeholder', 'Tìm note, field hoặc deck…')}
              aria-label={t('diff.search_aria_label', 'Tìm trong thay đổi')}
            />
          </div>
          <Button type="submit" variant="outline">
            {t('diff.btn_search', 'Tìm')}
          </Button>
        </form>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {summary.notes !== undefined ? (
            <span>
              {t('diff.notes_count', {
                count: summary.notes.toLocaleString(locale),
                defaultValue: `${summary.notes.toLocaleString(locale)} note`,
              })}
            </span>
          ) : (
            <span>
              {t('diff.entities_count', {
                count: summary.entities.toLocaleString(locale),
                defaultValue: `${summary.entities.toLocaleString(locale)} thực thể`,
              })}
            </span>
          )}
          {summary.fields !== undefined ? (
            <span>
              {t('diff.fields_count', {
                count: summary.fields.toLocaleString(locale),
                defaultValue: `${summary.fields.toLocaleString(locale)} field`,
              })}
            </span>
          ) : (
            <span>
              {t('diff.changes_count', {
                count: summary.total.toLocaleString(locale),
                defaultValue: `${summary.total.toLocaleString(locale)} thay đổi`,
              })}
            </span>
          )}
          {isFetching && !isFetchingMore ? (
            <span className="inline-flex items-center gap-1">
              <LoaderCircle className="size-3.5 animate-spin" />
              {t('diff.filtering', 'Đang lọc')}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  )
}
