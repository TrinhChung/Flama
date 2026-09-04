export interface FieldSlot {
  key: string
  label_vi: string
  label_en: string
  required: boolean
  description_vi?: string
  suggested_names?: string[]
}

export interface WorksheetTemplate {
  id: string
  name_vi: string
  name_en: string
  description_vi: string
  description_en: string
  category: 'kanji' | 'vocabulary' | 'table' | 'sentence' | 'grammar' | 'essay'
  supported_orientations: ('portrait' | 'landscape')[]
  default_orientation: 'portrait' | 'landscape'
  default_rows_per_page: number
  field_slots: FieldSlot[]
  default_options: WorksheetLayoutOptions
}

export type AuxiliaryColumnType = 'dashed_line' | 'grid_boxes' | 'checkboxes' | 'blank' | 'double_line'

export interface WorksheetLayoutOptions {
  paper_size?: 'a4'
  orientation?: 'portrait' | 'landscape'
  margin?: 'minimal' | 'ultra_compact' | 'compact' | 'standard' | 'wide'
  rows_per_page?: number
  auto_fit_page?: boolean
  box_size?: number
  extra_blank_rows?: number
  fill_blank_rows?: boolean
  grid_style?: 'cross' | 'diagonal' | 'square'
  trace_count?: number
  practice_count?: number
  practice_type?: 'boxes' | 'lines' | 'grid'
  practice_boxes_count?: number
  show_stroke_diagram?: boolean
  reference_char_color?: string
  stroke_color_mode?: 'monochrome' | 'multicolor' | 'same_as_reference'
  show_reading?: boolean
  show_meaning?: boolean
  show_reading_hint?: boolean
  show_word_length_hint?: boolean
  include_practice_column?: boolean
  practice_column_label?: string
  column_widths?: Record<string, string | number>
  auxiliary_column_enabled?: boolean
  auxiliary_column_title?: string
  auxiliary_column_type?: AuxiliaryColumnType
  auxiliary_column_width?: string | number
  auxiliary_column_boxes_count?: number
  writing_lines_count?: number
  writing_line_style?: 'dashed' | 'solid' | 'ruled' | 'grid'
  show_sample_sentence?: boolean
  show_sample_reading?: boolean
  show_sample_meaning?: boolean
  exercise_prompt?: string
  show_explanation?: boolean
  show_example_hint?: boolean
  watermark_enabled?: boolean
  watermark_text?: string
  watermark_opacity?: number
  watermark_layout?: 'diagonal_grid' | 'margin_bounds'
  header_title?: string
  header_subtitle?: string
  show_student_info?: boolean
  show_date?: boolean
  locale?: 'ja' | 'zh' | 'zh-hant'
  grid_columns?: number
  grid_rows?: number
  box_style?: 'square' | 'cross' | 'diagonal'
  grid_color?: string
  has_spacer_band?: boolean
  spacer_height?: number
  content_mode?: 'blank' | 'text' | 'trace'
  custom_text?: string
  header_student_style?: 'chinese' | 'vietnamese' | 'japanese' | 'none'
  title_placement?: 'first_row' | 'header' | 'none'
  footer_date_format?: 'chinese' | 'vietnamese' | 'none'
  footer_brand_label?: string
  essay_page_count?: number
}

export type WorksheetFieldMapping = Record<string, string | string[]>

export interface NoteTypeMeta {
  id: string | number
  name: string
  fields: string[]
  note_count: number
}

export interface DeckWorksheetMeta {
  deck_id: number
  deck_name: string
  total_notes: number
  note_types: NoteTypeMeta[]
  suggested_mappings: Record<string, string>
  templates: WorksheetTemplate[]
}

export interface WorksheetKanjiItem {
  type: 'kanji'
  note_id: string
  char: string
  hex?: string
  has_stroke?: boolean
  stroke_svg?: string | null
  stroke_url?: string | null
  reading?: string
  meaning?: string
  source_word?: string
  extra_blank_rows?: number
  is_blank_filler?: boolean
}

export interface WorksheetVocabItem {
  type: 'vocab'
  note_id: string
  word: string
  reading?: string
  meaning?: string
  is_blank_filler?: boolean
}

export interface WorksheetRecallItem {
  type: 'recall'
  note_id: string
  word?: string
  reading?: string
  meaning?: string
  word_length?: number
  is_blank_filler?: boolean
}

export interface WorksheetTableRowItem {
  type: 'table_row'
  note_id: string
  data: Record<string, string>
  is_blank_filler?: boolean
}

export interface WorksheetSentenceItem {
  type: 'sentence'
  note_id: string
  sentence: string
  reading?: string
  meaning?: string
  is_blank_filler?: boolean
}

export interface WorksheetGrammarItem {
  type: 'grammar'
  note_id: string
  grammar_point: string
  meaning_usage?: string
  example?: string
  is_blank_filler?: boolean
}

export interface WorksheetEssayCell {
  col_index: number
  char?: string
  is_blank?: boolean
  is_title?: boolean
  is_trace?: boolean
}

export interface WorksheetEssayRowItem {
  type: 'essay_row'
  note_id: string
  row_index: number
  cells: WorksheetEssayCell[]
}

export type WorksheetItem =
  | WorksheetKanjiItem
  | WorksheetVocabItem
  | WorksheetRecallItem
  | WorksheetTableRowItem
  | WorksheetSentenceItem
  | WorksheetGrammarItem
  | WorksheetEssayRowItem

export interface WorksheetPageHeader {
  title: string
  subtitle: string
  deck_name: string
  show_student_info: boolean
  show_date: boolean
}

export interface WorksheetPageData {
  page_number: number
  total_pages: number
  header: WorksheetPageHeader
  items: WorksheetItem[]
}

export interface WorksheetPreviewResponse {
  template: WorksheetTemplate
  deck_id: number
  deck_name: string
  options: WorksheetLayoutOptions
  field_mapping: WorksheetFieldMapping
  total_items: number
  total_pages: number
  pages: WorksheetPageData[]
  warnings: string[]
}

export interface WorksheetGenerationRequest {
  deck_id?: number | null
  template_id: string
  note_type_id?: string | number
  field_mapping?: WorksheetFieldMapping
  options?: WorksheetLayoutOptions
  scope?: 'all' | 'first_n' | 'random_n'
  limit?: number
  card_ids?: (string | number)[]
  note_ids?: (string | number)[]
}
