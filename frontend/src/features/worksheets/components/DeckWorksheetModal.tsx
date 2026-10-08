import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  AlertTriangle,
  BookOpen,
  Boxes,
  Check,
  ChevronLeft,
  Database,
  Eye,
  FileEdit,
  FileText,
  FolderTree,
  HelpCircle,
  LayoutGrid,
  ListOrdered,
  Loader2,
  PenTool,
  Printer,
  Sliders,
  Table as TableIcon,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { fetchDeckWorksheetMeta } from '../api'
import type { DeckWorksheetMeta, WorksheetFieldMapping, WorksheetLayoutOptions } from '../types'
import { WorksheetWizardStepper, type WizardStepId } from './WorksheetWizardStepper'
import { WorksheetDeckSelectStep } from './WorksheetDeckSelectStep'
import { WorksheetFieldMappingStep } from './WorksheetFieldMappingStep'
import { WorksheetTemplateSelectStep } from './WorksheetTemplateSelectStep'
import { loadWorksheetPreset, saveWorksheetPreset } from '../utils/worksheetStorage'
import { useWorksheetStudio } from '../hooks/useWorksheetStudio'
import { StudioTemplateTab } from './studio/StudioTemplateTab'
import { StudioDataTab } from './studio/StudioDataTab'
import { StudioLayoutTab } from './studio/StudioLayoutTab'
import { StudioHeaderTab } from './studio/StudioHeaderTab'
import { StudioPreviewCanvas, getFitZoom } from './studio/StudioPreviewCanvas'

export interface DeckWorksheetModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  deckId?: number | null
  deckName?: string
  initialCardIds?: (string | number)[]
  initialStep?: WizardStepId
}

type StudioTab = 'template' | 'data' | 'layout' | 'header'

const templateIcons: Record<string, any> = {
  kanji_compact: PenTool,
  kanji_stroke: PenTool,
  kanji_compound: Boxes,
  kanji_step_by_step: ListOrdered,
  vocab_writing: BookOpen,
  vocab_recall: HelpCircle,
  deck_table: TableIcon,
  sentence_writing: FileText,
  grammar_practice: LayoutGrid,
  genkouyoushi: FileEdit,
}

