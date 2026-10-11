import '@/shared/config/i18n'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { ListChecks, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { FieldDefItem } from '../../hooks/useNoteTypeFields'
import type { ArrayConversionResult } from '../../hooks/useArrayConversion'
import { FieldArrayConversionDialog } from './FieldArrayConversionDialog'
import { FieldArrayRestoreDialog } from './FieldArrayRestoreDialog'

const CONVERTIBLE_TYPES = new Set(['text', 'richtext', 'markdown'])

/** Opens the array conversion (or its restore) for the saved field. */
export function FieldArrayConversionEntry({ noteTypeId, field, dirty, onChanged }: {
  noteTypeId: string
  field: FieldDefItem
  /** The field form has unsaved edits; convert from the saved field only. */
  dirty: boolean
  onChanged: () => void
}) {
  const { t } = useTranslation('note_types')
  const [open, setOpen] = useState<'convert' | 'restore' | null>(null)
  const isArray = field.field_type === 'array'
  if (field.identity_role === 'primary' || (!isArray && !CONVERTIBLE_TYPES.has(field.field_type))) return null

  const done = (message: string) => () => {
    setOpen(null)
    toast.success(message)
    onChanged()
  }
  return (
    <div className="space-y-1">
      <Button type="button" variant="outline" size="sm" className="h-8 rounded-xl text-xs" disabled={dirty} onClick={() => setOpen(isArray ? 'restore' : 'convert')}>
        {isArray ? <RotateCcw className="size-3.5" /> : <ListChecks className="size-3.5" />}
        {t(isArray ? 'fields.array_conversion.open_restore' : 'fields.array_conversion.open')}
      </Button>
      {dirty ? <p className="text-[11px] text-muted-foreground">{t('fields.array_conversion.save_first')}</p> : null}
      {open === 'convert' ? (
        <FieldArrayConversionDialog
          open
          onOpenChange={(next) => { if (!next) setOpen(null) }}
          noteTypeId={noteTypeId}
          field={field}
          onConverted={(result: ArrayConversionResult) => done(t('fields.array_conversion.success', { count: result.note_count }))()}
        />
      ) : null}
      {open === 'restore' ? (
        <FieldArrayRestoreDialog
          open
          onOpenChange={(next) => { if (!next) setOpen(null) }}
          noteTypeId={noteTypeId}
          field={field}
          onRestored={done(t('fields.array_conversion.restore_success'))}
        />
      ) : null}
    </div>
  )
}
