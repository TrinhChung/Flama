import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { StudioTab } from '../config/studioTabs'
import { useWorksheetWizard } from '../hooks/useWorksheetWizard'
import type { DeckWorksheetModalProps } from './DeckWorksheetModal'
import { WorksheetDeckSelectStep } from './WorksheetDeckSelectStep'
import { WorksheetFieldMappingStep } from './WorksheetFieldMappingStep'
import { WorksheetTemplateSelectStep } from './WorksheetTemplateSelectStep'
import { WorksheetWizardStepper } from './WorksheetWizardStepper'
import {
  WorksheetDesktopHeader,
  WorksheetMobileHeader,
  type StudioMobileView,
} from './modal/WorksheetModalHeader'
import { WorksheetMixedNoteTypesNotice } from './modal/WorksheetMixedNoteTypesNotice'
import { StudioPreviewCanvas } from './studio/StudioPreviewCanvas'
import { StudioSidebar } from './studio/StudioSidebar'

/**
 * Contents of the worksheet studio dialog. Rendered inside `WorksheetStudioDialog`,
 * so it only mounts while the dialog is open.
 */
export function WorksheetStudio({ onOpenChange, deckId, deckName, initialCardIds, initialStep }: DeckWorksheetModalProps) {
  // Suspends once, before the first paint, until the namespace is ready.
  useTranslation('worksheets')
  const session = useWorksheetWizard({ deckId, deckName, initialCardIds, initialStep })
  const { studio, wizardStep, meta, deckLabel, activeNoteType } = session
  const [activeTab, setActiveTab] = useState<StudioTab>('template')
  const [mobileView, setMobileView] = useState<StudioMobileView>('preview')

  const close = () => onOpenChange(false)
  const hasDeck = Boolean(session.currentDeckId)
  const totalPages = studio.previewData?.total_pages || 1

  return (
    <>
      <WorksheetDesktopHeader
        wizardStep={wizardStep}
        hasDeck={hasDeck}
        deckLabel={deckLabel}
        isGenerating={studio.isGenerating}
        onClose={close}
        totalNotes={meta?.total_notes || 0}
        zoomLevel={studio.zoomLevel}
        setZoomLevel={studio.setZoomLevel}
        orientation={studio.layoutOptions.orientation}
        onPrint={studio.handlePrint}
        isPrinting={studio.isPrinting}
        canPrint={Boolean(studio.previewData)}
      />

      <WorksheetMobileHeader
        wizardStep={wizardStep}
        hasDeck={hasDeck}
        deckLabel={deckLabel}
        isGenerating={studio.isGenerating}
        onClose={close}
        totalPages={totalPages}
        mobileView={mobileView}
        setMobileView={setMobileView}
      />

      <WorksheetWizardStepper
        currentStep={wizardStep}
        onSelectStep={session.goToStep}
        isStandalone={session.isStandalone}
      />

      {/* STEP 1: DECK SELECTION */}
      {wizardStep === 'deck' && (
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
          <WorksheetDeckSelectStep
            selectedDeckId={session.currentDeckId}
            onSelectDeck={session.selectDeck}
            onSelectStandalone={session.selectStandalone}
            onCancel={close}
          />
        </div>
      )}

      {/* STEP 2: FIELD MAPPING */}
      {wizardStep === 'mapping' && (
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
          {meta && session.isMixedDeck ? (
            <WorksheetMixedNoteTypesNotice
              noteTypeCount={meta.note_types?.length || 2}
              onChooseAnotherDeck={() => session.setWizardStep('deck')}
            />
          ) : activeNoteType ? (
            <WorksheetFieldMappingStep
              noteType={activeNoteType}
              deckName={deckLabel}
              totalNotes={meta?.total_notes || 0}
              suggestedMappings={meta?.suggested_mappings || {}}
              initialMapping={studio.fieldMapping}
              onConfirmMapping={session.confirmMapping}
              onBack={() => session.setWizardStep('deck')}
            />
          ) : (
            <div className="h-64 flex flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="size-6 animate-spin text-primary" />
              <span className="text-xs font-medium">Đang tải cấu hình trường bộ thẻ...</span>
            </div>
          )}
        </div>
      )}

      {/* STEP 3: TEMPLATE SELECTION */}
      {wizardStep === 'template' && (
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
          <WorksheetTemplateSelectStep
            templates={meta?.templates || []}
            selectedTemplateId={studio.selectedTemplateId}
            onSelectTemplate={studio.handleSelectTemplate}
            onConfirm={session.confirmTemplate}
            onBack={session.backFromTemplate}
            isStandalone={session.isStandalone}
          />
        </div>
      )}

      {/* STEP 4: LIVE STUDIO WORKSPACE */}
      {wizardStep === 'studio' && (
        <div className="flex-1 flex overflow-hidden min-h-0">
          <StudioSidebar
            session={session}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            mobileView={mobileView}
            setMobileView={setMobileView}
          />

          {/* Right Area: Live Workbench Preview Canvas (flex-1) */}
          <StudioPreviewCanvas
            mobileView={mobileView}
            currentPageIdx={studio.currentPageIdx}
            setCurrentPageIdx={studio.setCurrentPageIdx}
            previewData={studio.previewData}
            zoomLevel={studio.zoomLevel}
            setZoomLevel={studio.setZoomLevel}
            layoutOptions={studio.layoutOptions}
            isGenerating={studio.isGenerating}
            isLoadingMeta={session.isLoadingMeta}
            currentTemplate={studio.currentTemplate}
            fieldMapping={studio.fieldMapping}
            containerWidthPx={studio.containerWidthPx}
            containerHeightPx={studio.containerHeightPx}
            a4WidthMm={studio.a4WidthMm}
            a4HeightMm={studio.a4HeightMm}
            handleCanvasTouchEnd={studio.handleCanvasTouchEnd}
            handlePrint={studio.handlePrint}
            isPrinting={studio.isPrinting}
          />
        </div>
      )}
    </>
  )
}
