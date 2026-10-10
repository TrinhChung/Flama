import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Bold, Eye, ImageIcon, Italic, Music, FileImage, Upload } from 'lucide-react'
import { CardRendererFrame, resolveDisplayUrl } from '@/entities/flashcard'
import { apiJson } from '@/shared/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FIELD_TYPES } from '../../hooks/useNoteTypeFields'

const EXAMPLES: Record<string, string> = {
  text: '日本語',
  richtext: '<p><strong>日本語</strong> — Japanese language</p>',
  markdown: '## 日本語\n\n**Japanese language**\n\n- にほんご\n- A language spoken in Japan',
  image: '/media/proxy/sample-image',
  audio: '/media/proxy/sample-audio',
  diagram: '/media/proxy/sample-diagram',
  answers: 'ăn\ndùng bữa',
}
type FieldPreviewResult = { front_html: string; front_renderer_payload?: unknown }

export function FieldEditorPreview({ fieldType, value, onChange, localFile, onFileChange }: {
  fieldType: string
  value: string
  onChange: (value: string) => void
  localFile?: File | null
  onFileChange?: (file: File | null) => void
}) {
  const { t } = useTranslation('note_types')
  const supportedType = FIELD_TYPES.find((type) => type === fieldType) ?? 'text'
  const [mode, setMode] = useState('editor')
  const [debouncedValue, setDebouncedValue] = useState(value)
  const [objectUrl, setObjectUrl] = useState('')
  const [fileError, setFileError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const sourceInput = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedValue(value), 250)
    return () => clearTimeout(timeout)
  }, [value])
  useEffect(() => {
    if (!localFile) { setObjectUrl(''); return }
    const url = URL.createObjectURL(localFile)
    setObjectUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [localFile])
  const isMedia = ['image', 'audio', 'diagram'].includes(fieldType)
  const isFormatted = ['richtext', 'markdown'].includes(fieldType)
  const rendered = useQuery({
    queryKey: ['field-editor-preview', fieldType, debouncedValue],
    queryFn: () => apiJson<FieldPreviewResult>('/api/note-types/preview', 'POST', {
      front_html: '{{{Sample}}}', back_html: '{{{Sample}}}', shared_css: '',
      fields: [{ name: 'Sample', field_type: fieldType }], field_values: { Sample: debouncedValue },
    }),
    enabled: mode === 'preview' && isFormatted && Boolean(debouncedValue),
    retry: false,
  })
  const mediaUrl = objectUrl || (isMedia ? resolveDisplayUrl(value) : '')
  const MediaIcon = fieldType === 'audio' ? Music : fieldType === 'diagram' ? FileImage : ImageIcon
  const setSample = (sample: string) => { onFileChange?.(null); setFileError(null); onChange(sample) }
  const formatSource = (tag: 'strong' | 'em') => {
    const start = sourceInput.current?.selectionStart ?? value.length
    const end = sourceInput.current?.selectionEnd ?? value.length
    const text = value.slice(start, end) || t('setup.format_text')
    onChange(`${value.slice(0, start)}<${tag}>${text}</${tag}>${value.slice(end)}`)
    sourceInput.current?.focus()
  }
  const sourceEditor = <div className="space-y-2">
    <Label htmlFor="field-editor-sample" className="text-xs">{t(isMedia ? 'setup.media_reference' : 'setup.sample_value')}</Label>
    {fieldType === 'richtext' && <div className="flex gap-1" role="group" aria-label={t('setup.format_source')}>
      <Button type="button" variant="outline" size="icon-sm" aria-label={t('setup.format_bold')} onClick={() => formatSource('strong')}><Bold className="size-4" /></Button>
      <Button type="button" variant="outline" size="icon-sm" aria-label={t('setup.format_italic')} onClick={() => formatSource('em')}><Italic className="size-4" /></Button>
    </div>}
    {fieldType === 'text' ? <Input id="field-editor-sample" value={value} onChange={(event) => setSample(event.target.value)} placeholder={t('setup.sample_placeholder')} /> :
      <Textarea ref={sourceInput} id="field-editor-sample" value={value} onChange={(event) => setSample(event.target.value)}
        placeholder={isMedia ? '/media/proxy/…' : t('setup.sample_placeholder')} className="min-h-24 resize-y font-mono text-sm" />}
  </div>

  return (
    <section className="space-y-3 border-t border-border pt-4" aria-labelledby="field-preview-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="field-preview-heading" className="text-sm font-semibold flex items-center gap-2"><Eye className="size-4 text-primary" />{t('setup.editor_preview')}</h3>
        <div className="flex gap-1">
          <Button type="button" size="sm" variant="ghost" onClick={() => setSample(EXAMPLES[fieldType] ?? '')}>{t('setup.use_sample')}</Button>
          <Button type="button" size="sm" variant="ghost" disabled={!value && !localFile} onClick={() => setSample('')}>{t('setup.clear_sample')}</Button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{t(`setup.types.${supportedType}.hint`)}</p>
      {isFormatted && <Tabs value={mode} onValueChange={setMode}>
        <TabsList className="w-full"><TabsTrigger value="editor" className="flex-1">{t('setup.sample_editor')}</TabsTrigger><TabsTrigger value="preview" className="flex-1">{t('setup.sample_result')}</TabsTrigger></TabsList>
      </Tabs>}
      {mode === 'editor' || !isFormatted ? isMedia && fieldType !== 'diagram'
        ? <details className="text-xs"><summary className="cursor-pointer text-muted-foreground hover:text-foreground">{t('setup.media_reference_advanced')}</summary><div className="mt-3">{sourceEditor}</div></details>
        : sourceEditor : !value ? <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">{t('setup.sample_empty')}</p> :
        rendered.isPending || value !== debouncedValue ? <p role="status" className="text-xs text-muted-foreground">{t('setup.preview_loading')}</p> :
          rendered.error ? <p role="alert" className="text-xs text-destructive">{rendered.error.message}</p> :
            rendered.data && <CardRendererFrame cardId="field-editor-sample" revealed={false}
              frontPayload={rendered.data.front_renderer_payload} frontHtml={rendered.data.front_html}
              scope="field_editor_sample" className="min-h-40 rounded-xl border" />}
      {isMedia && <div className="space-y-3 rounded-xl border border-border bg-muted/20 p-3">
        {mediaUrl ? fieldType === 'audio'
          ? <audio controls preload="none" src={mediaUrl} className="w-full" aria-label={t('setup.audio_sample')} />
          : <img src={mediaUrl} alt={t(`setup.types.${supportedType}.label`)} className="mx-auto max-h-40 max-w-full rounded-lg object-contain" />
          : <div className="flex flex-col items-center gap-2 py-5 text-center text-xs text-muted-foreground"><MediaIcon className="size-6" /><p>{t(value ? 'setup.invalid_media_sample' : 'setup.media_empty')}</p></div>}
        {onFileChange && fieldType !== 'diagram' && <div className="flex flex-wrap items-center gap-2">
          <input ref={fileInput} type="file" accept={fieldType === 'audio' ? 'audio/*' : 'image/*'} className="sr-only"
            aria-label={t('setup.choose_media')} onChange={(event) => {
              const file = event.target.files?.[0]
              event.target.value = ''
              if (!file) return
              if (!file.type.startsWith(fieldType === 'audio' ? 'audio/' : 'image/')) { setFileError(t('setup.invalid_local_media')); return }
              setFileError(null); onChange(''); onFileChange(file)
            }} />
          <Button type="button" variant="outline" size="sm" onClick={() => fileInput.current?.click()}><Upload className="size-4" />{t(localFile ? 'setup.replace_media' : 'setup.choose_media')}</Button>
          {localFile && <span className="min-w-0 max-w-full truncate text-xs text-muted-foreground">{localFile.name}</span>}
          {fileError && <p role="alert" className="w-full text-xs text-destructive">{fileError}</p>}
        </div>}
      </div>}
      <p className="text-xs text-muted-foreground">{t('setup.sample_ephemeral')}</p>
    </section>
  )
}
