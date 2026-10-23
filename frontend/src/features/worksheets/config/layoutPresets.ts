import type { ParseKeys } from 'i18next'
import type { WorksheetLayoutOptions, WorksheetTemplate } from '../types'

type WorksheetKey = ParseKeys<'worksheets'>

/** One-tap layout preset shown in the Live Studio layout tab. */
export interface LayoutPreset {
  id: string
  icon?: string
  label: string
  labelKey?: WorksheetKey
  description: string
  descriptionKey?: WorksheetKey
  toast: string
  toastKey?: WorksheetKey
  options: Partial<WorksheetLayoutOptions>
  /** Recognizes the preset from options alone, used before any preset was clicked. */
  matches: (options: WorksheetLayoutOptions) => boolean
}

const DENSE_PAGE = { page_fill_mode: 'max_density', auto_fit_page: true } as const

const STEP_PRESETS: LayoutPreset[] = [
  {
    id: 'step_save',
    icon: '⚡',
    label: 'Tiết kiệm giấy',
    labelKey: 'studio.layout_tab.preset_save_paper',
    description: 'Ô 30px, 1 mờ, 8 dòng',
    descriptionKey: 'studio.layout_tab.desc_step_save',
    toast: 'Đã áp dụng mẫu: Tiết kiệm giấy (Ô 30px, 1 ô mờ, 8 dòng/trang)',
    toastKey: 'studio.layout_tab.toast_save_paper_step',
    options: { box_size: 30, margin: 'compact', trace_count: 1, practice_count: 2, extra_blank_rows: 0, ...DENSE_PAGE },
    matches: (o) => o.box_size === 30 && (o.trace_count ?? 1) === 1,
  },
  {
    id: 'step_standard',
    icon: '✍️',
    label: 'Viết chuẩn',
    labelKey: 'studio.layout_tab.preset_standard',
    description: 'Ô 34px, 2 mờ, 7 dòng',
    descriptionKey: 'studio.layout_tab.desc_step_standard',
    toast: 'Đã áp dụng mẫu: Luyện viết chuẩn (Ô 34px, 2 ô mờ, 7 dòng/trang)',
    toastKey: 'studio.layout_tab.toast_standard_step',
    options: { box_size: 34, margin: 'compact', trace_count: 2, practice_count: 2, extra_blank_rows: 0, ...DENSE_PAGE },
    matches: (o) => (o.box_size === 34 || !o.box_size) && (o.trace_count ?? 2) === 2,
  },
  {
    id: 'step_large',
    icon: '🎨',
    label: 'Nét to chuyên sâu',
    labelKey: 'studio.layout_tab.preset_large',
    description: 'Ô 38px to rõ, 6 dòng',
    descriptionKey: 'studio.layout_tab.desc_step_large',
    toast: 'Đã áp dụng mẫu: Nét to chuyên sâu (Ô 38px to rõ, 2 ô mờ, 6 dòng/trang)',
    toastKey: 'studio.layout_tab.toast_large_step',
    options: { box_size: 38, margin: 'compact', trace_count: 2, practice_count: 2, extra_blank_rows: 0, ...DENSE_PAGE },
    matches: (o) => o.box_size === 38,
  },
]

