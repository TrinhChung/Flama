import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowLeft,
  faArrowUpRightFromSquare,
  faCheck,
  faCircleCheck,
  faPlus,
  faRobot,
  faRotateLeft,
  faShareNodes,
  faSliders,
} from '@fortawesome/free-solid-svg-icons'
import { Button } from '@/components/ui/button'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { AmbientBackground } from '@/components/ambient-background'
import { TemplateCodeEditor } from '@/entities/card-template'
import { NoteTypeLivePreview } from '../components/NoteTypeLivePreview'
import { TemplateManagementBar } from '../components/TemplateManagementBar'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useNoteTypeDetail } from '../hooks/useNoteTypeDetail'

export function NoteTypeDetailPage() {
  const { t } = useTranslation('note_types')
  const {
    noteTypeId,
    detailQuery,
    noteType,
    templates,
    fields,
    selectedTemplate,
    selectedNoteCount,
    setSelectedTemplateId,
    activeTab,
    setActiveTab,
    frontHtml,
    setFrontHtml,
    backHtml,
    setBackHtml,
    sharedCss,
    setSharedCss,
    previewResult,
    previewError,
    isPreviewLoading,
    saveMutation,
    createTemplateMutation,
    resetTemplateMutation,
    invalidateTemplates,
  } = useNoteTypeDetail()

  if (detailQuery.isPending) return <PageLoading label={t('detail.loading')} />
  if (detailQuery.error) return <Page><PageError error={detailQuery.error} /></Page>

  return (
    <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />

      {/* Standardized Flama PageHeader */}
      <PageHeader
        title={noteType?.name || t('detail.header.fallback_title')}
        description={t('detail.header.description')}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl gap-1.5">
              <Link to="/flashcards/note-types">
                <FontAwesomeIcon icon={faArrowLeft} className="text-xs" /> {t('detail.header.back_btn')}
              </Link>
            </Button>

            {noteType?.publish_status === 'published' || noteType?.publish_status === 'unlisted' ? (
              <Button
                variant="outline"
                size="sm"
                asChild
                className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10 gap-1.5"
              >
                <Link to={`/marketplace/note-types/${noteTypeId}`}>
                  <FontAwesomeIcon icon={faCircleCheck} className="text-xs text-emerald-500" />
                  {t('detail.header.view_marketplace')}
                </Link>
              </Button>
            ) : (
              <Button
                variant="outline"
                size="sm"
                asChild
                className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl text-primary border-primary/30 hover:bg-primary/10 gap-1.5"
              >
                <Link to={`/marketplace/note-types/publish?id=${noteTypeId}`}>
                  <FontAwesomeIcon icon={faShareNodes} className="text-xs text-primary" />
                  {t('detail.header.share_marketplace')}
                </Link>
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              asChild
              className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-xl border-primary/30 text-primary hover:bg-primary/10 gap-1.5"
            >
              <Link to="/flashcards/note-types/guide" target="_blank" rel="noopener noreferrer">
                <FontAwesomeIcon icon={faRobot} className="text-primary text-xs" />
                {t('detail.header.guide_btn')}
                <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="opacity-70 text-[10px]" />
              </Link>
            </Button>

            <Button size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-bold rounded-xl shadow-xs gap-1.5">
              <Link to={`/flashcards/note-types/${noteTypeId}/fields`}>
                <FontAwesomeIcon icon={faSliders} className="text-xs" /> {t('detail.header.fields_btn')}
              </Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-5 lg:grid-cols-12 items-stretch">
        {/* Left Column: Code Editor & Template Selector */}
        <div className="lg:col-span-6 flex flex-col gap-4">
          <TemplateManagementBar
            noteTypeId={noteTypeId ?? ''}
            template={selectedTemplate}
            noteCount={selectedNoteCount}
            templateCount={templates.length}
            onRenamed={invalidateTemplates}
            onDeleted={(deletedId) => {
              invalidateTemplates()
              const remaining = templates.filter((t) => t.id !== deletedId)
              if (remaining.length > 0) {
                setSelectedTemplateId(remaining[0].id)
              }
            }}
          />

          <TemplateCodeEditor
            headerActions={
              <>
                <NativeSelect
                  value={selectedTemplate?.id}
                  onChange={(e) => setSelectedTemplateId(e.target.value)}
                  className="h-8 sm:h-9 text-xs font-medium flex-1 sm:w-40 min-w-[120px] rounded-xl bg-background"
                >
                  {templates.map((tmpl) => (
                    <NativeSelectOption key={tmpl.id} value={tmpl.id}>
                      {tmpl.name}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>

                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 sm:h-9 px-2.5 text-xs font-semibold rounded-xl shrink-0 gap-1.5"
                  onClick={() => createTemplateMutation.mutate()}
                >
                  <FontAwesomeIcon icon={faPlus} className="text-xs" /> {t('detail.editor_actions.new')}
                </Button>

                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 sm:h-9 px-2.5 text-xs font-semibold text-destructive hover:bg-destructive/10 rounded-xl shrink-0 gap-1.5"
                  onClick={() => {
                    if (window.confirm(t('detail.editor_actions.reset_confirm'))) {
                      resetTemplateMutation.mutate()
                    }
                  }}
                  title={t('detail.editor_actions.reset_tooltip')}
                >
                  <FontAwesomeIcon icon={faRotateLeft} className="text-xs" /> {t('detail.editor_actions.reset')}
                </Button>
              </>
            }
            fields={fields}
            activeTab={activeTab}
            onActiveTabChange={setActiveTab}
            frontHtml={frontHtml}
            backHtml={backHtml}
            sharedCss={sharedCss}
            onFrontHtmlChange={setFrontHtml}
            onBackHtmlChange={setBackHtml}
            onSharedCssChange={setSharedCss}
            footer={
              <Button
                size="sm"
                disabled={saveMutation.isPending}
                onClick={() =>
                  saveMutation.mutate({
                    front_html: frontHtml,
                    back_html: backHtml,
                    shared_css: sharedCss,
                  })
                }
                className="w-full sm:w-auto font-bold px-5 h-9 sm:h-10 text-xs sm:text-sm rounded-xl shadow-xs justify-center gap-1.5"
              >
                <FontAwesomeIcon icon={faCheck} className="text-xs" /> {t('detail.editor_actions.save_template')}
              </Button>
            }
          />
        </div>

        {/* Right Column: Live Preview Frame */}
        <div className="lg:col-span-6 flex flex-col">
          <NoteTypeLivePreview
            cardId={selectedTemplate?.id || 'preview'}
            templates={templates}
            selectedTemplateId={selectedTemplate?.id}
            onSelectTemplate={setSelectedTemplateId}
            frontPayload={previewResult?.front_renderer_payload}
            backPayload={previewResult?.back_renderer_payload}
            frontHtml={previewResult?.front_html || frontHtml}
            backHtml={previewResult?.back_html || backHtml}
            isLoading={isPreviewLoading}
            error={previewError}
            fieldDefs={noteType?.field_defs}
            scope="note_type_editor_live_preview"
            scopeId={noteTypeId}
            className="h-full flex-1 min-h-[480px] lg:min-h-[580px]"
            containerHeightClass="h-[clamp(20rem,55vh,42rem)] min-h-[360px]"
          />
        </div>
      </div>
    </Page>
  )
}
