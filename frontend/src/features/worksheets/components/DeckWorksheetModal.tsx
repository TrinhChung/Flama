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
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  HelpCircle,
  Layers,
  Loader2,
  PenTool,
  Printer,
  Sparkles,
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

export function DeckWorksheetModal({
  open,
  onOpenChange,
  deckId,
  deckName,
  initialCardIds,
}: DeckWorksheetModalProps) {
  const [step, setStep] = useState<WizardStep>('template')
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

  // Load deck worksheet meta on open
  useEffect(() => {
    if (!open || !deckId) return

    setIsLoadingMeta(true)
    setStep('template')
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
          kanji: data.suggested_mappings.kanji || 'Expression',
          reading: data.suggested_mappings.reading || '',
          meaning: data.suggested_mappings.meaning || '',
          word: data.suggested_mappings.word || 'Expression',
          prompt_reading: data.suggested_mappings.prompt_reading || '',
          prompt_meaning: data.suggested_mappings.prompt_meaning || 'Meaning',
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
        grid_style: (tpl.default_options.grid_style as any) || 'cross',
        trace_count: tpl.default_options.trace_count ?? 2,
        practice_count: tpl.default_options.practice_count ?? 5,
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
      setStep('preview')

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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[92vh] flex flex-col p-0 gap-0 overflow-hidden rounded-2xl border-border bg-background shadow-2xl">
        {/* Modal Header */}
        <DialogHeader className="px-6 py-4 border-b border-border/80 bg-muted/30 shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="size-9 rounded-xl bg-orange-500/10 text-orange-600 flex items-center justify-center">
                <Printer className="size-5" />
              </div>
              <div>
                <DialogTitle className="text-base font-bold text-foreground">
                  Xuất bài tập in ấn / PDF (A4)
                </DialogTitle>
                <DialogDescription className="text-xs text-muted-foreground">
                  {meta?.deck_name || deckName || 'Bộ thẻ'} &bull;{' '}
                  {meta?.total_notes || 0} ghi chú
                </DialogDescription>
              </div>
            </div>

            {/* Stepper indicator */}
            <div className="hidden sm:flex items-center gap-1.5 text-xs font-semibold">
              <span
                className={`px-2.5 py-1 rounded-full ${
                  step === 'template'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                1. Mẫu
              </span>
              <ChevronRight className="size-3.5 text-muted-foreground" />
              <span
                className={`px-2.5 py-1 rounded-full ${
                  step === 'fields'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                2. Dữ liệu
              </span>
              <ChevronRight className="size-3.5 text-muted-foreground" />
              <span
                className={`px-2.5 py-1 rounded-full ${
                  step === 'layout'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                3. Bố cục
              </span>
              <ChevronRight className="size-3.5 text-muted-foreground" />
              <span
                className={`px-2.5 py-1 rounded-full ${
                  step === 'preview'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                4. Xem trước & In
              </span>
            </div>
          </div>
        </DialogHeader>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 min-h-[380px]">
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
                      Chọn định dạng luyện tập bạn muốn in cho bộ thẻ này.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-1">
                    {meta?.templates.map((tpl) => {
                      const Icon = templateIcons[tpl.id] || FileText
                      const isSelected = selectedTemplateId === tpl.id

                      return (
                        <div
                          key={tpl.id}
                          onClick={() => handleSelectTemplate(tpl.id)}
                          className={`relative p-4 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between gap-3 ${
                            isSelected
                              ? 'border-primary bg-primary/5 shadow-sm'
                              : 'border-border hover:border-border/80 hover:bg-muted/30 bg-card'
                          }`}
                        >
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
                            <div className="space-y-1 flex-1">
                              <div className="flex items-center justify-between">
                                <h4 className="text-sm font-bold text-foreground">
                                  {tpl.name_vi}
                                </h4>
                                <Badge
                                  variant={isSelected ? 'default' : 'secondary'}
                                  className="text-[10px] uppercase font-semibold"
                                >
                                  {tpl.category}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                                {tpl.description_vi}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-2 border-t border-border/50">
                            <span>
                              Mặc định:{' '}
                              <strong>{tpl.default_rows_per_page} mục/trang</strong>
                            </span>
                            <span className="capitalize">
                              Khổ:{' '}
                              <strong>
                                {tpl.default_orientation === 'portrait' ? 'Dọc' : 'Ngang'}
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
                      Chỉ định các trường trong ghi chú để điền vào các vị trí của mẫu{' '}
                      <strong>{currentTemplate.name_vi}</strong>.
                    </p>
                  </div>

                  {/* Note Type Selector if multiple */}
                  {meta && meta.note_types.length > 1 && (
                    <div className="space-y-1.5 bg-muted/40 p-3.5 rounded-xl border border-border/60">
                      <Label className="text-xs font-semibold">
                        Loại ghi chú (Note Type)
                      </Label>
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
                  <div className="space-y-3 bg-card p-4 rounded-xl border border-border/70">
                    <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                      Ánh xạ trường ({currentTemplate.name_vi})
                    </h4>

                    {currentTemplate.id === 'deck_table' ? (
                      <div className="space-y-2">
                        <Label className="text-xs font-medium">
                          Chọn các trường hiển thị làm cột bảng:
                        </Label>
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                          {availableFields.map((f) => {
                            const currentCols = (fieldMapping.custom_columns as string[]) || []
                            const isChecked = currentCols.includes(f)
                            return (
                              <label
                                key={f}
                                className="flex items-center gap-2 p-2 rounded-lg border border-border text-xs cursor-pointer hover:bg-muted/40"
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
                                  className="rounded text-primary"
                                />
                                <span className="font-medium text-foreground">{f}</span>
                              </label>
                            )
                          })}
                        </div>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                        {currentTemplate.field_slots.map((slot) => {
                          const val = (fieldMapping[slot.key] as string) || ''
                          return (
                            <div key={slot.key} className="space-y-1">
                              <Label className="text-xs font-semibold flex items-center gap-1">
                                <span>{slot.label_vi}</span>
                                {slot.required && (
                                  <span className="text-rose-500">*</span>
                                )}
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
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 bg-muted/40 p-4 rounded-xl border border-border/60">
                    <div className="space-y-1">
                      <Label className="text-xs font-semibold">Phạm vi tạo bài tập</Label>
                      <NativeSelect
                        value={scope}
                        onChange={(e) => setScope(e.target.value as any)}
                        className="h-9 text-xs"
                      >
                        {initialCardIds && initialCardIds.length > 0 && (
                          <option value="selected">
                            {initialCardIds.length} thẻ đang chọn
                          </option>
                        )}
                        <option value="all">Toàn bộ bộ thẻ ({meta?.total_notes} ghi chú)</option>
                        <option value="first_n">N thẻ đầu tiên</option>
                        <option value="random_n">Lấy ngẫu nhiên N thẻ</option>
                      </NativeSelect>
                    </div>

                    {(scope === 'first_n' || scope === 'random_n') && (
                      <div className="space-y-1">
                        <Label className="text-xs font-semibold">
                          Số lượng ghi chú (N):
                        </Label>
                        <Input
                          type="number"
                          min={1}
                          max={500}
                          value={limitCount}
                          onChange={(e) => setLimitCount(Number(e.target.value))}
                          className="h-9 text-xs"
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* STEP 3: LAYOUT & PRINT OPTIONS */}
              {step === 'layout' && currentTemplate && (
                <div className="space-y-5">
                  <div>
                    <h3 className="text-sm font-bold text-foreground">
                      Bước 3: Tùy chỉnh Bố cục & Trang in A4
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Cấu hình kiểu ô chữ, số lượng ô luyện tập, và tiêu đề trang in.
                    </p>
                  </div>

                  {/* Grid / Kanji specific options */}
                  {currentTemplate.category === 'kanji' && (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 bg-card p-4 rounded-xl border border-border/70">
                      <div className="space-y-1">
                        <Label className="text-xs font-semibold">Kiểu đường kẻ ô chữ</Label>
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

                      <div className="space-y-1">
                        <Label className="text-xs font-semibold">Số ô mờ để đồ chữ</Label>
                        <Input
                          type="number"
                          min={0}
                          max={5}
                          value={layoutOptions.trace_count ?? 2}
                          onChange={(e) =>
                            setLayoutOptions((prev) => ({
                              ...prev,
                              trace_count: Number(e.target.value),
                            }))
                          }
                          className="h-9 text-xs"
                        />
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs font-semibold">Số ô trống tự viết</Label>
                        <Input
                          type="number"
                          min={1}
                          max={10}
                          value={layoutOptions.practice_count ?? 5}
                          onChange={(e) =>
                            setLayoutOptions((prev) => ({
                              ...prev,
                              practice_count: Number(e.target.value),
                            }))
                          }
                          className="h-9 text-xs"
                        />
                      </div>
                    </div>
                  )}

                  {/* Page & Density Options */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 bg-muted/40 p-4 rounded-xl border border-border/60">
                    <div className="space-y-1">
                      <Label className="text-xs font-semibold">Hướng giấy A4</Label>
                      <NativeSelect
                        value={layoutOptions.orientation || 'portrait'}
                        onChange={(e) =>
                          setLayoutOptions((prev) => ({
                            ...prev,
                            orientation: e.target.value as any,
                          }))
                        }
                        className="h-9 text-xs"
                      >
                        <option value="portrait">A4 Dọc (Portrait)</option>
                        <option value="landscape">A4 Ngang (Landscape)</option>
                      </NativeSelect>
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs font-semibold">Số mục mỗi trang A4</Label>
                      <Input
                        type="number"
                        min={1}
                        max={30}
                        value={layoutOptions.rows_per_page ?? 5}
                        onChange={(e) =>
                          setLayoutOptions((prev) => ({
                            ...prev,
                            rows_per_page: Number(e.target.value),
                          }))
                        }
                        className="h-9 text-xs"
                      >
                      </Input>
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs font-semibold">Căn lề trang (Margins)</Label>
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
                        <option value="compact">Thu gọn (10mm)</option>
                        <option value="standard">Tiêu chuẩn (12mm)</option>
                        <option value="wide">Rộng (18mm)</option>
                      </NativeSelect>
                    </div>
                  </div>

                  {/* Header & Typography info */}
                  <div className="space-y-3 bg-card p-4 rounded-xl border border-border/70">
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
                        />
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs font-semibold">Phụ đề / Hướng dẫn</Label>
                        <Input
                          value={layoutOptions.header_subtitle || ''}
                          onChange={(e) =>
                            setLayoutOptions((prev) => ({
                              ...prev,
                              header_subtitle: e.target.value,
                            }))
                          }
                          className="h-9 text-xs"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-6 pt-1">
                      <label className="flex items-center gap-2 text-xs cursor-pointer">
                        <input
                          type="checkbox"
                          checked={layoutOptions.show_student_info !== false}
                          onChange={(e) =>
                            setLayoutOptions((prev) => ({
                              ...prev,
                              show_student_info: e.target.checked,
                            }))
                          }
                          className="rounded text-primary"
                        />
                        <span>Hiện dòng Họ tên</span>
                      </label>

                      <label className="flex items-center gap-2 text-xs cursor-pointer">
                        <input
                          type="checkbox"
                          checked={layoutOptions.show_date !== false}
                          onChange={(e) =>
                            setLayoutOptions((prev) => ({
                              ...prev,
                              show_date: e.target.checked,
                            }))
                          }
                          className="rounded text-primary"
                        />
                        <span>Hiện dòng Ngày tháng</span>
                      </label>
                    </div>
                  </div>
                </div>
              )}

              {/* STEP 4: INTERACTIVE LIVE PREVIEW */}
              {step === 'preview' && previewData && currentTemplate && (
                <div className="space-y-4">
                  {/* Toolbar */}
                  <div className="flex items-center justify-between flex-wrap gap-2 bg-muted/40 p-2.5 rounded-xl border border-border/60 shrink-0">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={currentPageIdx === 0}
                        onClick={() => setCurrentPageIdx((p) => Math.max(0, p - 1))}
                        className="h-8 px-2.5 text-xs"
                      >
                        <ChevronLeft className="size-3.5 mr-1" />
                        Trang trước
                      </Button>

                      <span className="text-xs font-semibold px-2">
                        Trang {currentPageIdx + 1} / {previewData.total_pages || 1}
                      </span>

                      <Button
                        variant="outline"
                        size="sm"
                        disabled={currentPageIdx >= previewData.total_pages - 1}
                        onClick={() =>
                          setCurrentPageIdx((p) =>
                            Math.min(previewData.total_pages - 1, p + 1)
                          )
                        }
                        className="h-8 px-2.5 text-xs"
                      >
                        Trang sau
                        <ChevronRight className="size-3.5 ml-1" />
                      </Button>
                    </div>

                    {/* Zoom & summary */}
                    <div className="flex items-center gap-2">
                      <div className="flex items-center bg-background rounded-lg border border-border/80 px-1 py-0.5">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7"
                          onClick={() => setZoomLevel((z) => Math.max(0.5, z - 0.1))}
                          title="Thu nhỏ"
                        >
                          <ZoomOut className="size-3.5" />
                        </Button>
                        <span className="text-xs font-medium px-1.5">
                          {Math.round(zoomLevel * 100)}%
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7"
                          onClick={() => setZoomLevel((z) => Math.min(1.5, z + 0.1))}
                          title="Phóng to"
                        >
                          <ZoomIn className="size-3.5" />
                        </Button>
                      </div>

                      <Badge variant="secondary" className="text-xs font-semibold">
                        Tổng: {previewData.total_items} mục &bull;{' '}
                        {previewData.total_pages} trang A4
                      </Badge>
                    </div>
                  </div>

                  {/* Rendered Page Preview Container */}
                  <div className="overflow-auto max-h-[58vh] bg-slate-100 dark:bg-slate-950/80 p-4 rounded-xl border border-border/80 flex justify-center">
                    {previewData.pages.length > 0 && previewData.pages[currentPageIdx] ? (
                      <WorksheetPageRenderer
                        page={previewData.pages[currentPageIdx]}
                        template={currentTemplate}
                        options={layoutOptions}
                        fieldMapping={fieldMapping}
                        zoom={zoomLevel}
                      />
                    ) : (
                      <div className="py-12 text-center text-muted-foreground text-xs">
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
        <div className="px-6 py-3.5 border-t border-border/80 bg-muted/20 flex items-center justify-between shrink-0">
          <div>
            {step !== 'template' ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (step === 'preview') setStep('layout')
                  else if (step === 'layout') setStep('fields')
                  else if (step === 'fields') setStep('template')
                }}
                className="h-9 px-3 text-xs gap-1"
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

          <div className="flex items-center gap-2">
            {step === 'template' && (
              <Button
                size="sm"
                onClick={() => setStep('fields')}
                className="h-9 px-4 text-xs font-semibold gap-1"
              >
                Tiếp tục: Dữ liệu
                <ChevronRight className="size-4" />
              </Button>
            )}

            {step === 'fields' && (
              <Button
                size="sm"
                onClick={() => setStep('layout')}
                className="h-9 px-4 text-xs font-semibold gap-1"
              >
                Tiếp tục: Bố cục
                <ChevronRight className="size-4" />
              </Button>
            )}

            {step === 'layout' && (
              <Button
                size="sm"
                onClick={handleGeneratePreview}
                disabled={isGenerating}
                className="h-9 px-4 text-xs font-semibold gap-1.5 bg-orange-600 hover:bg-orange-700 text-white"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Đang xử lý...
                  </>
                ) : (
                  <>
                    <Sparkles className="size-4" />
                    Xem trước bài tập
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
                  className="h-9 px-3.5 text-xs gap-1.5 font-medium"
                >
                  <Download className="size-4" />
                  Tải file in (HTML)
                </Button>

                <Button
                  size="sm"
                  onClick={handlePrint}
                  disabled={isPrinting}
                  className="h-9 px-4 text-xs font-semibold gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground shadow-md"
                >
                  {isPrinting ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Đang chuẩn bị...
                    </>
                  ) : (
                    <>
                      <Printer className="size-4" />
                      In ngay (Print / PDF)
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
