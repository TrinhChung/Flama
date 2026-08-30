import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Badge } from '@/components/ui/badge'
import {
  BookOpen,
  Check,
  ChevronLeft,
  ChevronRight,
  Database,
  Eye,
  FileText,
  HelpCircle,
  Layers,
  LayoutGrid,
  Loader2,
  Minus,
  PanelLeft,
  PenTool,
  Plus,
  Printer,
  RotateCcw,
  Sliders,
  Sparkles,
  Table as TableIcon,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  fetchDeckWorksheetMeta,
  generateWorksheetPreview,
  renderWorksheetHtml,
} from '../api'
import type {
  DeckWorksheetMeta,
  WorksheetFieldMapping,
  WorksheetLayoutOptions,
  WorksheetPreviewResponse,
} from '../types'
import { printWorksheetHtml } from '../utils/printEngine'
import { WorksheetPageRenderer } from './WorksheetPageRenderer'

export interface DeckWorksheetModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  deckId: number
  deckName?: string
  initialCardIds?: (string | number)[]
}

type StudioTab = 'template' | 'data' | 'layout' | 'header'

const STUDIO_TABS: { id: StudioTab; label: string; icon: any }[] = [
  { id: 'template', label: 'Mẫu bài tập', icon: LayoutGrid },
  { id: 'data', label: 'Dữ liệu & Trường', icon: Database },
  { id: 'layout', label: 'Bố cục & Ô chữ', icon: Sliders },
  { id: 'header', label: 'Tiêu đề & Thông tin', icon: FileText },
]

const templateIcons: Record<string, any> = {
  kanji_stroke: PenTool,
  kanji_compact: Layers,
  vocab_writing: BookOpen,
  vocab_recall: Sparkles,
  deck_table: TableIcon,
  sentence_writing: FileText,
  grammar_practice: HelpCircle,
}

