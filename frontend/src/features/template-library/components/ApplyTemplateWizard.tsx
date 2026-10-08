import { useEffect, useId, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { attachLibraryTemplate, type TemplateApplication, type TemplateBindings, type TemplateLibraryDetail } from '@/entities/card-template'
import { suggestBindings, validateBindings, type MappingField, type MappingIssue } from '../lib/fieldMapping'
import { ApiError, apiRequest } from '@/shared/api/client'
import { FieldMappingEditor } from './FieldMappingEditor'

type AttachableNoteType = {
  id: string
  name: string
  field_defs: Array<MappingField & { position: number }>
  is_marketplace_install: boolean
}

export type ApplyTemplateWizardProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  template: TemplateLibraryDetail
  initialNoteTypeId?: string
  onApplied?: (application: TemplateApplication) => void
}

function useApplyTemplate({ template, initialNoteTypeId, onOpenChange, onApplied }: Omit<ApplyTemplateWizardProps, 'open'>) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const mounted = useRef(true)
  const initialized = useRef(false)
  const submitting = useRef(false)
  const [step, setStep] = useState<1 | 2>(1)
  const [selectedId, setSelectedId] = useState('')
  const [bindings, setBindings] = useState<TemplateBindings>({})
  const [displayName, setDisplayName] = useState(template.name)
  const [occurrence, setOccurrence] = useState('compat')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const noteTypes = useQuery({
    queryKey: ['note-types', 'template-attachment'],
    queryFn: ({ signal }) => apiRequest<{ items: AttachableNoteType[] }>('/api/note-types', { signal }),
  })
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  useEffect(() => {
    if (initialized.current || !noteTypes.data) return
    initialized.current = true
    const initial = noteTypes.data.items.find((item) => item.id === initialNoteTypeId)
    if (initial) {
      setSelectedId(initial.id)
      setBindings(suggestBindings(template.input_schema, initial.field_defs))
      setStep(2)
    }
  }, [noteTypes.data, initialNoteTypeId, template.input_schema])
  const selected = noteTypes.data?.items.find((item) => item.id === selectedId)
  const issues = validateBindings(template.input_schema, selected?.field_defs ?? [], bindings)
  if (error instanceof ApiError && template.input_schema.some((input) => input.key === error.field)) {
    const key = error.field!
    const fieldId = Object.hasOwn(bindings, key) ? bindings[key] ?? '' : ''
    const serverIssue: MappingIssue | null = error.code === 'FIELD_OUT_OF_SCOPE'
      ? { kind: 'field_out_of_scope', key, fieldId, blocking: true }
      : error.code === 'INPUT_TYPE_MISMATCH'
        ? { kind: 'type_mismatch', key, fieldId, blocking: true }
        : error.code === 'INPUT_NOT_FOUND' ? { kind: 'unknown_input', key, blocking: true } : null
    if (serverIssue && !issues.some((issue) => issue.key === key && issue.kind === serverIssue.kind)) issues.push(serverIssue)
  }
  const invalid = !selected || issues.some((issue) => issue.blocking)
    || !displayName.trim() || displayName.length > 255 || !occurrence.trim() || occurrence.trim().length > 64
    || Boolean(template.archived_at)
  const selectNoteType = (id: string) => {
    const next = noteTypes.data?.items.find((item) => item.id === id)
    setSelectedId(id)
    setBindings(suggestBindings(template.input_schema, next?.field_defs ?? []))
    setError(null)
  }
  const submit = async () => {
    if (invalid || submitting.current || !selected) return
    submitting.current = true
    setPending(true)
    setError(null)
    const noteTypeId = selected.id
    try {
      const application = await attachLibraryTemplate(noteTypeId, {
        template_id: template.id,
        occurrence_key: occurrence.trim(),
        display_name: displayName,
        input_bindings: bindings,
      })
      if (application.template_id !== template.id) throw new Error('Máy chủ trả về mẫu không khớp. Hãy tải lại danh sách mẫu đã gắn.')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['card-template'] }),
        queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] }),
        queryClient.invalidateQueries({ queryKey: ['note-types'] }),
      ])
      if (!mounted.current) return
      toast.success('Đã gắn mẫu vào loại thẻ.', {
        action: { label: 'Mở loại thẻ', onClick: () => navigate(`/note-types/${encodeURIComponent(noteTypeId)}`) },
      })
      onApplied?.(application)
      onOpenChange(false)
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause : new Error('Không thể gắn mẫu.'))
    } finally {
      submitting.current = false
      if (mounted.current) setPending(false)
    }
  }
  return { noteTypes, step, setStep, selected, selectedId, selectNoteType, bindings,
    setBindings: (next: TemplateBindings) => { setBindings(next); setError(null) },
    displayName, setDisplayName, occurrence, setOccurrence, pending, error, issues, invalid, submit }
}

