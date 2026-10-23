import { useTranslation } from 'react-i18next'
import type {
  WorksheetItem,
  WorksheetLayoutOptions,
  WorksheetRecallItem,
  WorksheetVocabItem,
} from '../../types'
import { KanjiGridBox } from '../KanjiGridBox'

/** Column widths of the vocab table, rebalanced when reading/meaning columns are hidden. */
function vocabColumnWidths(showReading: boolean, showMeaning: boolean) {
  if (!showReading && !showMeaning) {
    return { word: 'w-[35%]', reading: 'w-[20%]', meaning: 'w-[28%]', practice: 'w-[65%]' }
  }
  if (!showReading) {
    return { word: 'w-[28%]', reading: 'w-[20%]', meaning: 'w-[32%]', practice: 'w-[40%]' }
  }
  if (!showMeaning) {
    return { word: 'w-[28%]', reading: 'w-[32%]', meaning: 'w-[28%]', practice: 'w-[40%]' }
  }
  return { word: 'w-[22%]', reading: 'w-[20%]', meaning: 'w-[28%]', practice: 'w-[30%]' }
}

export function VocabWritingTable({
  items,
  options,
  isLandscape,
}: {
  items: WorksheetItem[]
  options: WorksheetLayoutOptions
  isLandscape: boolean
}) {
  const { t } = useTranslation('worksheets')
  const showReading = options.show_reading !== false
  const showMeaning = options.show_meaning !== false
  const practiceType = options.practice_type || 'boxes'
  const boxesCnt = Math.max(1, options.practice_boxes_count ?? (isLandscape ? 10 : 6))
  const widths = vocabColumnWidths(showReading, showMeaning)

  return (
    <table className="w-full border-collapse text-xs border border-slate-400">
      <thead>
        <tr className="bg-slate-100 text-slate-900 text-left font-semibold">
          <th className={`border border-slate-400 px-2 py-1 ${widths.word} text-xs`}>
            {t('renderer.table_vocab', 'Từ vựng')}
          </th>
          {showReading && (
            <th className={`border border-slate-400 px-2 py-1 ${widths.reading} text-xs`}>
              {t('renderer.table_reading', 'Cách đọc')}
            </th>
          )}
          {showMeaning && (
            <th className={`border border-slate-400 px-2 py-1 ${widths.meaning} text-xs`}>
              {t('renderer.table_meaning', 'Ý nghĩa')}
            </th>
          )}
          <th className={`border border-slate-400 px-2 py-1 ${widths.practice} text-xs`}>
            {t('renderer.table_practice', 'Luyện viết')}
          </th>
        </tr>
      </thead>
      <tbody>
        {items.map((rawItem, idx) => {
          const item = (rawItem || {}) as WorksheetVocabItem
          const word = item.word || (typeof item === 'object' && 'char' in item ? (item as any).char : '')

          return (
            <tr key={`${item.note_id || idx}-${idx}`} className="border-b border-slate-300">
              <td className="border border-slate-300 px-2 py-1 font-bold text-sm text-slate-900">
                {word}
              </td>
              {showReading && (
                <td className="border border-slate-300 px-2 py-1 text-slate-700 text-xs">
                  {item.reading || ''}
                </td>
              )}
              {showMeaning && (
                <td className="border border-slate-300 px-2 py-1 text-slate-700 text-xs">
                  {item.meaning || ''}
                </td>
              )}
              <td className="border border-slate-300 p-1">
                {practiceType === 'lines' ? (
                  <div className="w-full min-h-[24px] border-b border-dashed border-slate-400" />
                ) : practiceType === 'grid' ? (
                  <div className="flex -space-x-px border border-slate-400 rounded-xs overflow-hidden w-fit">
                    {Array.from({ length: boxesCnt }).map((_, bIdx) => (
                      <KanjiGridBox
                        key={bIdx}
                        char=""
                        gridStyle="cross"
                        size={24}
                        isBlank
                        rounded={false}
                        strokeColor="#94a3b8"
                      />
                    ))}
                  </div>
                ) : (
                  <div className="flex -space-x-px border border-slate-400 rounded-xs overflow-hidden w-fit">
                    {Array.from({ length: boxesCnt }).map((_, bIdx) => (
                      <div
                        key={bIdx}
                        className="size-6 sm:size-6.5 border-r border-slate-300 bg-white"
                      />
                    ))}
                  </div>
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

/** Cloze recall: hint on the left, empty line or length-hint boxes on the right. */
export function VocabRecallTable({
  items,
  options,
}: {
  items: WorksheetItem[]
  options: WorksheetLayoutOptions
}) {
  const { t } = useTranslation('worksheets')
  const showBoxes = options.recall_answer_style === 'boxes' || options.show_word_length_hint

  return (
    <table className="w-full border-collapse text-xs border border-slate-400">
      <thead>
        <tr className="bg-slate-100 text-slate-900 text-left font-semibold">
          <th className="border border-slate-400 px-2 py-1.5 w-1/2 text-xs">
            {t('renderer.cloze_hint', 'Gợi ý (Ý nghĩa / Âm đọc)')}
          </th>
          <th className="border border-slate-400 px-2 py-1.5 w-1/2 text-xs">
            {t('renderer.cloze_target', 'Từ vựng mục tiêu (Tự nhớ & Viết lại)')}
          </th>
        </tr>
      </thead>
      <tbody>
        {items.map((rawItem, idx) => {
          const item = (rawItem || {}) as WorksheetRecallItem
          const wordLen = item.word_length || (item.word ? item.word.length : 4)

          return (
            <tr key={`${item.note_id || idx}-${idx}`} className="border-b border-slate-300">
              <td className="border border-slate-300 px-2 py-1.5">
                <div className="font-semibold text-slate-900 text-sm">
                  {item.meaning || ''}
                </div>
                {item.reading && options.show_reading_hint !== false && (
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {item.reading}
                  </div>
                )}
              </td>
              <td className="border border-slate-300 px-2 py-1.5">
                {showBoxes ? (
                  <div className="flex items-center gap-1">
                    {Array.from({ length: Math.max(1, Math.min(12, wordLen)) }).map((_, bIdx) => (
                      <div
                        key={bIdx}
                        className="size-5.5 border border-slate-400 rounded-xs bg-white"
                      />
                    ))}
                  </div>
                ) : (
                  <div className="w-full min-h-[22px] border-b border-dashed border-slate-400" />
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
