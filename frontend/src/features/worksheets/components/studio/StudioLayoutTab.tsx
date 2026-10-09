import React from 'react'
import { useTranslation } from 'react-i18next'
import {
  Check,
  Minus,
  Plus,
  RotateCcw,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Badge } from '@/components/ui/badge'
import type { DeckWorksheetMeta, WorksheetLayoutOptions, WorksheetPreviewResponse } from '../../types'
import { getFitZoom } from './StudioPreviewCanvas'

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

export function StudioLayoutTab({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
  activePresetId,
  setActivePresetId,
  handleResetCurrentTemplateDefaults,
  meta,
  previewData,
  setZoomLevel,
}: StudioLayoutTabProps) {
  const { t } = useTranslation('worksheets')
  if (!currentTemplate) return null

  const isLandscape = layoutOptions.orientation === 'landscape'

  return (
                    <div className="space-y-4">
                      {/* QUICK PRESETS & RESET BUTTON */}
                      <div className="space-y-2.5 bg-card p-3.5 rounded-xl border border-border/70 shadow-xs">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5">
                            <Sparkles className="size-3.5 text-primary" />
                            <span className="text-xs font-bold text-foreground">
                              {t('studio.layout_tab.presets_title', 'Bố cục mẫu 1-chạm (Quick Presets)')}
                            </span>
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={handleResetCurrentTemplateDefaults}
                            className="h-6 text-[10.5px] px-2 text-muted-foreground hover:text-foreground"
                            title={t('studio.layout_tab.reset_defaults_title', 'Khôi phục lại thiết lập mặc định tối ưu của mẫu này')}
                          >
                            <RotateCcw className="size-3 mr-1" />
                            <span>{t('studio.layout_tab.reset_defaults', 'Mặc định tối ưu')}</span>
                          </Button>
                        </div>

                        {/* Presets according to current template */}
                        {currentTemplate.id === 'kanji_step_by_step' ? (
                          <div className="grid grid-cols-3 gap-1.5">
                            {(() => {
                              const isSavePaper = activePresetId === 'step_save' || (activePresetId === null && layoutOptions.box_size === 30 && (layoutOptions.trace_count ?? 1) === 1)
                              const isStandard = activePresetId === 'step_standard' || (activePresetId === null && (layoutOptions.box_size === 34 || !layoutOptions.box_size) && (layoutOptions.trace_count ?? 2) === 2)
                              const isLarge = activePresetId === 'step_large' || (activePresetId === null && layoutOptions.box_size === 38)

                              return (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('step_save')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_size: 30,
                                        margin: 'compact',
                                        trace_count: 1,
                                        practice_count: 2,
                                        extra_blank_rows: 0,
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success(t('studio.layout_tab.toast_save_paper_step', 'Đã áp dụng mẫu: Tiết kiệm giấy (Ô 30px, 1 ô mờ, 8 dòng/trang)'))
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isSavePaper
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isSavePaper ? 'text-primary' : 'text-foreground'}`}>
                                        ⚡ {t('studio.layout_tab.preset_save_paper', 'Tiết kiệm giấy')}
                                      </div>
                                      {isSavePaper && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isSavePaper ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      {t('studio.layout_tab.desc_step_save', 'Ô 30px, 1 mờ, 8 dòng')}
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('step_standard')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_size: 34,
                                        margin: 'compact',
                                        trace_count: 2,
                                        practice_count: 2,
                                        extra_blank_rows: 0,
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success(t('studio.layout_tab.toast_standard_step', 'Đã áp dụng mẫu: Luyện viết chuẩn (Ô 34px, 2 ô mờ, 7 dòng/trang)'))
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isStandard
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isStandard ? 'text-primary' : 'text-foreground'}`}>
                                        ✍️ {t('studio.layout_tab.preset_standard', 'Viết chuẩn')}
                                      </div>
                                      {isStandard && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isStandard ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      {t('studio.layout_tab.desc_step_standard', 'Ô 34px, 2 mờ, 7 dòng')}
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('step_large')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_size: 38,
                                        margin: 'compact',
                                        trace_count: 2,
                                        practice_count: 2,
                                        extra_blank_rows: 0,
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success(t('studio.layout_tab.toast_large_step', 'Đã áp dụng mẫu: Nét to chuyên sâu (Ô 38px to rõ, 2 ô mờ, 6 dòng/trang)'))
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isLarge
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isLarge ? 'text-primary' : 'text-foreground'}`}>
                                        🎨 {t('studio.layout_tab.preset_large', 'Nét to chuyên sâu')}
                                      </div>
                                      {isLarge && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isLarge ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      {t('studio.layout_tab.desc_step_large', 'Ô 38px to rõ, 6 dòng')}
                                    </div>
                                  </button>
                                </>
                              )
                            })()}
                          </div>
                        ) : currentTemplate.category === 'kanji' ? (
                          <div className="grid grid-cols-3 gap-1.5">
                            {(() => {
                              const isSavePaper = activePresetId === 'kanji_save' || (activePresetId === null && layoutOptions.box_size === 28 && layoutOptions.margin === 'minimal')
                              const isStandard = activePresetId === 'kanji_standard' || (activePresetId === null && (layoutOptions.box_size === 36 || !layoutOptions.box_size) && (layoutOptions.extra_blank_rows ?? 0) === 0 && layoutOptions.margin !== 'minimal')
                              const isLarge = activePresetId === 'kanji_large' || (activePresetId === null && (layoutOptions.box_size === 42 || (layoutOptions.extra_blank_rows ?? 0) >= 1))

                              return (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('kanji_save')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_size: 28,
                                        page_fill_mode: 'max_density',
                                        margin: 'minimal',
                                        trace_count: 1,
                                        practice_count: 8,
                                        extra_blank_rows: 0,
                                        auto_fit_page: true,
                                      }))
                                      toast.success(t('studio.layout_tab.toast_save_paper_kanji', 'Đã áp dụng mẫu: Tiết kiệm giấy (Ô 28px, 1 ô mờ, 8 ô tự viết)'))
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isSavePaper
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isSavePaper ? 'text-primary' : 'text-foreground'}`}>
                                        ⚡ {t('studio.layout_tab.preset_save_paper', 'Tiết kiệm giấy')}
                                      </div>
                                      {isSavePaper && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isSavePaper ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      {t('studio.layout_tab.desc_kanji_save', 'Ô 28px, 1 mờ, 8 viết')}
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('kanji_standard')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_size: 36,
                                        page_fill_mode: 'max_density',
                                        margin: 'compact',
                                        trace_count: 2,
                                        practice_count: 5,
                                        extra_blank_rows: 0,
                                        auto_fit_page: true,
                                      }))
                                      toast.success(t('studio.layout_tab.toast_standard_kanji', 'Đã áp dụng mẫu: Luyện viết chuẩn (Ô 36px, tối đa dòng, sát lề)'))
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isStandard
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isStandard ? 'text-primary' : 'text-foreground'}`}>
                                        ✍️ {t('studio.layout_tab.preset_standard', 'Viết chuẩn')}
                                      </div>
                                      {isStandard && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isStandard ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      {t('studio.layout_tab.desc_kanji_standard', 'Ô 36px, 2 mờ, 5 viết')}
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('kanji_large')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_size: 42,
                                        page_fill_mode: 'max_density',
                                        margin: 'standard',
                                        trace_count: 3,
                                        practice_count: 4,
                                        extra_blank_rows: 1,
                                        auto_fit_page: true,
                                      }))
                                      toast.success(t('studio.layout_tab.toast_large_kanji', 'Đã áp dụng mẫu: Ô chữ to chuyên sâu (+1 dòng luyện bổ sung)'))
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isLarge
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isLarge ? 'text-primary' : 'text-foreground'}`}>
                                        🎨 {t('studio.layout_tab.preset_large', 'Nét to chuyên sâu')}
                                      </div>
                                      {isLarge && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isLarge ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      {t('studio.layout_tab.desc_kanji_large', 'Ô 42px, +1 dòng trống')}
                                    </div>
                                  </button>
                                </>
                              )
                            })()}
                          </div>
                        ) : null}

                        {currentTemplate.id === 'vocab_writing' && (
                          <div className="grid grid-cols-3 gap-1.5">
                            {(() => {
                              const isBoxes = activePresetId === 'vocab_boxes' || (activePresetId === null && (layoutOptions.practice_type === 'boxes' || !layoutOptions.practice_type))
                              const isLines = activePresetId === 'vocab_lines' || (activePresetId === null && layoutOptions.practice_type === 'lines')
                              const isGrid = activePresetId === 'vocab_grid' || (activePresetId === null && layoutOptions.practice_type === 'grid')

                              return (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('vocab_boxes')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        practice_type: 'boxes',
                                        practice_boxes_count: 6,
                                        show_reading: true,
                                        show_meaning: true,
                                        margin: 'compact',
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success('Đã áp dụng mẫu: Bảng ô vuông 6 ô tiêu chuẩn')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isBoxes
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isBoxes ? 'text-primary' : 'text-foreground'}`}>
                                        🔲 Dải 6 ô vuông
                                      </div>
                                      {isBoxes && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isBoxes ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      Tiêu chuẩn từ vựng
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('vocab_lines')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        practice_type: 'lines',
                                        show_reading: true,
                                        show_meaning: true,
                                        margin: 'compact',
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success('Đã áp dụng mẫu: Dòng kẻ viết tay tự do')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isLines
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isLines ? 'text-primary' : 'text-foreground'}`}>
                                        ✍️ Dòng kẻ viết tay
                                      </div>
                                      {isLines && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isLines ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      Kẻ ngang nét đứt
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('vocab_grid')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        practice_type: 'grid',
                                        practice_boxes_count: 5,
                                        show_reading: true,
                                        show_meaning: true,
                                        margin: 'compact',
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success('Đã áp dụng mẫu: Ô lưới chữ thập Kanji/Kana')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isGrid
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isGrid ? 'text-primary' : 'text-foreground'}`}>
                                        田 Ô lưới chữ Hán
                                      </div>
                                      {isGrid && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isGrid ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      Nắn nót từng chữ
                                    </div>
                                  </button>
                                </>
                              )
                            })()}
                          </div>
                        )}

                        {currentTemplate.id === 'vocab_recall' && (
                          <div className="grid grid-cols-3 gap-1.5">
                            {(() => {
                              const isReading = activePresetId === 'recall_reading' || (activePresetId === null && layoutOptions.show_reading_hint !== false && !layoutOptions.show_word_length_hint)
                              const isHard = activePresetId === 'recall_hard' || (activePresetId === null && layoutOptions.show_reading_hint === false)
                              const isBoxes = activePresetId === 'recall_boxes' || (activePresetId === null && layoutOptions.show_word_length_hint === true)

                              return (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('recall_reading')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        show_reading_hint: true,
                                        show_word_length_hint: false,
                                        recall_answer_style: 'line',
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success('Đã áp dụng mẫu: Gợi ý cách đọc & nghĩa')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isReading
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isReading ? 'text-primary' : 'text-foreground'}`}>
                                        💡 Có gợi ý đọc
                                      </div>
                                      {isReading && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isReading ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      Kèm Furigana/Pinyin
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('recall_hard')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        show_reading_hint: false,
                                        show_word_length_hint: false,
                                        recall_answer_style: 'line',
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success('Đã áp dụng mẫu: Thử thách khó (Ẩn cách đọc)')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isHard
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isHard ? 'text-primary' : 'text-foreground'}`}>
                                        🧠 Thử thách khó
                                      </div>
                                      {isHard && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isHard ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      Chỉ hiện Nghĩa
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('recall_boxes')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        show_reading_hint: true,
                                        show_word_length_hint: true,
                                        recall_answer_style: 'boxes',
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success('Đã áp dụng mẫu: Gợi ý số ô ký tự')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isBoxes
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isBoxes ? 'text-primary' : 'text-foreground'}`}>
                                        🔲 Gợi ý số ô chữ
                                      </div>
                                      {isBoxes && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isBoxes ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      Tương ứng độ dài từ
                                    </div>
                                  </button>
                                </>
                              )
                            })()}
                          </div>
                        )}

                        {currentTemplate.id === 'sentence_writing' && (
                          <div className="grid grid-cols-3 gap-1.5">
                            {(() => {
                              const isShort = activePresetId === 'sentence_short' || (activePresetId === null && layoutOptions.writing_lines_count === 2)
                              const isStandard = activePresetId === 'sentence_standard' || (activePresetId === null && (layoutOptions.writing_lines_count === 3 || !layoutOptions.writing_lines_count))
                              const isParagraph = activePresetId === 'sentence_paragraph' || (activePresetId === null && layoutOptions.writing_lines_count === 5)

                              return (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('sentence_short')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_lines_count: 2,
                                        writing_line_style: 'dashed',
                                        exercise_prompt: 'Dịch các câu sau sang tiếng Việt:',
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success('Đã áp dụng mẫu: Dịch câu ngắn (2 dòng kẻ)')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isShort
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isShort ? 'text-primary' : 'text-foreground'}`}>
                                        ✍️ Dịch câu ngắn
                                      </div>
                                      {isShort && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isShort ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      2 dòng kẻ mỗi câu
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('sentence_standard')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_lines_count: 3,
                                        writing_line_style: 'dashed',
                                        exercise_prompt: 'Dịch các câu sau sang tiếng Việt hoặc phát triển thành đoạn văn:',
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success('Đã áp dụng mẫu: Luyện câu chuẩn (3 dòng kẻ)')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isStandard
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isStandard ? 'text-primary' : 'text-foreground'}`}>
                                        📝 Luyện câu chuẩn
                                      </div>
                                      {isStandard && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isStandard ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      3 dòng kẻ mỗi câu
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('sentence_paragraph')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_lines_count: 5,
                                        writing_line_style: 'dashed',
                                        exercise_prompt: 'Phát triển câu mẫu thành đoạn văn hoàn chỉnh:',
                                        page_fill_mode: 'max_density',
                                        auto_fit_page: true,
                                      }))
                                      toast.success('Đã áp dụng mẫu: Viết đoạn văn (5 dòng kẻ)')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isParagraph
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isParagraph ? 'text-primary' : 'text-foreground'}`}>
                                        📖 Viết đoạn văn
                                      </div>
                                      {isParagraph && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isParagraph ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      5 dòng kẻ mỗi câu
                                    </div>
                                  </button>
                                </>
                              )
                            })()}
                          </div>
                        )}

                        {currentTemplate.id === 'genkouyoushi' && (
                          <div className="grid grid-cols-3 gap-1.5">
                            {(() => {
                              const isPlain = activePresetId === 'genkou_400_plain' || (activePresetId === null && layoutOptions.grid_rows === 20 && (layoutOptions.box_style === 'square' || !layoutOptions.box_style))
                              const isCross = activePresetId === 'genkou_400_cross' || (activePresetId === null && layoutOptions.grid_rows === 20 && layoutOptions.box_style === 'cross')
                              const isSpacious = activePresetId === 'genkou_200_spacious' || (activePresetId === null && layoutOptions.grid_rows === 10)

                              return (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('genkou_400_plain')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        grid_columns: 20,
                                        grid_rows: 20,
                                        box_style: 'square',
                                        footer_brand_label: 'Flama (400格)',
                                      }))
                                      toast.success('Đã áp dụng mẫu: 400 ô trơn tiêu chuẩn')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isPlain
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isPlain ? 'text-primary' : 'text-foreground'}`}>
                                        400 ô Trơn
                                      </div>
                                      {isPlain && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isPlain ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      Chuẩn 作文纸 20x20
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('genkou_400_cross')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        grid_columns: 20,
                                        grid_rows: 20,
                                        box_style: 'cross',
                                        footer_brand_label: 'Flama (400格)',
                                      }))
                                      toast.success('Đã áp dụng mẫu: 400 ô chữ thập (+)')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isCross
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isCross ? 'text-primary' : 'text-foreground'}`}>
                                        400 ô Chữ thập
                                      </div>
                                      {isCross && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isCross ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      Luyện bút thuận (+)
                                    </div>
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActivePresetId('genkou_200_spacious')
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        grid_columns: 20,
                                        grid_rows: 10,
                                        box_style: 'square',
                                        footer_brand_label: 'Flama (200格)',
                                      }))
                                      toast.success('Đã áp dụng mẫu: 200 ô thoáng (20x10)')
                                    }}
                                    className={`p-2 rounded-lg border-2 text-left transition-all relative ${
                                      isSpacious
                                        ? 'border-primary bg-primary/10 ring-1 ring-primary/30 shadow-xs'
                                        : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className={`text-xs font-bold ${isSpacious ? 'text-primary' : 'text-foreground'}`}>
                                        200 ô Thoáng
                                      </div>
                                      {isSpacious && <Check className="size-3.5 text-primary shrink-0 stroke-[2.5]" />}
                                    </div>
                                    <div className={`text-[10px] line-clamp-1 ${isSpacious ? 'text-primary/80 font-medium' : 'text-muted-foreground'}`}>
                                      Sơ cấp 20x10
                                    </div>
                                  </button>
                                </>
                              )
                            })()}
                          </div>
                        )}
                      </div>

                      {/* Orientation & Page Margins */}
                      <div className="space-y-3 bg-card p-3.5 rounded-xl border border-border/70 shadow-xs">
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                          Khổ giấy & Hướng in A4
                        </h4>

                        {/* Orientation Toggle */}
                        <div className="grid grid-cols-2 gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setLayoutOptions((prev) => ({ ...prev, orientation: 'portrait' }))
                              if (typeof window !== 'undefined' && window.innerWidth < 768) {
                                setZoomLevel?.(getFitZoom('portrait'))
                              }
                            }}
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
                            onClick={() => {
                              setLayoutOptions((prev) => ({ ...prev, orientation: 'landscape' }))
                              if (typeof window !== 'undefined' && window.innerWidth < 768) {
                                setZoomLevel?.(getFitZoom('landscape'))
                              }
                            }}
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

                        {/* Page Fill Mode: Balanced Stretch vs Max Density */}
                        <div className="space-y-2 pt-1 border-t border-border/50">
                          <Label className="text-xs font-bold text-foreground uppercase tracking-wider block">
                            Mật độ & Bố cục lấp đầy A4
                          </Label>
                          <div className="grid grid-cols-2 gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  page_fill_mode: 'balanced_stretch',
                                  auto_fit_page: true,
                                }))
                                toast.success('Đã chọn: Dàn đều kín trang (Đỡ mỏi tay, tự giãn khoảng cách dòng)')
                              }}
                              className={`flex flex-col p-2.5 rounded-lg border text-left transition-all ${
                                layoutOptions.page_fill_mode === 'balanced_stretch'
                                  ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                  : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                              }`}
                            >
                              <div className="text-xs font-bold flex items-center gap-1.5 text-foreground">
                                <span>🌿 Dàn đều kín trang</span>
                                {layoutOptions.page_fill_mode === 'balanced_stretch' && (
                                  <span className="text-[10px] text-primary">●</span>
                                )}
                              </div>
                              <p className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                                {layoutOptions.orientation === 'landscape' ? '6-7 từ/trang' : '8-10 từ/trang'}, tự giãn đều 100% không để trống đáy
                              </p>
                            </button>

                            <button
                              type="button"
                              onClick={() => {
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  page_fill_mode: 'max_density',
                                  auto_fit_page: true,
                                  box_size: prev.box_size && prev.box_size > 34 ? 32 : prev.box_size,
                                }))
                                toast.success('Đã chọn: Tiết kiệm giấy (Tối đa dòng, lấp kịch khung A4)')
                              }}
                              className={`flex flex-col p-2.5 rounded-lg border text-left transition-all ${
                                (layoutOptions.page_fill_mode || 'max_density') === 'max_density'
                                  ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                  : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                              }`}
                            >
                              <div className="text-xs font-bold flex items-center gap-1.5 text-foreground">
                                <span>⚡ {t('studio.layout_tab.preset_save_paper', 'Tiết kiệm giấy')}</span>
                                {(layoutOptions.page_fill_mode || 'max_density') === 'max_density' && (
                                  <span className="text-[10px] text-primary">●</span>
                                )}
                              </div>
                              <p className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                                {layoutOptions.orientation === 'landscape' ? '12-14 từ/trang' : '18-20 từ/trang'}, phủ kín tối đa số từ
                              </p>
                            </button>
                          </div>
                        </div>

                        {/* Auto-fit A4 Mode vs Manual Rows per page */}
                        <div className="space-y-2 pt-1 border-t border-border/50">
                          <div className="flex items-center justify-between">
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.auto_fit_page !== false}
                                onChange={(e) => {
                                  const isChecked = e.target.checked
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    auto_fit_page: isChecked,
                                    rows_per_page: !isChecked
                                      ? (previewData?.options?.rows_per_page ?? prev.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8)
                                      : prev.rows_per_page,
                                  }))
                                }}
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

                          {layoutOptions.auto_fit_page !== false && (
                            <div className="pl-6 pt-1">
                              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                                <span>⚡ Đang áp dụng:</span>
                                <strong className="font-bold">
                                  {previewData?.options?.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8} dòng/trang
                                </strong>
                                <span className="text-muted-foreground text-[10px]">
                                  ({previewData?.total_pages ?? 1} trang A4)
                                </span>
                              </div>
                            </div>
                          )}

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
                                    setLayoutOptions((prev) => {
                                      const current = prev.rows_per_page ?? previewData?.options?.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8
                                      return {
                                        ...prev,
                                        rows_per_page: Math.max(1, current - 1),
                                      }
                                    })
                                  }
                                >
                                  <Minus className="size-3.5" />
                                </Button>
                                <div className="h-8 flex-1 flex items-center justify-center bg-muted/40 rounded-md border border-border text-xs font-bold text-foreground">
                                  {layoutOptions.rows_per_page ?? previewData?.options?.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8} dòng/trang
                                </div>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="icon"
                                  className="size-8 shrink-0"
                                  onClick={() =>
                                    setLayoutOptions((prev) => {
                                      const current = prev.rows_per_page ?? previewData?.options?.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8
                                      return {
                                        ...prev,
                                        rows_per_page: Math.min(30, current + 1),
                                      }
                                    })
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

                          {/* Color & Stroke Settings */}
                          <div className="space-y-3 pt-2 border-t border-border/60">
                            {/* Ngôn ngữ & Bộ nét chữ Hán */}
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between">
                                <Label className="text-[11px] font-semibold text-foreground">
                                  Bộ nét & Ngôn ngữ chữ Hán:
                                </Label>
                                {meta?.detected_locale && (
                                  <Badge variant="outline" className="text-[9.5px] px-1.5 py-0 h-4.5 bg-primary/5 text-primary border-primary/20">
                                    Tự động: {meta.detected_locale === 'zh' ? 'Tiếng Trung' : meta.detected_locale === 'zh-hant' ? 'Phồn thể' : 'Tiếng Nhật'}
                                  </Badge>
                                )}
                              </div>
                              <NativeSelect
                                value={layoutOptions.locale || meta?.detected_locale || 'ja'}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    locale: e.target.value as any,
                                  }))
                                }
                                className="h-8 text-xs bg-card"
                              >
                                <option value="ja">Tiếng Nhật (KanjiVG - Bộ nét chuẩn Nhật)</option>
                                <option value="zh">Tiếng Trung Giản thể (Make Me A Hanzi - Chuẩn HSK)</option>
                                <option value="zh-hant">Tiếng Trung Phồn thể (Make Me A Hanzi - Đài Loan / HK)</option>
                              </NativeSelect>
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-[11px] font-semibold text-foreground flex items-center justify-between">
                                <span>Màu chữ mẫu (Ô đầu tiên):</span>
                                <span
                                  className="size-3.5 rounded-full border border-border inline-block shrink-0 shadow-2xs"
                                  style={{ backgroundColor: layoutOptions.reference_char_color || '#e11d48' }}
                                />
                              </Label>
                              <div className="flex items-center gap-1.5 flex-wrap">
                                {[
                                  { label: 'Đỏ', color: '#e11d48' },
                                  { label: 'Xanh dương', color: '#2563eb' },
                                  { label: 'Xanh lá', color: '#16a34a' },
                                  { label: 'Cam', color: '#ea580c' },
                                  { label: 'Tím', color: '#9333ea' },
                                  { label: 'Đen', color: '#0f172a' },
                                ].map((p) => {
                                  const isSelected = (layoutOptions.reference_char_color || '#e11d48') === p.color
                                  return (
                                    <button
                                      key={p.color}
                                      type="button"
                                      onClick={() =>
                                        setLayoutOptions((prev) => ({
                                          ...prev,
                                          reference_char_color: p.color,
                                        }))
                                      }
                                      className={`size-5 rounded-full transition-all flex items-center justify-center ${
                                        isSelected
                                          ? 'ring-2 ring-primary ring-offset-1 scale-110 shadow-xs'
                                          : 'opacity-70 hover:opacity-100 hover:scale-105'
                                      }`}
                                      style={{ backgroundColor: p.color }}
                                      title={p.label}
                                    >
                                      {isSelected && <span className="text-[9px] text-white font-bold leading-none">✓</span>}
                                    </button>
                                  )
                                })}
                                <label
                                  className="size-5 rounded-full border border-dashed border-border cursor-pointer flex items-center justify-center hover:bg-muted transition-colors relative overflow-hidden"
                                  title="Chọn màu tuỳ chỉnh"
                                >
                                  <span className="text-[10px] text-muted-foreground font-bold">🎨</span>
                                  <input
                                    type="color"
                                    value={layoutOptions.reference_char_color || '#e11d48'}
                                    onChange={(e) =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        reference_char_color: e.target.value,
                                      }))
                                    }
                                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                                  />
                                </label>
                              </div>
                            </div>

                            {(currentTemplate.id === 'kanji_compact' || currentTemplate.id === 'kanji_stroke') && (
                              <div className="space-y-1.5">
                                <Label className="text-[11px] font-semibold text-foreground block">
                                  Kiểu màu nét vẽ (Ô thứ 2):
                                </Label>
                                <div className="grid grid-cols-3 gap-1">
                                  {[
                                    {
                                      id: 'monochrome',
                                      label: 'Đen đơn sắc',
                                      icon: '🖤',
                                      hint: 'Rõ nét khi in/photo',
                                    },
                                    {
                                      id: 'multicolor',
                                      label: 'Đa màu sắc',
                                      icon: '🌈',
                                      hint: 'Phân biệt từng nét',
                                    },
                                    {
                                      id: 'same_as_reference',
                                      label: 'Theo chữ mẫu',
                                      icon: '🎨',
                                      hint: 'Đồng bộ màu sắc',
                                    },
                                  ].map((modeOpt) => {
                                    const isSelected =
                                      (layoutOptions.stroke_color_mode || 'monochrome') === modeOpt.id
                                    return (
                                      <button
                                        key={modeOpt.id}
                                        type="button"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            stroke_color_mode: modeOpt.id as any,
                                          }))
                                        }
                                        className={`px-1.5 py-1 rounded-md text-[10px] border font-medium flex flex-col items-center text-center transition-all ${
                                          isSelected
                                            ? 'border-primary bg-primary/10 text-primary font-bold shadow-2xs'
                                            : 'border-border/70 bg-card text-muted-foreground hover:bg-muted/50'
                                        }`}
                                        title={modeOpt.hint}
                                      >
                                        <span className="text-xs">{modeOpt.icon}</span>
                                        <span className="truncate w-full mt-0.5">{modeOpt.label}</span>
                                      </button>
                                    )
                                  })}
                                </div>
                              </div>
                            )}

                            {currentTemplate.id === 'kanji_step_by_step' && (
                              <div className="space-y-1.5">
                                <Label className="text-[11px] font-semibold text-foreground flex items-center justify-between">
                                  <span>Màu nét mới (Bước hiện tại - để tô theo):</span>
                                  <span
                                    className="size-3.5 rounded-full border border-border inline-block shrink-0 shadow-2xs"
                                    style={{ backgroundColor: layoutOptions.step_highlight_color || '#e11d48' }}
                                  />
                                </Label>
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  {[
                                    { label: 'Đỏ', color: '#e11d48' },
                                    { label: 'Xanh dương', color: '#2563eb' },
                                    { label: 'Xanh lá', color: '#16a34a' },
                                    { label: 'Cam', color: '#ea580c' },
                                    { label: 'Tím', color: '#9333ea' },
                                    { label: 'Đen', color: '#0f172a' },
                                  ].map((p) => {
                                    const isSelected = (layoutOptions.step_highlight_color || '#e11d48') === p.color
                                    return (
                                      <button
                                        key={p.color}
                                        type="button"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            step_highlight_color: p.color,
                                          }))
                                        }
                                        className={`size-5 rounded-full transition-all flex items-center justify-center ${
                                          isSelected
                                            ? 'ring-2 ring-primary ring-offset-1 scale-110 shadow-xs'
                                            : 'opacity-70 hover:opacity-100 hover:scale-105'
                                        }`}
                                        style={{ backgroundColor: p.color }}
                                        title={p.label}
                                      >
                                        {isSelected && <span className="text-[9px] text-white font-bold leading-none">✓</span>}
                                      </button>
                                    )
                                  })}
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Toggles */}
                          <div className="space-y-1.5 pt-2 border-t border-border/60 text-xs">
                            {currentTemplate.id === 'kanji_step_by_step' && (
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={Boolean(layoutOptions.show_step_numbers)}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_step_numbers: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện số thứ tự bước (1, 2, 3...)</span>
                              </label>
                            )}
                            {(currentTemplate.id === 'kanji_compact' || currentTemplate.id === 'kanji_stroke') && (
                              <>
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
                                  <span>Hiện sơ đồ nét bút SVG (Ô thứ 2)</span>
                                </label>
                                {layoutOptions.show_stroke_diagram !== false && (
                                  <label className="flex items-center gap-2 cursor-pointer select-none pl-3 border-l-2 border-primary/30">
                                    <input
                                      type="checkbox"
                                      checked={layoutOptions.show_stroke_numbers !== false}
                                      onChange={(e) =>
                                        setLayoutOptions((prev) => ({
                                          ...prev,
                                          show_stroke_numbers: e.target.checked,
                                        }))
                                      }
                                      className="rounded text-primary size-3.5"
                                    />
                                    <span>Hiện số thứ tự nét 1, 2, 3...</span>
                                  </label>
                                )}
                              </>
                            )}
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={Boolean(layoutOptions.show_reading)}
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
                                checked={Boolean(layoutOptions.show_meaning)}
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
                            {(currentTemplate.id === 'kanji_compact' ||
                              currentTemplate.id === 'kanji_stroke' ||
                              currentTemplate.id === 'kanji_step_by_step') && (
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={Boolean(layoutOptions.show_source_word)}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_source_word: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện Từ ví dụ</span>
                              </label>
                            )}
                          </div>
                        </div>
                      )}

                      {/* VOCABULARY WRITING SPECIFIC CONTROLS */}
                      {currentTemplate.id === 'vocab_writing' && (
                        <div className="space-y-3 bg-muted/30 p-3.5 rounded-xl border border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Bảng Luyện viết Từ vựng
                          </h4>

                          {/* Practice Type: Boxes, Lines, Grid */}
                          <div className="space-y-1.5">
                            <Label className="text-xs font-semibold">Kiểu vùng luyện viết:</Label>
                            <div className="grid grid-cols-3 gap-1.5">
                              {[
                                { id: 'boxes', label: '🔲 Ô vuông liền', desc: 'Dải ô vuông đều nhau' },
                                { id: 'lines', label: '✍️ Dòng kẻ viết', desc: 'Đường kẻ đứt tự do' },
                                { id: 'grid', label: '田 Ô lưới chữ Hán', desc: 'Đường kẻ chữ thập (+)' },
                              ].map((pt) => {
                                const currentType = layoutOptions.practice_type || 'boxes'
                                const isSelected = currentType === pt.id
                                return (
                                  <button
                                    key={pt.id}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        practice_type: pt.id as any,
                                      }))
                                    }
                                    className={`p-2 rounded-lg border text-left text-xs transition-all ${
                                      isSelected
                                        ? 'border-primary bg-primary/10 text-primary font-bold shadow-2xs'
                                        : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    <div className="truncate font-semibold">{pt.label}</div>
                                    <div className="text-[9.5px] text-muted-foreground font-normal line-clamp-1 mt-0.5">
                                      {pt.desc}
                                    </div>
                                  </button>
                                )
                              })}
                            </div>
                          </div>

                          {/* If boxes or grid: Practice Boxes Count Stepper & Quick Select */}
                          {layoutOptions.practice_type !== 'lines' && (
                            <div className="space-y-1.5 pt-1 border-t border-border/50">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Số ô luyện viết mỗi từ:</Label>
                                <span className="text-xs font-bold text-primary">
                                  {layoutOptions.practice_boxes_count ?? (isLandscape ? 10 : 6)} ô
                                </span>
                              </div>
                              <div className="grid grid-cols-5 gap-1">
                                {[4, 6, 8, 10, 12].map((cnt) => {
                                  const currentCnt = layoutOptions.practice_boxes_count ?? (isLandscape ? 10 : 6)
                                  return (
                                    <Button
                                      key={cnt}
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      onClick={() =>
                                        setLayoutOptions((prev) => ({
                                          ...prev,
                                          practice_boxes_count: cnt,
                                        }))
                                      }
                                      className={`h-7.5 text-xs ${
                                        currentCnt === cnt
                                          ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                          : 'bg-card hover:bg-muted text-muted-foreground'
                                      }`}
                                    >
                                      {cnt} ô
                                    </Button>
                                  )
                                })}
                              </div>
                            </div>
                          )}

                          {/* Visible Columns Toggles: Reading & Meaning */}
                          <div className="space-y-2 pt-1.5 border-t border-border/50">
                            <Label className="text-xs font-semibold">Hiển thị các cột nội dung:</Label>
                            <div className="grid grid-cols-2 gap-2 text-xs">
                              <label className="flex items-center gap-2 p-2 rounded-lg border border-border/70 bg-card cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_reading !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_reading: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-4"
                                />
                                <div>
                                  <div className="font-semibold text-foreground">Cột Cách đọc</div>
                                  <div className="text-[10px] text-muted-foreground">Furigana / Kana / Pinyin</div>
                                </div>
                              </label>
                              <label className="flex items-center gap-2 p-2 rounded-lg border border-border/70 bg-card cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_meaning !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_meaning: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-4"
                                />
                                <div>
                                  <div className="font-semibold text-foreground">Cột Ý nghĩa</div>
                                  <div className="text-[10px] text-muted-foreground">Dịch nghĩa tiếng Việt</div>
                                </div>
                              </label>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* VOCAB RECALL SPECIFIC CONTROLS */}
                      {currentTemplate.id === 'vocab_recall' && (
                        <div className="space-y-3 bg-muted/30 p-3.5 rounded-xl border border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Bài tập Kiểm tra Trí nhớ (Recall & Cloze)
                          </h4>

                          {/* Answer Area Style */}
                          <div className="space-y-1.5">
                            <Label className="text-xs font-semibold">Kiểu vùng điền câu trả lời:</Label>
                            <div className="grid grid-cols-2 gap-2">
                              <button
                                type="button"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    recall_answer_style: 'line',
                                    show_word_length_hint: false,
                                  }))
                                }
                                className={`p-2 rounded-lg border text-left text-xs transition-all ${
                                  (layoutOptions.recall_answer_style || 'line') === 'line' && !layoutOptions.show_word_length_hint
                                    ? 'border-primary bg-primary/10 text-primary font-bold shadow-2xs'
                                    : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                                }`}
                              >
                                <div className="font-bold">✍️ Dòng kẻ nét đứt</div>
                                <div className="text-[10px] text-muted-foreground font-normal mt-0.5">
                                  Dòng kẻ sạch sẽ để học sinh tự do nhớ và viết
                                </div>
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    recall_answer_style: 'boxes',
                                    show_word_length_hint: true,
                                  }))
                                }
                                className={`p-2 rounded-lg border text-left text-xs transition-all ${
                                  layoutOptions.recall_answer_style === 'boxes' || layoutOptions.show_word_length_hint
                                    ? 'border-primary bg-primary/10 text-primary font-bold shadow-2xs'
                                    : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                                }`}
                              >
                                <div className="font-bold">🔲 Dải ô chữ cái (Gợi ý số ký tự)</div>
                                <div className="text-[10px] text-muted-foreground font-normal mt-0.5">
                                  Hiển thị số ô tương ứng độ dài từ cần điền
                                </div>
                              </button>
                            </div>
                          </div>

                          {/* Reading hint toggle */}
                          <div className="pt-1.5 border-t border-border/50">
                            <label className="flex items-center gap-2 p-2.5 rounded-lg border border-border/70 bg-card cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.show_reading_hint !== false}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    show_reading_hint: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-4"
                              />
                              <div>
                                <div className="text-xs font-semibold text-foreground">
                                  Hiển thị gợi ý Cách đọc (Furigana / Kana)
                                </div>
                                <p className="text-[10px] text-muted-foreground">
                                  Tắt đi nếu muốn học viên phải tự nhớ toàn bộ từ chỉ dựa trên Nghĩa
                                </p>
                              </div>
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
                            <div className="space-y-1.5">
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
                              <div className="flex items-center gap-1 flex-wrap pt-0.5">
                                {[
                                  'Dịch các câu sau sang tiếng Việt:',
                                  'Viết lại mỗi câu 3 lần:',
                                  'Đặt câu mới sử dụng cấu trúc mẫu:',
                                  'Nghe & chép chính tả (Dictation):',
                                ].map((pText) => (
                                  <button
                                    key={pText}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        exercise_prompt: pText,
                                      }))
                                    }
                                    className="text-[10px] px-2 py-0.5 rounded-md border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                  >
                                    {pText}
                                  </button>
                                ))}
                              </div>
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
                            <div className="space-y-1.5">
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
                              <div className="flex items-center gap-1 flex-wrap pt-0.5">
                                {[
                                  'Hãy đặt câu hoàn chỉnh sử dụng cấu trúc / từ vựng trên:',
                                  'Viết đoạn văn ngắn (3-4 câu) áp dụng ngữ pháp:',
                                  'Dịch các câu ví dụ sang tiếng Việt:',
                                  'Tìm lỗi sai và viết lại câu đúng:',
                                ].map((pText) => (
                                  <button
                                    key={pText}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        exercise_prompt: pText,
                                      }))
                                    }
                                    className="text-[10px] px-2 py-0.5 rounded-md border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                  >
                                    {pText}
                                  </button>
                                ))}
                              </div>
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

                      {/* Genkouyoushi Essay Grid Controls */}
                      {currentTemplate.id === 'genkouyoushi' && (
                        <div className="space-y-3 pt-3 border-t border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Lưới bài văn Genkō Yōshi / 作文纸 (400 ô)
                          </h4>

                          {/* Content Mode Selection */}
                          <div className="space-y-2 bg-muted/20 p-3 rounded-xl border border-border/80">
                            <Label className="text-xs font-bold text-foreground">Chế độ nội dung trang:</Label>
                            <div className="grid grid-cols-3 gap-1.5">
                              {[
                                { id: 'blank', label: 'Trang trắng (Tập viết tay)' },
                                { id: 'text', label: 'Điền văn bản mẫu' },
                                { id: 'trace', label: 'Tô chữ nét mờ' },
                              ].map((m) => (
                                <button
                                  key={m.id}
                                  type="button"
                                  onClick={() =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      content_mode: m.id as any,
                                    }))
                                  }
                                  className={`py-2 px-1.5 rounded-lg border text-center text-xs font-medium transition-all ${
                                    (layoutOptions.content_mode || 'blank') === m.id
                                      ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                      : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                  }`}
                                >
                                  {m.label}
                                </button>
                              ))}
                            </div>

                            {/* Text Input when mode is text or trace */}
                            {(layoutOptions.content_mode === 'text' || layoutOptions.content_mode === 'trace') && (
                              <div className="space-y-1 pt-2">
                                <Label className="text-xs font-semibold">Nhập nội dung bài văn mẫu:</Label>
                                <textarea
                                  rows={4}
                                  value={layoutOptions.custom_text || ''}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      custom_text: e.target.value,
                                    }))
                                  }
                                  className="w-full text-xs p-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary font-sans leading-relaxed"
                                  placeholder="Dán hoặc gõ đoạn văn bản tại đây (tự động phân bổ vào từng ô vuông 20x20)..."
                                />
                                <p className="text-[10px] text-muted-foreground">
                                  Để trống nếu muốn hệ thống tự động lấy nội dung từ các thẻ học trong bộ.
                                </p>
                              </div>
                            )}

                            {/* Page count for sheets */}
                            <div className="space-y-1 pt-2 border-t border-border/50">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Số trang in:</Label>
                                <span className="text-xs font-bold text-primary">
                                  {layoutOptions.essay_page_count ?? 1} trang
                                </span>
                              </div>
                              <div className="flex items-center gap-1.5">
                                {[1, 2, 3, 4, 5].map((cnt) => (
                                  <Button
                                    key={cnt}
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        essay_page_count: cnt,
                                      }))
                                    }
                                    className={`flex-1 h-7.5 text-xs ${
                                      (layoutOptions.essay_page_count ?? 1) === cnt
                                        ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                    }`}
                                  >
                                    {cnt} trang
                                  </Button>
                                ))}
                              </div>
                            </div>
                          </div>

                          {/* Grid Specifications */}
                          <div className="space-y-2.5 bg-muted/20 p-3 rounded-xl border border-border/80">
                            <Label className="text-xs font-bold text-foreground">Khổ ô & Quy cách:</Label>
                            <div className="grid grid-cols-2 gap-2">
                              <button
                                type="button"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    grid_columns: 20,
                                    grid_rows: 20,
                                    footer_brand_label: 'Flama (400格)',
                                  }))
                                }
                                className={`p-2 rounded-lg border text-left text-xs transition-all ${
                                  (layoutOptions.grid_columns ?? 20) === 20 && (layoutOptions.grid_rows ?? 20) === 20
                                    ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                    : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                }`}
                              >
                                <div className="font-bold">400 ô (20 × 20)</div>
                                <div className="text-[10px] text-muted-foreground font-normal">Chuẩn giấy làm văn tiêu chuẩn</div>
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    grid_columns: 20,
                                    grid_rows: 10,
                                    footer_brand_label: 'Flama (200格)',
                                  }))
                                }
                                className={`p-2 rounded-lg border text-left text-xs transition-all ${
                                  (layoutOptions.grid_rows ?? 20) === 10
                                    ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                    : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                }`}
                              >
                                <div className="font-bold">200 ô (20 × 10)</div>
                                <div className="text-[10px] text-muted-foreground font-normal">Khổ thưa thoáng cho người mới</div>
                              </button>
                            </div>

                            {/* Box Style */}
                            <div className="space-y-1 pt-1.5 border-t border-border/50">
                              <Label className="text-xs font-semibold">Kiểu ô kẻ:</Label>
                              <div className="grid grid-cols-3 gap-1.5">
                                {[
                                  { id: 'square', label: 'Ô trơn (Plain)' },
                                  { id: 'cross', label: 'Chữ thập (+)' },
                                  { id: 'diagonal', label: 'Hoa thị (*)' },
                                ].map((bs) => (
                                  <button
                                    key={bs.id}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_style: bs.id as any,
                                      }))
                                    }
                                    className={`py-1.5 px-2 rounded-lg border text-center text-xs font-medium transition-all ${
                                      (layoutOptions.box_style || 'square') === bs.id
                                        ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                        : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    {bs.label}
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Grid Line Color */}
                            <div className="space-y-1 pt-1.5 border-t border-border/50">
                              <Label className="text-xs font-semibold">Màu mực đường kẻ:</Label>
                              <div className="grid grid-cols-3 gap-1.5">
                                {[
                                  { color: '#475569', label: 'Xám than (Chuẩn)' },
                                  { color: '#0d9488', label: 'Xanh ngọc' },
                                  { color: '#e11d48', label: 'Đỏ đất' },
                                ].map((c) => (
                                  <button
                                    key={c.color}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        grid_color: c.color,
                                      }))
                                    }
                                    className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg border text-xs font-medium transition-all ${
                                      (layoutOptions.grid_color || '#475569') === c.color
                                        ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                        : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    <span className="size-2.5 rounded-full" style={{ backgroundColor: c.color }} />
                                    <span>{c.label}</span>
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Spacer Band Between Rows */}
                            <div className="space-y-2 pt-1.5 border-t border-border/50">
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.has_spacer_band !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      has_spacer_band: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-4"
                                />
                                <div>
                                  <div className="text-xs font-bold text-foreground">
                                    Dải đệm ngang giữa các hàng (Spacer Band)
                                  </div>
                                  <p className="text-[10px] text-muted-foreground">
                                    Đúng chuẩn giấy luyện văn 作文纸 (dải đệm trống không kẻ dọc giữa các dòng ô)
                                  </p>
                                </div>
                              </label>

                              {layoutOptions.has_spacer_band !== false && (
                                <div className="flex items-center gap-1.5 pl-6">
                                  <Label className="text-[11px] text-muted-foreground shrink-0">Độ cao đệm:</Label>
                                  {[6, 8, 10, 12, 14].map((h) => (
                                    <Button
                                      key={h}
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      onClick={() =>
                                        setLayoutOptions((prev) => ({
                                          ...prev,
                                          spacer_height: h,
                                        }))
                                      }
                                      className={`flex-1 h-6 text-[10px] px-1 ${
                                        (layoutOptions.spacer_height ?? 10) === h
                                          ? 'bg-primary text-primary-foreground font-bold border-primary'
                                          : 'bg-background hover:bg-muted text-muted-foreground'
                                      }`}
                                    >
                                      {h}px
                                    </Button>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
  )
}
