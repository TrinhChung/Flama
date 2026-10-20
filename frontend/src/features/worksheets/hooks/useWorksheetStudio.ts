import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { generateWorksheetPreview } from '../api'
import type {
  DeckWorksheetMeta,
  WorksheetFieldMapping,
  WorksheetLayoutOptions,
  WorksheetPreviewResponse,
  WorksheetTemplate,
} from '../types'
import { createDefaultLayoutOptions } from '../config/defaultLayoutOptions'
import type { WizardStepId } from '../config/wizardSteps'
import { printWorksheet } from '../utils/printEngine'
import type { StudioSetup } from '../utils/worksheetMeta'
import { getFirstPreviewZoom, getFitZoom, isMobileViewport } from '../utils/zoom'

export type WorksheetScope = 'all' | 'first_n' | 'random_n' | 'selected'

const MM_TO_PX = 3.7795
const PREVIEW_DEBOUNCE_MS = 300

export interface UseWorksheetStudioProps {
  wizardStep: WizardStepId
  currentDeckId: number | null
  deckName?: string
  initialCardIds?: (string | number)[]
  meta: DeckWorksheetMeta | null
  initialTemplateId: string
  selectedNoteTypeId: string
  scope: WorksheetScope
  limitCount: number
}

/** Template, layout, live preview, zoom and print state of the Live Studio. */
export function useWorksheetStudio({
  wizardStep,
  currentDeckId,
  deckName,
  initialCardIds,
  meta,
  initialTemplateId,
  selectedNoteTypeId,
  scope,
  limitCount,
}: UseWorksheetStudioProps) {
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>(initialTemplateId)
  const [fieldMapping, setFieldMapping] = useState<WorksheetFieldMapping>({})
  const [templateOptionsMap, setTemplateOptionsMap] = useState<Record<string, WorksheetLayoutOptions>>({})
  const [templateFieldMappingMap, setTemplateFieldMappingMap] = useState<Record<string, WorksheetFieldMapping>>({})
  const [layoutOptions, setLayoutOptions] = useState<WorksheetLayoutOptions>(createDefaultLayoutOptions)

  const [activePresetId, setActivePresetId] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<WorksheetPreviewResponse | null>(null)
  const [currentPageIdx, setCurrentPageIdx] = useState<number>(0)
  const [zoomLevel, setZoomLevel] = useState<number>(() =>
    isMobileViewport() ? getFitZoom('portrait', window.innerWidth) : 0.8,
  )
  const [isGenerating, setIsGenerating] = useState(false)
  const [isPrinting, setIsPrinting] = useState(false)

  const isFirstLoadRef = useRef(true)
  const lastTapRef = useRef<number>(0)
  const layoutOptionsRef = useRef(layoutOptions)
  layoutOptionsRef.current = layoutOptions
  const fieldMappingRef = useRef(fieldMapping)
  fieldMappingRef.current = fieldMapping

  const currentTemplate = useMemo<WorksheetTemplate | null>(() => {
    if (!meta?.templates) return null
    return meta.templates.find((tpl) => tpl.id === selectedTemplateId) || meta.templates[0]
  }, [meta, selectedTemplateId])

  /** Latest layout options, safe to read from async callbacks. */
  const getLayoutOptions = () => layoutOptionsRef.current

  /** Clears the preview so the next generated one re-applies the first-load zoom. */
  const resetPreview = () => {
    setPreviewData(null)
    setCurrentPageIdx(0)
    isFirstLoadRef.current = true
    if (isMobileViewport()) {
      setZoomLevel(getFitZoom(layoutOptionsRef.current.orientation, window.innerWidth))
    }
  }

  const applySetup = (setup: StudioSetup) => {
    setSelectedTemplateId(setup.templateId)
    setFieldMapping(setup.fieldMapping)
    setLayoutOptions(setup.layoutOptions)
    if (setup.template) {
      setTemplateOptionsMap({ [setup.template.id]: setup.layoutOptions })
      setTemplateFieldMappingMap({ [setup.template.id]: setup.fieldMapping })
    }
  }

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
    if (wizardStep !== 'studio' || !meta || !currentTemplate) return

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
          setZoomLevel(getFirstPreviewZoom(layoutOptions.orientation))
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
    }, PREVIEW_DEBOUNCE_MS)

    return () => {
      clearTimeout(timer)
      abortController.abort()
    }
  }, [
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
  const a4WidthMm = isLandscape ? 297 : 210
  const a4HeightMm = isLandscape ? 210 : 297
  const containerWidthPx = Math.round(a4WidthMm * MM_TO_PX * zoomLevel)
  const containerHeightPx = Math.round(a4HeightMm * MM_TO_PX * zoomLevel)

  return {
    selectedTemplateId,
    setSelectedTemplateId,
    currentTemplate,
    fieldMapping,
    setFieldMapping,
    layoutOptions,
    setLayoutOptions,
    getLayoutOptions,
    activePresetId,
    setActivePresetId,
    previewData,
    currentPageIdx,
    setCurrentPageIdx,
    zoomLevel,
    setZoomLevel,
    isGenerating,
    isPrinting,
    applySetup,
    resetPreview,
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

export type WorksheetStudioState = ReturnType<typeof useWorksheetStudio>
