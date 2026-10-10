import '@/shared/config/i18n'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { ListChecks, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { FieldDefItem } from '../../hooks/useNoteTypeFields'
import type { AnswersConversionResult } from '../../hooks/useAnswersConversion'
import { FieldAnswersConversionDialog } from './FieldAnswersConversionDialog'
import { FieldAnswersRestoreDialog } from './FieldAnswersRestoreDialog'

const CONVERTIBLE_TYPES = new Set(['text', 'richtext', 'markdown'])

/** Opens the answers conversion (or its restore) for the saved field. */
export function FieldAnswersConversionEntry({ noteTypeId, field, dirty, onChanged }: {
  noteTypeId: string
  field: FieldDefItem
  /** The field form has unsaved edits; convert from the saved field only. */
  dirty: boolean
  onChanged: () => void
}) {
  const { t } = useTranslation('note_types')
  const [open, setOpen] = useState<'convert' | 'restore' | null>(null)
  const isAnswers = field.field_type === 'answers'
  if (field.identity_role === 'primary' || (!isAnswers && !CONVERTIBLE_TYPES.has(field.field_type))) return null

  const done = (message: string) => () => {
    setOpen(null)
    toast.success(message)
    onChanged()
  }
  return (
    <div className="space-y-1">
      <Button type="button" variant="outline" size="sm" className="h-8 rounded-xl text-xs" disabled={dirty} onClick={() => setOpen(isAnswers ? 'restore' : 'convert')}>
        {isAnswers ? <RotateCcw className="size-3.5" /> : <ListChecks className="size-3.5" />}
        {t(isAnswers ? 'fields.answers_conversion.open_restore' : 'fields.answers_conversion.open')}
      </Button>
      {dirty ? <p className="text-[11px] text-muted-foreground">{t('fields.answers_conversion.save_first')}</p> : null}
      {open === 'convert' ? (
        <FieldAnswersConversionDialog
          open
          onOpenChange={(next) => { if (!next) setOpen(null) }}
          noteTypeId={noteTypeId}
          field={field}
          onConverted={(result: AnswersConversionResult) => done(t('fields.answers_conversion.success', { count: result.note_count }))()}
        />
      ) : null}
      {open === 'restore' ? (
        <FieldAnswersRestoreDialog
          open
          onOpenChange={(next) => { if (!next) setOpen(null) }}
          noteTypeId={noteTypeId}
          field={field}
          onRestored={done(t('fields.answers_conversion.restore_success'))}
        />
      ) : null}
    </div>
  )
}
