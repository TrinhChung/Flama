import { memo, useCallback, useState, type ReactNode } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { fieldValueEditorText, isArrayField } from '@/lib/arrayField'
import {
  fieldShapePrefersMultiline,
  normalizedFieldType,
  valuePrefersMultiline,
  type NoteFieldLayoutField,
} from '../lib/noteFieldLayout'
import { ArrayFieldInput } from './ArrayFieldInput'
import { MediaFieldPreview } from './MediaFieldPreview'

const MEDIA_FIELD_TYPES = new Set(['image', 'audio', 'diagram'])

export type NoteFieldEditorDensity = 'compact' | 'touch'

export interface NoteFieldEditorField extends NoteFieldLayoutField {
  required?: boolean
}

export interface NoteFieldEditorProps {
  field: NoteFieldEditorField
  value: unknown
  /**
   * The stored value when the editor opened. Together with the field type and
   * name it picks Input or Textarea once at mount, so typing never swaps (and
   * remounts) the element under the caret.
   */
  initialValue?: unknown
  onChange: (fieldName: string, value: string) => void
  onValidityChange?: (fieldName: string, valid: boolean) => void
  resolveMediaUrl?: (raw: string) => string | undefined
  mediaUploadDisabled?: boolean
  placeholder?: string
  arrayPlaceholder?: string
  /** Shown beside the label of multiline text fields (touch density only). */
  multilineHint?: ReactNode
  density?: NoteFieldEditorDensity
}

const INPUT_CLASS: Record<NoteFieldEditorDensity, string> = {
  compact: 'h-9 text-xs sm:text-sm rounded-lg bg-muted/50',
  touch: 'h-10 sm:h-9 text-base sm:text-sm rounded-lg bg-muted/50 focus:bg-background transition-colors',
}

const TEXTAREA_CLASS: Record<NoteFieldEditorDensity, string> = {
  compact: 'min-h-20 text-xs sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50',
  touch: 'min-h-20 text-base sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50 focus:bg-background transition-colors',
}

const LABEL_CLASS = 'text-xs font-semibold text-muted-foreground uppercase tracking-wide'

/** One editor for a note field: media preview, native array input or plain text. */
export const NoteFieldEditor = memo(function NoteFieldEditor({
  field,
  value,
  initialValue,
  onChange,
  onValidityChange,
  resolveMediaUrl,
  mediaUploadDisabled,
  placeholder,
  arrayPlaceholder,
  multilineHint,
  density = 'compact',
}: NoteFieldEditorProps) {
  const fieldName = field.name
  const ft = normalizedFieldType(field)
  // Locked at mount: the live value must not decide the element type.
  const [initialValueIsLong] = useState(() => valuePrefersMultiline(initialValue))
  const handleChange = useCallback((next: string) => onChange(fieldName, next), [onChange, fieldName])
  const handleValidityChange = useCallback(
    (valid: boolean) => onValidityChange?.(fieldName, valid),
    [onValidityChange, fieldName],
  )

  if (MEDIA_FIELD_TYPES.has(ft)) {
    return (
      <MediaFieldPreview
        fieldName={fieldName}
        fieldType={ft as 'image' | 'audio' | 'diagram'}
        value={fieldValueEditorText(value)}
        onChange={handleChange}
        required={field.required}
        resolveUrl={resolveMediaUrl}
        uploadDisabled={mediaUploadDisabled}
      />
    )
  }

  if (isArrayField(ft)) {
    return (
      <ArrayFieldInput
        fieldName={fieldName}
        value={value}
        onChange={handleChange}
        required={field.required}
        onValidityChange={handleValidityChange}
        placeholderNormal={arrayPlaceholder}
      />
    )
  }

  const isMultiline = fieldShapePrefersMultiline(field) || initialValueIsLong
  const text = fieldValueEditorText(value)
  const required = field.required && <span className="text-destructive">*</span>

  return (
    <div className="space-y-1.5">
      {density === 'touch' ? (
        <Label className={`${LABEL_CLASS} flex items-center justify-between`}>
          <span>
            {fieldName} {required}
          </span>
          {isMultiline && multilineHint && (
            <span className="text-[10px] lowercase font-normal opacity-70">{multilineHint}</span>
          )}
        </Label>
      ) : (
        <Label className={LABEL_CLASS}>
          {fieldName} {required}
        </Label>
      )}
      {isMultiline ? (
        <Textarea
          value={text}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={placeholder}
          className={TEXTAREA_CLASS[density]}
        />
      ) : (
        <Input
          value={text}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={placeholder}
          className={INPUT_CLASS[density]}
        />
      )}
    </div>
  )
})
