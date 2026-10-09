import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Archive, ArrowLeft, History, Save } from 'lucide-react'
import { cardTemplateQueryKeys, fetchTemplateVersion, fetchTemplateVersions, restoreTemplateVersion, TemplateCodeEditor, type TemplateEditorTab } from '@/entities/card-template'
import { TemplateVersionHistorySheet } from '@/features/template-versions'
import { NoteTypeLivePreview } from '@/features/note-types/components/NoteTypeLivePreview'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ConfirmDialog } from '@/shared/ui'
import { TemplateInputSchemaEditor } from '../components/TemplateInputSchemaEditor'
import { useTemplateLibraryEditor } from '../model/useTemplateLibraryEditor'
import { ApplyTemplateWizard } from '../components/ApplyTemplateWizard'
import { TemplateDistributionPanel } from '@/features/template-distribution'

export function TemplateDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  // A keyed editor also resets UI-only selection/dialog state across route changes.
  return <TemplateDetailEditor key={id} id={id} />
}
function TemplateDetailEditor({ id }: { id: string }) {
  const editor = useTemplateLibraryEditor(id)
  const { template, draft } = editor
  const [activeTab, setActiveTab] = useState<TemplateEditorTab>('front')
  const [historyOpen, setHistoryOpen] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [reloadOpen, setReloadOpen] = useState(false)
  const [applyOpen, setApplyOpen] = useState(false)
  const historySource = useMemo(() => ({
    listKey: cardTemplateQueryKeys.templateVersions(id), detailKey: (versionId: string) => cardTemplateQueryKeys.templateVersion(id, versionId),
    list: (signal?: AbortSignal) => fetchTemplateVersions(id, signal), get: (versionId: string, signal?: AbortSignal) => fetchTemplateVersion(id, versionId, signal),
    restore: (versionId: string) => restoreTemplateVersion(id, versionId),
  }), [id])
  if (editor.detailQuery.isPending) return <PageLoading label="Đang tải mẫu thẻ…" />
  if (editor.detailQuery.error && !template) return <Page><PageError error={editor.detailQuery.error} /></Page>
  if (!template || !draft) return <PageLoading label="Đang tải mẫu thẻ…" />
  const locked = restoring || editor.isReplacingDraft || editor.saveMutation.isPending
  const reload = async () => { try { await editor.refreshAndReplaceDraft(); setReloadOpen(false) } catch { /* Hook preserves the error and draft. */ } }
  return <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
    <PageHeader title={template.name} description={template.archived_at ? 'Mẫu thẻ đã lưu trữ.' : 'Thay đổi mẫu này áp dụng cho mọi loại thẻ đang gắn.'} actions={<div className="flex flex-wrap gap-2">
      <Button variant="outline" asChild><Link to="/card-templates"><ArrowLeft className="size-4" />Quay lại</Link></Button>
      <Button variant="outline" disabled={locked} onClick={() => setHistoryOpen(true)}><History className="size-4" />Lịch sử</Button>
      <Button variant="outline" disabled={locked || editor.archiveMutation.isPending} onClick={() => { if (template.archived_at) editor.setArchived(false); else setArchiveOpen(true) }}><Archive className="size-4" />{template.archived_at ? 'Bỏ lưu trữ' : 'Lưu trữ'}</Button>
      <Button disabled={locked || Boolean(template.archived_at)} title={template.archived_at ? 'Bỏ lưu trữ để gắn mẫu.' : undefined} onClick={() => setApplyOpen(true)}>Áp dụng vào loại thẻ</Button>
    </div>} />
    <Card className="p-4 sm:p-5 rounded-2xl space-y-4">
      <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><Label htmlFor="library-template-name">Tên mẫu</Label><Input id="library-template-name" value={draft.name} disabled={locked} onChange={(event) => editor.updateDraft({ name: event.target.value })} maxLength={255} /></div><div className="space-y-2"><Label htmlFor="library-template-category">Danh mục</Label><Input id="library-template-category" value={draft.primary_category} disabled={locked} onChange={(event) => editor.updateDraft({ primary_category: event.target.value })} maxLength={120} /></div></div>
      <div className="space-y-2"><Label htmlFor="library-template-description">Mô tả</Label><Input id="library-template-description" value={draft.description} disabled={locked} onChange={(event) => editor.updateDraft({ description: event.target.value })} /></div>
      <TemplateInputSchemaEditor value={draft.input_schema} onChange={(input_schema) => editor.updateDraft({ input_schema })} disabled={locked} />
    </Card>
    <TemplateDistributionPanel templateId={id} origin={template.origin} currentVersionId={template.current_version_id} onSourceChanged={() => editor.refreshAndReplaceDraft()} />
    <ApplyTemplateWizard open={applyOpen} onOpenChange={setApplyOpen} template={template} />
    {(editor.saveError || editor.refreshError) && <div role="alert" className="rounded-xl border border-destructive/30 p-4 space-y-2"><p className="text-sm text-destructive">{editor.saveError || editor.refreshError}</p><Button variant="outline" disabled={locked} onClick={() => { if (editor.dirty) setReloadOpen(true); else void reload() }}>Tải lại</Button></div>}
    <div className="grid gap-5 lg:grid-cols-2 items-stretch">
      <TemplateCodeEditor fields={draft.input_schema.map((input) => ({ id: input.key, name: input.key }))} activeTab={activeTab} onActiveTabChange={setActiveTab} frontHtml={draft.front_html} backHtml={draft.back_html} sharedCss={draft.shared_css}
        onFrontHtmlChange={(front_html) => editor.updateDraft({ front_html })} onBackHtmlChange={(back_html) => editor.updateDraft({ back_html })} onSharedCssChange={(shared_css) => editor.updateDraft({ shared_css })} readOnly={locked}
        footer={<Button disabled={locked || !editor.canSave} onClick={editor.save}><Save className="size-4" />Lưu thay đổi</Button>} />
      <div className="space-y-4"><Card className="p-4 rounded-2xl space-y-3"><h2 className="font-semibold">Dữ liệu xem trước</h2>{draft.input_schema.map((input) => <div key={input.key} className="space-y-1"><Label htmlFor={`sample-${encodeURIComponent(input.key)}`}>{input.label || input.key}</Label><Input id={`sample-${encodeURIComponent(input.key)}`} placeholder={`Dữ liệu mẫu cho ${input.key}`} value={editor.sampleValues[input.key] ?? ''} disabled={locked} onChange={(event) => editor.setSampleValue(input.key, event.target.value)} /></div>)}</Card>
        <NoteTypeLivePreview cardId={`library-preview:${id}`} frontPayload={editor.previewResult?.front_renderer_payload} backPayload={editor.previewResult?.back_renderer_payload} frontHtml={editor.previewResult?.front_html ?? ''} backHtml={editor.previewResult?.back_html ?? ''} isLoading={editor.isPreviewLoading} error={editor.previewError}
          fieldDefs={draft.input_schema.map((input, index) => ({ id: `f_${index}`, name: input.key, field_type: input.type, position: index }))} className="min-h-[400px] [&_.study-card-shell]:bg-white" />
      </div>
    </div>
    <Card className="p-4 sm:p-5 rounded-2xl space-y-3"><h2 className="font-semibold">Đang dùng ở</h2><p className="text-sm text-muted-foreground">Thay đổi mẫu này áp dụng cho mọi loại thẻ đang gắn.</p><p className="text-sm">{template.note_type_count} loại thẻ · {template.application_count} lần gắn</p>
      {template.applications.map((application) => <div key={application.id} className="rounded-lg border p-3 text-sm"><Link className="font-semibold text-primary hover:underline" to={`/flashcards/note-types/${encodeURIComponent(application.note_type_id)}`}>{application.note_type_name}</Link><p>{application.display_name || template.name} · {application.occurrence_key}</p></div>)}
      {!template.applications.length && <p className="text-sm text-muted-foreground">Chưa dùng.</p>}
    </Card>
    {historyOpen && <TemplateVersionHistorySheet open={historyOpen} onOpenChange={setHistoryOpen} source={historySource} current={draft} onRestored={editor.refreshAndReplaceDraft} onRestorePendingChange={setRestoring} />}
    <ConfirmDialog open={archiveOpen} onOpenChange={setArchiveOpen} title="Lưu trữ mẫu thẻ này?" description="Mẫu sẽ ẩn khỏi thư viện. Các loại thẻ đang dùng không bị ảnh hưởng." confirmText="Lưu trữ" isLoading={editor.archiveMutation.isPending} onConfirm={async () => { try { await editor.archive(true); setArchiveOpen(false) } catch { /* Mutation displays the error. */ } }} />
    <ConfirmDialog open={reloadOpen} onOpenChange={setReloadOpen} title="Tải lại mẫu thẻ?" description="Nội dung chưa lưu sẽ được thay bằng bản mới nhất trên máy chủ." confirmText="Tải lại" isLoading={editor.isReplacingDraft} onConfirm={reload} />
  </Page>
}
