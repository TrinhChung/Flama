import { AlertTriangle, Link2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'
import '@/shared/config/i18n'
import type { SchemaChange } from '../../model/noteChanges'
import type { NoteSelectionControls } from '../../model/selection'
import { ReviewDecisionBadge } from './ReviewDecisionBadge'

type CollabT = ReturnType<typeof useTranslation<'collaboration'>>['t']

function fieldTypeLabel(t: CollabT, value: unknown): string {
  const type = typeof value === 'string' && value ? value.toLowerCase() : 'text'
  const labels: Record<string, string> = {
    text: t('notes.field_type_text', 'văn bản'),
    richtext: t('notes.field_type_richtext', 'văn bản định dạng'),
    markdown: t('notes.field_type_markdown', 'Markdown'),
    array: t('notes.field_type_array', 'danh sách'),
    image: t('notes.field_type_image', 'ảnh'),
    audio: t('notes.field_type_audio', 'âm thanh'),
    diagram: t('notes.field_type_diagram', 'sơ đồ'),
  }
  return labels[type] || type
}

function orderNames(value: unknown): string {
  if (!Array.isArray(value)) return ''
  return value
    .map((token) => (token && typeof token === 'object' ? String((token as { name?: unknown }).name || '') : ''))
    .filter(Boolean)
    .join(' · ')
}

function describe(t: CollabT, change: SchemaChange): { title: string; detail?: string } {
  const name = change.fieldName
  if (change.changeType === 'field_def_add') {
    const after = (change.after && typeof change.after === 'object' ? change.after : {}) as Record<string, unknown>
    return {
      title: t('notes.schema_add', {
        name: String(after.name || name),
        type: fieldTypeLabel(t, after.field_type),
        defaultValue: `Thêm trường mới “${String(after.name || name)}” (${fieldTypeLabel(t, after.field_type)})`,
      }),
    }
  }
  if (change.changeType === 'field_def_disable') {
    return { title: t('notes.schema_disable', { name, defaultValue: `Ẩn trường “${name}”` }) }
  }
  if (change.changeType === 'field_order_update') {
    return {
      title: t('notes.schema_order', 'Sắp xếp lại thứ tự trường'),
      detail: `${orderNames(change.before)} → ${orderNames(change.after)}`,
    }
  }
  if (change.property === 'name') {
    return {
      title: t('notes.schema_rename', {
        from: String(change.before ?? name),
        to: String(change.after ?? ''),
        defaultValue: `Đổi tên trường “${String(change.before ?? name)}” thành “${String(change.after ?? '')}”`,
      }),
    }
  }
  if (change.property === 'field_type') {
    return {
      title: t('notes.schema_type', {
        name,
        from: fieldTypeLabel(t, change.before),
        to: fieldTypeLabel(t, change.after),
        defaultValue: `Đổi loại trường “${name}”: ${fieldTypeLabel(t, change.before)} → ${fieldTypeLabel(t, change.after)}`,
      }),
    }
  }
  if (change.property === 'required') {
    return {
      title: change.after
        ? t('notes.schema_required_on', { name, defaultValue: `Đặt trường “${name}” là bắt buộc` })
        : t('notes.schema_required_off', { name, defaultValue: `Bỏ bắt buộc cho trường “${name}”` }),
    }
  }
  return { title: t('notes.schema_position', { name, defaultValue: `Đổi vị trí trường “${name}”` }) }
}

/** The contributor's changes to the note type itself, in plain words. */
export function SchemaChangeCard({
  changes,
  selection,
}: {
  changes: SchemaChange[]
  selection?: NoteSelectionControls
}) {
  const { t } = useTranslation('collaboration')
  const groupState = selection?.schemaGranularity === 'group' ? selection.schemaState(null) : null

  return (
    <article
      className={cn(
        'overflow-hidden rounded-xl border bg-card shadow-xs',
        groupState === false && 'border-dashed bg-muted/20',
      )}
      aria-label={t('notes.schema_title', 'Cấu trúc trường')}
    >
      <header className="flex items-center gap-3 border-b bg-muted/30 px-3 py-2.5 sm:px-4">
        {selection && groupState !== null ? (
          <Checkbox
            checked={groupState}
            onCheckedChange={(checked) => selection.setSchema(null, checked === true)}
            aria-label={t('notes.select_schema', 'Chọn thay đổi cấu trúc trường')}
          />
        ) : null}
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold">{t('notes.schema_title', 'Cấu trúc trường')}</h3>
          <p className="text-xs text-muted-foreground">
            {t('notes.schema_desc', 'Thay đổi tên, loại hoặc thứ tự các trường của loại thẻ.')}
          </p>
        </div>
      </header>
      <ul>
        {changes.map((change) => {
          const { title, detail } = describe(t, change)
          const required = Boolean(selection?.schemaRequired(change))
          return (
            <li
              key={change.key}
              className={cn(
                'flex items-start gap-3 border-t px-3 py-2.5 first:border-t-0 sm:px-4',
                change.reviewDecision === 'declined' && 'opacity-60',
              )}
            >
              {selection?.schemaGranularity === 'item' ? (
                <Checkbox
                  className="mt-0.5"
                  checked={required || selection.schemaState(change) === true}
                  disabled={required}
                  onCheckedChange={(checked) => selection.setSchema(change, checked === true)}
                  aria-label={title}
                />
              ) : null}
              <div className="min-w-0 flex-1 space-y-0.5">
                <p className="text-sm">{title}</p>
                {detail ? <p className="break-words text-xs text-muted-foreground">{detail}</p> : null}
                {required ? (
                  <p className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Link2 className="size-3" />
                    {selection?.schemaGranularity === 'item'
                      ? t('notes.schema_required_accept', 'Nhận kèm vì note đã chọn dùng trường này.')
                      : t('notes.schema_required_send', 'Sẽ gửi kèm vì note đã chọn dùng trường này.')}
                  </p>
                ) : null}
              </div>
              {change.hasUnresolvedConflict ? (
                <Badge variant="outline" className="h-5 border-amber-500/40 px-1.5 text-[10px] text-amber-800 dark:text-amber-200">
                  <AlertTriangle />
                  {t('notes.badge_conflict', 'Xung đột')}
                </Badge>
              ) : null}
              {change.reviewDecision ? <ReviewDecisionBadge decision={change.reviewDecision} /> : null}
            </li>
          )
        })}
      </ul>
    </article>
  )
}
