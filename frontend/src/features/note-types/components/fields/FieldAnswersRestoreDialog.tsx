import '@/shared/config/i18n'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LoaderCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { parseAnswersBackup, type AnswersBackup } from '../../lib/answersConversion'
import { useAnswersRestore, type AnswersConversionResult } from '../../hooks/useAnswersConversion'
import type { FieldDefItem } from '../../hooks/useNoteTypeFields'

/** Restore an answers field to its original type and values from a backup file. */
export function FieldAnswersRestoreDialog({ open, onOpenChange, noteTypeId, field, onRestored }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  noteTypeId: string
  field: FieldDefItem
  onRestored: (result: AnswersConversionResult) => void
}) {
  const { t } = useTranslation('note_types')
  const fileId = useId()
  const restore = useAnswersRestore({ noteTypeId, field, enabled: open, onDone: onRestored })
  const [backup, setBackup] = useState<AnswersBackup | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const plan = backup && restore.source.data ? restore.plan(backup) : null

  const readFile = async (file: File | undefined) => {
    setBackup(null)
    setFileError(null)
    if (!file) return
    try {
      const parsed = parseAnswersBackup(JSON.parse(await file.text()), { noteTypeId, fieldId: field.id })
      if (parsed.ok) setBackup(parsed.backup)
      else setFileError(t(parsed.error === 'other_field' ? 'fields.answers_conversion.restore_other_field' : 'fields.answers_conversion.restore_invalid'))
    } catch {
      setFileError(t('fields.answers_conversion.restore_invalid'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!restore.write.isPending) onOpenChange(next) }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('fields.answers_conversion.restore_title', { name: field.name })}</DialogTitle>
          <DialogDescription>{t('fields.answers_conversion.restore_description')}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor={fileId}>{t('fields.answers_conversion.restore_file')}</Label>
            <input id={fileId} type="file" accept="application/json,.json" className="block w-full text-sm" onChange={(event) => { void readFile(event.target.files?.[0]) }} />
          </div>
          {fileError ? <p role="alert" className="text-sm text-destructive">{fileError}</p> : null}
          {restore.source.isPending ? <p role="status" className="text-sm text-muted-foreground">{t('fields.answers_conversion.loading')}</p> : null}
          {plan && backup ? (
            <p role="status" className="text-sm">
              {t('fields.answers_conversion.restore_summary', {
                restored: plan.restored,
                kept: plan.kept,
                gone: plan.gone,
                type: t(`setup.types.${backup.original_type}.label`),
              })}
            </p>
          ) : null}
          {restore.write.error ? <p role="alert" className="text-sm text-destructive">{restore.write.error.message}</p> : null}
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" disabled={restore.write.isPending} onClick={() => onOpenChange(false)}>{t('fields.answers_conversion.cancel')}</Button>
          <Button type="button" disabled={!plan || restore.write.isPending} onClick={() => { if (plan) restore.write.mutate(plan.body) }}>
            {restore.write.isPending ? <LoaderCircle className="size-4 animate-spin" /> : null}
            {t('fields.answers_conversion.restore_apply')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