export function DeckWorksheetModal({
  open,
  onOpenChange,
  deckId,
  deckName,
  initialCardIds,
}: DeckWorksheetModalProps) {
  const [activeTab, setActiveTab] = useState<StudioTab>('template')
  const [mobileView, setMobileView] = useState<'controls' | 'preview'>('preview')
  const [isLoadingMeta, setIsLoadingMeta] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isPrinting, setIsPrinting] = useState(false)

  // Meta state
  const [meta, setMeta] = useState<DeckWorksheetMeta | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('kanji_stroke')
  const [selectedNoteTypeId, setSelectedNoteTypeId] = useState<string>('')
  const [scope, setScope] = useState<'all' | 'first_n' | 'random_n' | 'selected'>('all')
  const [limitCount, setLimitCount] = useState<number>(20)

  // Field mapping state
  const [fieldMapping, setFieldMapping] = useState<WorksheetFieldMapping>({})

  // Layout options state
  const [layoutOptions, setLayoutOptions] = useState<WorksheetLayoutOptions>({
    paper_size: 'a4',
    orientation: 'portrait',
    margin: 'standard',
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
    show_stroke_diagram: true,
    show_reading: true,
    show_meaning: true,
    show_student_info: true,
    show_date: true,
    header_title: '',
    header_subtitle: 'Luyện viết từ vựng và chữ Hán mỗi ngày',
    locale: 'ja',
  })

  // Live Preview state
  const [previewData, setPreviewData] = useState<WorksheetPreviewResponse | null>(null)
  const [currentPageIdx, setCurrentPageIdx] = useState<number>(0)
  const [zoomLevel, setZoomLevel] = useState<number>(0.8)

  const isFirstLoadRef = useRef(true)

  // Load deck worksheet meta on open
  useEffect(() => {
    if (!open || !deckId) return

    setIsLoadingMeta(true)
    setPreviewData(null)
    setCurrentPageIdx(0)
    isFirstLoadRef.current = true

    if (initialCardIds && initialCardIds.length > 0) {
      setScope('selected')
    } else {
      setScope('all')
    }

    fetchDeckWorksheetMeta(deckId)
      .then((data) => {
        setMeta(data)
        if (data.note_types && data.note_types.length > 0) {
          setSelectedNoteTypeId(String(data.note_types[0].id))
        }

        // Initialize default mappings (custom_columns is empty by default so user can choose)
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

        // Initialize title
        const defaultTitle = `${data.deck_name || deckName || 'Bộ thẻ'} - Bài tập`
        setLayoutOptions((prev) => ({
          ...prev,
          header_title: defaultTitle,
        }))
      })
      .catch((err) => {
        toast.error('Không thể tải thông tin bộ thẻ: ' + String(err.message || err))
      })
      .finally(() => {
        setIsLoadingMeta(false)
      })
  }, [open, deckId, deckName, initialCardIds])

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

  // Select template handler
  const handleSelectTemplate = (templateId: string) => {
    setSelectedTemplateId(templateId)
    const tpl = meta?.templates.find((t) => t.id === templateId)
    if (tpl) {
      setLayoutOptions((prev) => ({
        ...prev,
        orientation: tpl.default_orientation || 'portrait',
        rows_per_page: tpl.default_rows_per_page || (templateId === 'deck_table' ? 15 : 5),
        grid_style: (tpl.default_options?.grid_style as any) || 'cross',
        trace_count: tpl.default_options?.trace_count ?? 2,
        practice_count: tpl.default_options?.practice_count ?? 5,
      }))
    }
  }

  // Reactive Debounced Live Preview Generator
  useEffect(() => {
    if (!open || !deckId || !meta || !currentTemplate) return

    const timer = setTimeout(async () => {
      setIsGenerating(true)
      try {
        const response = await generateWorksheetPreview({
          deck_id: deckId,
          template_id: currentTemplate.id,
          note_type_id: selectedNoteTypeId,
          field_mapping: fieldMapping,
          options: layoutOptions,
          scope: scope === 'selected' ? 'all' : scope,
          limit: scope === 'first_n' || scope === 'random_n' ? limitCount : undefined,
          card_ids: scope === 'selected' ? initialCardIds : undefined,
        })

        setPreviewData(response)

        // Clamp page index if total pages shrank
        setCurrentPageIdx((prev) => Math.min(prev, Math.max(0, response.total_pages - 1)))

        if (isFirstLoadRef.current) {
          isFirstLoadRef.current = false
          if (layoutOptions.orientation === 'landscape') {
            setZoomLevel(0.72)
          } else {
            setZoomLevel(0.8)
          }
        }
      } catch (err: any) {
        console.error('Worksheet preview error:', err)
      } finally {
        setIsGenerating(false)
      }
    }, 200)

    return () => clearTimeout(timer)
  }, [
    open,
    deckId,
    meta,
    selectedTemplateId,
    selectedNoteTypeId,
    fieldMapping,
    layoutOptions,
    scope,
    limitCount,
    initialCardIds,
  ])

  // Handle direct print
  const handlePrint = async () => {
    if (!previewData) return
    setIsPrinting(true)
    try {
      const html = await renderWorksheetHtml(previewData)
      printWorksheetHtml(html)
    } catch (err: any) {
      toast.error('Không thể in tài liệu: ' + (err.message || err))
    } finally {
      setIsPrinting(false)
    }
  }

  const templateIcons: Record<string, any> = {
    kanji_stroke: PenTool,
    kanji_compact: Layers,
    vocab_writing: BookOpen,
    vocab_recall: HelpCircle,
    deck_table: TableIcon,
  }

  const isLandscape = layoutOptions.orientation === 'landscape'
  const mmToPx = 3.7795
  const a4WidthMm = isLandscape ? 297 : 210
  const a4HeightMm = isLandscape ? 210 : 297
  const containerWidthPx = Math.round(a4WidthMm * mmToPx * zoomLevel)
  const containerHeightPx = Math.round(a4HeightMm * mmToPx * zoomLevel)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-screen h-screen sm:w-[98vw] sm:h-[96vh] sm:max-w-none max-h-none flex flex-col p-0 gap-0 overflow-hidden rounded-none sm:rounded-2xl border-border bg-background shadow-2xl">
        {/* Studio Top Header Bar */}
        <DialogHeader className="px-5 py-3 border-b border-border/80 bg-muted/40 shrink-0">
          <div className="flex items-center justify-between gap-4">
            {/* Left: Branding & Deck Metadata */}
            <div className="flex items-center gap-3">
              <div className="size-10 rounded-xl bg-orange-500/15 text-orange-600 dark:text-orange-400 flex items-center justify-center shadow-xs shrink-0">
                <Printer className="size-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <DialogTitle className="text-base font-bold text-foreground">
                    Xuất bài tập in ấn / PDF (A4)
                  </DialogTitle>
                  <Badge variant="outline" className="hidden sm:inline-flex text-[10px] font-semibold bg-primary/5 text-primary border-primary/20">
                    Live Studio
                  </Badge>
                </div>
                <DialogDescription className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2">
                  <span>{meta?.deck_name || deckName || 'Bộ thẻ'}</span>
                  <span>&bull;</span>
                  <span className="font-semibold text-foreground">{meta?.total_notes || 0} ghi chú</span>
                  {isGenerating ? (
                    <span className="inline-flex items-center gap-1 text-orange-600 dark:text-orange-400 font-medium animate-pulse">
                      <Loader2 className="size-3 animate-spin" />
                      <span>Đang cập nhật demo...</span>
                    </span>
                  ) : (
                    <span className="hidden sm:inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                      <Check className="size-3" />
                      <span>Bản demo sẵn sàng</span>
                    </span>
                  )}
                </DialogDescription>
              </div>
            </div>

            {/* Center / Right: Controls, Zoom, Actions & Mobile Toggle */}
            <div className="flex items-center gap-2.5">
              {/* Mobile View Switcher */}
              <div className="flex md:hidden items-center bg-background rounded-lg border border-border/80 p-0.5">
                <Button
                  type="button"
                  variant={mobileView === 'controls' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setMobileView('controls')}
                  className="h-7 px-2.5 text-xs font-semibold"
                >
                  <Sliders className="size-3.5 mr-1" />
                  Cấu hình
                </Button>
                <Button
                  type="button"
                  variant={mobileView === 'preview' ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setMobileView('preview')}
                  className="h-7 px-2.5 text-xs font-semibold"
                >
                  <Eye className="size-3.5 mr-1" />
                  Bản in
                </Button>
              </div>

              {/* Zoom Controls */}
              <div className="hidden sm:flex items-center bg-background rounded-lg border border-border/80 px-1 py-0.5 shadow-2xs">
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  onClick={() => setZoomLevel((z) => Math.max(0.4, Number((z - 0.1).toFixed(2))))}
                  title="Thu nhỏ"
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
                  onClick={() => setZoomLevel((z) => Math.min(1.4, Number((z + 0.1).toFixed(2))))}
                  title="Phóng to"
                >
                  <ZoomIn className="size-3.5" />
                </Button>
              </div>

              {/* Quick Zoom Presets */}
              <div className="hidden lg:flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setZoomLevel(isLandscape ? 0.72 : 0.8)}
                  className="h-8 px-2.5 text-[11px] font-medium"
                >
                  Vừa trang
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
                    <span>Đang chuẩn bị...</span>
                  </>
                ) : (
                  <>
                    <Printer className="size-3.5" />
                    <span>In ngay (A4)</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </DialogHeader>

        {/* Studio Main Workspace (Split View) */}
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Left Sidebar: Controls & Inspector (~380px) */}
          <aside
            className={`w-full md:w-[380px] lg:w-[410px] flex flex-col border-r border-border/80 bg-card/60 backdrop-blur-xs shrink-0 ${
              mobileView === 'controls' ? 'flex' : 'hidden md:flex'
            }`}
          >
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
                    <span className="truncate">{tab.label}</span>
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
                    <div className="space-y-3">
                      <div>
                        <h3 className="text-xs font-bold text-foreground uppercase tracking-wider">
                          Chọn mẫu bài tập
                        </h3>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          Nhấp chọn mẫu để xem ngay bản demo cập nhật trực tiếp bên phải.
                        </p>
                      </div>

                      <div className="space-y-2.5 pt-1">
                        {meta?.templates.map((tpl) => {
                          const Icon = templateIcons[tpl.id] || FileText
                          const isSelected = selectedTemplateId === tpl.id

                          const categoryBadgeColor =
                            tpl.category === 'kanji'
                              ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                              : tpl.category === 'vocabulary'
                              ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
                              : tpl.category === 'sentence'
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                              : tpl.category === 'grammar'
                              ? 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20'
                              : 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20'

                          return (
                            <div
                              key={tpl.id}
                              onClick={() => handleSelectTemplate(tpl.id)}
                              className={`relative p-3.5 rounded-xl border-2 cursor-pointer transition-all flex flex-col gap-2 text-left ${
                                isSelected
                                  ? 'border-primary bg-primary/5 shadow-xs ring-2 ring-primary/20'
                                  : 'border-border hover:border-border/80 hover:bg-muted/40 bg-card'
                              }`}
                            >
                              {isSelected && (
                                <div className="absolute top-3 right-3 size-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-xs">
                                  <Check className="size-3" />
                                </div>
                              )}

                              <div className="flex items-start gap-2.5">
                                <div
                                  className={`size-9 rounded-xl flex items-center justify-center shrink-0 ${
                                    isSelected
                                      ? 'bg-primary text-primary-foreground'
                                      : 'bg-muted text-muted-foreground'
                                  }`}
                                >
                                  <Icon className="size-4.5" />
                                </div>
                                <div className="space-y-0.5 flex-1 pr-5">
                                  <div className="flex items-center gap-2">
                                    <h4 className="text-xs font-bold text-foreground">
                                      {tpl.name_vi}
                                    </h4>
                                  </div>
                                  <Badge
                                    variant="outline"
                                    className={`text-[9px] uppercase font-semibold px-1.5 py-0 border ${categoryBadgeColor}`}
                                  >
                                    {tpl.category === 'kanji'
                                      ? 'Chữ Hán'
                                      : tpl.category === 'vocabulary'
                                      ? 'Từ vựng'
                                      : tpl.category === 'sentence'
                                      ? 'Mẫu câu & Dịch'
                                      : tpl.category === 'grammar'
                                      ? 'Ngữ pháp'
                                      : 'Bảng dữ liệu'}
                                  </Badge>
                                  <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2 mt-1">
                                    {tpl.description_vi}
                                  </p>
                                </div>
                              </div>

                              <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-2 border-t border-border/50">
                                <span>
                                  Mặc định: <strong>{tpl.default_rows_per_page} mục/trang</strong>
                                </span>
                                <span className="capitalize">
                                  Khổ: <strong>{tpl.default_orientation === 'portrait' ? 'A4 Dọc' : 'A4 Ngang'}</strong>
                                </span>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* TAB 2: DATA & MAPPINGS */}
                  {activeTab === 'data' && currentTemplate && (
                    <div className="space-y-4">
                      {/* Scope & Limit */}
                      <div className="space-y-2.5 bg-muted/30 p-3.5 rounded-xl border border-border/60">
                        <div className="flex items-center justify-between">
                          <Label className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Phạm vi dữ liệu
                          </Label>
                          <Badge variant="secondary" className="text-[10px] font-semibold">
                            {scope === 'all'
                              ? `Toàn bộ (${meta?.total_notes || 0} ghi chú)`
                              : scope === 'selected'
                              ? `${initialCardIds?.length || 0} thẻ đã chọn`
                              : `${limitCount} ghi chú`}
                          </Badge>
                        </div>

                        <div className="space-y-2">
                          <NativeSelect
                            value={scope}
                            onChange={(e) => setScope(e.target.value as any)}
                            className="h-8.5 text-xs"
                          >
                            {initialCardIds && initialCardIds.length > 0 && (
                              <option value="selected">
                                {initialCardIds.length} thẻ đang chọn trong danh sách
                              </option>
                            )}
                            <option value="all">Toàn bộ bộ thẻ ({meta?.total_notes} ghi chú)</option>
                            <option value="first_n">N thẻ đầu tiên</option>
                            <option value="random_n">Lấy ngẫu nhiên N thẻ</option>
                          </NativeSelect>

                          {(scope === 'first_n' || scope === 'random_n') && (
                            <div className="space-y-1.5 pt-1">
                              <Label className="text-[11px] font-medium text-muted-foreground">
                                Số lượng ghi chú (N):
                              </Label>
                              <div className="flex items-center gap-1.5">
                                <Input
                                  type="number"
                                  min={1}
                                  max={500}
                                  value={limitCount}
                                  onChange={(e) => setLimitCount(Math.max(1, Number(e.target.value)))}
                                  className="h-8 text-xs w-20"
                                />
                                {[10, 20, 50, 100].map((cnt) => (
                                  <Button
                                    key={cnt}
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setLimitCount(cnt)}
                                    className={`h-8 px-2 text-[11px] ${
                                      limitCount === cnt ? 'bg-primary text-primary-foreground font-bold' : ''
                                    }`}
                                  >
                                    {cnt}
                                  </Button>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Note Type Selector if multiple */}
                      {meta && meta.note_types.length > 1 && (
                        <div className="space-y-1.5 bg-muted/30 p-3.5 rounded-xl border border-border/60">
                          <Label className="text-xs font-semibold">Loại ghi chú (Note Type)</Label>
                          <NativeSelect
                            value={selectedNoteTypeId}
                            onChange={(e) => setSelectedNoteTypeId(e.target.value)}
                            className="h-8.5 text-xs"
                          >
                            {meta.note_types.map((nt) => (
                              <option key={nt.id} value={nt.id}>
                                {nt.name} ({nt.note_count} ghi chú)
                              </option>
                            ))}
                          </NativeSelect>
                        </div>
                      )}

                      {/* Field Slots Mapping */}
                      <div className="space-y-3 bg-card p-3.5 rounded-xl border border-border/70 shadow-xs">
                        <div className="flex items-center justify-between">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Ánh xạ trường nguồn
                          </h4>
                          <Badge variant="outline" className="text-[10px] text-muted-foreground">
                            {availableFields.length} trường
                          </Badge>
                        </div>

                        {currentTemplate.id === 'deck_table' ? (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1.5">
                                <Label className="text-[11px] font-bold text-foreground">Chọn các cột bảng:</Label>
                                <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 font-semibold">
                                  {((fieldMapping.custom_columns as string[]) || []).length} cột
                                </Badge>
                              </div>
                              <div className="flex items-center gap-1">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 text-[10px] px-1.5 text-primary hover:bg-primary/10"
                                  onClick={() =>
                                    setFieldMapping((prev) => ({
                                      ...prev,
                                      custom_columns: [...availableFields],
                                    }))
                                  }
                                >
                                  Tất cả
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 text-[10px] px-1.5 text-muted-foreground hover:bg-muted"
                                  onClick={() =>
                                    setFieldMapping((prev) => ({
                                      ...prev,
                                      custom_columns: [],
                                    }))
                                  }
                                >
                                  Bỏ chọn
                                </Button>
                              </div>
                            </div>

                            {((fieldMapping.custom_columns as string[]) || []).length === 0 && (
                              <div className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-lg leading-relaxed">
                                💡 <strong>Chưa chọn cột nào</strong>. Tích chọn các trường bên dưới để thêm vào bảng in (tránh chọn quá nhiều làm vỡ layout).
                              </div>
                            )}

                            {/* Selected Columns with Width Adjustment */}
                            {((fieldMapping.custom_columns as string[]) || []).length > 0 && (
                              <div className="space-y-2 p-2.5 rounded-xl border border-border/80 bg-muted/20">
                                <Label className="text-[11px] font-bold text-foreground block">
                                  Độ rộng từng cột đã chọn:
                                </Label>
                                <div className="space-y-2">
                                  {((fieldMapping.custom_columns as string[]) || []).map((colName) => {
                                    const currentW = (layoutOptions.column_widths || {})[colName]
                                    return (
                                      <div
                                        key={colName}
                                        className="p-2 rounded-lg border border-border bg-background space-y-1.5 shadow-2xs"
                                      >
                                        <div className="flex items-center justify-between">
                                          <span className="text-xs font-bold text-foreground truncate max-w-[180px]">
                                            {colName}
                                          </span>
                                          <button
                                            type="button"
                                            onClick={() => {
                                              const currentCols = (fieldMapping.custom_columns as string[]) || []
                                              setFieldMapping((prev) => ({
                                                ...prev,
                                                custom_columns: currentCols.filter((c) => c !== colName),
                                              }))
                                            }}
                                            className="text-muted-foreground hover:text-destructive p-0.5 rounded transition-colors"
                                            title="Xóa cột này"
                                          >
                                            <X className="size-3.5" />
                                          </button>
                                        </div>
                                        <div className="flex items-center gap-1">
                                          {['Auto', '15%', '20%', '25%', '30%', '40%'].map((wOpt) => {
                                            const isAuto = wOpt === 'Auto'
                                            const isSelected = isAuto
                                              ? !currentW
                                              : currentW === wOpt || currentW === parseInt(wOpt, 10)
                                            return (
                                              <button
                                                key={wOpt}
                                                type="button"
                                                onClick={() => {
                                                  setLayoutOptions((prev) => {
                                                    const nextWidths = { ...(prev.column_widths || {}) }
                                                    if (isAuto) {
                                                      delete nextWidths[colName]
                                                    } else {
                                                      nextWidths[colName] = wOpt
                                                    }
                                                    return { ...prev, column_widths: nextWidths }
                                                  })
                                                }}
                                                className={`flex-1 text-[10px] py-0.5 rounded border font-medium transition-colors ${
                                                  isSelected
                                                    ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                                    : 'bg-muted/40 text-muted-foreground hover:bg-muted border-border/70'
                                                }`}
                                              >
                                                {wOpt}
                                              </button>
                                            )
                                          })}
                                        </div>
                                      </div>
                                    )
                                  })}
                                </div>
                              </div>
                            )}

                            {/* Available Fields Picker Checkboxes */}
                            <div className="space-y-1.5">
                              <Label className="text-[11px] font-semibold text-muted-foreground block">
                                Danh sách trường trong Note Type:
                              </Label>
                              <div className="grid grid-cols-2 gap-1.5">
                                {availableFields.map((f) => {
                                  const currentCols = (fieldMapping.custom_columns as string[]) || []
                                  const isChecked = currentCols.includes(f)
                                  return (
                                    <label
                                      key={f}
                                      className={`flex items-center gap-1.5 p-2 rounded-lg border text-xs cursor-pointer transition-all ${
                                        isChecked
                                          ? 'border-primary bg-primary/5 text-foreground font-semibold shadow-2xs'
                                          : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                      }`}
                                    >
                                      <input
                                        type="checkbox"
                                        checked={isChecked}
                                        onChange={(e) => {
                                          if (e.target.checked) {
                                            setFieldMapping((prev) => ({
                                              ...prev,
                                              custom_columns: [...currentCols, f],
                                            }))
                                          } else {
                                            setFieldMapping((prev) => ({
                                              ...prev,
                                              custom_columns: currentCols.filter((c) => c !== f),
                                            }))
                                          }
                                        }}
                                        className="rounded text-primary focus:ring-primary size-3.5"
                                      />
                                      <span className="truncate">{f}</span>
                                    </label>
                                  )
                                })}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            {currentTemplate.field_slots.map((slot) => {
                              const val = (fieldMapping[slot.key] as string) || ''
                              return (
                                <div key={slot.key} className="space-y-1 p-2.5 rounded-xl border border-border/60 bg-muted/10">
                                  <div className="flex items-center justify-between">
                                    <Label className="text-xs font-semibold flex items-center gap-1.5">
                                      <span>{slot.label_vi}</span>
                                      {slot.required ? (
                                        <Badge variant="outline" className="text-[9px] text-rose-500 border-rose-200 bg-rose-50 px-1 py-0 font-bold">
                                          Bắt buộc
                                        </Badge>
                                      ) : (
                                        <Badge variant="outline" className="text-[9px] text-muted-foreground border-border px-1 py-0 font-normal">
                                          Tùy chọn
                                        </Badge>
                                      )}
                                    </Label>
                                    {!slot.required && val && (
                                      <button
                                        type="button"
                                        onClick={() =>
                                          setFieldMapping((prev) => ({
                                            ...prev,
                                            [slot.key]: '',
                                          }))
                                        }
                                        className="text-[10px] font-medium text-muted-foreground hover:text-rose-500 transition-colors"
                                      >
                                        Bỏ qua trường này
                                      </button>
                                    )}
                                  </div>
                                  <NativeSelect
                                    value={val}
                                    onChange={(e) =>
                                      setFieldMapping((prev) => ({
                                        ...prev,
                                        [slot.key]: e.target.value,
                                      }))
                                    }
                                    className={`h-8.5 text-xs ${
                                      !val && !slot.required ? 'text-muted-foreground bg-background/50 border-dashed' : ''
                                    }`}
                                  >
                                    <option value="">
                                      {slot.required ? '-- Chọn trường nguồn (Bắt buộc) --' : '-- Bỏ trống (Không sử dụng trường này) --'}
                                    </option>
                                    {availableFields.map((f) => (
                                      <option key={f} value={f}>
                                        {f}
                                      </option>
                                    ))}
                                  </NativeSelect>
                                  {slot.description_vi && (
                                    <p className="text-[10px] text-muted-foreground leading-tight">
                                      {slot.description_vi}
                                    </p>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* TAB 3: LAYOUT & DENSITY */}
                  {activeTab === 'layout' && currentTemplate && (
                    <div className="space-y-4">
                      {/* Orientation & Page Margins */}
                      <div className="space-y-3 bg-card p-3.5 rounded-xl border border-border/70 shadow-xs">
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                          Khổ giấy & Hướng in A4
                        </h4>

                        {/* Orientation Toggle */}
                        <div className="grid grid-cols-2 gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              setLayoutOptions((prev) => ({ ...prev, orientation: 'portrait' }))
                            }
                            className={`flex flex-col items-center justify-center p-2 rounded-lg border text-xs font-medium transition-all ${
                              layoutOptions.orientation === 'portrait'
                                ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                            }`}
                          >
                            <div className="w-4 h-6 border-2 border-current rounded-xs mb-1" />
                            <span>A4 Dọc (Portrait)</span>
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              setLayoutOptions((prev) => ({ ...prev, orientation: 'landscape' }))
                            }
                            className={`flex flex-col items-center justify-center p-2 rounded-lg border text-xs font-medium transition-all ${
                              layoutOptions.orientation === 'landscape'
                                ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                            }`}
                          >
                            <div className="w-6 h-4 border-2 border-current rounded-xs mb-1.5" />
                            <span>A4 Ngang (Landscape)</span>
                          </button>
                        </div>

                        {/* Auto-fit A4 Mode vs Manual Rows per page */}
                        <div className="space-y-2 pt-1 border-t border-border/50">
                          <div className="flex items-center justify-between">
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.auto_fit_page !== false}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    auto_fit_page: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-4"
                              />
                              <div>
                                <div className="text-xs font-bold text-foreground flex items-center gap-1.5">
                                  <span>⚡ Tự tính số dòng Full trang A4</span>
                                  <Badge variant="outline" className="text-[9px] bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
                                    Tối ưu
                                  </Badge>
                                </div>
                                <p className="text-[10px] text-muted-foreground">
                                  Tự động phủ kín 100% trang A4 theo hướng in & dòng trống
                                </p>
                              </div>
                            </label>
                          </div>

                          {layoutOptions.auto_fit_page === false && (
                            <div className="space-y-1.5 pl-6 pt-1">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Tuỳ chỉnh số dòng mỗi trang:</Label>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="icon"
                                  className="size-8 shrink-0"
                                  onClick={() =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      rows_per_page: Math.max(1, (prev.rows_per_page ?? 7) - 1),
                                    }))
                                  }
                                >
                                  <Minus className="size-3.5" />
                                </Button>
                                <div className="h-8 flex-1 flex items-center justify-center bg-muted/40 rounded-md border border-border text-xs font-bold text-foreground">
                                  {layoutOptions.rows_per_page ?? 7} dòng/trang
                                </div>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="icon"
                                  className="size-8 shrink-0"
                                  onClick={() =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      rows_per_page: Math.min(30, (prev.rows_per_page ?? 7) + 1),
                                    }))
                                  }
                                >
                                  <Plus className="size-3.5" />
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Extra Blank Practice Rows */}
                        <div className="space-y-1.5 pt-2 border-t border-border/50">
                          <div className="flex items-center justify-between">
                            <Label className="text-xs font-bold text-foreground">
                              Dòng trống luyện viết bổ sung:
                            </Label>
                            <span className="text-[10px] text-primary font-semibold">
                              {layoutOptions.extra_blank_rows ? `+${layoutOptions.extra_blank_rows} dòng/mục` : 'Không thêm'}
                            </span>
                          </div>
                          <div className="grid grid-cols-4 gap-1.5">
                            {[
                              { label: '0 dòng', val: 0 },
                              { label: '+1 dòng', val: 1 },
                              { label: '+2 dòng', val: 2 },
                              { label: '+3 dòng', val: 3 },
                            ].map((opt) => (
                              <Button
                                key={opt.val}
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    extra_blank_rows: opt.val,
                                  }))
                                }
                                className={`h-7.5 text-xs ${
                                  (layoutOptions.extra_blank_rows ?? 0) === opt.val
                                    ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                    : 'bg-muted/30 text-muted-foreground hover:bg-muted/60'
                                }`}
                              >
                                {opt.label}
                              </Button>
                            ))}
                          </div>
                          <p className="text-[10px] text-muted-foreground">
                            Thêm dải ô trống hoàn chỉnh bên dưới mỗi chữ để viết thêm nhiều lần.
                          </p>
                        </div>

                        {/* Fill Blank Rows at end of sheet */}
                        <div className="pt-2 border-t border-border/50">
                          <label className="flex items-center gap-2 cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={layoutOptions.fill_blank_rows !== false}
                              onChange={(e) =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  fill_blank_rows: e.target.checked,
                                }))
                              }
                              className="rounded text-primary size-4"
                            />
                            <div>
                              <div className="text-xs font-semibold text-foreground">
                                Điền đầy trang cuối bằng dòng trống
                              </div>
                              <p className="text-[10px] text-muted-foreground">
                                Tận dụng 100% diện tích giấy in, không để trống chân trang khi photo
                              </p>
                            </div>
                          </label>
                        </div>

                        {/* Margins */}
                        <div className="space-y-1.5 pt-2 border-t border-border/50">
                          <div className="flex items-center justify-between">
                            <Label className="text-xs font-semibold">Căn lề trang (Margins):</Label>
                            <Badge variant="secondary" className="text-[10px] font-bold text-primary">
                              {layoutOptions.margin === 'minimal' || layoutOptions.margin === 'ultra_compact'
                                ? '4mm (Siêu tiết kiệm)'
                                : layoutOptions.margin === 'compact'
                                ? '6mm (Thu gọn)'
                                : layoutOptions.margin === 'wide'
                                ? '14mm (Rộng)'
                                : '10mm (Chuẩn)'}
                            </Badge>
                          </div>
                          <NativeSelect
                            value={layoutOptions.margin || 'compact'}
                            onChange={(e) =>
                              setLayoutOptions((prev) => ({
                                ...prev,
                                margin: e.target.value as any,
                              }))
                            }
                            className="h-8.5 text-xs font-medium"
                          >
                            <option value="minimal">Siêu nhỏ (4mm - Tiết kiệm giấy tối đa, khai thác 98% A4)</option>
                            <option value="compact">Thu gọn (6mm - Gọn gàng, tiết kiệm giấy)</option>
                            <option value="standard">Tiêu chuẩn (10mm - Cân đối, phổ thông)</option>
                            <option value="wide">Rộng (14mm - Đóng gáy hồ sơ / kẹp tài liệu)</option>
                          </NativeSelect>
                        </div>
                      </div>

                      {/* Kanji Grid & Practice Box Options */}
                      {currentTemplate.category === 'kanji' && (
                        <div className="space-y-3 bg-muted/30 p-3.5 rounded-xl border border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Ô chữ & Nét bút Kanji
                          </h4>

                          {/* Box Size Control */}
                          <div className="space-y-1.5 pt-1">
                            <div className="flex items-center justify-between">
                              <Label className="text-xs font-semibold">Kích thước ô viết:</Label>
                              <span className="text-[10px] text-primary font-bold">
                                {layoutOptions.box_size ?? (currentTemplate.id === 'kanji_compact' ? 30 : 36)}px
                              </span>
                            </div>
                            <div className="grid grid-cols-4 gap-1">
                              {[
                                { label: '18px', val: 18 },
                                { label: '28px', val: 28 },
                                { label: '36px', val: 36 },
                                { label: '44px', val: 44 },
                              ].map((preset) => (
                                <Button
                                  key={preset.val}
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      box_size: preset.val,
                                    }))
                                  }
                                  className={`h-7 text-xs ${
                                    (layoutOptions.box_size ?? (currentTemplate.id === 'kanji_compact' ? 30 : 36)) === preset.val
                                      ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                      : 'bg-background hover:bg-muted text-muted-foreground'
                                  }`}
                                >
                                  {preset.label}
                                </Button>
                              ))}
                            </div>
                            <div className="flex items-center gap-1.5 pt-1">
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-7.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    box_size: Math.max(10, (prev.box_size ?? 36) - 2),
                                  }))
                                }
                              >
                                <Minus className="size-3" />
                              </Button>
                              <div className="flex-1 flex items-center gap-1">
                                <Input
                                  type="number"
                                  min={10}
                                  max={120}
                                  value={layoutOptions.box_size ?? (currentTemplate.id === 'kanji_compact' ? 30 : 36)}
                                  onChange={(e) => {
                                    const val = parseInt(e.target.value, 10)
                                    if (!isNaN(val)) {
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_size: Math.max(10, Math.min(120, val)),
                                      }))
                                    }
                                  }}
                                  className="h-7.5 text-xs text-center font-bold"
                                />
                                <span className="text-xs font-semibold text-muted-foreground">px</span>
                              </div>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-7.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    box_size: Math.min(120, (prev.box_size ?? 36) + 2),
                                  }))
                                }
                              >
                                <Plus className="size-3" />
                              </Button>
                            </div>
                            <p className="text-[10px] text-muted-foreground">
                              Tự do tuỳ chỉnh từ 10px trở lên. Ô càng nhỏ thì càng chứa được nhiều ô/dòng và nhiều dòng/trang.
                            </p>
                          </div>

                          {/* Grid Style Selection */}
                          <div className="space-y-1">
                            <Label className="text-xs font-semibold">Kiểu đường kẻ ô:</Label>
                            <NativeSelect
                              value={layoutOptions.grid_style || 'cross'}
                              onChange={(e) =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  grid_style: e.target.value as any,
                                }))
                              }
                              className="h-8.5 text-xs"
                            >
                              <option value="cross">Ô chữ thập (+ / 田)</option>
                              <option value="diagonal">Ô hoa thị (米字格)</option>
                              <option value="square">Ô vuông trơn (□)</option>
                            </NativeSelect>
                          </div>

                          {/* Trace Count Stepper */}
                          <div className="space-y-1">
                            <Label className="text-xs font-semibold">Số ô đồ chữ (mờ):</Label>
                            <div className="flex items-center gap-1.5">
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-8.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    trace_count: Math.max(0, (prev.trace_count ?? 2) - 1),
                                  }))
                                }
                              >
                                <Minus className="size-3.5" />
                              </Button>
                              <div className="flex-1 flex items-center gap-1">
                                <Input
                                  type="number"
                                  min={0}
                                  max={30}
                                  value={layoutOptions.trace_count ?? 2}
                                  onChange={(e) => {
                                    const val = parseInt(e.target.value, 10)
                                    if (!isNaN(val)) {
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        trace_count: Math.max(0, Math.min(30, val)),
                                      }))
                                    }
                                  }}
                                  className="h-8.5 text-xs text-center font-bold"
                                />
                                <span className="text-xs font-semibold text-muted-foreground">ô</span>
                              </div>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-8.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    trace_count: Math.min(30, (prev.trace_count ?? 2) + 1),
                                  }))
                                }
                              >
                                <Plus className="size-3.5" />
                              </Button>
                            </div>
                          </div>

                          {/* Practice Count Stepper */}
                          <div className="space-y-1">
                            <Label className="text-xs font-semibold">Số ô tự viết (trống):</Label>
                            <div className="flex items-center gap-1.5">
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-8.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    practice_count: Math.max(1, (prev.practice_count ?? 6) - 1),
                                  }))
                                }
                              >
                                <Minus className="size-3.5" />
                              </Button>
                              <div className="flex-1 flex items-center gap-1">
                                <Input
                                  type="number"
                                  min={1}
                                  max={100}
                                  value={layoutOptions.practice_count ?? 6}
                                  onChange={(e) => {
                                    const val = parseInt(e.target.value, 10)
                                    if (!isNaN(val)) {
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        practice_count: Math.max(1, Math.min(100, val)),
                                      }))
                                    }
                                  }}
                                  className="h-8.5 text-xs text-center font-bold"
                                />
                                <span className="text-xs font-semibold text-muted-foreground">ô</span>
                              </div>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-8.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    practice_count: Math.min(100, (prev.practice_count ?? 6) + 1),
                                  }))
                                }
                              >
                                <Plus className="size-3.5" />
                              </Button>
                            </div>
                          </div>

                          {/* Toggles */}
                          <div className="space-y-1.5 pt-1 text-xs">
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.show_stroke_diagram !== false}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    show_stroke_diagram: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-3.5"
                              />
                              <span>Hiện sơ đồ nét bút SVG</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.show_reading !== false}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    show_reading: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-3.5"
                              />
                              <span>Hiện Âm đọc</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.show_meaning !== false}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    show_meaning: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-3.5"
                              />
                              <span>Hiện Ý nghĩa</span>
                            </label>
                          </div>
                        </div>
                      )}

                      {/* TABLE SPECIFIC OPTIONS (Generic Deck Table) */}
                      {currentTemplate.id === 'deck_table' && (
                        <div className="space-y-3 pt-3 border-t border-border/60">
                          <div className="flex items-center justify-between">
                            <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                              Cột phụ bổ sung (Luyện viết / Đánh giá)
                            </h4>
                            <Badge variant="outline" className="text-[10px] text-primary bg-primary/5">
                              Tuỳ biến
                            </Badge>
                          </div>

                          {/* Toggle auxiliary column */}
                          <div className="space-y-1.5">
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={
                                  layoutOptions.auxiliary_column_enabled !== undefined
                                    ? layoutOptions.auxiliary_column_enabled
                                    : layoutOptions.include_practice_column !== false
                                }
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    auxiliary_column_enabled: e.target.checked,
                                    include_practice_column: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-4"
                              />
                              <span className="text-xs font-bold text-foreground">
                                Bật cột phụ bổ sung ở cuối bảng
                              </span>
                            </label>
                            <p className="text-[10px] text-muted-foreground pl-6">
                              Thêm 1 cột để học sinh luyện viết, dịch nghĩa hoặc tự đánh giá bài làm.
                            </p>
                          </div>

                          {(layoutOptions.auxiliary_column_enabled !== undefined
                            ? layoutOptions.auxiliary_column_enabled
                            : layoutOptions.include_practice_column !== false) && (
                            <div className="space-y-3 p-3 rounded-xl border border-border/80 bg-muted/20">
                              {/* Auxiliary Column Title */}
                              <div className="space-y-1">
                                <Label className="text-xs font-semibold">Tên / Tiêu đề cột phụ:</Label>
                                <Input
                                  value={
                                    layoutOptions.auxiliary_column_title ??
                                    layoutOptions.practice_column_label ??
                                    'Ghi chú / Luyện viết'
                                  }
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      auxiliary_column_title: e.target.value,
                                      practice_column_label: e.target.value,
                                    }))
                                  }
                                  className="h-8 text-xs font-medium"
                                  placeholder="Ví dụ: Ghi chú, Luyện viết, Tự dịch, Đánh giá..."
                                />
                              </div>

                              {/* Auxiliary Column Types (5 basic types) */}
                              <div className="space-y-1.5">
                                <Label className="text-xs font-semibold">Kiểu hiển thị cột phụ:</Label>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                                  {[
                                    {
                                      id: 'dashed_line',
                                      label: '✍️ Dòng kẻ đứt',
                                      desc: 'Dòng kẻ ngang nét đứt để ghi chú / viết tự do',
                                    },
                                    {
                                      id: 'grid_boxes',
                                      label: '🔲 Ô kẻ ô chữ',
                                      desc: 'Dải ô vuông Genkō yōshi để tập viết chữ Hán',
                                    },
                                    {
                                      id: 'checkboxes',
                                      label: '☑️ Đánh dấu kiểm tra',
                                      desc: '3 ô tích [ ] 1  [ ] 2  [ ] 3 theo dõi tiến độ',
                                    },
                                    {
                                      id: 'double_line',
                                      label: '═ Dòng kẻ đôi',
                                      desc: '2 dòng kẻ song song để viết câu hoàn chỉnh',
                                    },
                                    {
                                      id: 'blank',
                                      label: '📄 Khung trắng',
                                      desc: 'Khoảng trống sạch sẽ không đường kẻ',
                                    },
                                  ].map((tOpt) => {
                                    const currentType = layoutOptions.auxiliary_column_type || 'dashed_line'
                                    const isSelected = currentType === tOpt.id
                                    return (
                                      <button
                                        key={tOpt.id}
                                        type="button"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            auxiliary_column_type: tOpt.id as any,
                                          }))
                                        }
                                        className={`flex flex-col text-left p-2 rounded-lg border transition-all ${
                                          isSelected
                                            ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                            : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                        }`}
                                      >
                                        <span className="text-xs">{tOpt.label}</span>
                                        <span className="text-[10px] text-muted-foreground font-normal line-clamp-1">
                                          {tOpt.desc}
                                        </span>
                                      </button>
                                    )
                                  })}
                                </div>
                              </div>

                              {/* If Grid Boxes selected: Stepper to choose number of boxes */}
                              {layoutOptions.auxiliary_column_type === 'grid_boxes' && (
                                <div className="space-y-1 pt-1">
                                  <div className="flex items-center justify-between">
                                    <Label className="text-xs font-semibold">Số ô vuông kẻ ô mỗi dòng:</Label>
                                    <span className="text-xs font-bold text-primary">
                                      {layoutOptions.auxiliary_column_boxes_count ?? 4} ô
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-1.5">
                                    {[2, 3, 4, 5, 6].map((num) => (
                                      <Button
                                        key={num}
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            auxiliary_column_boxes_count: num,
                                          }))
                                        }
                                        className={`flex-1 h-7.5 text-xs ${
                                          (layoutOptions.auxiliary_column_boxes_count ?? 4) === num
                                            ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                            : 'bg-background hover:bg-muted text-muted-foreground'
                                        }`}
                                      >
                                        {num} ô
                                      </Button>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Auxiliary Column Width */}
                              <div className="space-y-1.5 pt-1">
                                <div className="flex items-center justify-between">
                                  <Label className="text-xs font-semibold">Độ rộng cột phụ:</Label>
                                  <span className="text-xs font-bold text-primary">
                                    {layoutOptions.auxiliary_column_width || (isLandscape ? '25%' : '30%')}
                                  </span>
                                </div>
                                <div className="grid grid-cols-6 gap-1">
                                  {['15%', '20%', '25%', '30%', '35%', '40%'].map((wOpt) => {
                                    const defaultW = isLandscape ? '25%' : '30%'
                                    const currentW = layoutOptions.auxiliary_column_width || defaultW
                                    const isSelected = currentW === wOpt
                                    return (
                                      <button
                                        key={wOpt}
                                        type="button"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            auxiliary_column_width: wOpt,
                                          }))
                                        }
                                        className={`h-7 text-[11px] rounded border font-medium transition-colors ${
                                          isSelected
                                            ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                            : 'bg-background text-muted-foreground hover:bg-muted border-border'
                                        }`}
                                      >
                                        {wOpt}
                                      </button>
                                    )
                                  })}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* SENTENCE WRITING OPTIONS */}
                      {currentTemplate.id === 'sentence_writing' && (
                        <div className="space-y-3 pt-3 border-t border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Mẫu câu & Dòng kẻ viết tay
                          </h4>
                          <div className="space-y-2.5 bg-muted/20 p-3 rounded-xl border border-border/80">
                            {/* Exercise prompt for sentence writing */}
                            <div className="space-y-1">
                              <Label className="text-xs font-semibold">Đề bài / Yêu cầu của bài tập (Đầu trang):</Label>
                              <Input
                                value={
                                  layoutOptions.exercise_prompt ??
                                  'Dịch các câu sau sang tiếng Việt hoặc phát triển thành đoạn văn:'
                                }
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    exercise_prompt: e.target.value,
                                  }))
                                }
                                className="h-8 text-xs font-medium"
                                placeholder="Ví dụ: Dịch câu sang tiếng Việt, Viết phát triển thành đoạn văn..."
                              />
                            </div>

                            {/* Number of writing lines */}
                            <div className="space-y-1 pt-1">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Số dòng kẻ viết tay mỗi câu:</Label>
                                <span className="text-xs font-bold text-primary">
                                  {layoutOptions.writing_lines_count ?? 3} dòng
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                {[1, 2, 3, 4, 5, 6, 8].map((n) => (
                                  <Button
                                    key={n}
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_lines_count: n,
                                      }))
                                    }
                                    className={`flex-1 h-7.5 text-xs ${
                                      (layoutOptions.writing_lines_count ?? 3) === n
                                        ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                    }`}
                                  >
                                    {n}
                                  </Button>
                                ))}
                              </div>
                              <p className="text-[10px] text-muted-foreground">
                                Tăng số dòng nếu yêu cầu học sinh viết cả đoạn văn hoặc dịch câu dài.
                              </p>
                            </div>

                            {/* Writing line style */}
                            <div className="space-y-1 pt-1">
                              <Label className="text-xs font-semibold">Kiểu đường kẻ:</Label>
                              <div className="grid grid-cols-2 gap-1.5">
                                {[
                                  { id: 'dashed', label: '--- Nét đứt (Dashed)' },
                                  { id: 'solid', label: '─── Nét liền (Solid)' },
                                ].map((st) => (
                                  <button
                                    key={st.id}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_line_style: st.id as any,
                                      }))
                                    }
                                    className={`py-1.5 px-2 rounded-lg border text-xs font-medium transition-all ${
                                      (layoutOptions.writing_line_style || 'dashed') === st.id
                                        ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                        : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    {st.label}
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Toggles for sentence parts */}
                            <div className="space-y-1.5 pt-1 text-xs">
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_sample_sentence !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_sample_sentence: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện câu mẫu</span>
                              </label>
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_sample_reading !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_sample_reading: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện cách đọc / Furigana</span>
                              </label>
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_sample_meaning !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_sample_meaning: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện ý nghĩa (Tắt để bắt học sinh tự dịch)</span>
                              </label>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* GRAMMAR PRACTICE OPTIONS */}
                      {currentTemplate.id === 'grammar_practice' && (
                        <div className="space-y-3 pt-3 border-t border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Bài tập Ngữ pháp & Đề bài
                          </h4>
                          <div className="space-y-2.5 bg-muted/20 p-3 rounded-xl border border-border/80">
                            {/* Exercise prompt */}
                            <div className="space-y-1">
                              <Label className="text-xs font-semibold">Đề bài / Yêu cầu của giáo viên:</Label>
                              <Input
                                value={
                                  layoutOptions.exercise_prompt ??
                                  'Hãy đặt câu hoàn chỉnh sử dụng cấu trúc / từ vựng trên:'
                                }
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    exercise_prompt: e.target.value,
                                  }))
                                }
                                className="h-8 text-xs font-medium"
                                placeholder="Ví dụ: Đặt 2 câu với cấu trúc trên, Dịch sang tiếng Nhật..."
                              />
                            </div>

                            {/* Number of writing lines */}
                            <div className="space-y-1 pt-1">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Số dòng kẻ viết bài mỗi mục:</Label>
                                <span className="text-xs font-bold text-primary">
                                  {layoutOptions.writing_lines_count ?? 3} dòng
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                {[1, 2, 3, 4, 5, 6, 8].map((n) => (
                                  <Button
                                    key={n}
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_lines_count: n,
                                      }))
                                    }
                                    className={`flex-1 h-7.5 text-xs ${
                                      (layoutOptions.writing_lines_count ?? 3) === n
                                        ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                    }`}
                                  >
                                    {n}
                                  </Button>
                                ))}
                              </div>
                            </div>

                            {/* Writing line style */}
                            <div className="space-y-1 pt-1">
                              <Label className="text-xs font-semibold">Kiểu đường kẻ:</Label>
                              <div className="grid grid-cols-2 gap-1.5">
                                {[
                                  { id: 'dashed', label: '--- Nét đứt (Dashed)' },
                                  { id: 'solid', label: '─── Nét liền (Solid)' },
                                ].map((st) => (
                                  <button
                                    key={st.id}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_line_style: st.id as any,
                                      }))
                                    }
                                    className={`py-1.5 px-2 rounded-lg border text-xs font-medium transition-all ${
                                      (layoutOptions.writing_line_style || 'dashed') === st.id
                                        ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                        : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    {st.label}
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Toggles for explanation & example */}
                            <div className="space-y-1.5 pt-1 text-xs">
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_explanation !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_explanation: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện giải thích cách dùng / ý nghĩa</span>
                              </label>
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_example_hint !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_example_hint: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện câu ví dụ mẫu gợi ý</span>
                              </label>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 4: HEADER & METADATA */}
                  {activeTab === 'header' && (
                    <div className="space-y-4 bg-card p-3.5 rounded-xl border border-border/70 shadow-xs">
                      <div className="space-y-3">
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                          Tiêu đề & Đầu trang
                        </h4>

                        <div className="space-y-2.5">
                          <div className="space-y-1">
                            <Label className="text-xs font-semibold">Tiêu đề bài tập</Label>
                            <Input
                              value={layoutOptions.header_title || ''}
                              onChange={(e) =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  header_title: e.target.value,
                                }))
                              }
                              className="h-8.5 text-xs"
                              placeholder="Ví dụ: JLPT N5 - Luyện viết chữ Hán"
                            />
                          </div>

                          <div className="space-y-1">
                            <Label className="text-xs font-semibold">Phụ đề / Hướng dẫn nhỏ</Label>
                            <Input
                              value={layoutOptions.header_subtitle || ''}
                              onChange={(e) =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  header_subtitle: e.target.value,
                                }))
                              }
                              className="h-8.5 text-xs"
                              placeholder="Luyện viết từ vựng và chữ Hán mỗi ngày"
                            />
                          </div>

                          <div className="space-y-1">
                            <div className="flex items-center justify-between">
                              <Label className="text-xs font-semibold">Đề bài / Yêu cầu bài tập (In ở đầu trang)</Label>
                              {layoutOptions.exercise_prompt && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      exercise_prompt: '',
                                    }))
                                  }
                                  className="text-[10px] text-muted-foreground hover:text-rose-500 transition-colors"
                                >
                                  Xoá yêu cầu
                                </button>
                              )}
                            </div>
                            <Input
                              value={layoutOptions.exercise_prompt || ''}
                              onChange={(e) =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  exercise_prompt: e.target.value,
                                }))
                              }
                              className="h-8.5 text-xs font-medium"
                              placeholder="Ví dụ: Hãy đặt 2 câu hoàn chỉnh với mỗi cấu trúc, Dịch các câu sau sang tiếng Việt..."
                            />
                            <p className="text-[10px] text-muted-foreground">
                              Đề bài sẽ được in nổi bật trong khung ở đầu trang để học sinh nắm rõ yêu cầu làm bài.
                            </p>
                          </div>

                          <div className="space-y-1.5 pt-1 text-xs">
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.show_student_info !== false}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    show_student_info: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-3.5"
                              />
                              <span>Hiện dòng Họ tên</span>
                            </label>

                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.show_date !== false}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    show_date: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-3.5"
                              />
                              <span>Hiện dòng Ngày tháng</span>
                            </label>
                          </div>
                        </div>
                      </div>

                      {/* WATERMARK ANTI-COPY SECTION (MANDATORY) */}
                      <div className="space-y-3 pt-3 border-t border-border/60">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                              Hình mờ chống sao chép (Watermark)
                            </h4>
                            <Badge variant="outline" className="text-[9.5px] text-amber-600 dark:text-amber-400 bg-amber-500/10 border-amber-500/20">
                              Bảo vệ bản quyền
                            </Badge>
                          </div>
                        </div>

                        <div className="space-y-2.5 bg-muted/20 p-3 rounded-xl border border-border/80">
                          <p className="text-[11px] text-muted-foreground leading-relaxed">
                            Mặc định in lớp hoa văn chéo thanh mảnh phủ nổi trên trang A4 với độ mờ tinh tế, giúp bảo vệ tài liệu chống sao chép/xoá watermark tuyệt đối mà học sinh đọc chữ và viết bài vẫn rõ nét 100%.
                          </p>

                          <div className="space-y-2 pt-1 border-t border-border/50">
                            <div className="space-y-1">
                              <Label className="text-xs font-semibold">Nội dung chữ Watermark (DNS / Tên miền):</Label>
                              <Input
                                value={
                                  layoutOptions.watermark_text ??
                                  (typeof window !== 'undefined' ? window.location.hostname : 'flama.app') ??
                                  'flama.app'
                                }
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    watermark_text: e.target.value,
                                  }))
                                }
                                className="h-8 text-xs font-medium uppercase"
                                placeholder="Ví dụ: flama.app, tiengnhatonline.com..."
                              />
                            </div>

                            <div className="space-y-1 pt-1">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Độ mờ / đậm của Watermark:</Label>
                                <span className="text-xs font-bold text-primary">
                                  {((layoutOptions.watermark_opacity ?? 0.04) * 100).toFixed(1).replace('.0', '')}%
                                </span>
                              </div>
                              <div className="grid grid-cols-4 gap-1.5">
                                {[
                                  { val: 0.02, label: '2% (Rất nhẹ)' },
                                  { val: 0.035, label: '3.5% (Chuẩn)' },
                                  { val: 0.05, label: '5% (Vừa)' },
                                  { val: 0.07, label: '7% (Đậm)' },
                                ].map((op) => {
                                  const currentOp = layoutOptions.watermark_opacity ?? 0.04
                                  const isSelected = Math.abs(currentOp - op.val) < 0.008
                                  return (
                                    <button
                                      key={op.val}
                                      type="button"
                                      onClick={() =>
                                        setLayoutOptions((prev) => ({
                                          ...prev,
                                          watermark_opacity: op.val,
                                        }))
                                      }
                                      className={`py-1 px-1.5 rounded-lg border text-[10px] font-medium transition-all ${
                                        isSelected
                                          ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                          : 'bg-background text-muted-foreground hover:bg-muted/50 border-border'
                                      }`}
                                    >
                                      {op.label}
                                    </button>
                                  )
                                })}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Sidebar Footer Stats & Quick Tab Jump */}
            <div className="p-3 border-t border-border/80 bg-muted/30 flex items-center justify-between text-xs text-muted-foreground shrink-0">
              <span className="truncate">
                {currentTemplate?.name_vi || 'Mẫu'} &bull; {layoutOptions.rows_per_page || 5} dòng/trang
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 text-xs font-semibold text-primary px-2"
                onClick={() => {
                  const tabIdx = STUDIO_TABS.findIndex((t) => t.id === activeTab)
                  const nextTab = STUDIO_TABS[(tabIdx + 1) % STUDIO_TABS.length]
                  setActiveTab(nextTab.id)
                }}
              >
                Tiếp tục &rarr;
              </Button>
            </div>
          </aside>

          {/* Right Area: Live Workbench Preview Canvas (flex-1) */}
          <main
            className={`flex-1 flex flex-col bg-slate-200/90 dark:bg-slate-950 min-h-0 relative ${
              mobileView === 'preview' ? 'flex' : 'hidden md:flex'
            }`}
          >
            {/* Workbench Top Bar (Page Navigation & Live Stats) */}
            <div className="px-4 py-2 bg-background/80 backdrop-blur-xs border-b border-border/70 flex items-center justify-between gap-3 shrink-0 z-10">
              {/* Page Navigator */}
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentPageIdx === 0 || !previewData}
                  onClick={() => setCurrentPageIdx((p) => Math.max(0, p - 1))}
                  className="h-7.5 px-2 text-xs font-semibold gap-1"
                >
                  <ChevronLeft className="size-3.5" />
                  <span className="hidden sm:inline">Trang trước</span>
                </Button>

                {/* Page Selector */}
                <div className="flex items-center gap-1 px-2 text-xs font-bold text-foreground">
                  <span>Trang</span>
                  {previewData && previewData.total_pages > 1 ? (
                    <NativeSelect
                      value={currentPageIdx}
                      onChange={(e) => setCurrentPageIdx(Number(e.target.value))}
                      className="h-7 text-xs py-0 px-2 font-bold w-16"
                    >
                      {Array.from({ length: previewData.total_pages }).map((_, idx) => (
                        <option key={idx} value={idx}>
                          {idx + 1}
                        </option>
                      ))}
                    </NativeSelect>
                  ) : (
                    <span>1</span>
                  )}
                  <span>/ {previewData?.total_pages || 1}</span>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  disabled={!previewData || currentPageIdx >= previewData.total_pages - 1}
                  onClick={() =>
                    setCurrentPageIdx((p) =>
                      Math.min((previewData?.total_pages || 1) - 1, p + 1)
                    )
                  }
                  className="h-7.5 px-2 text-xs font-semibold gap-1"
                >
                  <span className="hidden sm:inline">Trang sau</span>
                  <ChevronRight className="size-3.5" />
                </Button>
              </div>

              {/* Total Stats Badge */}
              <div className="flex items-center gap-2">
                {previewData && (
                  <Badge variant="secondary" className="text-xs font-semibold px-2.5 py-0.5">
                    Tổng: {previewData.total_items} mục &bull; {previewData.total_pages} trang A4
                  </Badge>
                )}
              </div>
            </div>

            {/* Canvas Scrollable Viewport */}
            <div className="flex-1 overflow-auto p-6 flex justify-center items-start min-h-0 select-none relative">
              {isLoadingMeta ? (
                <div className="m-auto flex flex-col items-center justify-center gap-3 text-muted-foreground">
                  <Loader2 className="size-8 animate-spin text-primary" />
                  <span className="text-xs font-medium">Đang tải tài liệu...</span>
                </div>
              ) : previewData && previewData.pages.length > 0 && previewData.pages[currentPageIdx] && currentTemplate ? (
                <div
                  style={{
                    width: `${containerWidthPx}px`,
                    height: `${containerHeightPx}px`,
                  }}
                  className="relative shrink-0 transition-all duration-150"
                >
                  <div
                    style={{
                      transform: `scale(${zoomLevel})`,
                      transformOrigin: 'top left',
                      width: `${a4WidthMm}mm`,
                      height: `${a4HeightMm}mm`,
                    }}
                    className="absolute top-0 left-0"
                  >
                    <WorksheetPageRenderer
                      page={previewData.pages[currentPageIdx]}
                      template={currentTemplate}
                      options={layoutOptions}
                      fieldMapping={fieldMapping}
                      zoom={1}
                    />
                  </div>
                </div>
              ) : (
                <div className="m-auto py-16 text-center text-muted-foreground text-xs space-y-2">
                  <FileText className="size-10 mx-auto text-muted-foreground/40" />
                  <p>Không có dữ liệu trang xem trước. Vui lòng kiểm tra lại ánh xạ trường dữ liệu.</p>
                </div>
              )}
            </div>
          </main>
        </div>
      </DialogContent>
    </Dialog>
  )
}


