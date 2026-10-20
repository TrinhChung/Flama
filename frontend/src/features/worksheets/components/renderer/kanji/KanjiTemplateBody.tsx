import type {
  WorksheetItem,
  WorksheetKanjiCompoundItem,
  WorksheetKanjiItem,
  WorksheetKanjiStepItem,
  WorksheetLayoutOptions,
  WorksheetTemplate,
} from '../../../types'
import { stackJustifyClass, type PageMetrics } from '../pageMetrics'
import { KanjiCompoundRow } from './KanjiCompoundRow'
import { KanjiSingleRow } from './KanjiSingleRow'
import { KanjiStepRow } from './KanjiStepRow'

/** Rows of every kanji-category template, laid out to fill the page. */
export function KanjiTemplateBody({
  template,
  items,
  options,
  metrics,
}: {
  template: WorksheetTemplate
  items: WorksheetItem[]
  options: WorksheetLayoutOptions
  metrics: PageMetrics
}) {
  const justifyClass = stackJustifyClass(
    options,
    items.length,
    metrics.isLandscape,
    { stretch: [4, 5], dense: [8, 13] },
    'justify-start gap-1 sm:gap-1.5',
  )

  return (
    <div className={`flex-1 flex flex-col ${justifyClass}`}>
      {items.map((rawItem, idx) => {
        const key = `${rawItem?.note_id || 'row'}-${idx}`
        if (template.id === 'kanji_compound') {
          return (
            <KanjiCompoundRow
              key={key}
              item={(rawItem || {}) as WorksheetKanjiCompoundItem}
              options={options}
              metrics={metrics}
            />
          )
        }
        if (template.id === 'kanji_step_by_step') {
          return (
            <KanjiStepRow
              key={key}
              item={(rawItem || {}) as WorksheetKanjiStepItem}
              options={options}
              metrics={metrics}
            />
          )
        }
        return (
          <KanjiSingleRow
            key={key}
            item={(rawItem || {}) as WorksheetKanjiItem}
            options={options}
            metrics={metrics}
          />
        )
      })}
    </div>
  )
}
