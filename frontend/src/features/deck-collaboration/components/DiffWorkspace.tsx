import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  CirclePlus,
  FilePenLine,
  LoaderCircle,
  MinusCircle,
  Search,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type {
  DiffChangeFilter,
  DiffChangeType,
  DiffFilters,
  DiffItem,
  DiffSummary,
  DiffValue,
} from '../types'

type DiffWorkspaceProps = {
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

const FILTERS: Array<{
  value: DiffChangeFilter
  label: string
  summaryKey: keyof Pick<
    DiffSummary,
    'total' | 'added' | 'modified' | 'removed' | 'conflicts'
  >
}> = [
  { value: 'all', label: 'Tất cả', summaryKey: 'total' },
  { value: 'added', label: 'Thêm', summaryKey: 'added' },
  { value: 'modified', label: 'Sửa', summaryKey: 'modified' },
  { value: 'removed', label: 'Xóa', summaryKey: 'removed' },
  { value: 'conflict', label: 'Xung đột', summaryKey: 'conflicts' },
]

const CHANGE_LABELS: Record<DiffChangeType, string> = {
  added: 'Thêm',
  modified: 'Sửa',
  removed: 'Xóa',
  conflict: 'Xung đột',
}

function ChangeIcon({ type }: { type: DiffChangeType }) {
  if (type === 'added') return <CirclePlus className="size-4" />
  if (type === 'removed') return <MinusCircle className="size-4" />
  if (type === 'conflict') return <AlertTriangle className="size-4" />
  return <FilePenLine className="size-4" />
}

function changeTone(type: DiffChangeType) {
  if (type === 'added') {
    return 'border-emerald-500/35 bg-emerald-500/8 text-emerald-700 dark:text-emerald-300'
  }
  if (type === 'removed') {
    return 'border-red-500/35 bg-red-500/8 text-red-700 dark:text-red-300'
  }
  if (type === 'conflict') {
    return 'border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200'
  }
  return 'border-blue-500/35 bg-blue-500/8 text-blue-700 dark:text-blue-300'
}

function valueToText(value: DiffValue) {
  if (value === undefined) return '(không có dữ liệu)'
  if (value === null) return '(null)'
  if (value === '') return '(chuỗi rỗng)'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  const serialized = JSON.stringify(value, null, 2)
  return serialized === undefined ? String(value) : serialized
}

function DiffValueBlock({
  value,
  side,
}: {
  value: DiffValue
  side: 'before' | 'after'
}) {
  const text = valueToText(value)
  const lines = text.split('\n')
  const isBefore = side === 'before'

  return (
    <div
      className={cn(
        'overflow-x-auto border-y font-mono text-xs leading-5',
        isBefore
          ? 'border-red-500/20 bg-red-500/8'
          : 'border-emerald-500/20 bg-emerald-500/8',
      )}
    >
      {lines.map((line, index) => (
        <div
          key={`${index}-${line}`}
          className="grid min-w-max grid-cols-[2.25rem_1rem_minmax(0,1fr)] px-2"
        >
          <span className="select-none border-r border-foreground/10 pr-2 text-right text-muted-foreground/70">
            {index + 1}
          </span>
          <span
            className={cn(
              'select-none text-center font-semibold',
              isBefore ? 'text-red-700 dark:text-red-300' : 'text-emerald-700 dark:text-emerald-300',
            )}
          >
            {isBefore ? '-' : '+'}
          </span>
          <span className="whitespace-pre-wrap break-words pr-3">{line || ' '}</span>
        </div>
      ))}
    </div>
  )
}

function DiffRow({
  item,
  expanded,
  onToggle,
}: {
  item: DiffItem
  expanded: boolean
  onToggle: () => void
}) {
  const beforeValue = item.before_value !== undefined
    ? item.before_value
    : item.before_preview
  const afterValue = item.after_value !== undefined
    ? item.after_value
    : item.after_preview
  const title = item.note_label || item.note_id || item.entity_id
  const fieldLabel = item.field_name || item.entity_kind.replaceAll('_', ' ')

  return (
    <article
      className="overflow-hidden rounded-xl border bg-card shadow-xs"
      style={{ contentVisibility: 'auto', containIntrinsicSize: '72px' }}
    >
      <button
        type="button"
        className="flex w-full items-center gap-3 px-3 py-3 text-left transition-colors hover:bg-muted/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:px-4"
        aria-expanded={expanded}
        onClick={onToggle}
      >
        <span className="text-muted-foreground">
          {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </span>
        <span
          className={cn(
            'flex size-8 shrink-0 items-center justify-center rounded-lg border',
            changeTone(item.change_type),
          )}
        >
          <ChangeIcon type={item.change_type} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="truncate text-sm font-semibold">{title}</span>
            <span className="text-xs text-muted-foreground">/ {fieldLabel}</span>
          </span>
          <span className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            {item.deck_path ? <span className="truncate">{item.deck_path}</span> : null}
            {item.is_truncated ? <span>Giá trị đã rút gọn</span> : null}
          </span>
        </span>
        <Badge variant="outline" className={cn('hidden border sm:inline-flex', changeTone(item.change_type))}>
          {CHANGE_LABELS[item.change_type]}
        </Badge>
      </button>

      {expanded ? (
        <div className="border-t">
          <div className="flex flex-wrap items-center justify-between gap-2 bg-muted/35 px-3 py-2 font-mono text-[11px] text-muted-foreground sm:px-4">
            <span>@@ {title} / {fieldLabel} @@</span>
            <span>{item.operation || item.change_type}</span>
          </div>
          {item.change_type !== 'added' ? (
            <DiffValueBlock value={beforeValue} side="before" />
          ) : null}
          {item.change_type !== 'removed' ? (
            <DiffValueBlock value={afterValue} side="after" />
          ) : null}
          {item.is_truncated ? (
            <p className="px-3 py-2 text-xs text-muted-foreground sm:px-4">
              Nội dung dài đang được hiển thị dưới dạng preview từ máy chủ.
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  )
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
  emptyTitle = 'Không có thay đổi',
  emptyDescription = 'Không có mục nào khớp với bộ lọc hiện tại.',
  headerAction,
}: DiffWorkspaceProps) {
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

  return (
    <section className="space-y-4" aria-label="So sánh thay đổi">
      <div className="sticky top-0 z-10 space-y-3 rounded-2xl border bg-background/95 p-3 shadow-sm backdrop-blur sm:p-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {FILTERS.map((filter) => {
              const selected = filter.value === filters.changeType
              return (
                <button
                  key={filter.value}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => selectFilter(filter.value)}
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
                    {summary[filter.summaryKey].toLocaleString('vi-VN')}
                  </span>
                </button>
              )
            })}
          </div>
          {headerAction}
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <form onSubmit={submitSearch} className="flex w-full max-w-xl gap-2">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchDraft}
                onChange={(event) => setSearchDraft(event.target.value)}
                className="pl-9"
                placeholder="Tìm note, field hoặc deck…"
                aria-label="Tìm trong thay đổi"
              />
            </div>
            <Button type="submit" variant="outline">Tìm</Button>
          </form>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {summary.notes !== undefined ? (
              <span>{summary.notes.toLocaleString('vi-VN')} note</span>
            ) : (
              <span>{summary.entities.toLocaleString('vi-VN')} thực thể</span>
            )}
            {summary.fields !== undefined ? (
              <span>{summary.fields.toLocaleString('vi-VN')} field</span>
            ) : (
              <span>{summary.total.toLocaleString('vi-VN')} thay đổi</span>
            )}
            {isFetching && !isFetchingMore ? (
              <span className="inline-flex items-center gap-1">
                <LoaderCircle className="size-3.5 animate-spin" />
                Đang lọc
              </span>
            ) : null}
          </div>
        </div>
      </div>

      {!items.length && !isFetching ? (
        <div className="rounded-2xl border border-dashed bg-muted/20 px-6 py-14 text-center">
          <h3 className="font-semibold">{emptyTitle}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{emptyDescription}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <DiffRow
              key={item.id}
              item={item}
              expanded={expandedId === item.id}
              onToggle={() => setExpandedId((current) => current === item.id ? null : item.id)}
            />
          ))}
        </div>
      )}

      {hasPrevious || hasMore ? (
        <div className="flex items-center justify-center gap-2 pt-2">
          <Button
            type="button"
            variant="outline"
            disabled={!hasPrevious || isFetchingMore}
            onClick={onPrevious}
          >
            Trang trước
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
            Trang tiếp
          </Button>
        </div>
      ) : null}
    </section>
  )
}
