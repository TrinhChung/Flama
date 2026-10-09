import '@/shared/config/i18n'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
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

function issueMessage(issue: MappingIssue, t: (key: 'mapping_editor.issue_unbound_required' | 'mapping_editor.issue_unbound_optional' | 'mapping_editor.issue_field_out_of_scope' | 'mapping_editor.issue_type_mismatch' | 'mapping_editor.issue_unknown_input') => string): string {
  switch (issue.kind) {
    case 'unbound': return issue.required
      ? t('mapping_editor.issue_unbound_required')
      : t('mapping_editor.issue_unbound_optional')
    case 'field_out_of_scope': return t('mapping_editor.issue_field_out_of_scope')
    case 'type_mismatch': return t('mapping_editor.issue_type_mismatch')
    case 'unknown_input': return t('mapping_editor.issue_unknown_input')
  }
}

export function FieldMappingEditor({ inputs, fields, bindings, onChange, issues, disabled }: FieldMappingEditorProps) {
  const { t } = useTranslation('card_templates')
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
          {input.required && <Badge variant="secondary">{t('mapping_editor.badge_recommended')}</Badge>}
        </Label>
        <NativeSelect id={id} className="w-full" value={fieldId} disabled={disabled}
          aria-invalid={inputIssues.some((issue) => issue.blocking)}
          aria-describedby={inputIssues.length ? `${id}-issues` : undefined}
          onChange={(event) => { if (!disabled) onChange({ ...bindings, [input.key]: event.target.value || null }) }}>
          <NativeSelectOption value="">{t('mapping_editor.select_unbound')}</NativeSelectOption>
          {stale && <NativeSelectOption value={fieldId} disabled>{t('mapping_editor.stale_field', { id: fieldId })}</NativeSelectOption>}
          {fields.map((field) => <NativeSelectOption key={field.id} value={field.id}
            disabled={!isTypeCompatible(input.type, field.field_type)}>{field.name} · {field.field_type}</NativeSelectOption>)}
        </NativeSelect>
        {inputIssues.length > 0 && <div id={`${id}-issues`} className="space-y-1">
          {inputIssues.map((issue) => <p key={issue.kind} className={`text-xs ${issue.blocking ? 'text-destructive' : 'text-muted-foreground'}`}>{issueMessage(issue, t)}</p>)}
        </div>}
      </div>
    })}
    {issues.filter((issue) => issue.kind === 'unknown_input').map((issue) => <p key={issue.key} role="alert" className="text-xs text-destructive">
      {`{{${issue.key}}}`} — {issueMessage(issue, t)}
      <button type="button" disabled={disabled} className="ml-2 underline" onClick={() => {
        if (disabled) return
        const next = { ...bindings }
        delete next[issue.key]
        onChange(next)
      }}>{t('mapping_editor.btn_unmap')}</button>
    </p>)}
  </div>
}
