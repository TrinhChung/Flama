import { memo } from 'react'
import type {
  WorksheetLayoutOptions,
  WorksheetPageData,
  WorksheetTemplate,
} from '../types'
import { DeckTableBody } from './renderer/DeckTableBody'
import { EssayGridBody } from './renderer/EssayGridBody'
import { KanjiTemplateBody } from './renderer/kanji/KanjiTemplateBody'
import { getPageBranding } from './renderer/pageBranding'
import { getPageMetrics } from './renderer/pageMetrics'
import { WORKSHEET_PAGE_CSS } from './renderer/pageStyles'
import { VocabRecallTable, VocabWritingTable } from './renderer/VocabTables'
import { EssayPageFooter, StandardPageFooter } from './renderer/WorksheetPageFooter'
import { EssayPageHeader, StandardPageHeader } from './renderer/WorksheetPageHeader'
import { WorksheetPageWatermark } from './renderer/WorksheetPageWatermark'
import { ExercisePromptBanner, WritingPromptList } from './renderer/WritingPromptList'

export interface WorksheetPageRendererProps {
  page: WorksheetPageData
  template: WorksheetTemplate
  options: WorksheetLayoutOptions
  fieldMapping?: Record<string, string | string[]>
  zoom?: number
  isPrintMode?: boolean
}

/** One printable A4 page: page frame, watermark, header, template body and footer. */
export const WorksheetPageRenderer = memo(function WorksheetPageRenderer({
  page,
  template,
  options,
  fieldMapping = {},
  zoom = 1,
  isPrintMode = false,
}: WorksheetPageRendererProps) {
  const { header, items, page_number, total_pages } = page
  const metrics = getPageMetrics(template, options)
  const branding = getPageBranding(options)
  const isEssay = template.id === 'genkouyoushi'

  return (
    <div
      style={{
        transform: isPrintMode || zoom === 1 ? undefined : `scale(${zoom})`,
        transformOrigin: 'top left',
      }}
      className={`bg-white text-slate-900 mx-auto shadow-2xl border border-slate-300/80 flex flex-col justify-between select-none box-border shrink-0 print:shadow-none print:border-none print:m-0 font-['Segoe_UI',-apple-system,BlinkMacSystemFont,Roboto,'Noto_Sans','Noto_Sans_JP','Hiragino_Kaku_Gothic_ProN','Yu_Gothic','Meiryo',sans-serif] relative overflow-hidden ${
        metrics.isLandscape
          ? 'w-[297mm] min-h-[210mm] max-h-[210mm]'
          : 'w-[210mm] min-h-[297mm] max-h-[297mm]'
      } ${metrics.paddingClass}`}
    >
      {/* Global CSS overrides for stroke diagram color modes */}
      <style>{WORKSHEET_PAGE_CSS}</style>

      <WorksheetPageWatermark
        watermarkText={branding.watermarkText}
        watermarkOpacity={branding.watermarkOpacity}
        watermarkLayout={branding.watermarkLayout}
      />

      {isEssay ? (
        <EssayPageHeader header={header} options={options} />
      ) : (
        <StandardPageHeader
          header={header}
          pageNumber={page_number}
          totalPages={total_pages}
          currentUrl={branding.currentUrl}
        />
      )}

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col justify-start relative z-10">
        {options.exercise_prompt &&
          (template.id === 'grammar_practice' || template.id === 'sentence_writing') && (
            <ExercisePromptBanner prompt={options.exercise_prompt} />
          )}

        {template.category === 'kanji' && (
          <KanjiTemplateBody template={template} items={items} options={options} metrics={metrics} />
        )}

        {template.id === 'vocab_writing' && (
          <VocabWritingTable items={items} options={options} isLandscape={metrics.isLandscape} />
        )}

        {template.id === 'vocab_recall' && <VocabRecallTable items={items} options={options} />}

        {template.id === 'deck_table' && (
          <DeckTableBody items={items} options={options} fieldMapping={fieldMapping} gridStyle={metrics.gridStyle} />
        )}

        {template.id === 'sentence_writing' && (
          <WritingPromptList variant="sentence" items={items} options={options} isLandscape={metrics.isLandscape} />
        )}

        {template.id === 'grammar_practice' && (
          <WritingPromptList variant="grammar" items={items} options={options} isLandscape={metrics.isLandscape} />
        )}

        {(template.category === 'essay' || isEssay) && <EssayGridBody items={items} options={options} />}
      </main>

      {isEssay ? (
        <EssayPageFooter options={options} pageNumber={page_number} totalPages={total_pages} />
      ) : (
        <StandardPageFooter
          currentUrl={branding.currentUrl}
          currentDomain={branding.currentDomain}
          pageNumber={page_number}
          totalPages={total_pages}
        />
      )}
    </div>
  )
})
