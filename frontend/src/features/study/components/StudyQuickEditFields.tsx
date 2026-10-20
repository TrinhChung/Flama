import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { NoteFieldEditor } from '@/entities/flashcard'

export type StudyQuickEditFieldDef = {
  name: string
  position: number
  required: boolean
  field_type: 'image' | 'audio' | 'diagram' | 'text' | 'array'
}

export type StudyQuickEditFieldsProps = {
  fieldDefs: StudyQuickEditFieldDef[]
  fieldValues: Record<string, unknown>
  /** Stored values when the dialog opened; they fix Input vs Textarea per field. */
  initialFieldValues?: Record<string, unknown>
  onFieldValueChange: (fieldName: string, value: string) => void
  onFieldValidityChange?: (fieldName: string, valid: boolean) => void
  resolveMediaUrl: (rawRef: string) => string | undefined
}

export function StudyQuickEditFields({
  fieldDefs,
  fieldValues,
  initialFieldValues,
  onFieldValueChange,
  onFieldValidityChange,
  resolveMediaUrl,
}: StudyQuickEditFieldsProps) {
  const { t } = useTranslation('study')

  return (
    <div className="space-y-3.5 sm:space-y-4">
      {/* Dynamic Note Fields */}
      {fieldDefs.map((field) => (
        <NoteFieldEditor
          key={field.name}
          field={field}
          value={fieldValues[field.name]}
          initialValue={initialFieldValues?.[field.name] ?? fieldValues[field.name]}
          onChange={onFieldValueChange}
          onValidityChange={onFieldValidityChange}
          resolveMediaUrl={resolveMediaUrl}
          placeholder={t('quick_edit.enter_field', { fieldName: field.name })}
          arrayPlaceholder={t('quick_edit.array_placeholder')}
          multilineHint={t('quick_edit.multiline')}
          density="touch"
        />
      ))}
    </div>
  )
}