export function DeckWorksheetModal({
  open,
  onOpenChange,
  deckId,
  deckName,
  initialCardIds,
  initialStep,
}: DeckWorksheetModalProps) {
  const { t } = useTranslation('worksheets')
  const [currentDeckId, setCurrentDeckId] = useState<number | null>(deckId || null)
  const [isStandalone, setIsStandalone] = useState<boolean>(!deckId)
  const [wizardStep, setWizardStep] = useState<WizardStepId>(() => {
    if (initialStep) return initialStep
    return deckId ? 'mapping' : 'deck'
  })

  const [activeTab, setActiveTab] = useState<StudioTab>('template')
  const [mobileView, setMobileView] = useState<'controls' | 'preview'>('preview')
  const [isLoadingMeta, setIsLoadingMeta] = useState(false)

  // Meta state
  const [meta, setMeta] = useState<DeckWorksheetMeta | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>(
    deckId ? 'kanji_compact' : 'genkouyoushi',
  )
  const [selectedNoteTypeId, setSelectedNoteTypeId] = useState<string>('')
  const [scope, setScope] = useState<'all' | 'first_n' | 'random_n' | 'selected'>('all')
  const [limitCount, setLimitCount] = useState<number>(20)

  const currentTemplate = useMemo(() => {
    if (!meta?.templates) return null
    return meta.templates.find((t) => t.id === selectedTemplateId) || meta.templates[0]
  }, [meta, selectedTemplateId])

  const activeNoteType = useMemo(() => {
    if (!meta?.note_types) return null
    return (
      meta.note_types.find((nt) => String(nt.id) === String(selectedNoteTypeId)) ||
      meta.note_types[0]
    )
  }, [meta, selectedNoteTypeId])

  const availableFields = useMemo(() => {
    return activeNoteType?.fields || []
  }, [activeNoteType])

  const studio = useWorksheetStudio({
    open,
    wizardStep,
    currentDeckId,
    deckName,
    initialCardIds,
    meta,
    currentTemplate,
    selectedTemplateId,
    setSelectedTemplateId,
    selectedNoteTypeId,
    scope,
    limitCount,
  })

  const {
    fieldMapping,
    setFieldMapping,
    setTemplateOptionsMap,
    setTemplateFieldMappingMap,
    layoutOptions,
    setLayoutOptions,
    activePresetId,
    setActivePresetId,
    previewData,
    setPreviewData,
    currentPageIdx,
    setCurrentPageIdx,
    zoomLevel,
    setZoomLevel,
    isGenerating,
    isPrinting,
    isFirstLoadRef,
    layoutOptionsRef,
    handleCanvasTouchEnd,
    handleSelectTemplate,
    handleResetCurrentTemplateDefaults,
    handlePrint,
    containerWidthPx,
    containerHeightPx,
    a4WidthMm,
    a4HeightMm,
  } = studio

  const acceptedMetaDeckIdRef = useRef<number | null>(null)

  const studioTabs: { id: StudioTab; label: string; shortLabel: string; icon: any }[] = useMemo(
    () => [
      { id: 'template', label: t('studio.tabs.template', 'Mẫu bài tập'), shortLabel: 'Mẫu', icon: LayoutGrid },
      { id: 'data', label: t('studio.tabs.data', 'Dữ liệu & Trường'), shortLabel: 'Dữ liệu', icon: Database },
      { id: 'layout', label: t('studio.tabs.layout', 'Bố cục & Ô chữ'), shortLabel: 'Bố cục', icon: Sliders },
      { id: 'header', label: t('studio.tabs.header', 'Tiêu đề & Thông tin'), shortLabel: 'Tiêu đề', icon: FileText },
    ],
    [t],
  )

  // Sync deckId and initialStep when modal opens or props change
  useEffect(() => {
    if (!open) return
    const dId = deckId || null
    setCurrentDeckId(dId)
    setIsStandalone(!dId)
    setWizardStep(initialStep || (dId ? 'mapping' : 'deck'))
  }, [open, deckId, initialStep])

  // Load deck worksheet meta on open or when currentDeckId changes
  useEffect(() => {
    if (!open) return

    setIsLoadingMeta(true)
    setPreviewData(null)
    setCurrentPageIdx(0)
    isFirstLoadRef.current = true

    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setZoomLevel(getFitZoom(layoutOptions.orientation, window.innerWidth))
    }

    if (initialCardIds && initialCardIds.length > 0) {
      setScope('selected')
    } else {
      setScope('all')
    }

    // The picker already fetched this exact metadata before confirmation.
    if (currentDeckId && acceptedMetaDeckIdRef.current === currentDeckId) {
      acceptedMetaDeckIdRef.current = null
      setIsLoadingMeta(false)
      return
    }

    fetchDeckWorksheetMeta(currentDeckId)
      .then((data) => {
        setMeta(data)
        if (data.note_types && data.note_types.length > 0) {
          setSelectedNoteTypeId(String(data.note_types[0].id))
        }

        // If deck has multiple note types, stay/return to deck selection step with warning
        if (currentDeckId && (data.has_mixed_note_types || (data.note_types && data.note_types.length > 1))) {
          setWizardStep('deck')
        }

        // Check if preset exists in localStorage for this note type
        let loadedPresetMapping: WorksheetFieldMapping | null = null
        if (data.note_types && data.note_types.length === 1) {
          const primaryNt = data.note_types[0]
          const preset = loadWorksheetPreset(primaryNt.id)
          if (preset) {
            if (preset.fieldMapping && Object.keys(preset.fieldMapping).length > 0) {
              loadedPresetMapping = preset.fieldMapping
              setFieldMapping(preset.fieldMapping)
            }
            if (preset.templateId) {
              setSelectedTemplateId(preset.templateId)
            }
            if (preset.layoutOptions) {
              setLayoutOptions((prev) => ({ ...prev, ...preset.layoutOptions }))
            }
          }
        }

        // Initialize default mappings if no preset was loaded
        if (!loadedPresetMapping) {
          const initMapping: WorksheetFieldMapping = {
            kanji: data.suggested_mappings?.kanji || 'Expression',
            reading: data.suggested_mappings?.reading || '',
            meaning: data.suggested_mappings?.meaning || '',
            word: data.suggested_mappings?.word || 'Expression',
            prompt_reading: data.suggested_mappings?.prompt_reading || '',
            prompt_meaning: data.suggested_mappings?.prompt_meaning || 'Meaning',
            sentence: data.suggested_mappings?.sentence || data.suggested_mappings?.kanji || 'Expression',
            grammar_point: data.suggested_mappings?.grammar_point || data.suggested_mappings?.kanji || 'Expression',
            meaning_usage: data.suggested_mappings?.meaning_usage || data.suggested_mappings?.meaning || '',
            example: data.suggested_mappings?.example || data.suggested_mappings?.reading || '',
            custom_columns: [],
          }
          setFieldMapping(initMapping)
        }

        // Initialize title and detected deck language/locale
        const defaultTitle = data.deck_name || deckName || ''
        const detectedLocale = data.detected_locale || 'ja'
        const initialTpl = data.templates?.find(
          (t) => t.id === (currentDeckId ? 'kanji_compact' : 'genkouyoushi'),
        )
        const initialOptions: WorksheetLayoutOptions = {
          ...layoutOptions,
          locale: detectedLocale,
          header_title: (selectedTemplateId === 'genkouyoushi' ? '' : defaultTitle),
          ...(initialTpl?.default_options || {}),
        }
        setLayoutOptions(initialOptions)
        if (initialTpl) {
          setTemplateOptionsMap({ [initialTpl.id]: initialOptions })
          setTemplateFieldMappingMap({ [initialTpl.id]: loadedPresetMapping || {} })
        }
      })
      .catch((err) => {
        toast.error('Không thể tải thông tin bộ thẻ: ' + String(err.message || err))
      })
      .finally(() => {
        setIsLoadingMeta(false)
      })
  }, [open, currentDeckId, deckName, initialCardIds])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="fixed inset-0 z-50 flex flex-col w-full h-[100dvh] max-w-none translate-x-0 translate-y-0 top-0 left-0 p-0 gap-0 overflow-hidden rounded-none border-0 ring-0 bg-background sm:fixed sm:top-1/2 sm:left-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 sm:w-[98vw] sm:max-w-none sm:h-[96vh] sm:rounded-2xl sm:border sm:border-border sm:shadow-2xl sm:ring-1 sm:ring-foreground/10"
      >
        {/* Desktop Header */}
        <DialogHeader className="hidden md:flex px-5 py-3 border-b border-border/80 bg-muted/40 shrink-0">
          <div className="flex items-center justify-between gap-4">
            {/* Left: Branding & Step / Deck Metadata */}
            <div className="flex items-center gap-3 min-w-0">
              <div className="size-10 rounded-xl bg-orange-500/15 text-orange-600 dark:text-orange-400 flex items-center justify-center shadow-xs shrink-0">
                <Printer className="size-5" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <DialogTitle className="text-base font-bold text-foreground truncate">
                    {wizardStep === 'deck'
                      ? t('modal.title_step_deck', 'Mẫu giấy luyện viết & In ấn (A4) - Chọn bộ thẻ')
                      : wizardStep === 'mapping'
                      ? t('modal.title_step_mapping', {
                          name: meta?.deck_name || deckName || 'Bộ thẻ',
                          defaultValue: `Ánh xạ trường dữ liệu - ${meta?.deck_name || deckName || 'Bộ thẻ'}`,
                        })
                      : wizardStep === 'template'
                      ? t('modal.title_step_template', {
                          name: meta?.deck_name || deckName || 'Bộ thẻ',
                          defaultValue: `Chọn mẫu bài tập - ${meta?.deck_name || deckName || 'Bộ thẻ'}`,
                        })
                      : currentDeckId
                      ? t('modal.title_step_studio_deck', 'Xuất bài tập in ấn / PDF (A4)')
                      : t('modal.title_step_studio_standalone', 'Mẫu giấy luyện viết & In ấn (A4)')}
                  </DialogTitle>
                  <Badge variant="outline" className="text-[10px] font-semibold bg-primary/5 text-primary border-primary/20 shrink-0">
                    {wizardStep === 'studio' ? t('modal.badge_studio', 'Live Studio') : t('modal.badge_wizard', 'Quy trình tạo')}
                  </Badge>
                </div>
                <DialogDescription className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2 truncate">
                  {wizardStep === 'deck' ? (
                    <span>{t('modal.desc_step_deck', 'Bước 1/4: Chọn bộ thẻ bạn muốn tạo mẫu giấy luyện viết & in ấn')}</span>
                  ) : wizardStep === 'mapping' ? (
                    <span>{t('modal.desc_step_mapping', 'Bước 2/4: Xác nhận các trường từ vựng, cách đọc, ý nghĩa')}</span>
                  ) : wizardStep === 'template' ? (
                    <span>{t('modal.desc_step_template', 'Bước 3/4: Chọn loại bài tập muốn in (Chữ Hán, Từ vựng, Đặt câu...)')}</span>
                  ) : (
                    <>
                      <span>{currentDeckId ? (meta?.deck_name || deckName || 'Bộ thẻ') : t('modal.standalone_label', 'Mẫu giấy độc lập (Không cần deck)')}</span>
                      {currentDeckId ? (
                        <>
                          <span>&bull;</span>
                          <span className="font-semibold text-foreground">
                            {t('modal.total_notes', { count: meta?.total_notes || 0, defaultValue: `${meta?.total_notes || 0} ghi chú` })}
                          </span>
                        </>
                      ) : (
                        <>
                          <span>&bull;</span>
                          <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                            {t('modal.free_practice', 'Tự do luyện viết')}
                          </span>
                        </>
                      )}
                      {isGenerating ? (
                        <span className="inline-flex items-center gap-1 text-orange-600 dark:text-orange-400 font-medium animate-pulse shrink-0">
                          <Loader2 className="size-3 animate-spin" />
                          <span>{t('modal.demo_updating', 'Đang cập nhật demo...')}</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium shrink-0">
                          <Check className="size-3" />
                          <span>{t('modal.demo_ready', 'Bản demo sẵn sàng')}</span>
                        </span>
                      )}
                    </>
                  )}
                </DialogDescription>
              </div>
            </div>

            {/* Center / Right: Controls, Zoom, Actions & Desktop Close Button */}
            <div className="flex items-center gap-2.5 shrink-0">
              {wizardStep === 'studio' && (
                <>
                  {/* Zoom Controls */}
                  <div className="flex items-center bg-background rounded-lg border border-border/80 px-1 py-0.5 shadow-2xs">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7"
                      onClick={() => setZoomLevel((z) => Math.max(0.25, Number((z - 0.1).toFixed(2))))}
                      title={t('modal.zoom_out', 'Thu nhỏ')}
                    >
                      <ZoomOut className="size-3.5" />
                    </Button>
                    <span className="text-xs font-bold px-2 min-w-12 text-center">
                      {Math.round(zoomLevel * 100)}%
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7"
                      onClick={() => setZoomLevel((z) => Math.min(1.5, Number((z + 0.1).toFixed(2))))}
                      title={t('modal.zoom_in', 'Phóng to')}
                    >
                      <ZoomIn className="size-3.5" />
                    </Button>
                  </div>

                  {/* Quick Zoom Presets */}
                  <div className="hidden lg:flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setZoomLevel(getFitZoom(layoutOptions.orientation))}
                      className="h-8 px-2.5 text-[11px] font-medium"
                    >
                      {t('modal.zoom_fit', 'Vừa trang')}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setZoomLevel(1)}
                      className="h-8 px-2.5 text-[11px] font-medium"
                    >
                      100%
                    </Button>
                  </div>

                  {/* Print Button */}
                  <Button
                    size="sm"
                    onClick={handlePrint}
                    disabled={isPrinting || !previewData}
                    className="h-8.5 px-4 text-xs font-bold gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground shadow-md"
                  >
                    {isPrinting ? (
                      <>
                        <Loader2 className="size-3.5 animate-spin" />
                        <span>{t('modal.print_preparing', 'Đang chuẩn bị...')}</span>
                      </>
                    ) : (
                      <>
                        <Printer className="size-3.5" />
                        <span>{t('modal.print_button', 'In / Lưu PDF')}</span>
                      </>
                    )}
                  </Button>
                </>
              )}

              {/* Desktop Close Button */}
              <Button
                variant="ghost"
                size="icon"
                className="size-8 rounded-lg text-muted-foreground hover:text-foreground ml-1"
                onClick={() => onOpenChange(false)}
                title={t('modal.close', 'Đóng')}
                aria-label={t('modal.close', 'Đóng')}
              >
                <X className="size-4" />
              </Button>
            </div>
          </div>
        </DialogHeader>

        {/* Mobile Header */}
        <DialogHeader className="flex md:hidden px-3.5 py-2.5 border-b border-border/80 bg-muted/40 shrink-0 gap-2">
          {/* Row 1: Brand Icon + Title + Close Button */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="size-8 rounded-lg bg-orange-500/15 text-orange-600 dark:text-orange-400 flex items-center justify-center shrink-0">
                <Printer className="size-4" />
              </div>
              <div className="min-w-0">
                <DialogTitle className="text-sm font-bold text-foreground truncate">
                  {wizardStep === 'deck'
                    ? t('stepper.step_deck', 'Chọn bộ thẻ')
                    : wizardStep === 'mapping'
                    ? t('stepper.step_mapping', 'Ánh xạ dữ liệu')
                    : wizardStep === 'template'
                    ? t('stepper.step_template', 'Chọn mẫu bài tập')
                    : currentDeckId
                    ? t('modal.title_step_studio_deck', 'Xuất bài tập in ấn / PDF (A4)')
                    : t('modal.title_step_studio_standalone', 'Mẫu giấy luyện viết & In ấn (A4)')}
                </DialogTitle>
                <div className="text-[10px] text-muted-foreground truncate flex items-center gap-1.5">
                  <span>{currentDeckId ? (meta?.deck_name || deckName || 'Bộ thẻ') : 'Mẫu tự do'}</span>
                  {wizardStep === 'studio' && (
                    <>
                      <span>&bull;</span>
                      {isGenerating ? (
                        <span className="text-orange-600 dark:text-orange-400 font-medium inline-flex items-center gap-1">
                          <Loader2 className="size-2.5 animate-spin" />
                          <span>Cập nhật...</span>
                        </span>
                      ) : (
                        <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                          {previewData?.total_pages || 1} trang A4
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>

            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8 rounded-lg text-muted-foreground hover:text-foreground shrink-0"
              onClick={() => onOpenChange(false)}
              aria-label={t('modal.close', 'Đóng')}
            >
              <X className="size-4" />
            </Button>
          </div>

          {/* Row 2: Full-width Segmented View Switcher (Only in Studio mode) */}
          {wizardStep === 'studio' && (
            <div className="grid grid-cols-2 p-0.5 bg-background rounded-lg border border-border/80 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setMobileView('controls')}
                className={`flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-md transition-all ${
                  mobileView === 'controls'
                    ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Sliders className="size-3.5 shrink-0" />
                <span>{t('modal.mobile_config', 'Cấu hình')}</span>
              </button>
              <button
                type="button"
                onClick={() => setMobileView('preview')}
                className={`flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-md transition-all ${
                  mobileView === 'preview'
                    ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Eye className="size-3.5 shrink-0" />
                <span>{t('modal.mobile_preview', { count: previewData?.total_pages || 1, defaultValue: `Xem bản in (${previewData?.total_pages || 1})` })}</span>
              </button>
            </div>
          )}
        </DialogHeader>

        {/* Wizard Stepper Bar */}
        <WorksheetWizardStepper
          currentStep={wizardStep}
          onSelectStep={(step) => {
            if (step === 'mapping' && (!currentDeckId || meta?.has_mixed_note_types || (meta?.note_types && meta.note_types.length > 1))) {
              return
            }
            setWizardStep(step)
          }}
          isStandalone={isStandalone}
        />

        {/* STEP 1: DECK SELECTION */}
        {wizardStep === 'deck' && (
          <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
            <WorksheetDeckSelectStep
              selectedDeckId={currentDeckId}
              onSelectDeck={(newDeckId, newMeta) => {
                acceptedMetaDeckIdRef.current = newDeckId
                setCurrentDeckId(newDeckId)
                setMeta(newMeta)
                setIsStandalone(false)
                const primaryNoteType = newMeta.note_types?.[0]
                if (primaryNoteType) {
                  setSelectedNoteTypeId(String(primaryNoteType.id))
                }
                const preset = primaryNoteType ? loadWorksheetPreset(primaryNoteType.id) : null
                const nextTemplateId = preset?.templateId || 'kanji_compact'
                const nextTemplate = newMeta.templates?.find((item) => item.id === nextTemplateId)
                const nextMapping = preset?.fieldMapping || {
                  kanji: newMeta.suggested_mappings?.kanji || 'Expression',
                  reading: newMeta.suggested_mappings?.reading || '',
                  meaning: newMeta.suggested_mappings?.meaning || '',
                  word: newMeta.suggested_mappings?.word || 'Expression',
                  prompt_reading: newMeta.suggested_mappings?.prompt_reading || '',
                  prompt_meaning: newMeta.suggested_mappings?.prompt_meaning || 'Meaning',
                  sentence: newMeta.suggested_mappings?.sentence || newMeta.suggested_mappings?.kanji || 'Expression',
                  grammar_point: newMeta.suggested_mappings?.grammar_point || newMeta.suggested_mappings?.kanji || 'Expression',
                  meaning_usage: newMeta.suggested_mappings?.meaning_usage || newMeta.suggested_mappings?.meaning || '',
                  example: newMeta.suggested_mappings?.example || newMeta.suggested_mappings?.reading || '',
                  custom_columns: [],
                }
                setSelectedTemplateId(nextTemplateId)
                setFieldMapping(nextMapping)
                const nextOptions = {
                  ...layoutOptionsRef.current,
                  locale: newMeta.detected_locale || 'ja',
                  header_title: newMeta.deck_name || '',
                  ...(nextTemplate?.default_options || {}),
                  ...(preset?.layoutOptions || {}),
                }
                setLayoutOptions(nextOptions)
                if (nextTemplate) {
                  setTemplateOptionsMap({ [nextTemplate.id]: nextOptions })
                  setTemplateFieldMappingMap({ [nextTemplate.id]: nextMapping })
                }
                setWizardStep('mapping')
              }}
              onSelectStandalone={() => {
                setCurrentDeckId(null)
                setIsStandalone(true)
                setSelectedTemplateId('genkouyoushi')
                setWizardStep('template')
              }}
              onCancel={() => onOpenChange(false)}
            />
          </div>
        )}

        {/* STEP 2: FIELD MAPPING */}
        {wizardStep === 'mapping' && (
          <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
            {meta && (meta.has_mixed_note_types || (meta.note_types && meta.note_types.length > 1)) ? (
              <div className="p-6 flex flex-col items-center justify-center text-center space-y-4 max-w-lg mx-auto h-full">
                <div className="size-12 rounded-full bg-amber-500/10 text-amber-600 flex items-center justify-center">
                  <AlertTriangle className="size-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-foreground">
                    Bộ thẻ chứa {meta.note_types?.length || 2} loại thẻ khác nhau
                  </h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Để hệ thống trích xuất dữ liệu và in bài tập chính xác nhất, vui lòng chọn một bộ thẻ chỉ chứa <strong>1 loại thẻ duy nhất</strong>.
                  </p>
                </div>
                <Button onClick={() => setWizardStep('deck')} size="sm" className="gap-1.5 font-bold">
                  <FolderTree className="size-3.5" />
                  <span>Chọn bộ thẻ khác</span>
                </Button>
              </div>
            ) : activeNoteType ? (
              <WorksheetFieldMappingStep
                noteType={activeNoteType}
                deckName={meta?.deck_name || deckName || 'Bộ thẻ'}
                totalNotes={meta?.total_notes || 0}
                suggestedMappings={meta?.suggested_mappings || {}}
                initialMapping={fieldMapping}
                onConfirmMapping={(newMapping) => {
                  setFieldMapping(newMapping)
                  if (activeNoteType) {
                    saveWorksheetPreset(activeNoteType.id, {
                      fieldMapping: newMapping,
                      templateId: selectedTemplateId,
                      layoutOptions,
                    })
                  }
                  setWizardStep('template')
                }}
                onBack={() => setWizardStep('deck')}
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
              selectedTemplateId={selectedTemplateId}
              onSelectTemplate={(tplId) => handleSelectTemplate(tplId)}
              onConfirm={() => {
                if (activeNoteType) {
                  saveWorksheetPreset(activeNoteType.id, {
                    fieldMapping,
                    templateId: selectedTemplateId,
                    layoutOptions,
                  })
                }
                setWizardStep('studio')
              }}
              onBack={() => setWizardStep(isStandalone ? 'deck' : 'mapping')}
              isStandalone={isStandalone}
            />
          </div>
        )}

        {/* STEP 4: LIVE STUDIO WORKSPACE */}
        {wizardStep === 'studio' && (
          <div className="flex-1 flex overflow-hidden min-h-0">
            {/* Left Sidebar: Controls & Inspector (~380px) */}
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
              <div className="mx-3 mt-3 p-1 bg-muted/80 rounded-xl border border-border/70 flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() =>
                    setLayoutOptions((prev) => ({
                      ...prev,
                      locale: 'zh',
                    }))
                  }
                  className={`flex-1 py-1.5 px-1.5 rounded-lg text-[11px] sm:text-xs font-semibold flex items-center justify-center gap-1 transition-all ${
                    (layoutOptions.locale || 'ja') === 'zh'
                      ? 'bg-background text-foreground shadow-xs font-bold text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <span>🇨🇳</span>
                  <span>Tiếng Trung (Giản thể)</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setLayoutOptions((prev) => ({
                      ...prev,
                      locale: 'zh-hant',
                    }))
                  }
                  className={`flex-1 py-1.5 px-1.5 rounded-lg text-[10px] sm:text-xs font-semibold flex items-center justify-center gap-1 transition-all ${
                    (layoutOptions.locale || 'ja') === 'zh-hant'
                      ? 'bg-background text-foreground shadow-xs font-bold text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <span>🇹🇼</span>
                  <span>Tiếng Trung (Phồn thể)</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setLayoutOptions((prev) => ({
                      ...prev,
                      locale: 'ja',
                    }))
                  }
                  className={`flex-1 py-1.5 px-1.5 rounded-lg text-[11px] sm:text-xs font-semibold flex items-center justify-center gap-1 transition-all ${
                    (layoutOptions.locale || 'ja') === 'ja'
                      ? 'bg-background text-foreground shadow-xs font-bold text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <span>🇯🇵</span>
                  <span>Tiếng Nhật</span>
                </button>
              </div>

              {/* Sidebar Tabs Navigator */}
              <div className="grid grid-cols-4 p-1.5 m-3 mb-0 bg-muted/60 rounded-xl border border-border/60 shrink-0">
                {studioTabs.map((tab) => {
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
                      <span className="hidden sm:inline truncate">{tab.label}</span>
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
                        selectedTemplateId={selectedTemplateId}
                        onSelectTemplate={(tplId) => handleSelectTemplate(tplId)}
                        templateIcons={templateIcons}
                      />
                    )}

                    {/* TAB 2: DATA & MAPPINGS */}
                    {activeTab === 'data' && currentTemplate && (
                      <StudioDataTab
                        isStandalone={isStandalone}
                        deckId={currentDeckId}
                        currentTemplate={currentTemplate}
                        scope={scope}
                        setScope={setScope}
                        limitCount={limitCount}
                        setLimitCount={setLimitCount}
                        initialCardIds={initialCardIds}
                        meta={meta}
                        selectedNoteTypeId={selectedNoteTypeId}
                        setSelectedNoteTypeId={setSelectedNoteTypeId}
                        availableFields={availableFields}
                        fieldMapping={fieldMapping}
                        setFieldMapping={setFieldMapping}
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
                        activePresetId={activePresetId}
                        setActivePresetId={setActivePresetId}
                        handleResetCurrentTemplateDefaults={handleResetCurrentTemplateDefaults}
                        meta={meta}
                        previewData={previewData}
                        setZoomLevel={setZoomLevel}
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
                    onClick={() => {
                      const tabIdx = studioTabs.findIndex((t) => t.id === activeTab)
                      const nextTab = studioTabs[(tabIdx + 1) % studioTabs.length]
                      setActiveTab(nextTab.id)
                    }}
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

            {/* Right Area: Live Workbench Preview Canvas (flex-1) */}
            <StudioPreviewCanvas
              mobileView={mobileView}
              currentPageIdx={currentPageIdx}
              setCurrentPageIdx={setCurrentPageIdx}
              previewData={previewData}
              zoomLevel={zoomLevel}
              setZoomLevel={setZoomLevel}
              layoutOptions={layoutOptions}
              isGenerating={isGenerating}
              isLoadingMeta={isLoadingMeta}
              currentTemplate={currentTemplate}
              fieldMapping={fieldMapping}
              containerWidthPx={containerWidthPx}
              containerHeightPx={containerHeightPx}
              a4WidthMm={a4WidthMm}
              a4HeightMm={a4HeightMm}
              handleCanvasTouchEnd={handleCanvasTouchEnd}
              handlePrint={handlePrint}
              isPrinting={isPrinting}
            />
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
