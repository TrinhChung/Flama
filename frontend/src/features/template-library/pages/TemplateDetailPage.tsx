import '@/shared/config/i18n'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Archive, ArrowLeft, History, Info, MoreHorizontal, Save, SlidersHorizontal } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cardTemplateQueryKeys, fetchTemplateVersion, fetchTemplateVersions, restoreTemplateVersion, TemplateCodeEditor, type TemplateEditorTab } from '@/entities/card-template'
import { TemplateVersionHistorySheet } from '@/features/template-versions'
import { NoteTypeLivePreview } from '@/features/note-types/components/NoteTypeLivePreview'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useUnsavedChangesGuard } from '@/shared/hooks/useUnsavedChangesGuard'
import { ConfirmDialog } from '@/shared/ui'
import { TemplateInputsDialog } from '../components/TemplateInputsDialog'
import { TemplateInformationDialog } from '../components/TemplateInformationDialog'
import { TemplateSampleDataPanel } from '../components/TemplateSampleDataPanel'
import { useTemplateLibraryEditor } from '../model/useTemplateLibraryEditor'
import { ApplyTemplateWizard } from '../components/ApplyTemplateWizard'
import { templateInputReferences } from '../lib/templateInputReferences'

export function TemplateDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  return <TemplateDetailEditor key={id} id={id} />
}

