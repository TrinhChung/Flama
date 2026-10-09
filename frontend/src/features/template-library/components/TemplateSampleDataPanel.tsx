import { useTranslation } from 'react-i18next'
import type { TemplateInputSpec } from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'

export function TemplateSampleDataPanel({ open, onOpenChange, inputs, values, onChange, onReset }: {
  open: boolean; onOpenChange: (open: boolean) => void; inputs: TemplateInputSpec[]; values: Record<string, string>; onChange: (key: string, value: string) => void; onReset: () => void
}) {
  const { t } = useTranslation('card_templates')
  return <Sheet open={open} onOpenChange={onOpenChange}><SheetContent className="w-full sm:max-w-md">
    <SheetHeader><SheetTitle>{t('setup.sample_data')}</SheetTitle><SheetDescription>{t('setup.sample_description')}</SheetDescription></SheetHeader>
    <div className="min-h-0 overflow-y-auto p-4 pt-0 space-y-5">
      <Button variant="outline" size="sm" onClick={onReset}>{t('setup.default_samples')}</Button>
      {inputs.map((input) => <div key={input.key} className="space-y-2"><Label htmlFor={`sample-${encodeURIComponent(input.key)}`}>{input.label || input.key}</Label>
        {['image', 'audio', 'diagram'].includes(input.type) ? <div className="space-y-2"><p className="text-sm text-muted-foreground">{t('setup.media_sample_hint')}</p><Button variant="outline" size="sm" onClick={() => onChange(input.key, '')}>{t('setup.empty_sample')}</Button></div> : ['richtext', 'markdown'].includes(input.type) ? <Textarea id={`sample-${encodeURIComponent(input.key)}`} value={values[input.key] ?? ''} placeholder={t('detail.sample_input_placeholder', { key: input.key })} onChange={(event) => onChange(input.key, event.target.value)} className="min-h-32" /> : <Input id={`sample-${encodeURIComponent(input.key)}`} value={values[input.key] ?? ''} placeholder={t('detail.sample_input_placeholder', { key: input.key })} onChange={(event) => onChange(input.key, event.target.value)} />}
        {Object.hasOwn(values, input.key) && <p className="text-xs text-muted-foreground">{t('setup.sample_override')}</p>}
      </div>)}
      {!inputs.length && <p className="text-sm text-muted-foreground">{t('setup.no_inputs')}</p>}
    </div>
  </SheetContent></Sheet>
}
