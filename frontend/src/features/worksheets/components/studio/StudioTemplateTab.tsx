import { Check, FileText } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import type { DeckWorksheetMeta } from '../../types'

export interface StudioTemplateTabProps {
  templates?: DeckWorksheetMeta['templates']
  selectedTemplateId: string
  onSelectTemplate: (templateId: string) => void
  templateIcons?: Record<string, any>
}

export function StudioTemplateTab({
  templates,
  selectedTemplateId,
  onSelectTemplate,
  templateIcons = {},
}: StudioTemplateTabProps) {
  const { t } = useTranslation('worksheets')

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-xs font-bold text-foreground uppercase tracking-wider">
          {t('studio.template_tab.current_template', 'Chọn mẫu bài tập')}
        </h3>
        <p className="text-[11px] text-muted-foreground mt-0.5">
          Nhấp chọn mẫu để xem ngay bản demo cập nhật trực tiếp bên phải.
        </p>
      </div>

      <div className="space-y-2.5 pt-1">
        {templates?.map((tpl) => {
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
              : tpl.category === 'essay'
              ? 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20'
              : 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20'

          return (
            <div
              key={tpl.id}
              onClick={() => onSelectTemplate(tpl.id)}
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
                      : tpl.category === 'essay'
                      ? 'Bài luận'
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
  )
}
