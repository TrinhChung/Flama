import { ShieldAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import '@/shared/config/i18n'
import type { ChangeRequestConflict, ConflictResolutionInput } from '../../types'

function formatValue(value: unknown, noDataText: string, nullText: string, emptyText: string) {
  if (value === undefined) return noDataText
  if (value === null) return nullText
  if (value === '') return emptyText
  if (typeof value === 'string') return value
  const serialized = JSON.stringify(value, null, 2)
  return serialized === undefined ? String(value) : serialized
}

function parseManualValue(value: string) {
  const trimmed = value.trim()
  if (!trimmed) return ''
  try {
    return JSON.parse(trimmed) as unknown
  } catch {
    return value
  }
}

function ConflictValue({
  label,
  value,
  tone,
  noDataText,
  nullText,
  emptyText,
}: {
  label: string
  value: unknown
  tone: 'base' | 'mine' | 'upstream'
  noDataText: string
  nullText: string
  emptyText: string
}) {
  const toneClass = {
    base: 'border-border bg-muted/30',
    mine: 'border-blue-500/25 bg-blue-500/6',
    upstream: 'border-emerald-500/25 bg-emerald-500/6',
  }[tone]
  return (
    <div className={`overflow-hidden rounded-lg border ${toneClass}`}>
      <div className="border-b px-3 py-2 text-xs font-semibold">{label}</div>
      <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words p-3 text-xs font-mono">
        {formatValue(value, noDataText, nullText, emptyText)}
      </pre>
    </div>
  )
}

export function ContributionConflictCard({
  conflict,
  manualValue,
  disabled,
  onManualValueChange,
  onResolve,
}: {
  conflict: ChangeRequestConflict
  manualValue: string
  disabled: boolean
  onManualValueChange: (value: string) => void
  onResolve: (input: ConflictResolutionInput) => void
}) {
  const { t } = useTranslation('collaboration')

  const noDataText = t('diff.value_no_data', '(không có dữ liệu)')
  const nullText = t('diff.value_null', '(null)')
  const emptyText = t('diff.value_empty', '(chuỗi rỗng)')

  return (
    <Card className="overflow-hidden border-amber-500/35">
      <CardHeader className="bg-amber-500/8">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-sm">
              {conflict.conflict_type.replaceAll('_', ' ')} · {conflict.source_ref_id || 'field'}
            </CardTitle>
            <CardDescription>
              {t(
                'detail.conflict_upstream_local_title',
                'Upstream và bản local cùng thay đổi dữ liệu này.',
              )}
            </CardDescription>
          </div>
          <Badge
            variant="outline"
            className="border-amber-500/40 text-amber-700 dark:text-amber-300"
          >
            <ShieldAlert />
            {t('detail.decision_needed', 'Cần quyết định')}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        <div className="grid gap-3 xl:grid-cols-3">
          <ConflictValue
            label={t('detail.base_label', 'Base')}
            value={conflict.base_value}
            tone="base"
            noDataText={noDataText}
            nullText={nullText}
            emptyText={emptyText}
          />
          <ConflictValue
            label={t('detail.mine_label', 'Bản của tôi')}
            value={conflict.local_value}
            tone="mine"
            noDataText={noDataText}
            nullText={nullText}
            emptyText={emptyText}
          />
          <ConflictValue
            label={t('detail.upstream_label', 'Deck gốc hiện tại')}
            value={conflict.upstream_value}
            tone="upstream"
            noDataText={noDataText}
            nullText={nullText}
            emptyText={emptyText}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            onClick={() => onResolve({ resolution_mode: 'keep_mine' })}
          >
            {t('detail.btn_keep_mine', 'Giữ bản của tôi')}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={disabled}
            onClick={() => onResolve({ resolution_mode: 'keep_upstream' })}
          >
            {t('detail.btn_keep_upstream', 'Nhận bản upstream')}
          </Button>
        </div>
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <div className="space-y-2">
            <Label htmlFor={`manual-${conflict.id}`}>
              {t('detail.manual_value_label', 'Giá trị thủ công')}
            </Label>
            <Textarea
              id={`manual-${conflict.id}`}
              value={manualValue}
              onChange={(event) => onManualValueChange(event.target.value)}
              placeholder={t(
                'detail.manual_value_placeholder',
                'Nhập text hoặc JSON hợp lệ…',
              )}
              rows={2}
              disabled={disabled}
            />
          </div>
          <Button
            type="button"
            variant="secondary"
            disabled={disabled}
            onClick={() =>
              onResolve({
                resolution_mode: 'manual',
                resolved_value: parseManualValue(manualValue),
              })
            }
          >
            {t('detail.btn_use_value', 'Dùng giá trị này')}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
