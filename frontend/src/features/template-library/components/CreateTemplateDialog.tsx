import '@/shared/config/i18n'
import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { createLibraryTemplate } from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

// Parked 2026-10-10: the "Typed answer" starting point of the host typing mode
// (STUDY_TYPING_ANSWER_PLAN §12). Templates are no longer split into flip or
// typing; a typed answer is plain HTML/JS in the template's own sides. To
// restore, bring back this preset, the preset state and the radio fieldset
// below (imports: cn, defaultTypingOptions, TemplateInputSpec).
//
// type TemplatePreset = 'basic' | 'typing'
// type PresetContent = { front_html: string; back_html: string; shared_css: string; input_schema: TemplateInputSpec[] }
//
// const TYPING_CSS = `.flama-typing-prompt { font-size: 1.6em; font-weight: 600; text-align: center; }
// .flama-typing-answer { font-size: 1.4em; text-align: center; }`
//
// function presetContent(preset: TemplatePreset, labels: { prompt: string; answer: string }): PresetContent {
//   if (preset === 'typing') {
//     return {
//       front_html: '<div class="flama-typing-prompt">{{Prompt}}</div>',
//       back_html: '{{FrontSide}}<hr><div class="flama-typing-answer">{{Answer}}</div>',
//       shared_css: TYPING_CSS,
//       input_schema: [
//         { key: 'Prompt', label: labels.prompt, type: 'text', required: true },
//         { key: 'Answer', label: labels.answer, type: 'array', required: true, typing: { ...defaultTypingOptions } },
//       ],
//     }
//   }
//   return {
//     front_html: '{{Front}}', back_html: '{{Front}}<hr>{{Back}}', shared_css: '',
//     input_schema: [{ key: 'Front', label: 'Front', type: 'text', required: false }, { key: 'Back', label: 'Back', type: 'text', required: false }],
//   }
// }

function CreateTemplateForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation('card_templates')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  // const [preset, setPreset] = useState<TemplatePreset>('basic')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const create = useMutation({
    mutationFn: () => createLibraryTemplate({
      name: name.trim(), description,
      front_html: '{{Front}}', back_html: '{{Front}}<hr>{{Back}}', shared_css: '',
      input_schema: [{ key: 'Front', label: 'Front', type: 'text', required: false }, { key: 'Back', label: 'Back', type: 'text', required: false }],
      // ...presetContent(preset, { prompt: t('create_dialog.typing_prompt_label'), answer: t('create_dialog.typing_answer_label') }),
    }),
    onSuccess: (template) => {
      void queryClient.invalidateQueries({ queryKey: ['card-template', 'library'] })
      if (!active.current) return
      toast.success(t('create_dialog.toast_success'))
      onClose()
      navigate(`/card-templates/${encodeURIComponent(template.id)}`)
    },
  })
  // const presets: Array<{ value: TemplatePreset; label: string; description: string }> = [
  //   { value: 'basic', label: t('create_dialog.preset_basic'), description: t('create_dialog.preset_basic_desc') },
  //   { value: 'typing', label: t('create_dialog.preset_typing'), description: t('create_dialog.preset_typing_desc') },
  // ]
  return <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (name.trim() && name.trim().length <= 255 && !create.isPending) create.mutate() }}>
    <div className="space-y-2"><Label htmlFor="create-template-name">{t('create_dialog.name_label')}</Label><Input id="create-template-name" value={name} onChange={(event) => setName(event.target.value)} disabled={create.isPending} maxLength={255} autoFocus /></div>
    <div className="space-y-2"><Label htmlFor="create-template-description">{t('create_dialog.description_label')}</Label><Input id="create-template-description" value={description} onChange={(event) => setDescription(event.target.value)} disabled={create.isPending} /></div>
    {/* Parked 2026-10-10: flip/typing starting point (see the preset above).
    <fieldset className="space-y-2" disabled={create.isPending}>
      <legend className="text-sm font-medium">{t('create_dialog.preset_label')}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {presets.map((option) => <label key={option.value} className={cn('flex cursor-pointer gap-2 rounded-xl border p-3 text-sm transition-colors', preset === option.value ? 'border-primary bg-primary/5' : 'hover:bg-muted')}>
          <input type="radio" name="create-template-preset" value={option.value} checked={preset === option.value} onChange={() => setPreset(option.value)} className="mt-0.5" />
          <span><span className="block font-medium">{option.label}</span><span className="block text-xs text-muted-foreground">{option.description}</span></span>
        </label>)}
      </div>
    </fieldset>
    */}
    {create.error && <p role="alert" className="text-sm text-destructive">{create.error instanceof Error ? create.error.message : t('create_dialog.error_failed')}</p>}
    <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>{t('create_dialog.cancel')}</Button><Button type="submit" disabled={!name.trim() || name.trim().length > 255 || create.isPending}>{create.isPending ? t('create_dialog.creating') : t('create_dialog.create')}</Button></div>
  </form>
}

export function CreateTemplateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation('card_templates')
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent><DialogHeader><DialogTitle>{t('create_dialog.title')}</DialogTitle><DialogDescription>{t('create_dialog.description')}</DialogDescription></DialogHeader>
      {open && <CreateTemplateForm onClose={() => onOpenChange(false)} />}
    </DialogContent>
  </Dialog>
}
