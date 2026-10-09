import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'

const MEDIA_TYPES = new Set(['image', 'audio', 'diagram'])
const LONG_TEXT_TYPES = new Set(['richtext', 'markdown'])

export type SampleValueItem = {
  /** Key of the sample in `values` (template input key or Note Type field ID). */
  key: string
  label: string
  type: string
  /** Shown while no explicit sample is set, i.e. what the preview falls back to. */
  placeholder?: string
}

export type SampleValuesSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  items: SampleValueItem[]
  /** Explicit samples. A missing key keeps the preview's default sample; `""` renders empty. */
  values: Record<string, string>
  onChange: (key: string, value: string) => void
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
      {items.map((item) => {
        const id = `${idPrefix}-${encodeURIComponent(item.key)}`
        const placeholder = item.placeholder ?? t('detail.sample_input_placeholder', { key: item.key })
        return <div key={item.key} className="space-y-2"><Label htmlFor={id}>{item.label}</Label>
          {MEDIA_TYPES.has(item.type) ? <div className="space-y-2"><p className="text-sm text-muted-foreground">{t('setup.media_sample_hint')}</p><Button variant="outline" size="sm" onClick={() => onChange(item.key, '')}>{t('setup.empty_sample')}</Button></div>
            : LONG_TEXT_TYPES.has(item.type) ? <Textarea id={id} value={values[item.key] ?? ''} placeholder={placeholder} onChange={(event) => onChange(item.key, event.target.value)} className="min-h-32" />
              : <Input id={id} value={values[item.key] ?? ''} placeholder={placeholder} onChange={(event) => onChange(item.key, event.target.value)} />}
          {Object.hasOwn(values, item.key) && <p className="text-xs text-muted-foreground">{t('setup.sample_override')}</p>}
        </div>
      })}
      {!items.length && emptyText && <p className="text-sm text-muted-foreground">{emptyText}</p>}
    </div>
  </SheetContent></Sheet>
}
