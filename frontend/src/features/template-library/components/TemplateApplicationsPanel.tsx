import '@/shared/config/i18n'
import { useEffect, useId, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { attachLibraryTemplate, cardTemplateQueryKeys, fetchTemplateApplications, retireTemplateApplication, updateTemplateApplication,
  type TemplateApplication, type TemplateBindings } from '@/entities/card-template'
import { validateBindings, type MappingField } from '../lib/fieldMapping'
import { ApiError, apiRequest } from '@/shared/api/client'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'
import { FieldMappingEditor } from './FieldMappingEditor'

export type TemplateApplicationsPanelProps = {
  noteTypeId: string
  fields?: MappingField[]
  onChanged?: () => void
}

type ApplicationMutation = 'edit' | 'retire' | 'reattach'

function useTemplateApplications({ noteTypeId, fields, onChanged }: TemplateApplicationsPanelProps) {
  const { t } = useTranslation('card_templates')
  const queryClient = useQueryClient()
  const mounted = useRef(true)
  const submitting = useRef(false)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  const applications = useQuery({
    queryKey: cardTemplateQueryKeys.applications(noteTypeId, true),
    queryFn: ({ signal }) => fetchTemplateApplications(noteTypeId, true, signal),
  })
  const detail = useQuery({
    queryKey: ['note-type-detail', noteTypeId, 'attachment-fields'],
    queryFn: ({ signal }) => apiRequest<{ field_defs: MappingField[] }>(`/api/note-types/${encodeURIComponent(noteTypeId)}`, { signal }),
    enabled: fields === undefined,
  })
  const execute = async (kind: ApplicationMutation, application: TemplateApplication, inputBindings?: TemplateBindings, displayName?: string): Promise<boolean> => {
    if (submitting.current) return false
    submitting.current = true
    setPendingId(application.id)
    setError(null)
    try {
      const result = kind === 'retire'
        ? await retireTemplateApplication(noteTypeId, application.id)
        : kind === 'edit'
          ? await updateTemplateApplication(noteTypeId, application.id, { input_bindings: inputBindings, display_name: displayName })
          : await attachLibraryTemplate(noteTypeId, {
            template_id: application.template_id,
            occurrence_key: application.occurrence_key,
            input_bindings: application.input_bindings,
            display_name: application.display_name,
            position: application.position,
            is_default: application.is_default,
          })
      if (result.id !== application.id || result.template_id !== application.template_id) {
        throw new Error(t('applications_panel.error_mismatch'))
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['card-template'] }),
        queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] }),
      ])
      if (!mounted.current) return false
      onChanged?.()
      return true
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause : new Error(t('applications_panel.error_failed')))
      return false
    } finally {
      submitting.current = false
      if (mounted.current) setPendingId(null)
    }
  }
  return { applications, detail, fields: fields ?? detail.data?.field_defs ?? [], pendingId, error, setError, execute }
}

function ApplicationEditor({ application, fields, pending, error, onSave, onClose }: {
  application: TemplateApplication
  fields: MappingField[]
  pending: boolean
  error: Error | null
  onSave: (bindings: TemplateBindings, name: string) => void
  onClose: () => void
}) {
  const { t } = useTranslation('card_templates')
  const id = useId()
  const [bindings, setBindings] = useState(application.input_bindings)
  const [name, setName] = useState(application.display_name ?? application.template.name)
  const issues = validateBindings(application.input_schema, fields, bindings)
  const invalid = issues.some((issue) => issue.blocking) || name.length > 255
  const serverField = error instanceof ApiError ? error.field : undefined
  return <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); if (!invalid && !pending) onSave(bindings, name) }}>
    <DialogHeader>
      <DialogTitle>{t('applications_panel.dialog_edit_title')}</DialogTitle>
      <DialogDescription>{t('applications_panel.dialog_edit_desc')}</DialogDescription>
    </DialogHeader>
    <div className="space-y-2">
      <Label htmlFor={`${id}-name`}>{t('applications_panel.display_name_label')}</Label>
      <Input id={`${id}-name`} value={name} maxLength={255} disabled={pending}
        aria-invalid={serverField === 'display_name'} onChange={(event) => setName(event.target.value)} />
    </div>
    <FieldMappingEditor inputs={application.input_schema} fields={fields} bindings={bindings}
      onChange={setBindings} issues={issues} disabled={pending} />
    {error && <Alert variant="destructive"><AlertDescription>
      {serverField && application.input_schema.some((input) => input.key === serverField) && <code>{`{{${serverField}}}: `}</code>}{error.message}
    </AlertDescription></Alert>}
    <DialogFooter>
      <Button type="button" variant="outline" disabled={pending} onClick={onClose}>{t('applications_panel.cancel')}</Button>
      <Button type="submit" disabled={invalid || pending}>{pending ? t('applications_panel.saving') : t('applications_panel.save_mapping')}</Button>
    </DialogFooter>
  </form>
}

