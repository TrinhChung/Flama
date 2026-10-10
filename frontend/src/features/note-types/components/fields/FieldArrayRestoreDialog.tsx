import '@/shared/config/i18n'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LoaderCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { parseArrayBackup, type ArrayBackup } from '../../lib/arrayConversion'
import { knownConversionError } from '../../lib/conversionError'
import { useArrayRestore, type ArrayConversionResult } from '../../hooks/useArrayConversion'
import type { FieldDefItem } from '../../hooks/useNoteTypeFields'

/** Restore an array field to its original type and values from a backup file. */
export function FieldArrayRestoreDialog({ open, onOpenChange, noteTypeId, field, onRestored }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  noteTypeId: string
  field: FieldDefItem
  onRestored: (result: ArrayConversionResult) => void
}) {
  const { t } = useTranslation('note_types')
  const fileId = useId()
  const restore = useArrayRestore({ noteTypeId, field, enabled: open, onDone: onRestored })
  const [backup, setBackup] = useState<ArrayBackup | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const plan = backup && restore.source.data ? restore.plan(backup) : null
  const knownError = knownConversionError(restore.write.error)
  const writeError = restore.write.error
    ? knownError
      ? t(`fields.array_conversion.error_${knownError}`)
      : t('fields.array_conversion.error_generic', { message: restore.write.error.message })
    : null

  const readFile = async (file: File | undefined) => {
    setBackup(null)
    setFileError(null)
    if (!file) return
    try {
      const parsed = parseArrayBackup(JSON.parse(await file.text()), { noteTypeId, fieldId: field.id })
      if (parsed.ok) setBackup(parsed.backup)
      else setFileError(t(parsed.error === 'other_field' ? 'fields.array_conversion.restore_other_field' : 'fields.array_conversion.restore_invalid'))
    } catch {
      setFileError(t('fields.array_conversion.restore_invalid'))
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!restore.write.isPending) onOpenChange(next) }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('fields.array_conversion.restore_title', { name: field.name })}</DialogTitle>
          <DialogDescription>{t('fields.array_conversion.restore_description')}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor={fileId}>{t('fields.array_conversion.restore_file')}</Label>
            <input id={fileId} type="file" accept="application/json,.json" className="block w-full text-sm" onChange={(event) => { void readFile(event.target.files?.[0]) }} />
          </div>
          {fileError ? <p role="alert" className="text-sm text-destructive">{fileError}</p> : null}
          {restore.source.isPending ? <p role="status" className="text-sm text-muted-foreground">{t('fields.array_conversion.loading')}</p> : null}
          {plan && backup ? (
            <p role="status" className="text-sm">
              {t('fields.array_conversion.restore_summary', {
                restored: plan.restored,
                kept: plan.kept,
                gone: plan.gone,
                type: t(`setup.types.${backup.original_type}.label`),
              })}
            </p>
          ) : null}
          {writeError ? <p role="alert" className="text-sm text-destructive">{writeError}</p> : null}
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" disabled={restore.write.isPending} onClick={() => onOpenChange(false)}>{t('fields.array_conversion.cancel')}</Button>
          <Button type="button" disabled={!plan || restore.write.isPending} onClick={() => { if (plan) restore.write.mutate(plan.body) }}>
            {restore.write.isPending ? <LoaderCircle className="size-4 animate-spin" /> : null}
            {t('fields.array_conversion.restore_apply')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