function TemplateDetailEditor({ id }: { id: string }) {
  const { t } = useTranslation('card_templates')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const editor = useTemplateLibraryEditor(id)
  const { template, draft } = editor
  const previewFields = useMemo(() => draft?.input_schema.map((input, position) => ({
    id: `f_${position}`, name: input.key, field_type: input.type, position,
  })) ?? [], [draft?.input_schema])
  const [activeTab, setActiveTab] = useState<TemplateEditorTab>('front')
  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')
  const [mobilePanel, setMobilePanel] = useState<'editor' | 'preview'>('editor')
  const [inputsOpen, setInputsOpen] = useState(false)
  const [inputsDirty, setInputsDirty] = useState(false)
  const [samplesOpen, setSamplesOpen] = useState(false)
  const [informationOpen, setInformationOpen] = useState(false)
  const [informationDirty, setInformationDirty] = useState(false)
  const [usageOpen, setUsageOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [reloadOpen, setReloadOpen] = useState(false)
  const [applyOpen, setApplyOpen] = useState(false)
  const guard = useUnsavedChangesGuard(editor.dirty || inputsDirty || informationDirty, t('setup.unsaved_description'), { onSave: inputsDirty || informationDirty ? undefined : editor.saveAsync })
  const historySource = useMemo(() => ({
    listKey: cardTemplateQueryKeys.templateVersions(id), detailKey: (versionId: string) => cardTemplateQueryKeys.templateVersion(id, versionId),
    list: (signal?: AbortSignal) => fetchTemplateVersions(id, signal), get: (versionId: string, signal?: AbortSignal) => fetchTemplateVersion(id, versionId, signal),
    restore: (versionId: string) => restoreTemplateVersion(id, versionId),
  }), [id])
  const references = useMemo(() => draft ? templateInputReferences(draft.front_html, draft.back_html, draft.input_schema) : null, [draft])
  if (editor.detailQuery.isPending) return <PageLoading label={t('detail.loading')} />
  if (editor.detailQuery.error && !template) return <Page><PageError error={editor.detailQuery.error} /></Page>
  if (!template || !draft) return <PageLoading label={t('detail.loading')} />
  const locked = restoring || editor.isReplacingDraft || editor.saveMutation.isPending
  const reload = async () => { try { await editor.refreshAndReplaceDraft(); setReloadOpen(false) } catch { /* The hook preserves the error and draft. */ } }
  const returnTo = searchParams.get('returnTo')
  const backPath = returnTo && /^\/flashcards\/note-types\/[^/?#]+(?:\/templates(?:\/[^/?#]+)?)?$/.test(returnTo) ? returnTo : '/card-templates'
  const go = (path: string) => guard.requestNavigation(() => navigate(path))
  return <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4">
    <div className="flex items-center justify-between gap-3"><Button variant="ghost" size="sm" onClick={() => go(backPath)}><ArrowLeft className="size-4" />{backPath === '/card-templates' ? t('detail.back') : t('setup.back_to_mapping')}</Button><span role="status" className={`text-xs ${editor.dirty ? 'text-amber-600 dark:text-amber-400' : 'text-muted-foreground'}`}>{t(editor.dirty ? 'setup.unsaved' : 'setup.saved')}</span></div>
    <PageHeader title={draft.name} description={t('setup.workspace_description')} actions={<div className="flex items-center gap-2">
      {template.archived_at && <Badge variant="secondary">{t('library.badge_archived')}</Badge>}
      <Button disabled={locked || !editor.canSave || !editor.dirty} onClick={editor.save}><Save className="size-4" />{t('detail.save_changes')}</Button>
      <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" size="icon" disabled={locked} aria-label={t('setup.more_actions')}><MoreHorizontal className="size-4" /></Button></DropdownMenuTrigger><DropdownMenuContent align="end" className="w-64">
        <DropdownMenuItem onSelect={() => setInformationOpen(true)}><Info />{t('setup.information')}</DropdownMenuItem>
        <DropdownMenuItem disabled={Boolean(template.archived_at)} onSelect={() => setApplyOpen(true)}>{t('detail.apply_to_note_type')}</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setHistoryOpen(true)}><History />{t('detail.history')}</DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setUsageOpen(true)}>{t('detail.used_in_title')}</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled={editor.archiveMutation.isPending} onSelect={() => { if (template.archived_at) editor.setArchived(false); else setArchiveOpen(true) }}><Archive />{template.archived_at ? t('detail.unarchive') : t('detail.archive')}</DropdownMenuItem>
      </DropdownMenuContent></DropdownMenu>
    </div>} />
    <div className="flex flex-wrap items-center gap-2"><Button variant="outline" size="sm" disabled={locked} onClick={() => { setSamplesOpen(false); setInputsOpen(true) }}><SlidersHorizontal className="size-4" />{t('setup.inputs_count', { count: draft.input_schema.length })}</Button><Button variant="ghost" size="sm" onClick={() => setUsageOpen(true)}>{t('setup.usage_count', { count: template.note_type_count })}</Button><Button variant="outline" size="sm" disabled={locked} onClick={() => { setInputsOpen(false); setSamplesOpen(true) }}>{t('setup.sample_data')}</Button></div>
    {editor.dirty && template.application_count > 0 && <p className="text-xs text-muted-foreground">{t('setup.save_impact', { applications: template.application_count, noteTypes: template.note_type_count })}</p>}
    {(editor.saveError || editor.refreshError) && <div role="alert" className="rounded-xl border border-destructive/30 p-4 space-y-2"><p className="text-sm text-destructive">{editor.saveError || editor.refreshError}</p><Button variant="outline" disabled={locked} onClick={() => { if (editor.dirty) setReloadOpen(true); else void reload() }}>{t('detail.reload')}</Button></div>}
    <div className="flex lg:hidden rounded-xl border bg-muted/30 p-1" role="tablist" aria-label={t('setup.workspace_tabs')}><Button role="tab" aria-selected={mobilePanel === 'editor'} variant={mobilePanel === 'editor' ? 'default' : 'ghost'} className="flex-1" onClick={() => setMobilePanel('editor')}>{t('setup.editor')}</Button><Button role="tab" aria-selected={mobilePanel === 'preview'} variant={mobilePanel === 'preview' ? 'default' : 'ghost'} className="flex-1" onClick={() => setMobilePanel('preview')}>{t('setup.preview')}</Button></div>
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] items-stretch">
      <div className={`min-w-0 ${mobilePanel === 'editor' ? 'block' : 'hidden'} lg:flex`}><TemplateCodeEditor fields={draft.input_schema.map((input) => ({ id: input.key, name: input.key, label: input.label }))} activeTab={activeTab} onActiveTabChange={(tab) => { setActiveTab(tab); if (tab !== 'css') setPreviewSide(tab) }} frontHtml={draft.front_html} backHtml={draft.back_html} sharedCss={draft.shared_css} onFrontHtmlChange={(front_html) => editor.updateDraft({ front_html })} onBackHtmlChange={(back_html) => editor.updateDraft({ back_html })} onSharedCssChange={(shared_css) => editor.updateDraft({ shared_css })} readOnly={locked} /></div>
      <div className={`min-w-0 ${mobilePanel === 'preview' ? 'flex' : 'hidden'} lg:flex`}><NoteTypeLivePreview cardId={`library-preview:${id}`} side={previewSide} onSideChange={setPreviewSide} frontPayload={editor.previewResult?.front_renderer_payload} backPayload={editor.previewResult?.back_renderer_payload} frontHtml={editor.previewResult?.front_html ?? ''} backHtml={editor.previewResult?.back_html ?? ''} isLoading={editor.isPreviewLoading} error={editor.previewError} title={t('setup.preview')} subtitle="" fieldDefs={previewFields} className="min-h-[400px] [&_.study-card-shell]:bg-white" containerHeightClass="h-[clamp(20rem,50vh,36rem)] min-h-[320px]" /></div>
    </div>
    {references && references.unknown.length > 0 && <div className="rounded-xl border border-amber-500/30 p-3 text-sm"><p>{t('setup.unknown_inputs', { keys: references.unknown.join(', ') })}</p><Button variant="link" size="sm" disabled={locked} onClick={() => setInputsOpen(true)}>{t('setup.declare_inputs')}</Button></div>}
    {inputsOpen && <TemplateInputsDialog open onOpenChange={setInputsOpen} value={draft.input_schema} persistedKeys={editor.persistedInputKeys} onApply={(input_schema) => editor.updateDraft({ input_schema })} frontHtml={draft.front_html} backHtml={draft.back_html} applicationCount={template.application_count} onDirtyChange={setInputsDirty} />}
    <TemplateSampleDataPanel open={samplesOpen} onOpenChange={setSamplesOpen} inputs={draft.input_schema} values={editor.sampleValues} onChange={editor.setSampleValue} onReset={editor.resetSampleValues} />
    {informationOpen && <TemplateInformationDialog draft={draft} onApply={editor.updateDraft} onClose={() => setInformationOpen(false)} onDirtyChange={setInformationDirty} />}
    <Sheet open={usageOpen} onOpenChange={setUsageOpen}><SheetContent className="w-full sm:max-w-lg"><SheetHeader><SheetTitle>{t('detail.used_in_title')}</SheetTitle><SheetDescription>{t('detail.used_in_stats', { noteTypeCount: template.note_type_count, applicationCount: template.application_count })}</SheetDescription></SheetHeader><div className="p-4 pt-0 overflow-y-auto space-y-3">{template.applications.map((application) => <div key={application.id} className="rounded-xl border p-3 text-sm"><Link className="font-semibold text-primary hover:underline" to={`/flashcards/note-types/${encodeURIComponent(application.note_type_id)}/templates/${encodeURIComponent(application.application_id || application.id)}`} onClick={(event) => { event.preventDefault(); go(event.currentTarget.getAttribute('href')!) }}>{application.display_name || template.name}</Link><p className="text-xs text-muted-foreground mt-1">{application.note_type_name}</p></div>)}{!template.applications.length && <p className="text-sm text-muted-foreground">{t('detail.used_in_empty')}</p>}</div></SheetContent></Sheet>
    <ApplyTemplateWizard open={applyOpen} onOpenChange={setApplyOpen} template={template} />
    {historyOpen && <TemplateVersionHistorySheet open onOpenChange={setHistoryOpen} source={historySource} current={draft} onRestored={editor.refreshAndReplaceDraft} onRestorePendingChange={setRestoring} />}
    <ConfirmDialog open={archiveOpen} onOpenChange={setArchiveOpen} title={t('detail.archive_confirm_title')} description={t('detail.archive_confirm_desc')} confirmText={t('detail.archive_confirm_btn')} cancelText={t('setup.cancel')} isLoading={editor.archiveMutation.isPending} onConfirm={async () => { try { await editor.archive(true); setArchiveOpen(false) } catch { /* Mutation displays the error. */ } }} />
    <ConfirmDialog open={reloadOpen} onOpenChange={setReloadOpen} title={t('detail.reload_confirm_title')} description={t('detail.reload_confirm_desc')} confirmText={t('detail.reload_confirm_btn')} cancelText={t('setup.cancel')} isLoading={editor.isReplacingDraft} onConfirm={reload} />
    {guard.confirmDialog}
  </Page>
}
