import { Bold, Code2, Eye, Italic, List } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button, Textarea } from '@/shared/ui'
import { useSampleTextEditor } from '../hooks/useSampleTextEditor'

export function SampleTextEditor({ id, label, type, value, onChange }: { id: string; label: string; type: string; value: string; onChange: (value: string) => void }) {
  const { t } = useTranslation('card_templates')
  const editor = useSampleTextEditor(value, onChange)
  const rich = type === 'richtext'
  const visual = rich && !editor.sourceMode
  return <div className="space-y-2">
    <div role="group" aria-label={t('samples.format_text')} className="flex gap-1">
      <Button type="button" variant="outline" size="icon-sm" aria-label={t('samples.bold')} onMouseDown={(event) => event.preventDefault()} onClick={() => visual ? editor.formatRich('strong') : editor.format(rich ? '<strong>' : '**', rich ? '</strong>' : '**')}><Bold /></Button>
      <Button type="button" variant="outline" size="icon-sm" aria-label={t('samples.italic')} onMouseDown={(event) => event.preventDefault()} onClick={() => visual ? editor.formatRich('em') : editor.format(rich ? '<em>' : '*', rich ? '</em>' : '*')}><Italic /></Button>
      <Button type="button" variant="outline" size="icon-sm" aria-label={t('samples.list')} onMouseDown={(event) => event.preventDefault()} onClick={() => visual ? editor.formatRich('ul') : editor.format(rich ? '<ul><li>' : '\n- ', rich ? '</li></ul>' : '\n')}><List /></Button>
      {rich && <Button type="button" variant="ghost" size="sm" onClick={editor.toggleSource}>{visual ? <Code2 /> : <Eye />}{t(visual ? 'samples.html_mode' : 'samples.visual_mode')}</Button>}
    </div>
    {visual ? <div ref={editor.richRef} id={id} role="textbox" aria-label={label} aria-multiline="true" contentEditable suppressContentEditableWarning onInput={editor.inputRichText}
      className="min-h-32 rounded-lg border border-input px-3 py-2 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50 [&_strong]:font-bold [&_em]:italic [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5" />
      : <Textarea ref={editor.ref} id={id} aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} className="min-h-32" />}
  </div>
}
