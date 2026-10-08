import { useId } from 'react'
import type { TemplateBindings, TemplateInputSpec } from '@/entities/card-template'

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
  disabled?: boolean
}

export function TemplateInputBindingEditor({ inputSchema, fieldDefs, value, onChange, disabled = false }: TemplateInputBindingEditorProps) {
  const id = useId()
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Input chưa ánh xạ sẽ hiển thị rỗng.</p>
      {inputSchema.map((input, index) => {
        const candidates = fieldDefs.filter((field) => field.id && field.field_type === input.type)
        const target = value[input.key]
        const valid = Boolean(target && candidates.some((field) => field.id === target))
        const stale = Boolean(target && !valid)
        const hintId = `${id}-${index}-hint`
        return (
          <div key={input.key} className="space-y-1.5">
            <label htmlFor={`${id}-${index}`} className="block text-sm font-medium">
              {input.label || input.key}{input.label && input.label !== input.key ? ` (${input.key})` : ''}
            </label>
            <select id={`${id}-${index}`} value={valid ? target! : ''} disabled={disabled}
              aria-describedby={stale || (!valid && input.required) ? hintId : undefined}
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm disabled:opacity-50"
              onChange={(event) => onChange({ ...value, [input.key]: event.target.value || null })}>
              <option value="">Để trống</option>
              {candidates.map((field, fieldIndex) => (
                <option key={field.id} value={field.id}>
                  {field.name}{candidates.filter((other) => other.name === field.name).length > 1 ? ` (${fieldIndex + 1})` : ''}
                </option>
              ))}
            </select>
            {stale ? <p id={hintId} role="status" className="text-xs text-amber-700 dark:text-amber-400">Trường đã lưu không còn phù hợp. Hãy chọn lại hoặc để trống.</p>
              : !valid && input.required ? <p id={hintId} className="text-xs text-muted-foreground">Input được khuyến nghị; bạn vẫn có thể để trống.</p> : null}
          </div>
        )
      })}
    </div>
  )
}
