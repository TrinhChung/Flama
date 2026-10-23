import { ChevronLeft, Database, Eye, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { STUDIO_TABS, nextStudioTab, type StudioTab } from '../../config/studioTabs'
import type { WorksheetWizardState } from '../../hooks/useWorksheetWizard'
import type { StudioMobileView } from '../modal/WorksheetModalHeader'
import { StudioDataTab } from './StudioDataTab'
import { StudioHeaderTab } from './StudioHeaderTab'
import { StudioLayoutTab } from './StudioLayoutTab'
import { StudioLocaleSwitcher } from './StudioLocaleSwitcher'
import { StudioTemplateTab } from './StudioTemplateTab'

export interface StudioSidebarProps {
  session: WorksheetWizardState
  activeTab: StudioTab
  setActiveTab: (tab: StudioTab) => void
  mobileView: StudioMobileView
  setMobileView: (view: StudioMobileView) => void
}

/** Left inspector of the Live Studio: wizard shortcuts, locale, tabs and their panels. */
export function StudioSidebar({ session, activeTab, setActiveTab, mobileView, setMobileView }: StudioSidebarProps) {
  const { t } = useTranslation('worksheets')
  const { studio, isStandalone, setWizardStep, isLoadingMeta, meta } = session
  const { currentTemplate, layoutOptions, setLayoutOptions } = studio

  return (
    <aside
      className={`w-full md:w-[380px] lg:w-[410px] min-w-0 max-w-full flex flex-col border-r border-border/80 bg-card/60 backdrop-blur-xs shrink-0 overflow-hidden ${
        mobileView === 'controls' ? 'flex' : 'hidden md:flex'
      }`}
    >
      {/* Quick Wizard Jump Bar */}
      <div className="flex items-center justify-between px-3 pt-2 text-xs border-b border-border/60 pb-1.5 bg-muted/20">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setWizardStep('template')}
          className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1 px-1.5"
          title="Quay lại chọn mẫu bài tập"
        >
          <ChevronLeft className="size-3" />
          <span>Đổi mẫu bài</span>
        </Button>
        {!isStandalone && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setWizardStep('mapping')}
            className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1 px-1.5"
            title="Quay lại ánh xạ trường dữ liệu"
          >
            <Database className="size-3" />
            <span>Đổi ánh xạ</span>
          </Button>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setWizardStep('deck')}
          className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1 px-1.5"
          title="Quay lại chọn bộ thẻ khác"
        >
          <span>Đổi bộ thẻ</span>
        </Button>
      </div>

      {/* Quick Language Switcher: Giản thể vs Phồn thể vs Tiếng Nhật */}
      <StudioLocaleSwitcher
        locale={layoutOptions.locale}
        onChange={(locale) => setLayoutOptions((prev) => ({ ...prev, locale }))}
      />

      {/* Sidebar Tabs Navigator */}
      <div className="grid grid-cols-4 p-1.5 m-3 mb-0 bg-muted/60 rounded-xl border border-border/60 shrink-0">
        {STUDIO_TABS.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`flex flex-col items-center justify-center py-1.5 px-1 rounded-lg text-[11px] font-medium transition-all ${
                isActive
                  ? 'bg-background text-foreground shadow-xs font-bold'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              }`}
            >
              <Icon className="size-3.5 mb-0.5" />
              <span className="hidden sm:inline truncate">{t(tab.labelKey, tab.label)}</span>
              <span className="inline sm:hidden text-[11px] font-semibold">{tab.shortLabel}</span>
            </button>
          )
        })}
      </div>

      {/* Sidebar Tab Content (Scrollable) */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {isLoadingMeta ? (
          <div className="h-64 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="size-8 animate-spin text-primary" />
            <span className="text-xs font-medium">Đang tải cấu hình bộ thẻ...</span>
          </div>
        ) : (
          <>
            {/* TAB 1: TEMPLATES */}
            {activeTab === 'template' && (
              <StudioTemplateTab
                templates={meta?.templates}
                selectedTemplateId={studio.selectedTemplateId}
                onSelectTemplate={studio.handleSelectTemplate}
              />
            )}

            {/* TAB 2: DATA & MAPPINGS */}
            {activeTab === 'data' && currentTemplate && (
              <StudioDataTab
                isStandalone={isStandalone}
                deckId={session.currentDeckId}
                currentTemplate={currentTemplate}
                scope={session.scope}
                setScope={session.setScope}
                limitCount={session.limitCount}
                setLimitCount={session.setLimitCount}
                initialCardIds={session.initialCardIds}
                meta={meta}
                selectedNoteTypeId={session.selectedNoteTypeId}
                setSelectedNoteTypeId={session.setSelectedNoteTypeId}
                availableFields={session.availableFields}
                fieldMapping={studio.fieldMapping}
                setFieldMapping={studio.setFieldMapping}
                layoutOptions={layoutOptions}
                setLayoutOptions={setLayoutOptions}
              />
            )}

            {/* TAB 3: LAYOUT & DENSITY */}
            {activeTab === 'layout' && currentTemplate && (
              <StudioLayoutTab
                currentTemplate={currentTemplate}
                layoutOptions={layoutOptions}
                setLayoutOptions={setLayoutOptions}
                activePresetId={studio.activePresetId}
                setActivePresetId={studio.setActivePresetId}
                handleResetCurrentTemplateDefaults={studio.handleResetCurrentTemplateDefaults}
                meta={meta}
                previewData={studio.previewData}
                setZoomLevel={studio.setZoomLevel}
              />
            )}

            {/* TAB 4: HEADER & METADATA */}
            {activeTab === 'header' && (
              <StudioHeaderTab
                currentTemplate={currentTemplate}
                layoutOptions={layoutOptions}
                setLayoutOptions={setLayoutOptions}
              />
            )}
          </>
        )}
      </div>

      {/* Sidebar Footer Stats & Quick Tab Jump */}
      <div className="p-3 border-t border-border/80 bg-muted/30 flex items-center justify-between text-xs text-muted-foreground shrink-0">
        <span className="truncate">
          {currentTemplate?.name_vi || 'Mẫu'} &bull; {layoutOptions.rows_per_page || 5} dòng/trang
        </span>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 text-xs font-semibold text-primary px-2"
            onClick={() => setActiveTab(nextStudioTab(activeTab))}
          >
            Tiếp tục &rarr;
          </Button>
          {/* Prominent Preview Button for Mobile */}
          <Button
            type="button"
            size="sm"
            className="flex md:hidden h-7 text-xs font-bold bg-primary text-primary-foreground px-2.5 shadow-xs"
            onClick={() => setMobileView('preview')}
          >
            <Eye className="size-3 mr-1" />
            Xem bản in
          </Button>
        </div>
      </div>
    </aside>
  )
}
