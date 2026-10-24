import '@/shared/config/i18n'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { isTypeCompatible, type TemplateBindings, type TemplateInputSpec } from '@/entities/card-template'

export type StudyTemplateFieldDef = {
  id: string
  name: string
  field_type: string
  required?: boolean
  position?: number
}

export type TemplateInputBindingEditorProps = {
  inputSchema: TemplateInputSpec[]
  fieldDefs: StudyTemplateFieldDef[]
  value: TemplateBindings
  onChange: (value: TemplateBindings) => void
  staleInputs?: string[]
  disabled?: boolean
}

export function TemplateInputBindingEditor({ inputSchema, fieldDefs, value, onChange, staleInputs = [], disabled = false }: TemplateInputBindingEditorProps) {
  const { t } = useTranslation('study')
  const id = useId()
  return (
    <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
      {inputSchema.map((input, index) => {
        const candidates = fieldDefs.filter((field) => field.id)
        const target = value[input.key]
        const valid = Boolean(target && candidates.some((field) => field.id === target))
        const stale = staleInputs.includes(input.key)
        const field = candidates.find((item) => item.id === target)
        const mismatch = Boolean(field && !isTypeCompatible(input.type, field.field_type))
        const hintId = `${id}-${index}-hint`
        return (
          <div key={input.key} className="min-w-0 space-y-1">
            <label htmlFor={`${id}-${index}`} className="flex min-w-0 items-center gap-1.5 text-xs font-semibold text-foreground">
              <span className="truncate" title={input.key}>{input.label || input.key}</span>
              {input.required ? (
                <span className="shrink-0 rounded bg-orange-500/10 px-1 py-px text-[10px] font-bold text-orange-600 dark:text-orange-400">
                  {t('fields.recommended')}
                </span>
              ) : null}
              <span className="ml-auto shrink-0 font-mono text-[10px] font-normal text-muted-foreground">{input.type}</span>
            </label>
            <NativeSelect id={`${id}-${index}`} size="sm" className="w-full" value={valid ? target! : ''} disabled={disabled}
              aria-describedby={stale || mismatch ? hintId : undefined}
              onChange={(event) => onChange({ ...value, [input.key]: event.target.value || null })}>
              <NativeSelectOption value="">{t('fields.empty_option')}</NativeSelectOption>
              {candidates.map((field, fieldIndex) => (
                <NativeSelectOption key={field.id} value={field.id}>
                  {field.name}{candidates.filter((other) => other.name === field.name).length > 1 ? ` (${fieldIndex + 1})` : ''}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            {stale ? <p id={hintId} role="status" className="text-[11px] text-amber-700 dark:text-amber-400">{t('fields.stale')}</p> : null}
            {!stale && mismatch ? <p id={hintId} role="status" className="text-[11px] text-amber-700 dark:text-amber-400">{t('fields.type_mismatch')}</p> : null}
          </div>
        )
      })}
    </div>
  )
}