function TemplateApplicationsContent(props: TemplateApplicationsPanelProps) {
  const { t } = useTranslation('card_templates')
  const state = useTemplateApplications(props)
  const [editing, setEditing] = useState<TemplateApplication | null>(null)
  const [retiring, setRetiring] = useState<TemplateApplication | null>(null)
  const fieldsUnavailable = props.fields === undefined && !state.detail.data
  return <section aria-label={t('applications_panel.section_aria')} className="space-y-4 rounded-xl border border-border bg-card p-4 sm:p-6">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-lg font-semibold">{t('applications_panel.section_title')}</h2>
      <Button variant="outline" size="sm" asChild><Link to="/card-templates">{t('applications_panel.open_library')}</Link></Button>
    </div>
    <p className="text-sm text-muted-foreground">{t('applications_panel.subtitle')}</p>
    {state.applications.isPending && <p role="status">{t('applications_panel.loading')}</p>}
    {state.applications.isError && <Alert variant="destructive"><AlertDescription>
      {state.applications.error.message}
      <Button variant="outline" size="sm" onClick={() => void state.applications.refetch()}>{t('applications_panel.retry')}</Button>
    </AlertDescription></Alert>}
    {state.detail.isError && props.fields === undefined && <Alert variant="destructive"><AlertDescription>
      {t('applications_panel.error_fields')} {state.detail.error.message}
      <Button variant="outline" size="sm" onClick={() => void state.detail.refetch()}>{t('applications_panel.retry')}</Button>
    </AlertDescription></Alert>}
    {state.applications.data?.items.length === 0 && <p className="text-sm text-muted-foreground">{t('applications_panel.empty')}</p>}
    <div className="space-y-3">
      {state.applications.data?.items.map((application) => <article key={application.id} className="flex flex-col gap-3 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-1">
          <Link to={`/card-templates/${encodeURIComponent(application.template_id)}`} className="break-words font-medium text-primary underline-offset-4 hover:underline">{application.template.name}</Link>
          <p className="break-words text-sm">{application.display_name ?? application.template.name} · <code>{application.occurrence_key}</code></p>
          <Badge variant={application.status_code === 'ACTIVE' ? 'default' : 'secondary'}>{application.status_code}</Badge>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {application.status_code === 'ACTIVE' ? <>
            <Button variant="outline" size="sm" disabled={Boolean(state.pendingId) || fieldsUnavailable} onClick={() => { state.setError(null); setEditing(application) }}>{t('applications_panel.btn_edit')}</Button>
            <Button variant="outline" size="sm" disabled={Boolean(state.pendingId)} onClick={() => { state.setError(null); setRetiring(application) }}>{t('applications_panel.btn_retire')}</Button>
          </> : <Button variant="outline" size="sm" disabled={Boolean(state.pendingId)} onClick={() => void state.execute('reattach', application)}>{t('applications_panel.btn_reattach')}</Button>}
        </div>
      </article>)}
    </div>
    {state.error && !editing && !retiring && <Alert variant="destructive"><AlertDescription>{state.error.message}</AlertDescription></Alert>}
    <Dialog open={Boolean(editing)} onOpenChange={(open) => { if (!open && !state.pendingId) setEditing(null) }}>
      {editing && <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-xl" onEscapeKeyDown={(event) => { if (state.pendingId) event.preventDefault() }}
        onPointerDownOutside={(event) => { if (state.pendingId) event.preventDefault() }}>
        <ApplicationEditor key={editing.id} application={editing} fields={state.fields} pending={Boolean(state.pendingId)} error={state.error}
          onClose={() => setEditing(null)} onSave={(bindings, name) => { void state.execute('edit', editing, bindings, name).then((success) => { if (success) setEditing(null) }) }} />
      </DialogContent>}
    </Dialog>
    <ConfirmDialog open={Boolean(retiring)} onOpenChange={(open) => { if (!open) setRetiring(null) }}
      title={t('applications_panel.retire_confirm_title')} description={t('applications_panel.retire_confirm_desc')}
      variant="destructive" confirmText={t('applications_panel.retire_confirm_btn')} isLoading={Boolean(state.pendingId)}
      onConfirm={async () => { if (retiring && await state.execute('retire', retiring)) setRetiring(null) }}>
      {state.error && retiring && <p role="alert" className="text-destructive">{state.error.message}</p>}
    </ConfirmDialog>
  </section>
}

export function TemplateApplicationsPanel(props: TemplateApplicationsPanelProps) {
  return <TemplateApplicationsContent key={props.noteTypeId} {...props} />
}
