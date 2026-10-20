import type { ComponentType } from 'react'
import {
  BookOpen,
  Boxes,
  FileEdit,
  FileText,
  HelpCircle,
  Layers,
  LayoutGrid,
  ListOrdered,
  PenTool,
  Sparkles,
  Table as TableIcon,
  Type,
} from 'lucide-react'

export type TemplateIcon = ComponentType<{ className?: string }>

/** Icons for the Live Studio template tab. */
export const STUDIO_TEMPLATE_ICONS: Record<string, TemplateIcon> = {
  kanji_compact: PenTool,
  kanji_stroke: PenTool,
  kanji_compound: Boxes,
  kanji_step_by_step: ListOrdered,
  vocab_writing: BookOpen,
  vocab_recall: HelpCircle,
  deck_table: TableIcon,
  sentence_writing: FileText,
  grammar_practice: LayoutGrid,
  genkouyoushi: FileEdit,
}

/** Icons for the wizard's template-selection step. */
export const WIZARD_TEMPLATE_ICONS: Record<string, TemplateIcon> = {
  kanji_compact: LayoutGrid,
  kanji_step_by_step: Sparkles,
  kanji_stroke: Layers,
  kanji_compound: Type,
  vocab_writing: BookOpen,
  vocab_recall: FileText,
  sentence_writing: FileText,
  grammar_practice: BookOpen,
  deck_table: TableIcon,
  genkouyoushi: FileText,
}
