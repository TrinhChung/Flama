import '@/shared/config/i18n'
import { useEffect, useId, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { attachLibraryTemplate, cardTemplateQueryKeys, fetchTemplateApplications, FieldMappingEditor, suggestBindings, validateBindings,
  type MappingField, type MappingIssue, type TemplateApplication, type TemplateBindings, type TemplateLibraryDetail } from '@/entities/card-template'
import { ApiError, apiRequest } from '@/shared/api/client'

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
  initialOccurrenceKey?: string
  onApplied?: (application: TemplateApplication) => void
}

type ApplyTemplateFormProps = Omit<ApplyTemplateWizardProps, 'open'> & {
  onBack?: () => void
  onPendingChange?: (pending: boolean) => void
  submitLabel?: string
}

function useApplyTemplate({ template, initialNoteTypeId, onOpenChange, onApplied, onPendingChange }: ApplyTemplateFormProps) {
  const { t } = useTranslation('card_templates')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const mounted = useRef(true)
  const initialized = useRef(false)
  const submitting = useRef(false)
  const [step, setStep] = useState<1 | 2>(initialNoteTypeId ? 2 : 1)
  const [selectedId, setSelectedId] = useState('')
  const [bindings, setBindings] = useState<TemplateBindings>({})
  const [displayName, setDisplayName] = useState(template.name)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const noteTypes = useQuery({
    queryKey: ['note-types', 'template-attachment'],
    queryFn: ({ signal }) => apiRequest<{ items: AttachableNoteType[] }>('/api/note-types?compact=true', { signal }),
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
  const existingApplications = useQuery({
    queryKey: cardTemplateQueryKeys.applications(selectedId),
    queryFn: ({ signal }) => fetchTemplateApplications(selectedId, false, signal),
    enabled: Boolean(selectedId) && error instanceof ApiError && error.code === 'APPLICATION_EXISTS',
  })
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
    || !displayName.trim() || displayName.length > 255
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
    onPendingChange?.(true)
    setError(null)
    const noteTypeId = selected.id
    try {
      const application = await attachLibraryTemplate(noteTypeId, {
        template_id: template.id,
        occurrence_key: 'compat',
        display_name: displayName,
        input_bindings: bindings,
      })
      if (application.template_id !== template.id) throw new Error(t('apply_wizard.error_mismatch'))
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['card-template'] }),
        queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] }),
        queryClient.invalidateQueries({ queryKey: ['note-types'] }),
      ])
      if (!mounted.current) return
      toast.success(t('apply_wizard.toast_success'), {
        action: { label: t('apply_wizard.toast_action_open'), onClick: () => navigate(`/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(application.id)}`) },
      })
      onApplied?.(application)
      onOpenChange(false)
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause : new Error(t('apply_wizard.error_failed')))
    } finally {
      submitting.current = false
      if (mounted.current) {
        setPending(false)
        onPendingChange?.(false)
      }
    }
  }
  return { noteTypes, step, setStep, selected, selectedId, selectNoteType, bindings,
    setBindings: (next: TemplateBindings) => { setBindings(next); setError(null) },
    displayName, setDisplayName, pending, error, issues, invalid, submit, existingApplications }
}

