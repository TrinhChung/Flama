import { useEffect, useMemo, useState } from 'react'
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
  Download,
  Eye,
  FileText,
  HelpCircle,
  Layers,
  LayoutGrid,
  Loader2,
  Minus,
  PenTool,
  Plus,
  Printer,
  Sliders,
  Table as TableIcon,
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
import { downloadWorksheetHtml, printWorksheetHtml } from '../utils/printEngine'
import { WorksheetPageRenderer } from './WorksheetPageRenderer'

export interface DeckWorksheetModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  deckId: number
  deckName?: string
  initialCardIds?: (string | number)[]
}

type WizardStep = 'template' | 'fields' | 'layout' | 'preview'

const STEPS_CONFIG: { id: WizardStep; label: string; short: string; icon: any }[] = [
  { id: 'template', label: '1. Chọn mẫu bài tập', short: '1. Mẫu', icon: LayoutGrid },
  { id: 'fields', label: '2. Dữ liệu & Ánh xạ', short: '2. Dữ liệu', icon: Database },
  { id: 'layout', label: '3. Bố cục & Trang in', short: '3. Bố cục', icon: Sliders },
  { id: 'preview', label: '4. Xem trước & In', short: '4. In ấn', icon: Printer },
]

export function DeckWorksheetModal({
  open,
  onOpenChange,
  deckId,
  deckName,
  initialCardIds,
}: DeckWorksheetModalProps) {
  const [step, setStep] = useState<WizardStep>('template')
  const [visitedSteps, setVisitedSteps] = useState<Set<WizardStep>>(new Set(['template']))
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
    show_stroke_diagram: true,
    show_reading: true,
    show_meaning: true,
    show_student_info: true,
    show_date: true,
    header_title: '',
    header_subtitle: 'Luyện viết từ vựng và chữ Hán mỗi ngày',
    locale: 'ja',
  })

  // Preview state
  const [previewData, setPreviewData] = useState<WorksheetPreviewResponse | null>(null)
  const [currentPageIdx, setCurrentPageIdx] = useState<number>(0)
  const [zoomLevel, setZoomLevel] = useState<number>(0.85)

  const goToStep = (newStep: WizardStep) => {
    setStep(newStep)
    setVisitedSteps((prev) => new Set([...prev, newStep]))
  }

  // Load deck worksheet meta on open
  useEffect(() => {
    if (!open || !deckId) return

    setIsLoadingMeta(true)
    setStep('template')
    setVisitedSteps(new Set(['template']))
    setPreviewData(null)
    setCurrentPageIdx(0)

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

        // Initialize default mappings
        const initMapping: WorksheetFieldMapping = {
          kanji: data.suggested_mappings?.kanji || 'Expression',
          reading: data.suggested_mappings?.reading || '',
          meaning: data.suggested_mappings?.meaning || '',
          word: data.suggested_mappings?.word || 'Expression',
          prompt_reading: data.suggested_mappings?.prompt_reading || '',
          prompt_meaning: data.suggested_mappings?.prompt_meaning || 'Meaning',
          custom_columns: data.note_types[0]?.fields || ['Expression', 'Meaning'],
        }
        setFieldMapping(initMapping)

        // Initialize title
        setLayoutOptions((prev) => ({
          ...prev,
          header_title: `${data.deck_name || deckName || 'Bộ thẻ'} - Bài tập`,
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
        rows_per_page: tpl.default_rows_per_page || 5,
        grid_style: (tpl.default_options?.grid_style as any) || 'cross',
        trace_count: tpl.default_options?.trace_count ?? 2,
        practice_count: tpl.default_options?.practice_count ?? 5,
      }))
    }
  }

  // Generate preview
  const handleGeneratePreview = async () => {
    if (!currentTemplate) return
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
      setCurrentPageIdx(0)
      goToStep('preview')

      // Set responsive initial zoom
      if (layoutOptions.orientation === 'landscape') {
        setZoomLevel(0.72)
      } else {
        setZoomLevel(0.85)
      }

      if (response.warnings && response.warnings.length > 0) {
        response.warnings.forEach((w) => toast.warning(w))
      }
    } catch (err: any) {
      toast.error('Lỗi tạo bài tập: ' + (err.message || err))
    } finally {
      setIsGenerating(false)
    }
  }

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

  // Handle download HTML/PDF file
  const handleDownload = async () => {
    if (!previewData) return
    setIsPrinting(true)
    try {
      const html = await renderWorksheetHtml(previewData)
      downloadWorksheetHtml(html, `worksheet_${currentTemplate?.id || 'export'}.html`)
      toast.success('Đã tải file bài tập in ấn!')
    } catch (err: any) {
      toast.error('Không thể tải file: ' + (err.message || err))
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

  const stepIndex = STEPS_CONFIG.findIndex((s) => s.id === step)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={`flex flex-col p-0 gap-0 overflow-hidden rounded-2xl border-border bg-background shadow-2xl transition-all duration-200 ${
          step === 'preview'
            ? 'sm:max-w-5xl lg:max-w-6xl xl:max-w-7xl h-[92vh] max-h-[94vh]'
            : 'sm:max-w-3xl max-h-[90vh]'
        }`}
      >
        {/* Modal Header */}
        <DialogHeader className="px-6 py-3.5 border-b border-border/80 bg-muted/40 shrink-0">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="size-10 rounded-xl bg-orange-500/15 text-orange-600 dark:text-orange-400 flex items-center justify-center shadow-xs shrink-0">
                <Printer className="size-5" />
              </div>
              <div>
                <DialogTitle className="text-base font-bold text-foreground flex items-center gap-2">
                  <span>Xuất bài tập in ấn / PDF (A4)</span>
                </DialogTitle>
                <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                  {meta?.deck_name || deckName || 'Bộ thẻ'} &bull;{' '}
                  <span className="font-semibold text-foreground">{meta?.total_notes || 0}</span> ghi chú
                </DialogDescription>
              </div>
            </div>

            {/* Stepper indicator - Desktop */}
            <div className="hidden md:flex items-center gap-1.5 text-xs font-semibold">
              {STEPS_CONFIG.map((s, idx) => {
                const isActive = step === s.id
                const isVisited = visitedSteps.has(s.id)
                const isPassed = idx < stepIndex
                const Icon = s.icon

                return (
                  <div key={s.id} className="flex items-center gap-1.5">
                    {idx > 0 && <ChevronRight className="size-3.5 text-muted-foreground/60" />}
                    <button
                      type="button"
                      disabled={!isVisited && !isPassed}
                      onClick={() => isVisited && goToStep(s.id)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-all text-xs font-medium cursor-pointer ${
                        isActive
                          ? 'bg-primary text-primary-foreground shadow-sm font-semibold'
                          : isVisited || isPassed
                          ? 'bg-muted hover:bg-muted/80 text-foreground'
                          : 'bg-muted/40 text-muted-foreground/50 cursor-not-allowed'
                      }`}
                    >
                      {isPassed ? (
                        <Check className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                      ) : (
                        <Icon className="size-3.5" />
                      )}
                      <span>{s.short}</span>
                    </button>
                  </div>
                )
              })}
            </div>

            {/* Stepper indicator - Mobile / Tablet */}
            <div className="flex md:hidden items-center gap-2">
              <Badge variant="secondary" className="text-xs font-semibold px-2.5 py-1">
                Bước {stepIndex + 1}/4: {STEPS_CONFIG[stepIndex]?.short}
              </Badge>
            </div>
          </div>
        </DialogHeader>

        {/* Modal Body */}
        <div
          className={`flex-1 min-h-0 ${
            step === 'preview' ? 'flex flex-col p-0 overflow-hidden' : 'p-6 overflow-y-auto'
          }`}
        >
          {isLoadingMeta ? (
            <div className="h-64 flex flex-col items-center justify-center gap-3 text-muted-foreground">
              <Loader2 className="size-8 animate-spin text-primary" />
              <span className="text-sm font-medium">Đang tải cấu hình bộ thẻ...</span>
            </div>
          ) : (
            <>
              {/* STEP 1: CHOOSE TEMPLATE */}
              {step === 'template' && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-bold text-foreground">
                      Bước 1: Chọn mẫu bài tập phù hợp
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Chọn định dạng bài tập luyện viết hoặc phiếu học tập bạn muốn in.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
                    {meta?.templates.map((tpl) => {
                      const Icon = templateIcons[tpl.id] || FileText
                      const isSelected = selectedTemplateId === tpl.id

                      const categoryBadgeColor =
                        tpl.category === 'kanji'
                          ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                          : tpl.category === 'vocabulary'
                          ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
                          : 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20'

                      return (
                        <div
                          key={tpl.id}
                          onClick={() => handleSelectTemplate(tpl.id)}
                          className={`relative p-4 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between gap-3 text-left ${
                            isSelected
                              ? 'border-primary bg-primary/5 shadow-sm ring-2 ring-primary/20'
                              : 'border-border hover:border-border/80 hover:bg-muted/40 bg-card'
                          }`}
                        >
                          {isSelected && (
                            <div className="absolute top-3 right-3 size-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-xs">
                              <Check className="size-3.5" />
                            </div>
                          )}

                          <div className="flex items-start gap-3">
                            <div
                              className={`size-10 rounded-xl flex items-center justify-center shrink-0 ${
                                isSelected
                                  ? 'bg-primary text-primary-foreground'
                                  : 'bg-muted text-muted-foreground'
                              }`}
                            >
                              <Icon className="size-5" />
                            </div>
                            <div className="space-y-1 flex-1 pr-6">
                              <div className="flex items-center gap-2">
                                <h4 className="text-sm font-bold text-foreground">
                                  {tpl.name_vi}
                                </h4>
                              </div>
                              <Badge
                                variant="outline"
                                className={`text-[10px] uppercase font-semibold px-2 py-0.5 border ${categoryBadgeColor}`}
                              >
                                {tpl.category === 'kanji'
                                  ? 'Chữ Hán'
                                  : tpl.category === 'vocabulary'
                                  ? 'Từ vựng'
                                  : 'Bảng dữ liệu'}
                              </Badge>
                              <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2 mt-1">
                                {tpl.description_vi}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-2.5 border-t border-border/50">
                            <span>
                              Mặc định: <strong>{tpl.default_rows_per_page} mục/trang</strong>
                            </span>
                            <span className="capitalize">
                              Khổ:{' '}
                              <strong>
                                {tpl.default_orientation === 'portrait' ? 'A4 Dọc' : 'A4 Ngang'}
                              </strong>
                            </span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* STEP 2: FIELD MAPPING & DATA SCOPE */}
              {step === 'fields' && currentTemplate && (
                <div className="space-y-5">
                  <div>
                    <h3 className="text-sm font-bold text-foreground">
                      Bước 2: Ánh xạ trường dữ liệu & Phạm vi
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Chỉ định các trường trong ghi chú để điền vào mẫu{' '}
                      <strong className="text-foreground">{currentTemplate.name_vi}</strong>.
                    </p>
                  </div>

                  {/* Note Type Selector if multiple */}
                  {meta && meta.note_types.length > 1 && (
                    <div className="space-y-1.5 bg-muted/30 p-3.5 rounded-xl border border-border/60">
                      <Label className="text-xs font-semibold">Loại ghi chú (Note Type)</Label>
                      <NativeSelect
                        value={selectedNoteTypeId}
                        onChange={(e) => setSelectedNoteTypeId(e.target.value)}
                        className="h-9 text-xs"
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
                  <div className="space-y-3 bg-card p-4 rounded-xl border border-border/70 shadow-xs">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                        Ánh xạ trường ({currentTemplate.name_vi})
                      </h4>
                      <Badge variant="outline" className="text-[10px] text-muted-foreground">
                        {availableFields.length} trường khả dụng
                      </Badge>
                    </div>

                    {currentTemplate.id === 'deck_table' ? (
                      <div className="space-y-3 pt-1">
                        <div className="flex items-center justify-between">
                          <Label className="text-xs font-medium">
                            Chọn các trường hiển thị làm cột bảng:
                          </Label>
                          <div className="flex items-center gap-2">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-6 text-[11px] px-2"
                              onClick={() =>
                                setFieldMapping((prev) => ({
                                  ...prev,
                                  custom_columns: [...availableFields],
                                }))
                              }
                            >
                              Chọn tất cả
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-6 text-[11px] px-2 text-muted-foreground"
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
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                          {availableFields.map((f) => {
                            const currentCols = (fieldMapping.custom_columns as string[]) || []
                            const isChecked = currentCols.includes(f)
                            return (
                              <label
                                key={f}
                                className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                                  isChecked
                                    ? 'border-primary bg-primary/5 text-foreground font-semibold'
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
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
                        {currentTemplate.field_slots.map((slot) => {
                          const val = (fieldMapping[slot.key] as string) || ''
                          return (
                            <div key={slot.key} className="space-y-1">
                              <Label className="text-xs font-semibold flex items-center gap-1">
                                <span>{slot.label_vi}</span>
                                {slot.required && <span className="text-rose-500">*</span>}
                              </Label>
                              {slot.description_vi && (
                                <p className="text-[11px] text-muted-foreground">
                                  {slot.description_vi}
                                </p>
                              )}
                              <NativeSelect
                                value={val}
                                onChange={(e) =>
                                  setFieldMapping((prev) => ({
                                    ...prev,
                                    [slot.key]: e.target.value,
                                  }))
                                }
                                className="h-9 text-xs"
                              >
                                <option value="">-- Chọn trường nguồn --</option>
                                {availableFields.map((f) => (
                                  <option key={f} value={f}>
                                    {f}
                                  </option>
                                ))}
                              </NativeSelect>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {/* Scope & Limit */}
                  <div className="space-y-3 bg-muted/30 p-4 rounded-xl border border-border/60">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-bold text-foreground uppercase tracking-wider">
                        Phạm vi xuất bài tập
                      </Label>
                      <Badge variant="secondary" className="text-[11px] font-semibold">
                        {scope === 'all'
                          ? `Toàn bộ (${meta?.total_notes || 0} ghi chú)`
                          : scope === 'selected'
                          ? `${initialCardIds?.length || 0} thẻ đã chọn`
                          : `${limitCount} ghi chú`}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                      <div className="space-y-1">
                        <Label className="text-xs font-semibold">Chế độ lọc</Label>
                        <NativeSelect
                          value={scope}
                          onChange={(e) => setScope(e.target.value as any)}
                          className="h-9 text-xs"
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
                      </div>

                      {(scope === 'first_n' || scope === 'random_n') && (
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold">Số lượng ghi chú (N):</Label>
                          <div className="flex items-center gap-2">
                            <Input
                              type="number"
                              min={1}
                              max={500}
                              value={limitCount}
                              onChange={(e) => setLimitCount(Math.max(1, Number(e.target.value)))}
                              className="h-9 text-xs w-24"
                            />
                            {/* Preset chips */}
                            <div className="flex items-center gap-1">
                              {[10, 20, 50, 100].map((cnt) => (
                                <Button
                                  key={cnt}
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setLimitCount(cnt)}
                                  className={`h-7 px-2 text-[11px] ${
                                    limitCount === cnt ? 'bg-primary text-primary-foreground font-bold' : ''
                                  }`}
                                >
                                  {cnt}
                                </Button>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* STEP 3: LAYOUT & PRINT OPTIONS */}
              {step === 'layout' && currentTemplate && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-bold text-foreground">
                      Bước 3: Tùy chỉnh Bố cục & Trang in A4
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Cấu hình kiểu ô chữ, số dòng mỗi trang và tiêu đề phiếu bài tập.
                    </p>
                  </div>

                  {/* Card 1: Page & Density Options */}
                  <div className="space-y-3 bg-card p-4 rounded-xl border border-border/70 shadow-xs">
                    <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                      Thiết lập khổ giấy & Hướng in
                    </h4>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                      {/* Orientation Visual Toggle */}
                      <div className="space-y-1.5">
                        <Label className="text-xs font-semibold">Hướng giấy A4</Label>
                        <div className="grid grid-cols-2 gap-1.5">
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
                            <span>A4 Dọc</span>
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
                            <span>A4 Ngang</span>
                          </button>
                        </div>
                      </div>

                      {/* Rows per page stepper */}
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <Label className="text-xs font-semibold">Số mục / trang</Label>
                          <span className="text-[10px] text-muted-foreground">Khuyên dùng 5-10</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            className="size-9 shrink-0"
                            onClick={() =>
                              setLayoutOptions((prev) => ({
                                ...prev,
                                rows_per_page: Math.max(1, (prev.rows_per_page ?? 5) - 1),
                              }))
                            }
                          >
                            <Minus className="size-3.5" />
                          </Button>
                          <div className="h-9 flex-1 flex items-center justify-center bg-muted/40 rounded-md border border-border text-xs font-bold text-foreground">
                            {layoutOptions.rows_per_page ?? 5} dòng
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            className="size-9 shrink-0"
                            onClick={() =>
                              setLayoutOptions((prev) => ({
                                ...prev,
                                rows_per_page: Math.min(25, (prev.rows_per_page ?? 5) + 1),
                              }))
                            }
                          >
                            <Plus className="size-3.5" />
                          </Button>
                        </div>
                      </div>

                      {/* Margins */}
                      <div className="space-y-1.5">
                        <Label className="text-xs font-semibold">Căn lề (Margins)</Label>
                        <NativeSelect
                          value={layoutOptions.margin || 'standard'}
                          onChange={(e) =>
                            setLayoutOptions((prev) => ({
                              ...prev,
                              margin: e.target.value as any,
                            }))
                          }
                          className="h-9 text-xs"
                        >
                          <option value="compact">Thu gọn (10mm - Tiết kiệm giấy)</option>
                          <option value="standard">Tiêu chuẩn (12mm - Cân đối)</option>
                          <option value="wide">Rộng (18mm - Thoáng đẹp)</option>
                        </NativeSelect>
                      </div>
                    </div>
                  </div>

                  {/* Card 2: Grid / Kanji specific options */}
                  {currentTemplate.category === 'kanji' && (
                    <div className="space-y-3 bg-muted/30 p-4 rounded-xl border border-border/60">
                      <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                        Kiểu ô chữ & Thực hành Kanji
                      </h4>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                        {/* Grid Style */}
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold">Kiểu đường kẻ</Label>
                          <NativeSelect
                            value={layoutOptions.grid_style || 'cross'}
                            onChange={(e) =>
                              setLayoutOptions((prev) => ({
                                ...prev,
                                grid_style: e.target.value as any,
                              }))
                            }
                            className="h-9 text-xs"
                          >
                            <option value="cross">Ô chữ thập (+ / 田)</option>
                            <option value="diagonal">Ô hoa thị (米字格)</option>
                            <option value="square">Ô vuông trơn (□)</option>
                          </NativeSelect>
                        </div>

                        {/* Trace Count Stepper */}
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold">Số ô mờ (Đồ chữ)</Label>
                          <div className="flex items-center gap-1.5">
                            <Button
                              type="button"
                              variant="outline"
                              size="icon"
                              className="size-9 shrink-0"
                              onClick={() =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  trace_count: Math.max(0, (prev.trace_count ?? 2) - 1),
                                }))
                              }
                            >
                              <Minus className="size-3.5" />
                            </Button>
                            <div className="h-9 flex-1 flex items-center justify-center bg-background rounded-md border border-border text-xs font-bold text-foreground">
                              {layoutOptions.trace_count ?? 2} ô
                            </div>
                            <Button
                              type="button"
                              variant="outline"
                              size="icon"
                              className="size-9 shrink-0"
                              onClick={() =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  trace_count: Math.min(5, (prev.trace_count ?? 2) + 1),
                                }))
                              }
                            >
                              <Plus className="size-3.5" />
                            </Button>
                          </div>
                        </div>

                        {/* Blank Practice Count Stepper */}
                        <div className="space-y-1.5">
                          <Label className="text-xs font-semibold">Số ô trống (Tự viết)</Label>
                          <div className="flex items-center gap-1.5">
                            <Button
                              type="button"
                              variant="outline"
                              size="icon"
                              className="size-9 shrink-0"
                              onClick={() =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  practice_count: Math.max(1, (prev.practice_count ?? 5) - 1),
                                }))
                              }
                            >
                              <Minus className="size-3.5" />
                            </Button>
                            <div className="h-9 flex-1 flex items-center justify-center bg-background rounded-md border border-border text-xs font-bold text-foreground">
                              {layoutOptions.practice_count ?? 5} ô
                            </div>
                            <Button
                              type="button"
                              variant="outline"
                              size="icon"
                              className="size-9 shrink-0"
                              onClick={() =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  practice_count: Math.min(10, (prev.practice_count ?? 5) + 1),
                                }))
                              }
                            >
                              <Plus className="size-3.5" />
                            </Button>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center flex-wrap gap-4 pt-1 text-xs">
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

                  {/* Card 3: Header & Typography info */}
                  <div className="space-y-3 bg-card p-4 rounded-xl border border-border/70 shadow-xs">
                    <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                      Tiêu đề & Thông tin đầu trang
                    </h4>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                          className="h-9 text-xs"
                          placeholder="Ví dụ: JLPT N5 - Luyện viết chữ Hán"
                        />
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs font-semibold">Phụ đề / Lời dặn</Label>
                        <Input
                          value={layoutOptions.header_subtitle || ''}
                          onChange={(e) =>
                            setLayoutOptions((prev) => ({
                              ...prev,
                              header_subtitle: e.target.value,
                            }))
                          }
                          className="h-9 text-xs"
                          placeholder="Luyện viết từ vựng và chữ Hán mỗi ngày"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-6 pt-1 text-xs">
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
              )}

              {/* STEP 4: INTERACTIVE LIVE PREVIEW & WORKBENCH */}
              {step === 'preview' && previewData && currentTemplate && (
                <div className="flex flex-col h-full overflow-hidden bg-background">
                  {/* Top Workbench Toolbar */}
                  <div className="flex items-center justify-between flex-wrap gap-2 px-4 py-2.5 bg-muted/40 border-b border-border/70 shrink-0">
                    {/* Page pagination navigation */}
                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={currentPageIdx === 0}
                        onClick={() => setCurrentPageIdx((p) => Math.max(0, p - 1))}
                        className="h-8 px-2.5 text-xs font-semibold gap-1"
                      >
                        <ChevronLeft className="size-4" />
                        <span className="hidden sm:inline">Trang trước</span>
                      </Button>

                      {/* Page selector */}
                      <div className="flex items-center gap-1 px-2 text-xs font-bold text-foreground">
                        <span>Trang</span>
                        {previewData.total_pages > 1 ? (
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
                        <span>/ {previewData.total_pages || 1}</span>
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        disabled={currentPageIdx >= previewData.total_pages - 1}
                        onClick={() =>
                          setCurrentPageIdx((p) =>
                            Math.min(previewData.total_pages - 1, p + 1)
                          )
                        }
                        className="h-8 px-2.5 text-xs font-semibold gap-1"
                      >
                        <span className="hidden sm:inline">Trang sau</span>
                        <ChevronRight className="size-4" />
                      </Button>
                    </div>

                    {/* Zoom & Quick presets */}
                    <div className="flex items-center gap-2">
                      <div className="flex items-center bg-background rounded-lg border border-border/80 px-1 py-0.5 shadow-2xs">
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
                      <div className="hidden sm:flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setZoomLevel(isLandscape ? 0.72 : 0.85)}
                          className="h-7 px-2 text-[11px] font-medium"
                          title="Vừa trang"
                        >
                          Vừa trang
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setZoomLevel(1)}
                          className="h-7 px-2 text-[11px] font-medium"
                          title="100% kích thước thật"
                        >
                          100%
                        </Button>
                      </div>

                      <Badge variant="secondary" className="text-xs font-semibold px-2.5 py-1">
                        {previewData.total_items} mục &bull; {previewData.total_pages} trang A4
                      </Badge>
                    </div>
                  </div>

                  {/* Rendered Page Preview Canvas with Precise Bounding Box */}
                  <div className="flex-1 overflow-auto bg-slate-200/90 dark:bg-slate-950 p-6 flex justify-center items-start min-h-0 select-none">
                    {previewData.pages.length > 0 && previewData.pages[currentPageIdx] ? (
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
                      <div className="py-16 text-center text-muted-foreground text-xs">
                        Không có dữ liệu trang xem trước.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer / Navigation Controls */}
        <div className="px-6 py-3.5 border-t border-border/80 bg-muted/30 flex items-center justify-between shrink-0">
          <div>
            {step !== 'template' ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (step === 'preview') goToStep('layout')
                  else if (step === 'layout') goToStep('fields')
                  else if (step === 'fields') goToStep('template')
                }}
                className="h-9 px-3 text-xs font-semibold gap-1.5"
              >
                <ChevronLeft className="size-4" />
                Quay lại
              </Button>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onOpenChange(false)}
                className="h-9 px-3 text-xs text-muted-foreground"
              >
                Hủy bỏ
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2.5">
            {step === 'template' && (
              <Button
                size="sm"
                onClick={() => goToStep('fields')}
                className="h-9 px-4 text-xs font-semibold gap-1.5 shadow-xs"
              >
                <span>Tiếp tục: Dữ liệu</span>
                <ChevronRight className="size-4" />
              </Button>
            )}

            {step === 'fields' && (
              <Button
                size="sm"
                onClick={() => goToStep('layout')}
                className="h-9 px-4 text-xs font-semibold gap-1.5 shadow-xs"
              >
                <span>Tiếp tục: Bố cục</span>
                <ChevronRight className="size-4" />
              </Button>
            )}

            {step === 'layout' && (
              <Button
                size="sm"
                onClick={handleGeneratePreview}
                disabled={isGenerating}
                className="h-9 px-5 text-xs font-bold gap-2 bg-orange-600 hover:bg-orange-700 text-white shadow-md"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    <span>Đang xử lý & phân trang...</span>
                  </>
                ) : (
                  <>
                    <Eye className="size-4" />
                    <span>Xem trước bài tập</span>
                  </>
                )}
              </Button>
            )}

            {step === 'preview' && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDownload}
                  disabled={isPrinting}
                  className="h-9 px-3.5 text-xs gap-1.5 font-medium shadow-2xs"
                >
                  <Download className="size-4" />
                  <span className="hidden sm:inline">Tải file in (HTML)</span>
                  <span className="sm:hidden">Tải file</span>
                </Button>

                <Button
                  size="sm"
                  onClick={handlePrint}
                  disabled={isPrinting}
                  className="h-9 px-5 text-xs font-bold gap-2 bg-primary hover:bg-primary/90 text-primary-foreground shadow-md"
                >
                  {isPrinting ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      <span>Đang chuẩn bị in...</span>
                    </>
                  ) : (
                    <>
                      <Printer className="size-4" />
                      <span>In ngay (Print / PDF)</span>
                    </>
                  )}
                </Button>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

