import { ArrowDown, ArrowUp, Code2, List, Plus, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button, Input, Textarea } from '@/shared/ui'
import { useSampleArrayEditor } from '../hooks/useSampleArrayEditor'
import type { TemplateSampleValue } from '../model/previewSamples'

export function SampleArrayEditor({ id, label, value, onChange }: { id: string; label: string; value: TemplateSampleValue; onChange: (value: TemplateSampleValue) => void }) {
  const { t } = useTranslation('card_templates')
  const editor = useSampleArrayEditor(value, onChange)
  return <div className="space-y-2">
    <div className="flex items-center justify-between gap-2"><span className="text-xs text-muted-foreground">{t('samples.item_count', { count: editor.items.length })}</span>
      <Button type="button" variant="ghost" size="sm" disabled={editor.invalid || editor.nested} onClick={editor.toggleAdvanced}>{editor.advanced ? <List /> : <Code2 />}{t(editor.advanced ? 'samples.list_mode' : 'samples.json_mode')}</Button>
    </div>
    {editor.advanced ? <><Textarea id={id} aria-label={label} value={editor.code} aria-invalid={editor.invalid} onChange={(event) => editor.updateCode(event.target.value)} className="min-h-40 font-mono text-sm" />
      {editor.invalid && <p role="alert" className="text-xs text-destructive">{t('samples.invalid_array')}</p>}
    </> : <div className="space-y-2">
      {editor.items.map((item, index) => <div key={index} className="flex items-center gap-1">
        <Input id={index === 0 ? id : `${id}-${index}`} aria-label={t('samples.array_item', { label, number: index + 1 })} value={typeof item === 'string' ? item : ''} onChange={(event) => editor.changeItem(index, event.target.value)} />
        <Button type="button" variant="ghost" size="icon-sm" disabled={index === 0} aria-label={t('samples.move_up', { number: index + 1 })} onClick={() => editor.move(index, -1)}><ArrowUp /></Button>
        <Button type="button" variant="ghost" size="icon-sm" disabled={index === editor.items.length - 1} aria-label={t('samples.move_down', { number: index + 1 })} onClick={() => editor.move(index, 1)}><ArrowDown /></Button>
        <Button type="button" variant="ghost" size="icon-sm" aria-label={t('samples.remove_item', { number: index + 1 })} onClick={() => editor.remove(index)}><Trash2 /></Button>
      </div>)}
      <Button type="button" variant="outline" size="sm" onClick={editor.add}><Plus />{t('samples.add_item')}</Button>
    </div>}
  </div>
}
