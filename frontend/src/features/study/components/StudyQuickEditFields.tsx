import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { NoteFieldEditor } from '@/entities/flashcard'

export type StudyQuickEditFieldDef = {
  name: string
  position: number
  required: boolean
  field_type: 'image' | 'audio' | 'diagram' | 'text' | 'array'
}

export type StudyQuickEditFieldsProps = {
  deckList: Array<{ id: number; name: string; path?: string }>
  deckId: number | null
  onDeckChange: (deckId: number) => void
  fieldDefs: StudyQuickEditFieldDef[]
  fieldValues: Record<string, unknown>
  /** Stored values when the dialog opened; they fix Input vs Textarea per field. */
  initialFieldValues?: Record<string, unknown>
  onFieldValueChange: (fieldName: string, value: string) => void
  onFieldValidityChange?: (fieldName: string, valid: boolean) => void
  resolveMediaUrl: (rawRef: string) => string | undefined
}

export function StudyQuickEditFields({
  deckList,
  deckId,
  onDeckChange,
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
      {/* Destination Deck Selection (if available) */}
      {deckList.length > 0 && (
        <div className="space-y-1.5">
          <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            {t('quick_edit.dest_deck')}
          </Label>
          <NativeSelect
            value={deckId !== null ? String(deckId) : ''}
            onChange={(e) => onDeckChange(Number(e.target.value))}
            className="h-10 sm:h-9 text-base sm:text-sm rounded-lg bg-muted/50"
          >
            {deckList.map((d) => (
              <option key={d.id} value={d.id}>
                {d.path || d.name}
              </option>
            ))}
          </NativeSelect>
        </div>
      )}

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
