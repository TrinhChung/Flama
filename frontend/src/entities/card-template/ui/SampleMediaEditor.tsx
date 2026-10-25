import { useTranslation } from 'react-i18next'
import { Input } from '@/shared/ui'
import { resolveBackendUrl } from '@/shared/config/env'
import { sampleMediaUrl } from '../lib/previewSamples'

export function SampleMediaEditor({ id, label, type, value, onChange }: { id: string; label: string; type: string; value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation('card_templates')
  const source = resolveBackendUrl(sampleMediaUrl(value))
  return <div className="space-y-2">
    {source && <div className="rounded-xl border border-border bg-muted/20 p-3">{type === 'audio'
      ? <audio key={source} controls preload="none" src={source} aria-label={label} className="w-full" />
      : <img src={source} alt={label} className="mx-auto max-h-36 max-w-full rounded-lg object-contain" />}</div>}
    <Input id={id} aria-label={label} value={value} placeholder="https://…" aria-invalid={Boolean(value && !source)} onChange={(event) => onChange(event.target.value)} />
    {value && !source ? <p role="alert" className="text-xs text-destructive">{t('samples.invalid_media')}</p> : <p className="text-xs text-muted-foreground">{t('samples.media_hint')}</p>}
  </div>
}
