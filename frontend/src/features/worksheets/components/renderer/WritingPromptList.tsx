import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { WorksheetItem, WorksheetLayoutOptions } from '../../types'
import { stackJustifyClass } from './pageMetrics'

/** Prompt banner shown above sentence and grammar exercises. */
export function ExercisePromptBanner({ prompt }: { prompt: string }) {
  const { t } = useTranslation('worksheets')
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 flex items-start gap-2.5 text-xs text-amber-950 mb-2.5 shadow-2xs">
      <span className="text-base font-bold leading-none select-none">📝</span>
      <div className="flex-1">
        <span className="font-bold uppercase tracking-wider text-[9.5px] text-amber-800 block mb-0.5">
          {t('renderer.exercise_prompt_label', 'Đề bài / Yêu cầu bài tập:')}
        </span>
        <span className="font-semibold text-xs leading-relaxed text-slate-800">
          {prompt}
        </span>
      </div>
    </div>
  )
}

/** Ruled or dashed lines where the student writes the answer. */
function WritingLines({ options, className }: { options: WorksheetLayoutOptions; className: string }) {
  const linesCnt = Math.max(1, Math.min(10, Number(options.writing_lines_count ?? 3)))
  const borderStyleClass = (options.writing_line_style || 'dashed') === 'solid' ? 'border-solid' : 'border-dashed'
  return (
    <div className={className}>
      {Array.from({ length: linesCnt }).map((_, lIdx) => (
        <div
          key={`line-${lIdx}`}
          className={`w-full min-h-[20px] border-b border-slate-400 ${borderStyleClass}`}
        />
      ))}
    </div>
  )
}

function WritingPromptCard({
  badge,
  badgeClass,
  linesClass,
  options,
  children,
}: {
  badge: ReactNode
  badgeClass: string
  linesClass: string
  options: WorksheetLayoutOptions
  children: ReactNode
}) {
  return (
    <div className="border border-slate-300 rounded-lg p-2.5 bg-white flex flex-col gap-1.5 shadow-2xs">
      <div className="flex items-start gap-2">
        <span className={badgeClass}>{badge}</span>
        <div className="flex-1 min-w-0">{children}</div>
      </div>

      {/* Ruled / dashed writing lines for student */}
      <WritingLines options={options} className={linesClass} />
    </div>
  )
}

/** Sentence-writing and grammar-practice cards, each followed by answer lines. */
export function WritingPromptList({
  variant,
  items,
  options,
  isLandscape,
}: {
  variant: 'sentence' | 'grammar'
  items: WorksheetItem[]
  options: WorksheetLayoutOptions
  isLandscape: boolean
}) {
  const { t } = useTranslation('worksheets')
  const justifyClass = stackJustifyClass(
    options,
    items.length,
    isLandscape,
    { stretch: [3, 4], dense: [4, 6] },
    'justify-start gap-1.5 sm:gap-2',
  )

  return (
    <div className={`flex-1 flex flex-col ${justifyClass}`}>
      {items.map((rawItem, idx) => {
        const item = rawItem as any
        const key = `${item.note_id || idx}-${idx}`

        if (variant === 'sentence') {
          return (
            <WritingPromptCard
              key={key}
              badge={<>#{idx + 1}</>}
              badgeClass="text-[10px] font-bold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200 shrink-0"
              linesClass="flex flex-col gap-2 pt-1"
              options={options}
            >
              {options.show_sample_sentence !== false && item.sentence && (
                <div className="text-sm font-bold text-slate-900 leading-snug">
                  {item.sentence}
                </div>
              )}
              {options.show_sample_reading !== false && item.reading && (
                <div className="text-[10px] text-slate-500 font-medium">
                  {item.reading}
                </div>
              )}
              {options.show_sample_meaning !== false && item.meaning && (
                <div className="text-xs text-slate-700 font-normal mt-0.5">
                  {item.meaning}
                </div>
              )}
            </WritingPromptCard>
          )
        }

        return (
          <WritingPromptCard
            key={key}
            badge={t('renderer.grammar_structure_index', {
              index: idx + 1,
              defaultValue: `Cấu trúc #${idx + 1}`,
            })}
            badgeClass="text-[10px] font-bold text-amber-800 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 shrink-0"
            linesClass="flex flex-col gap-2 pt-0.5"
            options={options}
          >
            <div className="text-sm font-bold text-slate-900 leading-snug">
              {item.grammar_point || item.word || ''}
            </div>
            {options.show_explanation !== false && item.meaning_usage && (
              <div className="text-xs text-slate-600 mt-0.5">
                {item.meaning_usage}
              </div>
            )}
            {options.show_example_hint !== false && item.example && (
              <div className="text-xs text-slate-500 mt-1 bg-slate-50 border-l-2 border-slate-400 px-2 py-1 rounded-r">
                <span className="font-semibold text-slate-700">
                  {t('renderer.example_label', 'Ví dụ: ')}
                </span>
                {item.example}
              </div>
            )}
          </WritingPromptCard>
        )
      })}
    </div>
  )
}
