import '@/shared/config/i18n'
import { useId, useMemo, useState } from 'react'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { TemplateInputSpec } from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
// Parked 2026-10-10: host typing mode (STUDY_TYPING_ANSWER_PLAN §12); restore defaultTypingOptions with the typing options below.
import { inputSchemaIssues, templateInputTypes, withInputType } from '../lib/inputSchemaValidation'
import { templateInputReferences } from '../lib/templateInputReferences'

type Props = {
  value: TemplateInputSpec[]
  onChange: (value: TemplateInputSpec[]) => void
  disabled?: boolean
  persistedKeys?: string[]
  frontHtml?: string
  backHtml?: string
  applicationCount?: number
}

export function TemplateInputSchemaEditor({ value, onChange, disabled = false, persistedKeys = [], frontHtml = '', backHtml = '', applicationCount = 0 }: Props) {
  const { t } = useTranslation('card_templates')
  const prefix = useId()
  const [selected, setSelected] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const issues = inputSchemaIssues(value, t)
  const references = useMemo(() => templateInputReferences(frontHtml, backHtml, value), [frontHtml, backHtml, value])
  const input = selected === null ? null : value[selected]
  const replaceSelected = (next: (item: TemplateInputSpec) => TemplateInputSpec) => {
    if (!disabled && selected !== null) onChange(value.map((item, index) => index === selected ? next(item) : item))
  }
  const update = (patch: Partial<TemplateInputSpec>) => replaceSelected((item) => ({ ...item, ...patch }))
  // const typing = input?.type === 'array' ? { ...defaultTypingOptions, ...input.typing } : null
  const sides = input ? [references.front.has(input.key) && t('setup.front'), references.back.has(input.key) && t('setup.back')].filter(Boolean) : []
  const used = sides.length > 0
  const filtered = value.map((item, index) => ({ item, index })).filter(({ item }) => `${item.label} ${item.key}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))
  return <div className="min-h-0 grid flex-1 gap-4 sm:grid-cols-[240px_minmax(0,1fr)]">
    <div className={`min-h-0 flex flex-col gap-3 sm:border-r sm:pr-4 ${input ? 'hidden sm:flex' : 'flex'}`}>
      <Input aria-label={t('setup.search_inputs')} placeholder={t('setup.search_inputs')} value={search} onChange={(event) => setSearch(event.target.value)} />
      <div className="min-h-0 flex-1 overflow-y-auto space-y-1" aria-label={t('input_schema.title')}>
        {filtered.map(({ item, index }) => <button key={index} type="button" aria-pressed={selected === index} disabled={disabled} onClick={() => setSelected(index)} className={`w-full rounded-xl px-3 py-2.5 text-left transition-colors ${selected === index ? 'bg-primary/10 text-primary' : 'hover:bg-muted'}`}>
          <span className="block truncate font-medium">{item.label || item.key}</span><span className="block text-xs text-muted-foreground">{t(`setup.types.${item.type}`)}</span>
        </button>)}
        {!filtered.length && <p className="p-3 text-sm text-muted-foreground">{t(value.length ? 'setup.no_search_results' : 'setup.no_inputs')}</p>}
      </div>
      <Button type="button" variant="outline" disabled={disabled} onClick={() => {
        let number = 1
        while (value.some((item) => item.key === `Input${number}`)) number++
        onChange([...value, { key: `Input${number}`, label: '', type: 'text', required: false }]); setSelected(value.length); setSearch('')
      }}><Plus className="size-4" />{t('input_schema.add_input')}</Button>
    </div>
    <div className={`min-h-0 overflow-y-auto space-y-5 ${input ? 'block' : 'hidden sm:block'}`}>
      {input ? <>
        <Button type="button" variant="ghost" size="sm" className="sm:hidden" onClick={() => setSelected(null)}><ArrowLeft className="size-4" />{t('setup.input_list')}</Button>
        <div className="space-y-1"><h3 className="font-semibold break-words">{input.label || input.key}</h3><p className="text-xs text-muted-foreground">{t('setup.input_contract')}</p></div>
        <div className="space-y-2"><Label htmlFor={`${prefix}-label`}>{t('setup.input_label')}</Label><Input id={`${prefix}-label`} value={input.label} maxLength={255} disabled={disabled} onChange={(event) => update({ label: event.target.value })} /></div>
        <div className="space-y-2"><Label htmlFor={`${prefix}-type`}>{t('setup.input_type')}</Label><NativeSelect id={`${prefix}-type`} value={input.type} disabled={disabled} onChange={(event) => replaceSelected((item) => withInputType(item, event.target.value as TemplateInputSpec['type']))}>{templateInputTypes.map((type) => <NativeSelectOption key={type} value={type}>{t(`setup.types.${type}`)}</NativeSelectOption>)}</NativeSelect></div>
        {applicationCount > 0 && <p className="text-xs text-muted-foreground">{t('setup.type_change_hint', { count: applicationCount })}</p>}
        {/* Parked 2026-10-10: typing options of the host typing mode.
        {typing && <fieldset className="space-y-2 rounded-xl border p-3"><legend className="px-1 text-sm font-medium">{t('setup.typing.title')}</legend>
          <p className="text-xs text-muted-foreground">{t('setup.typing.description')}</p>
          <Label className="flex items-center gap-2"><input type="checkbox" checked={typing.show_length} disabled={disabled} onChange={(event) => update({ typing: { ...typing, show_length: event.target.checked } })} />{t('setup.typing.show_length')}</Label>
          <Label className="flex items-center gap-2"><input type="checkbox" checked={typing.hints} disabled={disabled} onChange={(event) => update({ typing: { ...typing, hints: event.target.checked } })} />{t('setup.typing.hints')}</Label>
        </fieldset>}
        */}
        <Label className="flex items-center gap-2"><input type="checkbox" checked={input.required} disabled={disabled} onChange={(event) => update({ required: event.target.checked })} />{t('input_schema.recommended_checkbox')}</Label>
        <details className="rounded-xl border p-3 space-y-3"><summary className="cursor-pointer font-medium">{t('setup.advanced')}</summary>
          <div className="space-y-2 pt-3"><Label htmlFor={`${prefix}-key`}>{t('setup.input_key')}</Label><Input id={`${prefix}-key`} value={input.key} readOnly={persistedKeys.includes(input.key)} disabled={disabled} onChange={(event) => update({ key: event.target.value })} />
            {persistedKeys.includes(input.key) && <p className="text-xs text-muted-foreground">{t('setup.stored_key_hint')}</p>}
            <p className="font-mono text-xs break-all">{`{{${input.key}}}`}</p>
            <p className="text-xs text-muted-foreground">{t('setup.used_on', { sides: sides.join(', ') || t('setup.not_used') })}</p>
          </div>
        </details>
        {issues.filter((issue) => issue.index === selected).map((issue) => <p key={issue.message} role="alert" className="text-xs text-destructive">{issue.message}</p>)}
        <div className="border-t pt-4 space-y-2"><Button type="button" variant="ghost" className="text-destructive" disabled={disabled || used || references.parseErrors.length > 0} onClick={() => { onChange(value.filter((_, index) => index !== selected)); setSelected(null) }}><Trash2 className="size-4" />{t('input_schema.delete_input')}</Button>
          {used && <p className="text-xs text-muted-foreground">{t('setup.remove_used_hint', { sides: sides.join(', ') })}</p>}
          {applicationCount > 0 && <p className="text-xs text-muted-foreground">{t('setup.remove_mapping_hint', { count: applicationCount })}</p>}
          {references.parseErrors.length > 0 && <p role="alert" className="text-xs text-destructive">{t('setup.parse_hint')}</p>}
        </div>
      </> : <p className="flex min-h-64 items-center justify-center text-sm text-muted-foreground">{t('setup.select_input')}</p>}
    </div>
  </div>
}
