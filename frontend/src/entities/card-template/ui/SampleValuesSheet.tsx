import '@/shared/config/i18n'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { RotateCcw } from 'lucide-react'
import { Button, Input, Label, Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/shared/ui'
import { defaultTemplateSample } from '../lib/previewSamples'
import type { SampleValueItem, TemplateSampleValues, TemplateSampleValue } from '../model/previewSamples'
import { SampleArrayEditor } from './SampleArrayEditor'
import { SampleTextEditor } from './SampleTextEditor'
import { SampleMediaEditor } from './SampleMediaEditor'

const MEDIA_TYPES = new Set(['image', 'audio', 'diagram'])
const LONG_TEXT_TYPES = new Set(['richtext', 'markdown'])

export type { SampleValueItem } from '../model/previewSamples'

export type SampleValuesSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  items: SampleValueItem[]
  /** Explicit samples. A missing key keeps the preview's default sample; `""` renders empty. */
  values: TemplateSampleValues
  onChange: (key: string, value: TemplateSampleValue) => void
  onReset: () => void
  /** Prefix for input IDs, e.g. `sample` → `#sample-Word`. */
  idPrefix: string
  emptyText?: string
}

/** Preview-only sample data editor shared by the template workspace and mapping pages. */
export function SampleValuesSheet({ open, onOpenChange, title, description, items, values, onChange, onReset, idPrefix, emptyText }: SampleValuesSheetProps) {
  const { t } = useTranslation('card_templates')
  return <Sheet open={open} onOpenChange={onOpenChange}><SheetContent className="w-full sm:max-w-md">
    <SheetHeader><SheetTitle>{title}</SheetTitle><SheetDescription>{description}</SheetDescription></SheetHeader>
    <div className="min-h-0 overflow-y-auto p-4 pt-0 space-y-5">
      <Button variant="outline" size="sm" onClick={onReset}>{t('setup.default_samples')}</Button>
      {items.map((item) => <SampleValueField key={`${item.key}:${item.type}`} item={item} idPrefix={idPrefix} values={values} onChange={onChange} />)}
      {!items.length && emptyText && <p className="text-sm text-muted-foreground">{emptyText}</p>}
    </div>
  </SheetContent></Sheet>
}

function SampleValueField({ item, idPrefix, values, onChange }: Pick<SampleValuesSheetProps, 'idPrefix' | 'values' | 'onChange'> & { item: SampleValueItem }) {
  const { t } = useTranslation('card_templates')
  const fallback = useMemo(() => defaultTemplateSample(item.type), [item.type])
  const id = `${idPrefix}-${encodeURIComponent(item.key)}`
  const value = Object.hasOwn(values, item.key) ? values[item.key] : fallback
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  const change = (next: TemplateSampleValue) => onChange(item.key, next)
  return <div className="space-y-2">
    <div className="flex items-center justify-between gap-2"><Label htmlFor={id}>{item.label}</Label><span className="text-xs text-muted-foreground">{t(`setup.types.${item.type}`, { defaultValue: item.type })}</span></div>
    {item.type === 'array' ? <SampleArrayEditor id={id} label={item.label} value={value} onChange={change} />
      : MEDIA_TYPES.has(item.type) ? <SampleMediaEditor id={id} label={item.label} type={item.type} value={text} onChange={change} />
        : LONG_TEXT_TYPES.has(item.type) ? <SampleTextEditor id={id} label={item.label} type={item.type} value={text} onChange={change} />
          : <Input id={id} value={text} placeholder={item.placeholder} onChange={(event) => change(event.target.value)} />}
    <div className="flex flex-wrap gap-1"><Button type="button" variant="ghost" size="sm" aria-label={t('samples.reset_field', { label: item.label })} onClick={() => change(defaultTemplateSample(item.type))}><RotateCcw />{t('samples.reset')}</Button>
      <Button type="button" variant="ghost" size="sm" aria-label={t('samples.empty_field', { label: item.label })} onClick={() => change(item.type === 'array' ? [] : '')}>{t('setup.empty_sample')}</Button></div>
    {Object.hasOwn(values, item.key) && <p className="text-xs text-muted-foreground">{t('setup.sample_override')}</p>}
  </div>
}
