import React from 'react'
import type { DeckWorksheetMeta, WorksheetLayoutOptions, WorksheetPreviewResponse } from '../../types'
import { StudioLayoutPresets } from './StudioLayoutPresets'
import { StudioPageSettings } from './StudioPageSettings'
import { KanjiTemplateConfig } from './templates/KanjiTemplateConfig'
import { VocabTemplateConfig } from './templates/VocabTemplateConfig'
import { DeckTableConfig } from './templates/DeckTableConfig'
import { EssayWritingConfig } from './templates/EssayWritingConfig'

export interface StudioLayoutTabProps {
  currentTemplate: DeckWorksheetMeta['templates'][0] | null
  layoutOptions: WorksheetLayoutOptions
  setLayoutOptions: React.Dispatch<React.SetStateAction<WorksheetLayoutOptions>>
  activePresetId: string | null
  setActivePresetId: (id: string | null) => void
  handleResetCurrentTemplateDefaults: () => void
  meta?: DeckWorksheetMeta | null
  previewData?: WorksheetPreviewResponse | null
  setZoomLevel?: React.Dispatch<React.SetStateAction<number>>
}

export function StudioLayoutTab(props: StudioLayoutTabProps) {
  const { currentTemplate } = props
  if (!currentTemplate) return null

  return (
    <div className="space-y-4">
      {/* 1. QUICK PRESETS & RESET BUTTON */}
      <StudioLayoutPresets {...props} />

      {/* 2. PAGE SETTINGS (PAPER SIZE, ORIENTATION, MARGINS, DENSITY) */}
      <StudioPageSettings {...props} />

      {/* 3. TEMPLATE-SPECIFIC CONFIGURATIONS */}
      <KanjiTemplateConfig {...props} />
      <VocabTemplateConfig {...props} />
      <DeckTableConfig {...props} />
      <EssayWritingConfig {...props} />
    </div>
  )
}
