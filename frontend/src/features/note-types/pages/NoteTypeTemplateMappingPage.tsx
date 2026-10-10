import '@/shared/config/i18n'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowUpRight, Database, Save, Settings2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FieldMappingEditor, inputSchemaPreviewFields, SampleValuesSheet } from '@/entities/card-template'
import { CardPreviewPanel } from '@/entities/flashcard'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useUnsavedChangesGuard } from '@/shared/hooks/useUnsavedChangesGuard'
import { WorkspaceLayout } from '@/shared/ui'
import { ApiError } from '@/shared/api/client'
import { NoteTypeSetupShell } from '../components/NoteTypeSetupShell'
import { useTemplateMappingDraft } from '../hooks/useTemplateMappingDraft'

export function NoteTypeTemplateMappingPage() {
  const { id = '', applicationId = '' } = useParams<{ id: string; applicationId: string }>()
  return <MappingEditor key={`${id}:${applicationId}`} noteTypeId={id} applicationId={applicationId} />
}

function MappingEditor({ noteTypeId, applicationId }: { noteTypeId: string; applicationId: string }) {
  const { t } = useTranslation('template_mapping')
  const navigate = useNavigate()
  const state = useTemplateMappingDraft(noteTypeId, applicationId)
  const [samplesOpen, setSamplesOpen] = useState(false)
  const [side, setSide] = useState<'front' | 'back'>('front')
  const previewFields = useMemo(() => inputSchemaPreviewFields(state.application?.input_schema ?? []), [state.application?.input_schema])
  const { confirmDialog, requestNavigation } = useUnsavedChangesGuard(state.dirty, t('discard_message'), {
    onSave: async () => {
      if (state.saveMutation.isPending) throw new Error(t('saving'))
      await state.saveMutation.mutateAsync()
    },
  })
  const { application, draft } = state
  const effectiveId = application?.id ?? applicationId

  useEffect(() => {
    if (application?.id && application.id !== applicationId) {
      window.history.replaceState(null, '', `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(application.id)}`)
    }
  }, [application?.id, applicationId, noteTypeId])

  const listPath = `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates`
  const mappingPath = `${listPath}/${encodeURIComponent(effectiveId)}`
  if (state.detail.isPending || state.applications.isPending) return <PageLoading />
  if (state.detail.error || state.applications.error) return <Page><PageError error={state.detail.error ?? state.applications.error} /><Button variant="outline" onClick={() => { void state.detail.refetch(); void state.applications.refetch() }}>{t('retry')}</Button></Page>
  if (!application) return <Page><PageError error={new Error(t('not_found'))} /><Button asChild variant="outline"><Link to={listPath}>{t('back')}</Link></Button></Page>
  if (!draft) return <PageLoading />
  const pending = state.saveMutation.isPending
  const readOnly = pending || application.status_code === 'RETIRED'
  const save = () => { void state.saveMutation.mutateAsync().catch(() => { /* Mutation error is shown with the draft. */ }) }
  const usedFieldIds = new Set(Object.values(draft.bindings))
  const saveError = state.saveMutation.error
  const fieldErrors = saveError instanceof ApiError && saveError.field ? Object.fromEntries([[saveError.field, saveError.message]]) : undefined

  const templateName = application.display_name ?? application.template.name
  const noteTypeName = state.detail.data!.name
  const handleNavigate = (to: string) => {
    if (!pending) requestNavigation(() => navigate(to))
  }

  return <NoteTypeSetupShell noteTypeId={noteTypeId} name={templateName} activeTab="templates" fill
    fieldCount={state.fields.length} templateCount={state.applications.data!.items.filter((item) => item.status_code === 'ACTIVE').length}
    onNavigate={handleNavigate}
    backTo={listPath}
    backLabel={t('back')}
    contextLabel={noteTypeName}
    titleBadge={<Badge variant="outline" className="text-xs font-normal text-muted-foreground shrink-0">{t('mapping_tab')}</Badge>}
    hideDescription
    actions={<div className="flex flex-wrap items-center gap-2">
      {state.dirty && <span role="status" className="text-xs font-medium text-amber-600 dark:text-amber-400">{t('unsaved')}</span>}
      <Button asChild variant="outline" size="sm"><Link to={`/card-templates/${encodeURIComponent(application.template_id)}?${new URLSearchParams({ returnTo: mappingPath })}`}><ArrowUpRight className="size-4" />{t('edit_design')}</Link></Button>
      <Button size="sm" disabled={pending || state.invalid || !state.dirty} onClick={save}><Save className="size-4" />{pending ? t('saving') : t('save')}</Button>
    </div>}>
    <div className="space-y-4 lg:flex lg:min-h-0 lg:flex-1 lg:flex-col">
      {application.status_code === 'RETIRED' && <p role="status" className="rounded-xl border p-4 text-sm text-muted-foreground">{t('retired_notice')}</p>}
      {state.sourceChanged && <p role="status" className="rounded-xl border border-primary/30 bg-primary/5 p-3 text-sm">{t('source_changed')}</p>}
      {state.saveMutation.error && <PageError error={state.saveMutation.error} />}
      <WorkspaceLayout className="lg:flex-1 lg:min-h-0" storageKey="flama:template-mapping:split" defaultRatio={42} minRatio={28} maxRatio={65}
        primaryLabel={t('mapping_tab')} secondaryLabel={t('preview_title')} tabsLabel={t('workspace_tabs')}
        primary={<Card className="h-full min-h-0 gap-4 rounded-2xl p-4 sm:p-5">
          <div className="shrink-0 space-y-1.5"><Label htmlFor="application-display-name">{t('display_name')}</Label><Input id="application-display-name" value={draft.name} maxLength={255} disabled={readOnly} onChange={(event) => state.updateName(event.target.value)} /></div>
          {!application.input_schema.length && <p className="text-sm text-muted-foreground">{t('static_template')}</p>}
          {/* On desktop the input rows scroll inside the pane, below a fixed search box, so the preview stays in view. */}
          <FieldMappingEditor inputs={application.input_schema} fields={state.fields} bindings={draft.bindings} onChange={state.updateBindings}
            issues={state.issues} fieldErrors={fieldErrors} searchable disabled={readOnly}
            className="lg:flex lg:min-h-0 lg:flex-1 lg:flex-col" listClassName="lg:-mx-1 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:px-1" />
          <Button asChild variant="outline" className="w-full shrink-0"><Link to={`/flashcards/note-types/${encodeURIComponent(noteTypeId)}/fields`}><Database className="size-4" />{t('manage_fields')}</Link></Button>
        </Card>}
        secondary={<CardPreviewPanel fill cardId={`mapping-preview:${effectiveId}`} title={t('preview_title')} subtitle={t('preview_description')} side={side} onSideChange={setSide}
          headerActions={<Button variant="outline" size="sm" className="h-8" onClick={() => setSamplesOpen(true)}><Settings2 className="size-4" />{t('samples')}</Button>}
          frontPayload={state.preview?.front_renderer_payload} backPayload={state.preview?.back_renderer_payload}
          frontHtml={state.preview?.front_html ?? ''} backHtml={state.preview?.back_html ?? ''} isLoading={state.isPreviewLoading} error={state.previewError}
          fieldDefs={previewFields} scope="template_mapping_preview" scopeId={effectiveId} />} />
    </div>
    <SampleValuesSheet open={samplesOpen} onOpenChange={setSamplesOpen} title={t('samples')} description={t('samples_description')} idPrefix="mapping-sample"
      items={state.fields.filter((field) => usedFieldIds.has(field.id)).map((field) => ({ key: field.id, label: field.name, type: field.field_type, placeholder: field.name }))}
      values={state.samples} onChange={state.setSample} onReset={state.resetSamples} />
    {confirmDialog}
  </NoteTypeSetupShell>
}
