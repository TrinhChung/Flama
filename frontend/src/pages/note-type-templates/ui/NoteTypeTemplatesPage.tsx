import '@/shared/config/i18n'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { AttachTemplateDialog, TemplateApplicationsPanel } from '@/features/template-library'
import { NoteTypeSetupShell } from '@/features/note-types'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useNoteTypeTemplatesPage } from '../hooks/useNoteTypeTemplatesPage'

export function NoteTypeTemplatesPage() {
  const { id = '' } = useParams<{ id: string }>()
  return <TemplatesEditor key={id} noteTypeId={id} />
}
function TemplatesEditor({ noteTypeId }: { noteTypeId: string }) {
  const { t } = useTranslation('template_mapping')
  const navigate = useNavigate()
  const { detail, applications, attachOpen, setAttachOpen } = useNoteTypeTemplatesPage(noteTypeId)
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
      <TemplateApplicationsPanel noteTypeId={noteTypeId} fields={detail.data!.field_defs} />
    </div>
    <AttachTemplateDialog open={attachOpen} onOpenChange={setAttachOpen} noteTypeId={noteTypeId}
      onApplied={(application) => { setAttachOpen(false); navigate(`/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(application.id)}`) }} />
  </NoteTypeSetupShell>
}
