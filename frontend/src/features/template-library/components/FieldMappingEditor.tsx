import { useId } from 'react'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import type { TemplateBindings } from '@/entities/card-template'
import { isTypeCompatible, type MappingField, type MappingInput, type MappingIssue } from '../lib/fieldMapping'

export type FieldMappingEditorProps = {
  inputs: MappingInput[]
  fields: MappingField[]
  bindings: TemplateBindings
  onChange: (next: TemplateBindings) => void
  issues: MappingIssue[]
  disabled?: boolean
}

function issueMessage(issue: MappingIssue): string {
  switch (issue.kind) {
    case 'unbound': return issue.required
      ? 'Input được khuyến nghị chưa ánh xạ; vẫn có thể sử dụng.'
      : 'Input này sẽ hiển thị rỗng.'
    case 'field_out_of_scope': return 'Trường không thuộc loại thẻ đã chọn.'
    case 'type_mismatch': return 'Kiểu trường không phù hợp.'
    case 'unknown_input': return 'Input không còn trong mẫu thẻ.'
  }
}

export function FieldMappingEditor({ inputs, fields, bindings, onChange, issues, disabled }: FieldMappingEditorProps) {
  const prefix = useId()
  return <div className="space-y-4">
    {inputs.map((input, index) => {
      const id = `${prefix}-${index}`
      const inputIssues = issues.filter((issue) => issue.key === input.key)
      const fieldId = Object.hasOwn(bindings, input.key) ? bindings[input.key] ?? '' : ''
      const stale = Boolean(fieldId) && !fields.some((field) => field.id === fieldId)
      return <div key={input.key} className="space-y-1.5">
        <Label htmlFor={id} className="flex flex-wrap items-center gap-2">
          <code>{`{{${input.key}}}`}</code>
          <span>{input.label}</span>
          {input.required && <Badge variant="secondary">Khuyến nghị</Badge>}
        </Label>
        <NativeSelect id={id} className="w-full" value={fieldId} disabled={disabled}
          aria-invalid={inputIssues.some((issue) => issue.blocking)}
          aria-describedby={inputIssues.length ? `${id}-issues` : undefined}
          onChange={(event) => { if (!disabled) onChange({ ...bindings, [input.key]: event.target.value || null }) }}>
          <NativeSelectOption value="">— Không dùng —</NativeSelectOption>
          {stale && <NativeSelectOption value={fieldId} disabled>Trường không còn tồn tại · {fieldId}</NativeSelectOption>}
          {fields.map((field) => <NativeSelectOption key={field.id} value={field.id}
            disabled={!isTypeCompatible(input.type, field.field_type)}>{field.name} · {field.field_type}</NativeSelectOption>)}
        </NativeSelect>
        {inputIssues.length > 0 && <div id={`${id}-issues`} className="space-y-1">
          {inputIssues.map((issue) => <p key={issue.kind} className={`text-xs ${issue.blocking ? 'text-destructive' : 'text-muted-foreground'}`}>{issueMessage(issue)}</p>)}
        </div>}
      </div>
    })}
    {issues.filter((issue) => issue.kind === 'unknown_input').map((issue) => <p key={issue.key} role="alert" className="text-xs text-destructive">
      {`{{${issue.key}}}`} — {issueMessage(issue)}
      <button type="button" disabled={disabled} className="ml-2 underline" onClick={() => {
        if (disabled) return
        const next = { ...bindings }
        delete next[issue.key]
        onChange(next)
      }}>Bỏ ánh xạ</button>
    </p>)}
  </div>
}
