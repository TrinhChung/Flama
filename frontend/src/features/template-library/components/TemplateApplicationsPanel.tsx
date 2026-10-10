import '@/shared/config/i18n'
import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { MoreHorizontal, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import {
  attachLibraryTemplate, cardTemplateQueryKeys, deleteNoteTypeTemplate, fetchTemplateApplications, retireTemplateApplication, updateTemplateApplication,
  validateBindings, type MappingField, type TemplateApplication,
} from '@/entities/card-template'
import { apiRequest } from '@/shared/api/client'
import { ConfirmDialog } from '@/shared/ui/ConfirmDialog'

export type TemplateApplicationsPanelProps = {
  noteTypeId: string
  fields?: MappingField[]
  onChanged?: () => void
}

type ApplicationMutation = 'default' | 'retire' | 'reattach' | 'delete'

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
  const execute = async (kind: ApplicationMutation, application: TemplateApplication): Promise<boolean> => {
    if (submitting.current) return false
    submitting.current = true
    setPendingId(application.id)
    setError(null)
    try {
      if (kind === 'delete') {
        await deleteNoteTypeTemplate(noteTypeId, application.template_id)
      } else {
        const result = kind === 'retire'
          ? await retireTemplateApplication(noteTypeId, application.id)
          : kind === 'default'
            ? await updateTemplateApplication(noteTypeId, application.id, { is_default: true })
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
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['card-template'] }),
        queryClient.invalidateQueries({ queryKey: ['note-type-detail', noteTypeId] }),
        queryClient.invalidateQueries({ queryKey: ['note-types'] }),
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

function ApplicationRow({ application, noteTypeId, fields, fieldsUnavailable, pending, onDefault, onRetire, onReattach, onDelete }: {
  application: TemplateApplication
  noteTypeId: string
  fields: MappingField[]
  fieldsUnavailable: boolean
  pending: boolean
  onDefault: () => void
  onRetire: () => void
  onReattach: () => void
  onDelete: () => void
}) {
  const { t } = useTranslation('template_mapping')
  const { t: legacyT } = useTranslation('card_templates')
  const name = application.display_name || application.template.name
  const mappingPath = `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(application.id)}`
  const issues = validateBindings(application.input_schema, fields, application.input_bindings)
  const invalidKeys = new Set(issues.map((issue) => issue.key))
  const mapped = application.input_schema.filter((input) => !invalidKeys.has(input.key)).length
  const emptyCount = issues.filter((issue) => issue.kind === 'unbound').length
  const needsRepair = issues.some((issue) => issue.blocking)
  const recommendedEmpty = issues.some((issue) => issue.kind === 'unbound' && issue.required)
  const active = application.status_code === 'ACTIVE'
  return <article className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 sm:flex-row sm:items-center sm:justify-between">
    <Link to={mappingPath} className="min-w-0 flex-1 space-y-1.5 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-primary">
      <div className="flex flex-wrap items-center gap-2">
        <span className="break-words font-semibold text-foreground hover:text-primary">{name}</span>
        {active && application.is_default && <Badge variant="secondary">{t('default')}</Badge>}
        {!active && <Badge variant="outline">{t('retired')}</Badge>}
      </div>
      <p className="break-words text-sm text-muted-foreground">{t('template_design', { name: application.template.name })}</p>
      <p className={`text-xs ${needsRepair && !fieldsUnavailable ? 'text-destructive' : 'text-muted-foreground'}`}>
        {fieldsUnavailable ? t('mapping_unavailable') : needsRepair ? t('needs_repair') : t('mapped', { mapped, total: application.input_schema.length })}
      </p>
      {!fieldsUnavailable && !needsRepair && emptyCount > 0 && <p className={`text-xs ${recommendedEmpty ? 'text-amber-700 dark:text-amber-400' : 'text-muted-foreground'}`}>{t('unbound', { count: emptyCount })}</p>}
    </Link>
    <div className="flex shrink-0 items-center gap-2">
      {active ? <>
        <Button variant="outline" size="sm" asChild><Link to={mappingPath}>{t('mapping_title')}</Link></Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button variant="ghost" size="icon-sm" disabled={pending} aria-label={t('actions', { name })}><MoreHorizontal className="size-4" /></Button></DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-48">
            <DropdownMenuItem asChild><Link to={`/card-templates/${encodeURIComponent(application.template_id)}`} state={{ returnTo: mappingPath }}>{t('edit_design')}</Link></DropdownMenuItem>
            <DropdownMenuItem disabled={application.is_default} onSelect={onDefault}>{t('set_default')}</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={onRetire}>{legacyT('applications_panel.btn_retire')}</DropdownMenuItem>
            <DropdownMenuItem variant="destructive" className="text-destructive focus:text-destructive" onSelect={onDelete}><Trash2 className="size-4" />{legacyT('applications_panel.btn_delete')}</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </> : <>
        <Button variant="outline" size="sm" disabled={pending} onClick={onReattach}>{legacyT('applications_panel.btn_reattach')}</Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild><Button variant="ghost" size="icon-sm" disabled={pending} aria-label={t('actions', { name })}><MoreHorizontal className="size-4" /></Button></DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-48">
            <DropdownMenuItem asChild><Link to={`/card-templates/${encodeURIComponent(application.template_id)}`} state={{ returnTo: mappingPath }}>{t('edit_design')}</Link></DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" className="text-destructive focus:text-destructive" onSelect={onDelete}><Trash2 className="size-4" />{legacyT('applications_panel.btn_delete')}</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </>}
    </div>
  </article>
}

function TemplateApplicationsContent(props: TemplateApplicationsPanelProps) {
  const { t } = useTranslation('template_mapping')
  const { t: legacyT } = useTranslation('card_templates')
  const state = useTemplateApplications(props)
  const [retiring, setRetiring] = useState<TemplateApplication | null>(null)
  const [deleting, setDeleting] = useState<TemplateApplication | null>(null)
  const fieldsUnavailable = props.fields === undefined && !state.detail.data
  const active = state.applications.data?.items.filter((application) => application.status_code === 'ACTIVE') ?? []
  const retired = state.applications.data?.items.filter((application) => application.status_code === 'RETIRED') ?? []
  const renderRow = (application: TemplateApplication) => <ApplicationRow key={application.id} application={application} noteTypeId={props.noteTypeId}
    fields={state.fields} fieldsUnavailable={fieldsUnavailable} pending={Boolean(state.pendingId)}
    onDefault={() => void state.execute('default', application)}
    onRetire={() => { state.setError(null); setRetiring(application) }}
    onReattach={() => void state.execute('reattach', application)}
    onDelete={() => { state.setError(null); setDeleting(application) }} />
  return <section aria-label={t('templates_title')} className="space-y-4">
    {state.applications.isPending && <p role="status">{legacyT('applications_panel.loading')}</p>}
    {state.applications.isError && <Alert variant="destructive"><AlertDescription>
      {state.applications.error.message}
      <Button variant="outline" size="sm" onClick={() => void state.applications.refetch()}>{t('retry')}</Button>
    </AlertDescription></Alert>}
    {state.detail.isError && props.fields === undefined && <Alert variant="destructive"><AlertDescription>
      {legacyT('applications_panel.error_fields')} {state.detail.error.message}
      <Button variant="outline" size="sm" onClick={() => void state.detail.refetch()}>{t('retry')}</Button>
    </AlertDescription></Alert>}
    {state.applications.isSuccess && active.length === 0 && <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">{t('empty')}</p>}
    <div className="space-y-3">{active.map(renderRow)}</div>
    {retired.length > 0 && <details className="rounded-xl border border-border">
      <summary className="cursor-pointer rounded-xl px-4 py-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">{t('removed', { count: retired.length })}</summary>
      <div className="space-y-3 border-t border-border p-3">{retired.map(renderRow)}</div>
    </details>}
    {state.error && !retiring && !deleting && <Alert variant="destructive"><AlertDescription>{state.error.message}</AlertDescription></Alert>}
    <ConfirmDialog open={Boolean(retiring)} onOpenChange={(open) => { if (!open) setRetiring(null) }}
      title={legacyT('applications_panel.retire_confirm_title')} description={legacyT('applications_panel.retire_confirm_desc')}
      variant="destructive" confirmText={legacyT('applications_panel.retire_confirm_btn')} cancelText={t('cancel')} isLoading={Boolean(state.pendingId)}
      onConfirm={async () => { if (retiring && await state.execute('retire', retiring)) setRetiring(null) }}>
      {state.error && retiring && <p role="alert" className="text-destructive">{state.error.message}</p>}
    </ConfirmDialog>
    <ConfirmDialog open={Boolean(deleting)} onOpenChange={(open) => { if (!open) setDeleting(null) }}
      title={legacyT('applications_panel.delete_confirm_title')} description={legacyT('applications_panel.delete_confirm_desc')}
      variant="destructive" confirmText={legacyT('applications_panel.delete_confirm_btn')} cancelText={t('cancel')} isLoading={Boolean(state.pendingId)}
      onConfirm={async () => {
        if (deleting) {
          const success = await state.execute('delete', deleting)
          if (success) {
            toast.success(legacyT('applications_panel.delete_success'))
            setDeleting(null)
          }
        }
      }}>
      {state.error && deleting && <p role="alert" className="text-destructive">{state.error.message}</p>}
    </ConfirmDialog>
  </section>
}

export function TemplateApplicationsPanel(props: TemplateApplicationsPanelProps) {
  return <TemplateApplicationsContent key={props.noteTypeId} {...props} />
}
