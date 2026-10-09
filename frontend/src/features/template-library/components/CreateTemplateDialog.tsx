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

function CreateTemplateForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation('card_templates')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const active = useRef(true)
  useEffect(() => { active.current = true; return () => { active.current = false } }, [])
  const create = useMutation({
    mutationFn: () => createLibraryTemplate({
      name: name.trim(), description,
      front_html: '{{Front}}', back_html: '{{Front}}<hr>{{Back}}', shared_css: '',
      input_schema: [{ key: 'Front', label: 'Front', type: 'text', required: false }, { key: 'Back', label: 'Back', type: 'text', required: false }],
    }),
    onSuccess: (template) => {
      void queryClient.invalidateQueries({ queryKey: ['card-template', 'library'] })
      if (!active.current) return
      toast.success(t('create_dialog.toast_success'))
      onClose()
      navigate(`/card-templates/${encodeURIComponent(template.id)}`)
    },
  })
  return <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (name.trim() && name.trim().length <= 255 && !create.isPending) create.mutate() }}>
    <div className="space-y-2"><Label htmlFor="create-template-name">{t('create_dialog.name_label')}</Label><Input id="create-template-name" value={name} onChange={(event) => setName(event.target.value)} disabled={create.isPending} maxLength={255} autoFocus /></div>
    <div className="space-y-2"><Label htmlFor="create-template-description">{t('create_dialog.description_label')}</Label><Input id="create-template-description" value={description} onChange={(event) => setDescription(event.target.value)} disabled={create.isPending} /></div>
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
