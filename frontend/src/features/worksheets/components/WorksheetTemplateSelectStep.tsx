import React, { useState } from 'react'
import {
  LayoutGrid,
  FileText,
  Type,
  BookOpen,
  Sparkles,
  Table as TableIcon,
  Layers,
  Check,
  ArrowRight,
  ArrowLeft,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { WorksheetTemplate } from '../types'

export interface WorksheetTemplateSelectStepProps {
  templates: WorksheetTemplate[]
  selectedTemplateId: string
  onSelectTemplate: (templateId: string) => void
  onConfirm: () => void
  onBack: () => void
  isStandalone?: boolean
  className?: string
}

const TEMPLATE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
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

type CategoryFilter = 'all' | 'kanji' | 'vocabulary' | 'sentence' | 'table'

export const WorksheetTemplateSelectStep: React.FC<WorksheetTemplateSelectStepProps> = ({
  templates,
  selectedTemplateId,
  onSelectTemplate,
  onConfirm,
  onBack,
  isStandalone = false,
  className = '',
}) => {
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>(
    isStandalone ? 'all' : 'all',
  )

  const filteredTemplates = React.useMemo(() => {
    if (activeCategory === 'all') return templates
    if (activeCategory === 'sentence') {
      return templates.filter((t) => t.category === 'sentence' || t.category === 'grammar')
    }
    return templates.filter((t) => t.category === activeCategory)
  }, [templates, activeCategory])

  return (
    <div className={`flex flex-col h-full overflow-hidden ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-border/70 bg-card/60 shrink-0 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
              <LayoutGrid className="size-4 text-primary" />
              <span>Bước 3: Chọn loại bài tập muốn in</span>
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              Chọn một mẫu bài tập phù hợp với mục tiêu luyện tập của bạn (Luyện nét, Viết từ vựng, Đặt câu...).
            </p>
          </div>
          <Badge variant="outline" className="text-[11px] font-semibold">
            {templates.length} mẫu in A4
          </Badge>
        </div>

        {/* Category Filters */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs font-semibold">
          {[
            { id: 'all', label: 'Tất cả mẫu' },
            { id: 'kanji', label: 'Chữ Hán & Nét' },
            { id: 'vocabulary', label: 'Từ vựng & Nhớ' },
            { id: 'sentence', label: 'Mẫu câu & Ngữ pháp' },
            { id: 'table', label: 'Bảng tuỳ biến' },
          ].map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setActiveCategory(cat.id as CategoryFilter)}
              className={`px-3 py-1.5 rounded-lg transition-all shrink-0 ${
                activeCategory === cat.id
                  ? 'bg-primary text-primary-foreground shadow-xs'
                  : 'bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid of Templates */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filteredTemplates.map((tpl) => {
            const Icon = TEMPLATE_ICONS[tpl.id] || FileText
            const isSelected = selectedTemplateId === tpl.id

            const categoryBadgeColor =
              tpl.category === 'kanji'
                ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                : tpl.category === 'vocabulary'
                ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20'
                : tpl.category === 'sentence' || tpl.category === 'grammar'
                ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                : tpl.category === 'essay'
                ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
                : 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20'

            return (
              <div
                key={tpl.id}
                onClick={() => onSelectTemplate(tpl.id)}
                className={`relative p-3.5 rounded-xl border-2 cursor-pointer transition-all flex flex-col justify-between text-left group ${
                  isSelected
                    ? 'border-primary bg-primary/5 shadow-xs ring-2 ring-primary/20'
                    : 'border-border/80 hover:border-primary/50 hover:bg-muted/30 bg-card'
                }`}
              >
                {isSelected && (
                  <div className="absolute top-3 right-3 size-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-xs">
                    <Check className="size-3 stroke-[3]" />
                  </div>
                )}

                <div>
                  <div className="flex items-start gap-3">
                    <div
                      className={`size-9 rounded-xl flex items-center justify-center shrink-0 transition-all ${
                        isSelected
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary'
                      }`}
                    >
                      <Icon className="size-4.5" />
                    </div>

                    <div className="space-y-1 flex-1 pr-6">
                      <div className="flex items-center gap-2">
                        <h4 className="text-xs font-bold text-foreground">
                          {tpl.name_vi}
                        </h4>
                      </div>
                      <Badge
                        variant="outline"
                        className={`text-[9.5px] uppercase font-semibold px-1.5 py-0 border ${categoryBadgeColor}`}
                      >
                        {tpl.category === 'kanji'
                          ? 'Chữ Hán'
                          : tpl.category === 'vocabulary'
                          ? 'Từ vựng'
                          : tpl.category === 'sentence'
                          ? 'Mẫu câu'
                          : tpl.category === 'grammar'
                          ? 'Ngữ pháp'
                          : tpl.category === 'essay'
                          ? 'Bài luận'
                          : 'Bảng dữ liệu'}
                      </Badge>
                      <p className="text-[11px] text-muted-foreground leading-relaxed mt-1 line-clamp-2">
                        {tpl.description_vi}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[10.5px] text-muted-foreground pt-2.5 mt-2.5 border-t border-border/50">
                  <span>
                    Mặc định: <strong>{tpl.default_rows_per_page} mục/trang</strong>
                  </span>
                  <span>
                    Khổ:{' '}
                    <strong>{tpl.default_orientation === 'portrait' ? 'A4 Dọc' : 'A4 Ngang'}</strong>
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Footer Navigation */}
      <div className="p-3.5 border-t border-border/80 bg-muted/30 flex items-center justify-between gap-2 shrink-0">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onBack}
          className="h-9 px-3 text-xs gap-1.5 font-semibold"
        >
          <ArrowLeft className="size-3.5" />
          <span>Quay lại</span>
        </Button>

        <Button
          type="button"
          size="sm"
          onClick={onConfirm}
          className="h-9 px-4 text-xs font-bold gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground shadow-xs"
        >
          <span>Tiếp tục: Cấu hình & In ấn</span>
          <ArrowRight className="size-3.5" />
        </Button>
      </div>
    </div>
  )
}
