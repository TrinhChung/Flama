import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { generateWorksheetPreview } from '../api'
import type {
  DeckWorksheetMeta,
  WorksheetFieldMapping,
  WorksheetLayoutOptions,
  WorksheetPreviewResponse,
} from '../types'
import { printWorksheet } from '../utils/printEngine'
import { getFitZoom } from '../components/studio/StudioPreviewCanvas'
import type { WizardStepId } from '../components/WorksheetWizardStepper'

export interface UseWorksheetStudioProps {
  open: boolean
  wizardStep: WizardStepId
  currentDeckId: number | null
  deckName?: string
  initialCardIds?: (string | number)[]
  meta: DeckWorksheetMeta | null
  currentTemplate: DeckWorksheetMeta['templates'][0] | null
  selectedTemplateId: string
  setSelectedTemplateId: (id: string) => void
  selectedNoteTypeId: string
  scope: 'all' | 'first_n' | 'random_n' | 'selected'
  limitCount: number
}

export function useWorksheetStudio({
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
}: UseWorksheetStudioProps) {
  const [fieldMapping, setFieldMapping] = useState<WorksheetFieldMapping>({})
  const [templateOptionsMap, setTemplateOptionsMap] = useState<Record<string, WorksheetLayoutOptions>>({})
  const [templateFieldMappingMap, setTemplateFieldMappingMap] = useState<Record<string, WorksheetFieldMapping>>({})

  const [layoutOptions, setLayoutOptions] = useState<WorksheetLayoutOptions>({
    paper_size: 'a4',
    orientation: 'portrait',
    margin: 'standard',
    page_fill_mode: 'max_density',
    grid_style: 'cross',
    trace_count: 2,
    practice_count: 5,
    practice_boxes_count: 5,
    rows_per_page: 5,
    writing_lines_count: 3,
    writing_line_style: 'dashed',
    show_sample_sentence: true,
    show_sample_reading: true,
    show_sample_meaning: true,
    exercise_prompt: 'Hãy đặt câu hoàn chỉnh sử dụng cấu trúc / từ vựng trên:',
    show_explanation: true,
    show_example_hint: true,
    watermark_enabled: true,
    watermark_text: typeof window !== 'undefined' ? window.location.hostname : 'flama.app',
    watermark_opacity: 0.07,
    current_url: typeof window !== 'undefined' ? window.location.href : undefined,
    show_stroke_diagram: true,
    show_stroke_numbers: true,
    reference_char_color: '#e11d48',
    stroke_color_mode: 'monochrome',
    show_reading: false,
    show_meaning: false,
    show_source_word: false,
    show_student_info: true,
    show_date: true,
    header_title: '',
    header_subtitle: 'Luyện viết từ vựng và chữ Hán mỗi ngày',
    locale: 'ja',
    grid_columns: 20,
    grid_rows: 20,
    box_style: 'square',
    grid_color: '#475569',
    has_spacer_band: true,
    spacer_height: 10,
    content_mode: 'blank',
    custom_text: '',
    header_student_style: 'chinese',
    title_placement: 'none',
    footer_date_format: 'chinese',
    footer_brand_label: 'Flama (400格)',
    essay_page_count: 1,
  })

  const [activePresetId, setActivePresetId] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<WorksheetPreviewResponse | null>(null)
  const [currentPageIdx, setCurrentPageIdx] = useState<number>(0)
  const [zoomLevel, setZoomLevel] = useState<number>(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      return getFitZoom('portrait', window.innerWidth)
    }
    return 0.8
  })
  const [isGenerating, setIsGenerating] = useState(false)
  const [isPrinting, setIsPrinting] = useState(false)

  const isFirstLoadRef = useRef(true)
  const lastTapRef = useRef<number>(0)
  const layoutOptionsRef = useRef(layoutOptions)
  layoutOptionsRef.current = layoutOptions
  const fieldMappingRef = useRef(fieldMapping)
  fieldMappingRef.current = fieldMapping

  const handleCanvasTouchEnd = (e: React.TouchEvent) => {
    const now = Date.now()
    if (now - lastTapRef.current < 300) {
      e.preventDefault()
      setZoomLevel((curr) => {
        const fit = getFitZoom(layoutOptions.orientation)
        return curr <= fit + 0.05 ? 1 : fit
      })
    }
    lastTapRef.current = now
  }

  const handleSelectTemplate = (templateId: string) => {
    if (selectedTemplateId) {
      setTemplateOptionsMap((prev) => ({
        ...prev,
        [selectedTemplateId]: { ...layoutOptionsRef.current },
      }))
      setTemplateFieldMappingMap((prev) => ({
        ...prev,
        [selectedTemplateId]: { ...fieldMappingRef.current },
      }))
    }

    setSelectedTemplateId(templateId)
    setActivePresetId(null)
    const tpl = meta?.templates.find((t) => t.id === templateId)
    if (tpl) {
      const cached = templateOptionsMap[templateId]
      if (cached) {
        setLayoutOptions(cached)
      } else {
        setLayoutOptions((prev) => ({
          ...prev,
          paper_size: 'a4',
          orientation: tpl.default_orientation || 'portrait',
          rows_per_page: tpl.default_rows_per_page || (templateId === 'deck_table' ? 15 : 5),
          auto_fit_page: true,
          margin: (tpl.default_options?.margin as any) || 'compact',
          locale: prev.locale || meta?.detected_locale || 'ja',
          watermark_enabled: prev.watermark_enabled ?? true,
          watermark_text: prev.watermark_text,
          watermark_opacity: prev.watermark_opacity ?? 0.07,
          current_url: prev.current_url || (typeof window !== 'undefined' ? window.location.href : undefined),
          header_title: prev.header_title || (templateId === 'genkouyoushi' ? '' : (meta?.deck_name || deckName || '')),
          header_subtitle: prev.header_subtitle,
          show_student_info: prev.show_student_info ?? true,
          show_date: prev.show_date ?? true,
          ...tpl.default_options,
        }))
      }

      const cachedMapping = templateFieldMappingMap[templateId]
      if (cachedMapping) {
        setFieldMapping(cachedMapping)
      }
    }
  }

  const handleResetCurrentTemplateDefaults = () => {
    if (!currentTemplate) return
    const tpl = currentTemplate
    setActivePresetId(null)
    const freshDefaults: WorksheetLayoutOptions = {
      ...layoutOptions,
      paper_size: 'a4',
      orientation: tpl.default_orientation || 'portrait',
      rows_per_page: tpl.default_rows_per_page || (tpl.id === 'deck_table' ? 15 : 5),
      auto_fit_page: true,
      margin: (tpl.default_options?.margin as any) || 'compact',
      extra_blank_rows: 0,
      fill_blank_rows: true,
      ...tpl.default_options,
    }
    setLayoutOptions(freshDefaults)
    setTemplateOptionsMap((prev) => ({
      ...prev,
      [tpl.id]: freshDefaults,
    }))
    toast.success(`Đã khôi phục thông số tối ưu cho "${tpl.name_vi}"`)
  }

  // Reactive Debounced Live Preview Generator
  useEffect(() => {
    if (!open || wizardStep !== 'studio' || !meta || !currentTemplate) return

    setIsGenerating(true)
    const abortController = new AbortController()

    const timer = setTimeout(async () => {
      try {
        const response = await generateWorksheetPreview({
          deck_id: currentDeckId || undefined,
          template_id: currentTemplate.id,
          note_type_id: selectedNoteTypeId,
          field_mapping: fieldMapping,
          options: layoutOptions,
          scope: scope === 'selected' ? 'all' : scope,
          limit: scope === 'first_n' || scope === 'random_n' ? limitCount : undefined,
          card_ids: scope === 'selected' ? initialCardIds : undefined,
          signal: abortController.signal,
        })

        if (abortController.signal.aborted) return

        setPreviewData(response)
        setCurrentPageIdx((prev) => Math.min(prev, Math.max(0, response.total_pages - 1)))

        if (isFirstLoadRef.current) {
          isFirstLoadRef.current = false
          if (typeof window !== 'undefined' && window.innerWidth < 768) {
            setZoomLevel(getFitZoom(layoutOptions.orientation, window.innerWidth))
          } else if (layoutOptions.orientation === 'landscape') {
            setZoomLevel(0.72)
          } else {
            setZoomLevel(0.8)
          }
        }
      } catch (err: any) {
        if (err?.name === 'AbortError' || abortController.signal.aborted) {
          return
        }
        console.error('Worksheet preview error:', err)
      } finally {
        if (!abortController.signal.aborted) {
          setIsGenerating(false)
        }
      }
    }, 300)

    return () => {
      clearTimeout(timer)
      abortController.abort()
    }
  }, [
    open,
    wizardStep,
    currentDeckId,
    meta,
    selectedTemplateId,
    selectedNoteTypeId,
    fieldMapping,
    layoutOptions,
    scope,
    limitCount,
    initialCardIds,
    currentTemplate,
  ])

  const handlePrint = async () => {
    if (!previewData) return
    setIsPrinting(true)
    try {
      await printWorksheet(previewData)
    } catch (err: any) {
      toast.error('Không thể in tài liệu: ' + (err.message || err))
    } finally {
      setIsPrinting(false)
    }
  }

  const isLandscape = layoutOptions.orientation === 'landscape'
  const mmToPx = 3.7795
  const a4WidthMm = isLandscape ? 297 : 210
  const a4HeightMm = isLandscape ? 210 : 297
  const containerWidthPx = Math.round(a4WidthMm * mmToPx * zoomLevel)
  const containerHeightPx = Math.round(a4HeightMm * mmToPx * zoomLevel)

  return {
    fieldMapping,
    setFieldMapping,
    templateOptionsMap,
    setTemplateOptionsMap,
    templateFieldMappingMap,
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
    setIsGenerating,
    isPrinting,
    setIsPrinting,
    isFirstLoadRef,
    layoutOptionsRef,
    fieldMappingRef,
    handleCanvasTouchEnd,
    handleSelectTemplate,
    handleResetCurrentTemplateDefaults,
    handlePrint,
    containerWidthPx,
    containerHeightPx,
    a4WidthMm,
    a4HeightMm,
  }
}
