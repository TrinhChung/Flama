import { useTranslation } from 'react-i18next'
import {
  Check,
  RotateCcw,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import type { StudioLayoutTabProps } from './StudioLayoutTab'

export function StudioLayoutPresets({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
  activePresetId,
  setActivePresetId,
  handleResetCurrentTemplateDefaults,
}: Pick<
  StudioLayoutTabProps,
  | 'currentTemplate'
  | 'layoutOptions'
  | 'setLayoutOptions'
  | 'activePresetId'
  | 'setActivePresetId'
  | 'handleResetCurrentTemplateDefaults'
>) {
  const { t } = useTranslation('worksheets')
  if (!currentTemplate) return null

  return (
    <>
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
    </>
  )
}