const KANJI_PRESETS: LayoutPreset[] = [
  {
    id: 'kanji_save',
    icon: '⚡',
    label: 'Tiết kiệm giấy',
    labelKey: 'studio.layout_tab.preset_save_paper',
    description: 'Ô 28px, 1 mờ, 8 viết',
    descriptionKey: 'studio.layout_tab.desc_kanji_save',
    toast: 'Đã áp dụng mẫu: Tiết kiệm giấy (Ô 28px, 1 ô mờ, 8 ô tự viết)',
    toastKey: 'studio.layout_tab.toast_save_paper_kanji',
    options: { box_size: 28, page_fill_mode: 'max_density', margin: 'minimal', trace_count: 1, practice_count: 8, extra_blank_rows: 0, auto_fit_page: true },
    matches: (o) => o.box_size === 28 && o.margin === 'minimal',
  },
  {
    id: 'kanji_standard',
    icon: '✍️',
    label: 'Viết chuẩn',
    labelKey: 'studio.layout_tab.preset_standard',
    description: 'Ô 36px, 2 mờ, 5 viết',
    descriptionKey: 'studio.layout_tab.desc_kanji_standard',
    toast: 'Đã áp dụng mẫu: Luyện viết chuẩn (Ô 36px, tối đa dòng, sát lề)',
    toastKey: 'studio.layout_tab.toast_standard_kanji',
    options: { box_size: 36, page_fill_mode: 'max_density', margin: 'compact', trace_count: 2, practice_count: 5, extra_blank_rows: 0, auto_fit_page: true },
    matches: (o) => (o.box_size === 36 || !o.box_size) && (o.extra_blank_rows ?? 0) === 0 && o.margin !== 'minimal',
  },
  {
    id: 'kanji_large',
    icon: '🎨',
    label: 'Nét to chuyên sâu',
    labelKey: 'studio.layout_tab.preset_large',
    description: 'Ô 42px, +1 dòng trống',
    descriptionKey: 'studio.layout_tab.desc_kanji_large',
    toast: 'Đã áp dụng mẫu: Ô chữ to chuyên sâu (+1 dòng luyện bổ sung)',
    toastKey: 'studio.layout_tab.toast_large_kanji',
    options: { box_size: 42, page_fill_mode: 'max_density', margin: 'standard', trace_count: 3, practice_count: 4, extra_blank_rows: 1, auto_fit_page: true },
    matches: (o) => o.box_size === 42 || (o.extra_blank_rows ?? 0) >= 1,
  },
]

const VOCAB_WRITING_PRESETS: LayoutPreset[] = [
  {
    id: 'vocab_boxes',
    icon: '🔲',
    label: 'Dải 6 ô vuông',
    description: 'Tiêu chuẩn từ vựng',
    toast: 'Đã áp dụng mẫu: Bảng ô vuông 6 ô tiêu chuẩn',
    options: { practice_type: 'boxes', practice_boxes_count: 6, show_reading: true, show_meaning: true, margin: 'compact', ...DENSE_PAGE },
    matches: (o) => o.practice_type === 'boxes' || !o.practice_type,
  },
  {
    id: 'vocab_lines',
    icon: '✍️',
    label: 'Dòng kẻ viết tay',
    description: 'Kẻ ngang nét đứt',
    toast: 'Đã áp dụng mẫu: Dòng kẻ viết tay tự do',
    options: { practice_type: 'lines', show_reading: true, show_meaning: true, margin: 'compact', ...DENSE_PAGE },
    matches: (o) => o.practice_type === 'lines',
  },
  {
    id: 'vocab_grid',
    icon: '田',
    label: 'Ô lưới chữ Hán',
    description: 'Nắn nót từng chữ',
    toast: 'Đã áp dụng mẫu: Ô lưới chữ thập Kanji/Kana',
    options: { practice_type: 'grid', practice_boxes_count: 5, show_reading: true, show_meaning: true, margin: 'compact', ...DENSE_PAGE },
    matches: (o) => o.practice_type === 'grid',
  },
]

const VOCAB_RECALL_PRESETS: LayoutPreset[] = [
  {
    id: 'recall_reading',
    icon: '💡',
    label: 'Có gợi ý đọc',
    description: 'Kèm Furigana/Pinyin',
    toast: 'Đã áp dụng mẫu: Gợi ý cách đọc & nghĩa',
    options: { show_reading_hint: true, show_word_length_hint: false, recall_answer_style: 'line', ...DENSE_PAGE },
    matches: (o) => o.show_reading_hint !== false && !o.show_word_length_hint,
  },
  {
    id: 'recall_hard',
    icon: '🧠',
    label: 'Thử thách khó',
    description: 'Chỉ hiện Nghĩa',
    toast: 'Đã áp dụng mẫu: Thử thách khó (Ẩn cách đọc)',
    options: { show_reading_hint: false, show_word_length_hint: false, recall_answer_style: 'line', ...DENSE_PAGE },
    matches: (o) => o.show_reading_hint === false,
  },
  {
    id: 'recall_boxes',
    icon: '🔲',
    label: 'Gợi ý số ô chữ',
    description: 'Tương ứng độ dài từ',
    toast: 'Đã áp dụng mẫu: Gợi ý số ô ký tự',
    options: { show_reading_hint: true, show_word_length_hint: true, recall_answer_style: 'boxes', ...DENSE_PAGE },
    matches: (o) => o.show_word_length_hint === true,
  },
]

