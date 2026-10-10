import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { NativeSelect } from '@/components/ui/native-select'
import { MediaFieldPreview } from '@/features/browse/components/MediaFieldPreview'

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
  fieldValues: Record<string, string>
  onFieldValueChange: (fieldName: string, value: string) => void
  resolveMediaUrl: (rawRef: string) => string | undefined
}

export function StudyQuickEditFields({
  deckList,
  deckId,
  onDeckChange,
  fieldDefs,
  fieldValues,
  onFieldValueChange,
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
      {fieldDefs.map((field) => {
        const val = fieldValues[field.name] || ''
        const ft = field.field_type

        if (ft === 'image' || ft === 'audio' || ft === 'diagram') {
          return (
            <MediaFieldPreview
              key={field.name}
              fieldName={field.name}
              fieldType={ft}
              value={val}
              onChange={(v) => onFieldValueChange(field.name, v)}
              required={field.required}
              resolveUrl={resolveMediaUrl}
            />
          )
        }

        const isArray = ft === 'array'
        const isMultiline =
          isArray ||
          val.length > 60 ||
          val.includes('\n') ||
          field.name.toLowerCase().includes('meaning') ||
          field.name.toLowerCase().includes('example') ||
          field.name.toLowerCase().includes('sentence') ||
          field.name.toLowerCase().includes('notes')

        return (
          <div key={field.name} className="space-y-1.5">
            <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center justify-between">
              <span>
                {field.name} {field.required && <span className="text-destructive">*</span>}
              </span>
              {isMultiline && (
                <span className="text-[10px] lowercase font-normal opacity-70">
                  {t('quick_edit.multiline')}
                </span>
              )}
            </Label>
            {isMultiline ? (
              <Textarea
                value={val}
                onChange={(e) => onFieldValueChange(field.name, e.target.value)}
                placeholder={isArray ? t('quick_edit.array_placeholder') : t('quick_edit.enter_field', { fieldName: field.name })}
                className="min-h-20 text-base sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50 focus:bg-background transition-colors"
              />
            ) : (
              <Input
                value={val}
                onChange={(e) => onFieldValueChange(field.name, e.target.value)}
                placeholder={t('quick_edit.enter_field', { fieldName: field.name })}
                className="h-10 sm:h-9 text-base sm:text-sm rounded-lg bg-muted/50 focus:bg-background transition-colors"
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