export function ApplyTemplateForm(props: ApplyTemplateFormProps) {
  const { t } = useTranslation('card_templates')
  const { t: mappingT } = useTranslation('template_mapping')
  const form = useApplyTemplate(props)
  const id = useId()
  const errorMessage = form.error instanceof ApiError && form.error.code === 'APPLICATION_EXISTS'
    ? t('apply_wizard.error_conflict')
    : form.error?.message
  return <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (form.step === 2) void form.submit() }}>
    <DialogHeader>
      <DialogTitle>{form.step === 1 ? t('apply_wizard.step1_title') : t('apply_wizard.step2_title')}</DialogTitle>
      <DialogDescription>{t('apply_wizard.description')}</DialogDescription>
    </DialogHeader>
    {form.noteTypes.isPending && <p role="status" className="text-muted-foreground">{t('apply_wizard.loading_note_types')}</p>}
    {form.noteTypes.isError && <Alert variant="destructive"><AlertDescription>
      {form.noteTypes.error.message}
      <Button type="button" variant="outline" className="mt-2" onClick={() => void form.noteTypes.refetch()}>{t('apply_wizard.retry')}</Button>
    </AlertDescription></Alert>}
    {form.noteTypes.data?.items.length === 0 && <div className="space-y-2 text-muted-foreground">
      <p>{t('apply_wizard.empty_note_types')}</p>
      <Button type="button" variant="outline" onClick={() => void form.noteTypes.refetch()}>{t('apply_wizard.reload')}</Button>
    </div>}
    {props.initialNoteTypeId && form.noteTypes.isSuccess && !form.selected && <Alert variant="destructive"><AlertDescription>{mappingT('unavailable_note_type')}</AlertDescription></Alert>}
    {!props.initialNoteTypeId && Boolean(form.noteTypes.data?.items.length) && <div className="space-y-2">
      <Label htmlFor={`${id}-note-type`}>{t('apply_wizard.note_type_label')}</Label>
      <NativeSelect id={`${id}-note-type`} className="w-full" value={form.selectedId} disabled={form.pending}
        onChange={(event) => form.selectNoteType(event.target.value)}>
        <NativeSelectOption value="">{t('apply_wizard.select_placeholder')}</NativeSelectOption>
        {form.noteTypes.data!.items.map((item) => <NativeSelectOption key={item.id} value={item.id}>
          {item.name}{item.is_marketplace_install ? t('apply_wizard.marketplace_suffix') : ''}
        </NativeSelectOption>)}
      </NativeSelect>
      {form.selected?.is_marketplace_install && <Badge variant="secondary">{t('apply_wizard.marketplace_badge')}</Badge>}
    </div>}
    {props.initialNoteTypeId && form.selected?.is_marketplace_install && <Badge variant="secondary">{t('apply_wizard.marketplace_badge')}</Badge>}
    {form.step === 2 && form.selected && <>
      <div className="space-y-2">
        <Label htmlFor={`${id}-name`}>{mappingT('display_name')}</Label>
        <Input id={`${id}-name`} value={form.displayName} maxLength={255} disabled={form.pending}
          aria-invalid={!form.displayName.trim() || (form.error instanceof ApiError && form.error.field === 'display_name')}
          onChange={(event) => form.setDisplayName(event.target.value)} />
      </div>
      <FieldMappingEditor inputs={props.template.input_schema} fields={form.selected.field_defs}
        bindings={form.bindings} onChange={form.setBindings} issues={form.issues} disabled={form.pending} />
    </>}
    {props.template.archived_at && <p className="text-muted-foreground">{t('apply_wizard.unarchive_warning')}</p>}
    {errorMessage && <Alert variant="destructive"><AlertDescription>{errorMessage}</AlertDescription></Alert>}
    {form.error instanceof ApiError && form.error.code === 'APPLICATION_EXISTS' && <div className="space-y-2">
      {form.existingApplications.data?.items.filter((item) => item.template_id === props.template.id).map((item) => <Button key={item.id} variant="outline" asChild>
        <Link to={`/flashcards/note-types/${encodeURIComponent(form.selectedId)}/templates/${encodeURIComponent(item.id)}`} onClick={() => props.onOpenChange(false)}>
          {mappingT('open_existing')}: {item.display_name || item.template.name}
        </Link>
      </Button>)}
      {form.existingApplications.isError && <Button type="button" variant="outline" onClick={() => void form.existingApplications.refetch()}>{mappingT('retry')}</Button>}
    </div>}
    <DialogFooter>
      {props.onBack ? <Button type="button" variant="outline" disabled={form.pending} onClick={props.onBack}>{mappingT('back_to_library')}</Button>
        : form.step === 2 && !props.initialNoteTypeId && <Button type="button" variant="outline" disabled={form.pending} onClick={() => form.setStep(1)}>{t('apply_wizard.back')}</Button>}
      <Button type="button" variant="outline" disabled={form.pending} onClick={() => props.onOpenChange(false)}>{t('apply_wizard.cancel')}</Button>
      {form.step === 1
        ? <Button key="continue" type="button" disabled={!form.selected} onClick={(event) => {
          // Cancel native activation before React renders the submit button for step two.
          event.preventDefault()
          form.setStep(2)
        }}>{t('apply_wizard.continue')}</Button>
        : <Button key="attach" type="submit" disabled={form.invalid || form.pending}>{form.pending ? t('apply_wizard.attaching') : props.submitLabel ?? t('apply_wizard.attach')}</Button>}
    </DialogFooter>
  </form>
}

export function ApplyTemplateWizard({ open, ...props }: ApplyTemplateWizardProps) {
  const [pending, setPending] = useState(false)
  useEffect(() => { if (!open) setPending(false) }, [open])
  return <Dialog open={open} onOpenChange={(nextOpen) => { if (!pending) props.onOpenChange(nextOpen) }}>
    {open && <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-xl" showCloseButton={!pending}
      onEscapeKeyDown={(event) => { if (pending) event.preventDefault() }} onPointerDownOutside={(event) => { if (pending) event.preventDefault() }}>
      <ApplyTemplateForm key={`${props.template.id}:${props.initialNoteTypeId ?? ''}:${props.initialOccurrenceKey ?? 'compat'}`} {...props} onPendingChange={setPending} />
    </DialogContent>}
  </Dialog>
}