function ApplyTemplateForm(props: Omit<ApplyTemplateWizardProps, 'open'>) {
  const form = useApplyTemplate(props)
  const id = useId()
  const errorMessage = form.error instanceof ApiError && form.error.code === 'APPLICATION_EXISTS'
    ? 'Lần gắn này đã tồn tại. Chọn mã lần gắn khác hoặc sửa ánh xạ hiện có.'
    : form.error?.message
  return <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (form.step === 2) void form.submit() }}>
    <DialogHeader>
      <DialogTitle>{form.step === 1 ? 'Chọn loại thẻ' : 'Ánh xạ trường'}</DialogTitle>
      <DialogDescription>Mẫu dùng chung giữ nguyên nội dung; ánh xạ chỉ áp dụng cho loại thẻ này.</DialogDescription>
    </DialogHeader>
    {form.noteTypes.isPending && <p role="status" className="text-muted-foreground">Đang tải loại thẻ…</p>}
    {form.noteTypes.isError && <Alert variant="destructive"><AlertDescription>
      {form.noteTypes.error.message}
      <Button type="button" variant="outline" className="mt-2" onClick={() => void form.noteTypes.refetch()}>Thử lại</Button>
    </AlertDescription></Alert>}
    {form.noteTypes.data?.items.length === 0 && <div className="space-y-2 text-muted-foreground">
      <p>Chưa có loại thẻ để gắn mẫu.</p>
      <Button type="button" variant="outline" onClick={() => void form.noteTypes.refetch()}>Tải lại</Button>
    </div>}
    {Boolean(form.noteTypes.data?.items.length) && <div className="space-y-2">
      <Label htmlFor={`${id}-note-type`}>Loại thẻ</Label>
      <NativeSelect id={`${id}-note-type`} className="w-full" value={form.selectedId} disabled={form.pending}
        onChange={(event) => form.selectNoteType(event.target.value)}>
        <NativeSelectOption value="">— Chọn loại thẻ —</NativeSelectOption>
        {form.noteTypes.data!.items.map((item) => <NativeSelectOption key={item.id} value={item.id}>
          {item.name}{item.is_marketplace_install ? ' · Bản cài từ marketplace' : ''}
        </NativeSelectOption>)}
      </NativeSelect>
      {form.selected?.is_marketplace_install && <Badge variant="secondary">Bản cài từ marketplace</Badge>}
    </div>}
    {form.step === 2 && form.selected && <>
      <div className="space-y-2">
        <Label htmlFor={`${id}-name`}>Tên hiển thị</Label>
        <Input id={`${id}-name`} value={form.displayName} maxLength={255} disabled={form.pending}
          aria-invalid={!form.displayName.trim() || (form.error instanceof ApiError && form.error.field === 'display_name')}
          onChange={(event) => form.setDisplayName(event.target.value)} />
      </div>
      <div className="space-y-2">
        <Label htmlFor={`${id}-occurrence`}>Mã lần gắn</Label>
        <Input id={`${id}-occurrence`} value={form.occurrence} maxLength={64} disabled={form.pending}
          aria-invalid={!form.occurrence.trim() || (form.error instanceof ApiError && form.error.field === 'occurrence_key')}
          onChange={(event) => form.setOccurrence(event.target.value)} />
      </div>
      <FieldMappingEditor inputs={props.template.input_schema} fields={form.selected.field_defs}
        bindings={form.bindings} onChange={form.setBindings} issues={form.issues} disabled={form.pending} />
    </>}
    {props.template.archived_at && <p className="text-muted-foreground">Bỏ lưu trữ để gắn mẫu.</p>}
    {errorMessage && <Alert variant="destructive"><AlertDescription>{errorMessage}</AlertDescription></Alert>}
    <DialogFooter>
      {form.step === 2 && <Button type="button" variant="outline" disabled={form.pending} onClick={() => form.setStep(1)}>Quay lại</Button>}
      <Button type="button" variant="outline" onClick={() => props.onOpenChange(false)}>Hủy</Button>
      {form.step === 1
        ? <Button key="continue" type="button" disabled={!form.selected} onClick={(event) => {
          // Cancel native activation before React renders the submit button for step two.
          event.preventDefault()
          form.setStep(2)
        }}>Tiếp tục</Button>
        : <Button key="attach" type="submit" disabled={form.invalid || form.pending}>{form.pending ? 'Đang gắn…' : 'Gắn mẫu'}</Button>}
    </DialogFooter>
  </form>
}

export function ApplyTemplateWizard({ open, ...props }: ApplyTemplateWizardProps) {
  return <Dialog open={open} onOpenChange={props.onOpenChange}>
    {open && <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-xl">
      <ApplyTemplateForm key={`${props.template.id}:${props.initialNoteTypeId ?? ''}`} {...props} />
    </DialogContent>}
  </Dialog>
}
