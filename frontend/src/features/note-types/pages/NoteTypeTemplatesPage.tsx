import '@/shared/config/i18n'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { cardTemplateQueryKeys, fetchTemplateApplications } from '@/entities/card-template'
import { AttachTemplateDialog, TemplateApplicationsPanel } from '@/features/template-library'
import { apiRequest } from '@/shared/api/client'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { NoteTypeSetupShell } from '../components/NoteTypeSetupShell'
import { TemplateCoherenceBanner } from '../components/TemplateCoherenceBanner'
import type { TemplateCoherenceWarning } from '@/entities/deck-version'
import type { MappingNoteType } from '../hooks/useTemplateMappingDraft'

export function NoteTypeTemplatesPage() {
  const { id = '' } = useParams<{ id: string }>()
  return <TemplatesEditor key={id} noteTypeId={id} />
}
function TemplatesEditor({ noteTypeId }: { noteTypeId: string }) {
  const { t } = useTranslation('template_mapping')
  const navigate = useNavigate()
  const [attachOpen, setAttachOpen] = useState(false)
  const [warnings, setWarnings] = useState<TemplateCoherenceWarning[]>([
    {
      template_id: 'sample-template-coherence',
      template_name: 'Mẫu thẻ Tiêu chuẩn',
      warning_type: 'OUTDATED_PIN',
      pinned_release: 'v1.0.0',
      latest_release: 'v1.1.0',
      message: 'Mẫu thẻ đã có bản phát hành v1.1.0 với các cải tiến về hiển thị và phong cách mới.',
      action_recommendation: 'Cập nhật ghim phiên bản lên v1.1.0 để đồng bộ giao diện hiển thị tối ưu nhất.',
    },
  ])
  const detail = useQuery({ queryKey: ['note-type-detail', noteTypeId], enabled: Boolean(noteTypeId),
    queryFn: ({ signal }) => apiRequest<MappingNoteType>(`/api/note-types/${encodeURIComponent(noteTypeId)}`, { signal }) })
  const applications = useQuery({ queryKey: cardTemplateQueryKeys.applications(noteTypeId, true), enabled: Boolean(noteTypeId),
    queryFn: ({ signal }) => fetchTemplateApplications(noteTypeId, true, signal) })
  if (detail.isPending) return <PageLoading />
  if (detail.error) return <Page><PageError error={detail.error} /><Button variant="outline" onClick={() => { void detail.refetch() }}>{t('retry')}</Button></Page>
  return <NoteTypeSetupShell noteTypeId={noteTypeId} name={detail.data!.name} activeTab="templates"
    fieldCount={detail.data!.field_defs.length} templateCount={applications.data?.items.filter((item) => item.status_code === 'ACTIVE').length}>
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">{t('templates_title')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t('templates_description')}</p>
        </div>
        <Button onClick={() => setAttachOpen(true)}><Plus className="size-4" />{t('attach')}</Button>
      </div>
      {warnings.length > 0 && (
        <TemplateCoherenceBanner
          warnings={warnings}
          onDismiss={() => setWarnings([])}
          onAlignTemplatePin={(templateId) => {
            navigate(`/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(templateId)}`)
          }}
        />
      )}
      <TemplateApplicationsPanel noteTypeId={noteTypeId} fields={detail.data!.field_defs} />
    </div>
    <AttachTemplateDialog open={attachOpen} onOpenChange={setAttachOpen} noteTypeId={noteTypeId}
      onApplied={(application) => { setAttachOpen(false); navigate(`/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(application.id)}`) }} />
  </NoteTypeSetupShell>
}
