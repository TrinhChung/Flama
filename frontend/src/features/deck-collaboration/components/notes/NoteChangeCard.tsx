import { memo, useId, useMemo, useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'
import { diffText } from '@/shared/lib'
import '@/shared/config/i18n'
import {
  buildNoteFieldRows,
  type FieldChange,
  type NoteChange,
  type NoteFieldRow,
} from '../../model/noteChanges'
import type { CheckState } from '../../model/selection'
import type { NoteContext, NoteFieldDef, ReviewDecision } from '../../types'
import { FieldValueView } from './FieldValueView'
import { ReviewDecisionBadge } from './ReviewDecisionBadge'

const TEXT_DIFF_TYPES = new Set(['text', 'richtext', 'markdown', ''])

function rowDiff(row: NoteFieldRow) {
  if (!row.change || !TEXT_DIFF_TYPES.has(row.fieldType.toLowerCase())) return null
  if (typeof row.before !== 'string' || typeof row.after !== 'string') return null
  return diffText(row.before, row.after)
}

function noteDecision(note: NoteChange): ReviewDecision | 'partial' | null {
  const decisions = new Set(note.changes.map((change) => change.reviewDecision))
  if (decisions.has(null)) return null
  if (decisions.size > 1) return 'partial'
  return decisions.has('declined') ? 'declined' : 'accepted'
}

const FieldDiffRow = memo(function FieldDiffRow({
  row,
  selected,
  onToggleField,
}: {
  row: NoteFieldRow
  /** Set only when single fields can be picked. */
  selected?: boolean
  onToggleField?: (change: FieldChange, selected: boolean) => void
}) {
  const { t } = useTranslation('collaboration')
  const diff = useMemo(() => rowDiff(row), [row])
  const change = row.change
  const declined = change?.reviewDecision === 'declined'
  const removed = Boolean(change && change.after === undefined)

  return (
    <div className={cn('border-t first:border-t-0', declined && 'opacity-60')}>
      <div className="flex flex-wrap items-center gap-2 px-3 pt-2.5 sm:px-4">
        {selected !== undefined && onToggleField && change?.itemId ? (
          <Checkbox
            checked={selected}
            onCheckedChange={(checked) => onToggleField(change, checked === true)}
            aria-label={t('notes.select_field', { field: row.name, defaultValue: `Chọn trường ${row.name}` })}
          />
        ) : null}
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {row.name}
        </span>
        {removed ? (
          <Badge variant="outline" className="h-5 border-red-500/35 px-1.5 text-[10px] text-red-700 dark:text-red-300">
            {t('notes.badge_cleared', 'Xóa nội dung')}
          </Badge>
        ) : null}
        {change?.hasUnresolvedConflict ? (
          <Badge variant="outline" className="h-5 border-amber-500/40 px-1.5 text-[10px] text-amber-800 dark:text-amber-200">
            <AlertTriangle />
            {t('notes.badge_conflict', 'Xung đột')}
          </Badge>
        ) : null}
        {change?.reviewDecision ? <ReviewDecisionBadge decision={change.reviewDecision} /> : null}
      </div>
      {change ? (
        <div className="grid sm:grid-cols-2">
          <div className="min-w-0 bg-red-500/6 px-3 py-2 sm:px-4">
            {/* The list shows one colour legend; rows keep a label for screen readers. */}
            <span className="sr-only">{t('notes.column_current', 'Bản hiện tại')}</span>
            <FieldValueView
              value={row.before}
              fieldType={row.fieldType}
              fieldName={row.name}
              side="before"
              compareTo={row.after}
              segments={diff?.before}
            />
          </div>
          <div className="min-w-0 bg-emerald-500/6 px-3 py-2 sm:border-l sm:px-4">
            <span className="sr-only">{t('notes.column_proposed', 'Bản đề xuất')}</span>
            <FieldValueView
              value={row.after}
              fieldType={row.fieldType}
              fieldName={row.name}
              side="after"
              compareTo={row.before}
              segments={diff?.after}
            />
          </div>
        </div>
      ) : (
        <div className="grid text-muted-foreground sm:grid-cols-2">
          <div className="min-w-0 px-3 py-2 sm:px-4">
            <FieldValueView value={row.before} fieldType={row.fieldType} fieldName={row.name} />
          </div>
          <div className="hidden min-w-0 border-l px-4 py-2 sm:block">
            <FieldValueView value={row.after} fieldType={row.fieldType} fieldName={row.name} />
          </div>
        </div>
      )}
    </div>
  )
})

/**
 * One note in git-like split view: current note on the left, proposed note
 * on the right. Unchanged fields stay folded until asked for.
 */
export type NoteChangeCardProps = {
  note: NoteChange
  fieldDefs: NoteFieldDef[]
  context?: NoteContext | null
  /** Omit when nothing can be picked. */
  granularity?: 'note' | 'field'
  checked?: CheckState
  /** One '1'/'0' per change, for picking single fields. */
  fieldMask?: string
  onToggleNote?: (note: NoteChange, selected: boolean) => void
  onToggleField?: (change: FieldChange, selected: boolean) => void
}

export const NoteChangeCard = memo(function NoteChangeCard({
  note,
  fieldDefs,
  context,
  granularity,
  checked,
  fieldMask = '',
  onToggleNote,
  onToggleField,
}: NoteChangeCardProps) {
  const { t } = useTranslation('collaboration')
  const [showAll, setShowAll] = useState(false)
  const bodyId = useId()
  const rows = useMemo(() => buildNoteFieldRows(note, fieldDefs, context), [note, fieldDefs, context])
  const changedRows = rows.filter((row) => row.change)
  const canExpand = Boolean(context?.values) && rows.length > changedRows.length
  const visibleRows = showAll && canExpand ? rows : changedRows
  const label = note.label || context?.label || t('notes.untitled_note', 'Note chưa có tên')
  const decision = noteDecision(note)
  const changeIndex = useMemo(
    () => new Map(note.changes.map((change, index) => [change, index])),
    [note.changes],
  )

  return (
    <article
      className={cn(
        'overflow-hidden rounded-xl border bg-card shadow-xs',
        granularity && checked === false && 'border-dashed bg-muted/20',
      )}
      style={{ contentVisibility: 'auto', containIntrinsicSize: '240px' }}
      aria-label={label}
    >
      <header className="flex flex-wrap items-center gap-3 border-b bg-muted/30 px-3 py-2.5 sm:px-4">
        {granularity && onToggleNote ? (
          <Checkbox
            checked={checked}
            onCheckedChange={(next) => onToggleNote(note, next === true)}
            aria-label={t('notes.select_note', { note: label, defaultValue: `Chọn note ${label}` })}
          />
        ) : null}
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold">{label}</h3>
          <p className="text-xs text-muted-foreground">
            {t('notes.changed_fields', {
              count: note.changes.length,
              defaultValue: `${note.changes.length} trường thay đổi`,
            })}
          </p>
        </div>
        {decision === 'partial' ? (
          <Badge variant="outline" className="border-amber-500/40 text-amber-800 dark:text-amber-200">
            {t('notes.decision_partial', 'Nhận một phần')}
          </Badge>
        ) : decision ? (
          <ReviewDecisionBadge decision={decision} />
        ) : null}
        {canExpand ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-expanded={showAll}
            aria-controls={bodyId}
            onClick={() => setShowAll((current) => !current)}
          >
            {showAll ? <ChevronUp /> : <ChevronDown />}
            {showAll
              ? t('notes.btn_changed_only', 'Chỉ trường đã sửa')
              : t('notes.btn_show_all_fields', {
                  count: rows.length,
                  defaultValue: `Hiện đủ ${rows.length} trường`,
                })}
          </Button>
        ) : null}
      </header>
      <div id={bodyId}>
        {visibleRows.map((row) => {
          const index = row.change ? changeIndex.get(row.change) : undefined
          return (
            <FieldDiffRow
              key={row.name}
              row={row}
              selected={granularity === 'field' && index !== undefined ? fieldMask[index] === '1' : undefined}
              onToggleField={onToggleField}
            />
          )
        })}
      </div>
    </article>
  )
})
