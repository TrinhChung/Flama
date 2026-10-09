import '@/shared/config/i18n'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import type { TemplateInputSpec } from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { inputSchemaIssues, templateInputTypes } from '../lib/inputSchemaValidation'

export function TemplateInputSchemaEditor({ value, onChange, disabled = false }: { value: TemplateInputSpec[]; onChange: (value: TemplateInputSpec[]) => void; disabled?: boolean }) {
  const { t } = useTranslation('card_templates')
  const prefix = useId()
  const issues = inputSchemaIssues(value, t)
  const update = (index: number, patch: Partial<TemplateInputSpec>) => { if (!disabled) onChange(value.map((input, i) => i === index ? { ...input, ...patch } : input)) }
  return <section className="space-y-3">
    <div><h2 className="font-semibold">{t('input_schema.title')}</h2><p className="text-sm text-muted-foreground">{t('input_schema.subtitle')}</p></div>
    {value.map((input, index) => <div key={index} className="rounded-xl border p-3 space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1"><Label htmlFor={`${prefix}-${index}-key`}>{t('input_schema.key_label', { index: index + 1 })}</Label><Input id={`${prefix}-${index}-key`} value={input.key} disabled={disabled} onChange={(event) => update(index, { key: event.target.value })} /></div>
        <div className="space-y-1"><Label htmlFor={`${prefix}-${index}-label`}>{t('input_schema.label_label', { index: index + 1 })}</Label><Input id={`${prefix}-${index}-label`} value={input.label} disabled={disabled} onChange={(event) => update(index, { label: event.target.value })} /></div>
        <div className="space-y-1"><Label htmlFor={`${prefix}-${index}-type`}>{t('input_schema.type_label', { index: index + 1 })}</Label><NativeSelect id={`${prefix}-${index}-type`} value={input.type} disabled={disabled} onChange={(event) => update(index, { type: event.target.value as TemplateInputSpec['type'] })}>{templateInputTypes.map((type) => <NativeSelectOption key={type} value={type}>{type}</NativeSelectOption>)}</NativeSelect></div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2"><Label className="flex items-center gap-2"><input type="checkbox" checked={input.required} disabled={disabled} onChange={(event) => update(index, { required: event.target.checked })} />{t('input_schema.recommended_checkbox')}</Label><Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={() => onChange(value.filter((_, i) => i !== index))} aria-label={t('input_schema.delete_input_aria', { index: index + 1 })}>{t('input_schema.delete_input')}</Button></div>
      {issues.filter((issue) => issue.index === index).map((issue) => <p key={issue.message} role="alert" className="text-xs text-destructive">{issue.message}</p>)}
    </div>)}
    {issues.filter((issue) => issue.index >= value.length).map((issue) => <p key={issue.message} role="alert" className="text-xs text-destructive">{issue.message}</p>)}
    <Button type="button" variant="outline" disabled={disabled} onClick={() => {
      if (disabled) return
      let n = 1
      while (value.some((input) => input.key === `Input${n}`)) n++
      onChange([...value, { key: `Input${n}`, label: `Input${n}`, type: 'text', required: false }])
    }}>{t('input_schema.add_input')}</Button>
  </section>
}
