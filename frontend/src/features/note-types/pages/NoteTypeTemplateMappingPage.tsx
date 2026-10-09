import '@/shared/config/i18n'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowUpRight, Database, Save, Settings2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { FieldMappingEditor } from '@/entities/card-template'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useUnsavedChangesGuard } from '@/shared/hooks/useUnsavedChangesGuard'
import { ApiError } from '@/shared/api/client'
import { NoteTypeLivePreview } from '../components/NoteTypeLivePreview'
import { NoteTypeSetupShell } from '../components/NoteTypeSetupShell'
import { useTemplateMappingDraft } from '../hooks/useTemplateMappingDraft'

export function NoteTypeTemplateMappingPage() {
  const { id = '', applicationId = '' } = useParams<{ id: string; applicationId: string }>()
  return <MappingEditor key={`${id}:${applicationId}`} noteTypeId={id} applicationId={applicationId} />
}

function MappingEditor({ noteTypeId, applicationId }: { noteTypeId: string; applicationId: string }) {
  const { t } = useTranslation('template_mapping')
  const state = useTemplateMappingDraft(noteTypeId, applicationId)
  const [samplesOpen, setSamplesOpen] = useState(false)
  const [side, setSide] = useState<'front' | 'back'>('front')
  const previewFields = useMemo(() => state.application?.input_schema.map((input, position) => ({
    id: `f_${position}`, name: input.key, field_type: input.type, position,
  })) ?? [], [state.application?.input_schema])
  const { confirmDialog } = useUnsavedChangesGuard(state.dirty, t('discard_message'), {
    onSave: async () => {
      if (state.saveMutation.isPending) throw new Error(t('saving'))
      await state.saveMutation.mutateAsync()
    },
  })
  const { application, draft } = state
  const listPath = `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates`
  const mappingPath = `${listPath}/${encodeURIComponent(applicationId)}`
  if (state.detail.isPending || state.applications.isPending) return <PageLoading />
  if (state.detail.error || state.applications.error) return <Page><PageError error={state.detail.error ?? state.applications.error} /><Button variant="outline" onClick={() => { void state.detail.refetch(); void state.applications.refetch() }}>{t('retry')}</Button></Page>
  if (!application) return <Page><PageError error={new Error(t('not_found'))} /><Button asChild variant="outline"><Link to={listPath}>{t('back')}</Link></Button></Page>
  if (!draft) return <PageLoading />
  const pending = state.saveMutation.isPending
  const save = () => { void state.saveMutation.mutateAsync().catch(() => { /* Mutation error is shown with the draft. */ }) }
  const usedFieldIds = new Set(Object.values(draft.bindings))
  const saveError = state.saveMutation.error
  const fieldErrors = saveError instanceof ApiError && saveError.field ? Object.fromEntries([[saveError.field, saveError.message]]) : undefined
  return <NoteTypeSetupShell noteTypeId={noteTypeId} name={state.detail.data!.name} activeTab="templates"
    fieldCount={state.fields.length} templateCount={state.applications.data!.items.filter((item) => item.status_code === 'ACTIVE').length}>
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1"><Link to={listPath} className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" />{t('back')}</Link>
          <h2 className="break-words text-xl font-semibold">{application.display_name ?? application.template.name}</h2>
          <p className="text-sm text-muted-foreground">{t('mapping_description')}</p></div>
        <div className="flex flex-wrap items-center gap-2">
          {state.dirty && <span role="status" className="text-xs text-muted-foreground">{t('unsaved')}</span>}
          <Button asChild variant="outline"><Link to={`/card-templates/${encodeURIComponent(application.template_id)}?${new URLSearchParams({ returnTo: mappingPath })}`}><ArrowUpRight className="size-4" />{t('edit_design')}</Link></Button>
          <Button disabled={pending || state.invalid || !state.dirty} onClick={save}><Save className="size-4" />{pending ? t('saving') : t('save')}</Button>
        </div>
      </div>
      {application.status_code === 'RETIRED' && <p role="status" className="rounded-xl border p-4 text-sm text-muted-foreground">{t('retired_notice')}</p>}
      {state.sourceChanged && <p role="status" className="rounded-xl border border-primary/30 bg-primary/5 p-3 text-sm">{t('source_changed')}</p>}
      {state.saveMutation.error && <PageError error={state.saveMutation.error} />}
      <div className="grid items-start gap-5 lg:grid-cols-[1.1fr_1fr]">
        <Card className="min-w-0 space-y-5 rounded-2xl p-4 sm:p-5">
          <div className="space-y-1.5"><Label htmlFor="application-display-name">{t('display_name')}</Label><Input id="application-display-name" value={draft.name} maxLength={255} disabled={pending || application.status_code === 'RETIRED'} onChange={(event) => state.updateName(event.target.value)} /></div>
          {!application.input_schema.length && <p className="text-sm text-muted-foreground">{t('static_template')}</p>}
          <FieldMappingEditor inputs={application.input_schema} fields={state.fields} bindings={draft.bindings} onChange={state.updateBindings}
            issues={state.issues} fieldErrors={fieldErrors} searchable disabled={pending || application.status_code === 'RETIRED'} />
          <Button asChild variant="outline" className="w-full"><Link to={`/flashcards/note-types/${encodeURIComponent(noteTypeId)}/fields`}><Database className="size-4" />{t('manage_fields')}</Link></Button>
        </Card>
        <div className="min-w-0 space-y-3 lg:sticky lg:top-5">
          <div className="flex justify-end"><Button variant="outline" size="sm" onClick={() => setSamplesOpen(true)}><Settings2 className="size-4" />{t('samples')}</Button></div>
          <NoteTypeLivePreview cardId={`mapping-preview:${applicationId}`} title={t('preview_title')} subtitle={t('preview_description')} side={side} onSideChange={setSide}
            frontPayload={state.preview?.front_renderer_payload} backPayload={state.preview?.back_renderer_payload}
            frontHtml={state.preview?.front_html ?? ''} backHtml={state.preview?.back_html ?? ''} isLoading={state.isPreviewLoading} error={state.previewError}
            fieldDefs={previewFields}
            scope="template_mapping_preview" scopeId={applicationId} className="min-h-[420px]" />
        </div>
      </div>
    </div>
    <Dialog open={samplesOpen} onOpenChange={setSamplesOpen}><DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-xl">
      <DialogHeader><DialogTitle>{t('samples')}</DialogTitle><DialogDescription>{t('samples_description')}</DialogDescription></DialogHeader>
      {state.fields.filter((field) => usedFieldIds.has(field.id)).map((field) => <div key={field.id} className="space-y-1.5"><Label htmlFor={`mapping-sample-${field.id}`}>{field.name}</Label>
        {field.field_type === 'audio' || field.field_type === 'image' ? <p className="text-xs text-muted-foreground">{t('media_sample')}</p>
          : <Textarea id={`mapping-sample-${field.id}`} value={state.samples[field.id] ?? field.name} onChange={(event) => state.setSample(field.id, event.target.value)} />}
      </div>)}
      <Button variant="outline" onClick={state.resetSamples}>{t('reset_samples')}</Button>
    </DialogContent></Dialog>
    {confirmDialog}
  </NoteTypeSetupShell>
}
