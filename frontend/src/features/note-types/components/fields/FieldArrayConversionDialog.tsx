import '@/shared/config/i18n'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowRight, Check, Download, LoaderCircle, Pencil, RotateCcw } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { MAX_CONVERSION_NOTES, SPLIT_PRESETS } from '../../lib/arrayConversion'
import { knownConversionError } from '../../lib/conversionError'
import { useArrayConversion, type ArrayConversionResult, type ConversionRow } from '../../hooks/useArrayConversion'
import type { FieldDefItem } from '../../hooks/useNoteTypeFields'

const PAGE_SIZE = 20

function ConversionRowItem({ row, onEdit }: { row: ConversionRow; onEdit: (text: string | undefined) => void }) {
  const { t } = useTranslation('note_types')
  const [editing, setEditing] = useState(false)
  return (
    <li className="space-y-2 rounded-xl border border-border/70 p-3">
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] sm:items-start">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">{t('fields.array_conversion.original')}</p>
          <p className="line-clamp-3 whitespace-pre-line break-words text-xs text-muted-foreground">{row.original || '—'}</p>
        </div>
        <ArrowRight className="hidden size-4 text-muted-foreground sm:mt-5 sm:block" aria-hidden="true" />
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase text-muted-foreground">{t('fields.array_conversion.result')}</p>
          {row.items.length ? (
            <ul className="flex flex-wrap gap-1">
              {row.items.map((item) => (
                <li key={item} className="rounded-md bg-primary/10 px-1.5 py-0.5 text-xs font-medium text-foreground">{item}</li>
              ))}
            </ul>
          ) : (
            <p className="text-xs italic text-muted-foreground">{t('fields.array_conversion.no_items')}</p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {row.flags.map((flag) => (
          <Badge key={flag} variant="outline" className="border-amber-400/60 text-[11px] text-amber-700 dark:text-amber-400">
            {t(`fields.array_conversion.flag_${flag}`)}
          </Badge>
        ))}
        {row.edited ? <Badge variant="secondary" className="text-[11px]">{t('fields.array_conversion.edited')}</Badge> : null}
        <div className="ml-auto flex gap-1">
          {row.edited ? (
            <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={() => { onEdit(undefined); setEditing(false) }}>
              <RotateCcw className="size-3.5" />{t('fields.array_conversion.reset_edit')}
            </Button>
          ) : null}
          <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setEditing((value) => !value)} aria-expanded={editing}>
            <Pencil className="size-3.5" />{t('fields.array_conversion.edit')}
          </Button>
        </div>
      </div>
      {editing ? (
        <Textarea
          aria-label={t('fields.array_conversion.edit_hint')}
          placeholder={t('fields.array_conversion.edit_hint')}
          defaultValue={row.value}
          onChange={(event) => onEdit(event.target.value)}
          className="min-h-20 text-sm"
        />
      ) : null}
    </li>
  )
}

