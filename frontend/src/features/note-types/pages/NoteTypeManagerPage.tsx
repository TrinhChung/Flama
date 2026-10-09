import { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowUpRightFromSquare,
  faRobot,
  faRoute,
} from '@fortawesome/free-solid-svg-icons'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'
import { SpotlightTour } from '../components/SpotlightTour'
import { useNoteTypeManager, type NoteTypeItem } from '../hooks/useNoteTypeManager'
import { CreateNoteTypeBar } from '../components/manager/CreateNoteTypeBar'
import { NoteTypeCard } from '../components/manager/NoteTypeCard'
import { DeleteNoteTypeDialog } from '../components/manager/DeleteNoteTypeDialog'
import { getNoteTypeManagerTourSteps } from '../components/manager/noteTypeManagerTourSteps'

const TOUR_STORAGE_KEY = 'flama_notetype_spotlight_tour_v1'

export function NoteTypeManagerPage() {
  const { t } = useTranslation('note_types')
  const {
    query,
    noteTypes,
    isAdmin,
    name,
    setName,
    noteTypeToDelete,
    setNoteTypeToDelete,
    purgeNoteType,
    setPurgeNoteType,
    tourOpen,
    setTourOpen,
    createMutation,
    deleteMutation,
    handleCreate,
  } = useNoteTypeManager()

  const tourSteps = useMemo(() => {
    return getNoteTypeManagerTourSteps(noteTypes.length > 0, t)
  }, [noteTypes.length, t])

  // Auto-launch spotlight tour for first-time visitors with no note types
  useEffect(() => {
    if (query.isSuccess) {
      const completed = localStorage.getItem(TOUR_STORAGE_KEY)
      if (!completed && noteTypes.length === 0) {
        const timer = setTimeout(() => {
          setTourOpen(true)
        }, 500)
        return () => clearTimeout(timer)
      }
    }
  }, [query.isSuccess, noteTypes.length, setTourOpen])

  if (query.isPending) return <PageLoading label={t('manager.loading')} />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />

      <PageHeader
        title={t('manager.header.title')}
        description={t('manager.header.description')}
        actions={
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-start sm:justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setTourOpen(true)}
              className="h-8 sm:h-9 px-2.5 sm:px-3 text-xs font-semibold rounded-xl shrink-0 gap-1.5"
            >
              <FontAwesomeIcon icon={faRoute} className="text-primary text-xs shrink-0" />
              <span className="hidden xs:inline">Tour </span>{t('manager.header.tour_btn')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              asChild
              data-tour="ai-prompt-btn"
              className="h-8 sm:h-9 px-2.5 sm:px-3 text-xs font-semibold rounded-xl border-primary/30 text-primary hover:bg-primary/10 shrink-0 gap-1.5"
            >
              <Link to="/flashcards/note-types/guide" target="_blank" rel="noopener noreferrer">
                <FontAwesomeIcon icon={faRobot} className="text-primary text-xs shrink-0" />
                {t('manager.header.ai_prompt_btn')}
                <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="opacity-70 text-[10px] shrink-0" />
              </Link>
            </Button>
            <ContextHelpButton
              guidePath="/guide/note-types/concept"
              guideTitle={t('manager.header.guide_concept')}
              troubleshootPath="/guide/troubleshooting/import-csv"
              troubleshootTitle={t('manager.header.troubleshoot_import')}
              label={t('manager.header.docs_btn')}
            />
          </div>
        }
      />

      {/* Compact Create NoteType Bar */}
      <CreateNoteTypeBar
        name={name}
        onNameChange={setName}
        onSubmit={handleCreate}
        isPending={createMutation.isPending}
      />

      {/* NoteTypes Card Grid */}
      {!noteTypes.length ? (
        <div data-tour="notetype-grid-area">
          <EmptyState
            title={t('manager.empty.title')}
            description={t('manager.empty.description')}
          />
        </div>
      ) : (
        <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {noteTypes.map((item, index) => (
            <NoteTypeCard
              key={item.id}
              item={item}
              index={index}
              onDelete={(nt: NoteTypeItem) => {
                setPurgeNoteType(false)
                setNoteTypeToDelete(nt)
              }}
            />
          ))}
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <DeleteNoteTypeDialog
        noteType={noteTypeToDelete}
        isOpen={Boolean(noteTypeToDelete)}
        onClose={() => setNoteTypeToDelete(null)}
        isAdmin={isAdmin}
        purgeNoteType={purgeNoteType}
        onPurgeChange={setPurgeNoteType}
        onConfirmDelete={() => {
          if (noteTypeToDelete) {
            deleteMutation.mutate({ id: noteTypeToDelete.id, purge: purgeNoteType })
          }
        }}
        isDeleting={deleteMutation.isPending}
      />

      {/* Interactive Spotlight Onboarding Tour */}
      <SpotlightTour
        steps={tourSteps}
        isOpen={tourOpen}
        onClose={() => {
          localStorage.setItem(TOUR_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
        onComplete={() => {
          localStorage.setItem(TOUR_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
      />
    </Page>
  )
}