const SENTENCE_PRESETS: LayoutPreset[] = [
  {
    id: 'sentence_short',
    icon: '✍️',
    label: 'Dịch câu ngắn',
    description: '2 dòng kẻ mỗi câu',
    toast: 'Đã áp dụng mẫu: Dịch câu ngắn (2 dòng kẻ)',
    options: { writing_lines_count: 2, writing_line_style: 'dashed', exercise_prompt: 'Dịch các câu sau sang tiếng Việt:', ...DENSE_PAGE },
    matches: (o) => o.writing_lines_count === 2,
  },
  {
    id: 'sentence_standard',
    icon: '📝',
    label: 'Luyện câu chuẩn',
    description: '3 dòng kẻ mỗi câu',
    toast: 'Đã áp dụng mẫu: Luyện câu chuẩn (3 dòng kẻ)',
    options: {
      writing_lines_count: 3,
      writing_line_style: 'dashed',
      exercise_prompt: 'Dịch các câu sau sang tiếng Việt hoặc phát triển thành đoạn văn:',
      ...DENSE_PAGE,
    },
    matches: (o) => o.writing_lines_count === 3 || !o.writing_lines_count,
  },
  {
    id: 'sentence_paragraph',
    icon: '📖',
    label: 'Viết đoạn văn',
    description: '5 dòng kẻ mỗi câu',
    toast: 'Đã áp dụng mẫu: Viết đoạn văn (5 dòng kẻ)',
    options: { writing_lines_count: 5, writing_line_style: 'dashed', exercise_prompt: 'Phát triển câu mẫu thành đoạn văn hoàn chỉnh:', ...DENSE_PAGE },
    matches: (o) => o.writing_lines_count === 5,
  },
]

const GENKOUYOUSHI_PRESETS: LayoutPreset[] = [
  {
    id: 'genkou_400_plain',
    label: '400 ô Trơn',
    description: 'Chuẩn 作文纸 20x20',
    toast: 'Đã áp dụng mẫu: 400 ô trơn tiêu chuẩn',
    options: { grid_columns: 20, grid_rows: 20, box_style: 'square', footer_brand_label: 'Flama (400格)' },
    matches: (o) => o.grid_rows === 20 && (o.box_style === 'square' || !o.box_style),
  },
  {
    id: 'genkou_400_cross',
    label: '400 ô Chữ thập',
    description: 'Luyện bút thuận (+)',
    toast: 'Đã áp dụng mẫu: 400 ô chữ thập (+)',
    options: { grid_columns: 20, grid_rows: 20, box_style: 'cross', footer_brand_label: 'Flama (400格)' },
    matches: (o) => o.grid_rows === 20 && o.box_style === 'cross',
  },
  {
    id: 'genkou_200_spacious',
    label: '200 ô Thoáng',
    description: 'Sơ cấp 20x10',
    toast: 'Đã áp dụng mẫu: 200 ô thoáng (20x10)',
    options: { grid_columns: 20, grid_rows: 10, box_style: 'square', footer_brand_label: 'Flama (200格)' },
    matches: (o) => o.grid_rows === 10,
  },
]

const PRESETS_BY_TEMPLATE_ID: Record<string, LayoutPreset[]> = {
  kanji_step_by_step: STEP_PRESETS,
  vocab_writing: VOCAB_WRITING_PRESETS,
  vocab_recall: VOCAB_RECALL_PRESETS,
  sentence_writing: SENTENCE_PRESETS,
  genkouyoushi: GENKOUYOUSHI_PRESETS,
}

export function layoutPresetsFor(template: WorksheetTemplate): LayoutPreset[] {
  return PRESETS_BY_TEMPLATE_ID[template.id] || (template.category === 'kanji' ? KANJI_PRESETS : [])
}

export function isLayoutPresetActive(
  preset: LayoutPreset,
  activePresetId: string | null,
  options: WorksheetLayoutOptions,
): boolean {
  return activePresetId === preset.id || (activePresetId === null && preset.matches(options))
}
