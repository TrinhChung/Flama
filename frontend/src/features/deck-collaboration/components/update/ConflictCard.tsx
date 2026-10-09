import { Check, LoaderCircle, ShieldAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import '@/shared/config/i18n'
import type { UpdateConflict, UpdateConflictResolution } from '../../types'

function valuePreview(
  value: unknown,
  noDataText: string,
  nullText: string,
  emptyText: string,
): string {
  if (value === null) return nullText
  if (value === undefined) return noDataText
  if (value === '') return emptyText
  if (typeof value === 'string') return value
  const serialized = JSON.stringify(value, null, 2)
  return serialized === undefined ? String(value) : serialized
}

export function ConflictCard({
  conflict,
  isSaving,
  pendingResolution,
  onResolve,
}: {
  conflict: UpdateConflict
  isSaving: boolean
  pendingResolution?: UpdateConflictResolution
  onResolve: (resolution: UpdateConflictResolution) => void
}) {
  const { t } = useTranslation('collaboration')

  const resolution =
    conflict.resolution_mode === 'keep_mine' ||
    conflict.resolution_mode === 'keep_upstream'
      ? conflict.resolution_mode
      : undefined
  const isResolved = Boolean(resolution && conflict.resolved_at)
  const hasBase = conflict.base_value !== undefined

  const noDataText = t('diff.value_no_data', '(không có dữ liệu)')
  const nullText = t('diff.value_null', '(null)')
  const emptyText = t('diff.value_empty', '(chuỗi rỗng)')

  return (
    <Card
      className={cn(
        'overflow-hidden',
        isResolved ? 'border-emerald-500/35' : 'border-amber-500/35',
      )}
    >
      <CardHeader className={isResolved ? 'bg-emerald-500/8' : 'bg-amber-500/8'}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-sm font-bold">
              {conflict.note_label || 'Note'} / {conflict.field_name || 'Field'}
            </CardTitle>
            <CardDescription className="text-xs">
              {t(
                'update.conflict_card.description',
                'Bản sửa đổi cá nhân (Local) và phiên bản mới từ tác giả (Upstream) cùng thay đổi trường này so với snapshot gốc.',
              )}
            </CardDescription>
          </div>
          <Badge
            variant="outline"
            className={cn(
              isResolved
                ? 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300 bg-emerald-500/10'
                : 'border-amber-500/40 text-amber-700 dark:text-amber-300 bg-amber-500/10',
            )}
          >
            {isResolved ? (
              <Check className="size-3 mr-1" />
            ) : (
              <ShieldAlert className="size-3 mr-1" />
            )}
            {isResolved
              ? t('update.conflict_card.resolved_badge', 'Đã xử lý')
              : t('update.conflict_card.unresolved_badge', 'Xung đột 3-Way')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        <div
          className={cn(
            'grid gap-3',
            hasBase ? 'grid-cols-1 md:grid-cols-3' : 'grid-cols-1 md:grid-cols-2',
          )}
        >
          {hasBase ? (
            <div className="overflow-hidden rounded-lg border border-border/70 bg-muted/40">
              <div className="border-b border-border/70 px-3 py-2 text-xs font-semibold text-muted-foreground flex items-center justify-between">
                <span>{t('update.conflict_card.base_label', '1. Giá trị ban đầu (Base)')}</span>
                <span className="text-[10px] text-muted-foreground/70">
                  {t('update.conflict_card.base_sub', 'Snapshot trước')}
                </span>
              </div>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs text-muted-foreground font-mono">
                {valuePreview(conflict.base_value, noDataText, nullText, emptyText)}
              </pre>
            </div>
          ) : null}

          <div className="overflow-hidden rounded-lg border border-blue-500/25 bg-blue-500/6">
            <div className="border-b border-blue-500/20 px-3 py-2 text-xs font-semibold text-blue-700 dark:text-blue-300 flex items-center justify-between">
              <span>
                {hasBase
                  ? t('update.conflict_card.local_label', '2. Bản sửa của bạn (Local)')
                  : t('update.conflict_card.local_label_nobase', 'Bản chỉnh sửa của tôi')}
              </span>
              <span className="text-[10px] text-blue-600/70">
                {t('update.conflict_card.local_sub', 'Máy của bạn')}
              </span>
            </div>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs font-mono">
              {valuePreview(conflict.local_value, noDataText, nullText, emptyText)}
            </pre>
          </div>

          <div className="overflow-hidden rounded-lg border border-emerald-500/25 bg-emerald-500/6">
            <div className="border-b border-emerald-500/20 px-3 py-2 text-xs font-semibold text-emerald-700 dark:text-emerald-300 flex items-center justify-between">
              <span>
                {hasBase
                  ? t('update.conflict_card.upstream_label', '3. Bản phát hành mới (Upstream)')
                  : t('update.conflict_card.upstream_label_nobase', 'Bản cập nhật từ tác giả')}
              </span>
              <span className="text-[10px] text-emerald-600/70">
                {t('update.conflict_card.upstream_sub', 'Tác giả deck')}
              </span>
            </div>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs font-mono">
              {valuePreview(conflict.upstream_value, noDataText, nullText, emptyText)}
            </pre>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant={resolution === 'keep_mine' ? 'default' : 'outline'}
              size="sm"
              disabled={isSaving}
              aria-pressed={resolution === 'keep_mine'}
              onClick={() => onResolve('keep_mine')}
              className={
                resolution === 'keep_mine'
                  ? 'bg-blue-600 hover:bg-blue-700 text-white'
                  : ''
              }
            >
              {isSaving && pendingResolution === 'keep_mine' ? (
                <LoaderCircle className="animate-spin size-3.5 mr-1" />
              ) : resolution === 'keep_mine' ? (
                <Check className="size-3.5 mr-1" />
              ) : null}
              {t('update.conflict_card.btn_keep_mine', 'Giữ bản của tôi')}
            </Button>
            <Button
              type="button"
              variant={resolution === 'keep_upstream' ? 'default' : 'outline'}
              size="sm"
              disabled={isSaving}
              aria-pressed={resolution === 'keep_upstream'}
              onClick={() => onResolve('keep_upstream')}
              className={
                resolution === 'keep_upstream'
                  ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  : ''
              }
            >
              {isSaving && pendingResolution === 'keep_upstream' ? (
                <LoaderCircle className="animate-spin size-3.5 mr-1" />
              ) : resolution === 'keep_upstream' ? (
                <Check className="size-3.5 mr-1" />
              ) : null}
              {t('update.conflict_card.btn_keep_upstream', 'Nhận bản cập nhật')}
            </Button>
          </div>
          {isResolved ? (
            <span className="text-xs text-muted-foreground">
              {t('update.conflict_card.selected_choice', 'Đã chọn:')}{' '}
              <strong className="text-foreground">
                {resolution === 'keep_mine'
                  ? t('update.conflict_card.choice_mine', 'Giữ bản của tôi')
                  : t('update.conflict_card.choice_upstream', 'Dùng bản tác giả')}
              </strong>
            </span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
