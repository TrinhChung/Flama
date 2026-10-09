import { useId } from 'react'
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  CirclePlus,
  FilePenLine,
  MinusCircle,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import '@/shared/config/i18n'
import type { DiffChangeType, DiffItem } from '../../types'
import { DiffValueBlock } from './DiffValueBlock'

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

const DEFAULT_CHANGE_LABELS: Record<DiffChangeType, string> = {
  added: 'Thêm',
  modified: 'Sửa',
  removed: 'Xóa',
  conflict: 'Xung đột',
}

export function DiffRow({
  item,
  expanded,
  onToggle,
}: {
  item: DiffItem
  expanded: boolean
  onToggle: () => void
}) {
  const { t } = useTranslation('collaboration')
  const contentId = useId()
  const beforeValue = item.before_value !== undefined
    ? item.before_value
    : item.before_preview
  const afterValue = item.after_value !== undefined
    ? item.after_value
    : item.after_preview
  const defaultTitle = t('diff.change_default_title', 'Thay đổi')
  const title = item.note_label || item.note_id || item.entity_id || defaultTitle
  const fieldLabel = item.field_name || item.entity_kind.replaceAll('_', ' ')
  const changeLabel = t(`diff.filter_${item.change_type}`, DEFAULT_CHANGE_LABELS[item.change_type])

  return (
    <article
      className="overflow-hidden rounded-xl border bg-card shadow-xs"
      style={{ contentVisibility: 'auto', containIntrinsicSize: '72px' }}
    >
      <button
        type="button"
        className="flex w-full items-center gap-3 px-3 py-3 text-left transition-colors hover:bg-muted/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:px-4"
        aria-expanded={expanded}
        aria-controls={contentId}
        onClick={onToggle}
      >
        <span aria-hidden="true" className="text-muted-foreground">
          {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        </span>
        <span
          aria-hidden="true"
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
            {item.is_truncated ? <span>{t('diff.value_truncated_tag', 'Giá trị đã rút gọn')}</span> : null}
          </span>
        </span>
        <Badge variant="outline" className={cn('hidden border sm:inline-flex', changeTone(item.change_type))}>
          {changeLabel}
        </Badge>
      </button>

      {expanded ? (
        <div id={contentId} className="border-t">
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
              {t('diff.truncated_server', 'Nội dung dài đang được hiển thị dưới dạng preview từ máy chủ.')}
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  )
}
