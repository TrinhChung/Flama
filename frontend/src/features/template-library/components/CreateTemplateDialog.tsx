import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { createLibraryTemplate } from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

function CreateTemplateForm({ onClose }: { onClose: () => void }) {
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
      toast.success('Đã tạo mẫu thẻ.')
      onClose()
      navigate(`/card-templates/${encodeURIComponent(template.id)}`)
    },
  })
  return <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (name.trim() && name.trim().length <= 255 && !create.isPending) create.mutate() }}>
    <div className="space-y-2"><Label htmlFor="create-template-name">Tên mẫu</Label><Input id="create-template-name" value={name} onChange={(event) => setName(event.target.value)} disabled={create.isPending} maxLength={255} autoFocus /></div>
    <div className="space-y-2"><Label htmlFor="create-template-description">Mô tả</Label><Input id="create-template-description" value={description} onChange={(event) => setDescription(event.target.value)} disabled={create.isPending} /></div>
    {create.error && <p role="alert" className="text-sm text-destructive">{create.error instanceof Error ? create.error.message : 'Không thể tạo mẫu thẻ.'}</p>}
    <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Hủy</Button><Button type="submit" disabled={!name.trim() || name.trim().length > 255 || create.isPending}>{create.isPending ? 'Đang tạo…' : 'Tạo mẫu'}</Button></div>
  </form>
}

export function CreateTemplateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent><DialogHeader><DialogTitle>Tạo mẫu mới</DialogTitle><DialogDescription>Tạo mẫu thẻ độc lập để dùng lại cho nhiều loại thẻ.</DialogDescription></DialogHeader>
      {open && <CreateTemplateForm onClose={() => onOpenChange(false)} />}
    </DialogContent>
  </Dialog>
}