/** Split, preview, back up and convert a field of an owned NoteType to an array. */
export function FieldArrayConversionDialog({ open, onOpenChange, noteTypeId, field, onConverted }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  noteTypeId: string
  field: FieldDefItem
  onConverted: (result: ArrayConversionResult) => void
}) {
  const { t } = useTranslation('note_types')
  const conversion = useArrayConversion({ noteTypeId, field, enabled: open, onDone: onConverted })
  const { source, rows, summary, write } = conversion
  const [flaggedOnly, setFlaggedOnly] = useState(true)
  const [page, setPage] = useState(0)
  const showFlagged = flaggedOnly && summary.flagged > 0
  const visible = useMemo(() => (showFlagged ? rows.filter((row) => row.flags.length > 0) : rows), [rows, showFlagged])
  const pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  const currentPage = Math.min(page, pages - 1)
  const pageRows = visible.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE)
  const blocked = source.data && !source.data.convertible ? source.data.blocked_reason : null
  const tooMany = summary.total > MAX_CONVERSION_NOTES
  const knownError = knownConversionError(write.error)
  const writeError = write.error
    ? knownError
      ? t(`fields.array_conversion.error_${knownError}`)
      : t('fields.array_conversion.error_generic', { message: write.error.message })
    : null
  const notesChanged = knownError === 'NOTES_CHANGED'

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!write.isPending) onOpenChange(next) }}>
      <DialogContent className="flex max-h-[90vh] flex-col gap-4 sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t('fields.array_conversion.title', { name: field.name })}</DialogTitle>
          <DialogDescription>{t('fields.array_conversion.description')}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {source.isPending ? (
            <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />{t('fields.array_conversion.loading')}</p>
          ) : source.error ? (
            <p role="alert" className="text-sm text-destructive">{source.error.message}</p>
          ) : blocked ? (
            <p role="alert" className="text-sm text-destructive">
              {t(blocked === 'PRIMARY_FIELD' ? 'fields.array_conversion.blocked_PRIMARY_FIELD' : 'fields.array_conversion.blocked_UNSUPPORTED_FIELD_TYPE')}
            </p>
          ) : (
            <>
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">{t('fields.array_conversion.presets_label')}</legend>
                <div className="grid gap-2 sm:grid-cols-2">
                  {SPLIT_PRESETS.map((preset) => (
                    <Label key={preset.id} className="flex cursor-pointer items-start gap-2 text-xs font-normal">
                      <Checkbox checked={conversion.presets.has(preset.id)} onCheckedChange={() => { conversion.togglePreset(preset.id); setPage(0) }} />
                      <span>
                        {t(`fields.array_conversion.preset_${preset.id}`)}
                        {preset.id === 'middle_dot' ? <span className="block text-muted-foreground">{t('fields.array_conversion.middle_dot_hint')}</span> : null}
                      </span>
                    </Label>
                  ))}
                </div>
              </fieldset>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium" role="status">{t('fields.array_conversion.summary', summary)}</p>
                {summary.flagged > 0 ? (
                  <div className="flex gap-1" role="group">
                    <Button type="button" size="sm" variant={showFlagged ? 'secondary' : 'ghost'} className="h-7 text-xs" aria-pressed={showFlagged} onClick={() => { setFlaggedOnly(true); setPage(0) }}>
                      {t('fields.array_conversion.show_flagged')}
                    </Button>
                    <Button type="button" size="sm" variant={showFlagged ? 'ghost' : 'secondary'} className="h-7 text-xs" aria-pressed={!showFlagged} onClick={() => { setFlaggedOnly(false); setPage(0) }}>
                      {t('fields.array_conversion.show_all')}
                    </Button>
                  </div>
                ) : null}
              </div>
              {pageRows.length ? (
                <ul className="space-y-2" aria-label={t('fields.array_conversion.result')}>
                  {pageRows.map((row) => (
                    <ConversionRowItem key={row.noteId} row={row} onEdit={(text) => conversion.setOverride(row.noteId, text)} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">{t('fields.array_conversion.no_rows')}</p>
              )}
              {pages > 1 ? (
                <div className="flex items-center justify-center gap-2">
                  <Button type="button" size="sm" variant="outline" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>{t('fields.array_conversion.previous')}</Button>
                  <span className="text-xs tabular-nums text-muted-foreground">{t('fields.array_conversion.page', { page: currentPage + 1, pages })}</span>
                  <Button type="button" size="sm" variant="outline" disabled={currentPage >= pages - 1} onClick={() => setPage(currentPage + 1)}>{t('fields.array_conversion.next')}</Button>
                </div>
              ) : null}
            </>
          )}
        </div>
        {tooMany ? (
          <p role="alert" className="text-sm text-destructive">
            {t('fields.array_conversion.too_many_notes', { count: summary.total, max: MAX_CONVERSION_NOTES })}
          </p>
        ) : null}
        {writeError ? (
          <div role="alert" className="flex flex-wrap items-center gap-2 text-sm text-destructive">
            <span>{writeError}</span>
            {notesChanged ? (
              <Button type="button" size="sm" variant="outline" onClick={() => { write.reset(); void source.refetch() }}>{t('fields.array_conversion.reload')}</Button>
            ) : null}
          </div>
        ) : null}
        <DialogFooter className="flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center">
            <Button type="button" variant="outline" disabled={!source.data || Boolean(blocked)} onClick={conversion.downloadBackup}>
              {conversion.backupReady ? <Check className="size-4 text-emerald-600" /> : <Download className="size-4" />}
              {t(conversion.backupReady ? 'fields.array_conversion.backup_done' : 'fields.array_conversion.backup')}
            </Button>
            {!conversion.backupReady ? <p className="max-w-xs text-[11px] text-muted-foreground">{t('fields.array_conversion.backup_required')}</p> : null}
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" disabled={write.isPending} onClick={() => onOpenChange(false)}>{t('fields.array_conversion.cancel')}</Button>
            <Button
              type="button"
              disabled={!source.data || Boolean(blocked) || tooMany || !conversion.backupReady || write.isPending}
              onClick={conversion.apply}
              className={cn(write.isPending && 'cursor-wait')}
            >
              {write.isPending ? <LoaderCircle className="size-4 animate-spin" /> : null}
              {write.isPending ? t('fields.array_conversion.applying') : t('fields.array_conversion.apply', { count: summary.total })}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
