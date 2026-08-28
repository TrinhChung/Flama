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
  category: 'kanji' | 'vocabulary' | 'table'
  supported_orientations: ('portrait' | 'landscape')[]
  default_orientation: 'portrait' | 'landscape'
  default_rows_per_page: number
  field_slots: FieldSlot[]
  default_options: WorksheetLayoutOptions
}

export interface WorksheetLayoutOptions {
  paper_size?: 'a4'
  orientation?: 'portrait' | 'landscape'
  margin?: 'compact' | 'standard' | 'wide'
  rows_per_page?: number
  grid_style?: 'cross' | 'diagonal' | 'square'
  trace_count?: number
  practice_count?: number
  practice_type?: 'boxes' | 'lines' | 'grid'
  practice_boxes_count?: number
  show_stroke_diagram?: boolean
  show_reading?: boolean
  show_meaning?: boolean
  show_reading_hint?: boolean
  show_word_length_hint?: boolean
  include_practice_column?: boolean
  practice_column_label?: string
  header_title?: string
  header_subtitle?: string
  show_student_info?: boolean
  show_date?: boolean
  locale?: 'ja' | 'zh' | 'zh-hant'
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
  hex: string
  has_stroke: boolean
  stroke_svg: string | null
  stroke_url: string | null
  reading: string
  meaning: string
  source_word: string
}

export interface WorksheetVocabItem {
  type: 'vocab'
  note_id: string
  word: string
  reading: string
  meaning: string
}

export interface WorksheetRecallItem {
  type: 'recall'
  note_id: string
  word: string
  reading: string
  meaning: string
  word_length: number
}

export interface WorksheetTableRowItem {
  type: 'table_row'
  note_id: string
  data: Record<string, string>
}

export type WorksheetItem =
  | WorksheetKanjiItem
  | WorksheetVocabItem
  | WorksheetRecallItem
  | WorksheetTableRowItem

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
  deck_id: number
  template_id: string
  note_type_id?: string | number
  field_mapping: WorksheetFieldMapping
  options?: WorksheetLayoutOptions
  scope?: 'all' | 'first_n' | 'random_n'
  limit?: number
  card_ids?: (string | number)[]
  note_ids?: (string | number)[]
}
