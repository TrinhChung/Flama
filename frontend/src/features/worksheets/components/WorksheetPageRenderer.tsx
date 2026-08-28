import { memo } from 'react'
import type {
  WorksheetKanjiItem,
  WorksheetLayoutOptions,
  WorksheetPageData,
  WorksheetRecallItem,
  WorksheetTableRowItem,
  WorksheetTemplate,
  WorksheetVocabItem,
} from '../types'
import { KanjiGridBox } from './KanjiGridBox'

export interface WorksheetPageRendererProps {
  page: WorksheetPageData
  template: WorksheetTemplate
  options: WorksheetLayoutOptions
  fieldMapping?: Record<string, string | string[]>
  zoom?: number
  isPrintMode?: boolean
}

export const WorksheetPageRenderer = memo(function WorksheetPageRenderer({
  page,
  template,
  options,
  fieldMapping = {},
  zoom = 1,
  isPrintMode = false,
}: WorksheetPageRendererProps) {
  const { header, items, page_number, total_pages } = page
  const orientation = options.orientation || 'portrait'
  const isLandscape = orientation === 'landscape'
  const gridStyle = options.grid_style || 'cross'
  const traceCount = Math.max(0, options.trace_count ?? 2)
  const practiceCount = Math.max(1, options.practice_count ?? 5)
  const boxSize = template.id === 'kanji_compact' ? 44 : 52

  return (
    <div
      style={{
        transform: isPrintMode ? undefined : `scale(${zoom})`,
        transformOrigin: 'top center',
      }}
      className={`bg-white text-slate-900 mx-auto shadow-md border border-border/80 flex flex-col justify-between transition-transform duration-150 select-none ${
        isLandscape
          ? 'w-[297mm] min-h-[210mm] max-w-full'
          : 'w-[210mm] min-h-[297mm] max-w-full'
      } ${
        options.margin === 'compact'
          ? 'p-[10mm]'
          : options.margin === 'wide'
          ? 'p-[18mm]'
          : 'p-[12mm]'
      }`}
    >
      {/* Header Block */}
      <header className="border-b-2 border-slate-900 pb-2 mb-3.5 flex justify-between items-end shrink-0">
        <div>
          <h1 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight leading-tight">
            {header.title || 'Flama Worksheet'}
          </h1>
          {header.subtitle && (
            <p className="text-[11px] text-slate-500 mt-0.5">{header.subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-700 font-medium shrink-0">
          {header.show_student_info && (
            <span>
              <strong className="text-slate-900">Họ tên:</strong> _______________
            </span>
          )}
          {header.show_date && (
            <span>
              <strong className="text-slate-900">Ngày:</strong> ___/___/20___
            </span>
          )}
          <span className="text-slate-500 font-normal">
            Trang {page_number} / {total_pages}
          </span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col justify-start">
        {/* Category: Kanji Templates */}
        {template.category === 'kanji' && (
          <div className="flex flex-col gap-2.5">
            {items.map((rawItem, idx) => {
              const item = rawItem as WorksheetKanjiItem
              return (
                <div
                  key={`${item.note_id}-${item.char}-${idx}`}
                  className="border border-slate-200 rounded-lg p-2 bg-white flex flex-col gap-1.5"
                >
                  <div className="flex items-center gap-2.5 flex-wrap sm:flex-nowrap">
                    {/* 1. Reference Kanji */}
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">
                        Mẫu
                      </span>
                      <KanjiGridBox
                        char={item.char}
                        gridStyle={gridStyle}
                        isTrace={false}
                        size={boxSize}
                      />
                    </div>

                    {/* 2. Stroke Order Box */}
                    {options.show_stroke_diagram !== false && (
                      <div className="flex flex-col items-center gap-1">
                        <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">
                          Thứ tự nét
                        </span>
                        {item.stroke_svg ? (
                          <div
                            className="shrink-0 rounded-[4px] bg-white border border-slate-400 p-0.5 flex items-center justify-center"
                            style={{ width: boxSize, height: boxSize }}
                            dangerouslySetInnerHTML={{ __html: item.stroke_svg }}
                          />
                        ) : (
                          <KanjiGridBox
                            char={item.char}
                            gridStyle={gridStyle}
                            isTrace={false}
                            size={boxSize}
                          />
                        )}
                      </div>
                    )}

                    {/* 3. Tracing Boxes */}
                    {traceCount > 0 && (
                      <div className="flex flex-col items-center gap-1">
                        <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">
                          Đồ chữ
                        </span>
                        <div className="flex gap-1">
                          {Array.from({ length: traceCount }).map((_, tIdx) => (
                            <KanjiGridBox
                              key={tIdx}
                              char={item.char}
                              gridStyle={gridStyle}
                              isTrace={true}
                              size={boxSize}
                            />
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 4. Blank Practice Boxes */}
                    <div className="flex flex-col items-center gap-1 flex-1">
                      <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">
                        Tự viết
                      </span>
                      <div className="flex gap-1 flex-wrap">
                        {Array.from({ length: practiceCount }).map((_, pIdx) => (
                          <KanjiGridBox
                            key={pIdx}
                            char=""
                            gridStyle={gridStyle}
                            isBlank={true}
                            size={boxSize}
                          />
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Metadata Row (Reading & Meaning) */}
                  {(item.reading || item.meaning) && (
                    <div className="flex items-center gap-3 pt-1 border-t border-dashed border-slate-100 text-[11px] text-slate-700">
                      {item.reading && options.show_reading !== false && (
                        <span>
                          <strong className="text-slate-500 text-[10px]">Âm:</strong>{' '}
                          {item.reading}
                        </span>
                      )}
                      {item.meaning && options.show_meaning !== false && (
                        <span>
                          <strong className="text-slate-500 text-[10px]">Nghĩa:</strong>{' '}
                          {item.meaning}
                        </span>
                      )}
                      {item.source_word && item.source_word !== item.char && (
                        <span className="text-slate-400 italic">
                          ({item.source_word})
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Category: Vocabulary Writing Template */}
        {template.id === 'vocab_writing' && (
          <table className="w-full border-collapse text-xs border border-slate-300">
            <thead>
              <tr className="bg-slate-100 text-slate-800 text-left font-semibold">
                <th className="border border-slate-300 p-2 w-[24%]">Từ vựng</th>
                <th className="border border-slate-300 p-2 w-[22%]">Cách đọc</th>
                <th className="border border-slate-300 p-2 w-[26%]">Ý nghĩa</th>
                <th className="border border-slate-300 p-2 w-[28%]">Luyện viết</th>
              </tr>
            </thead>
            <tbody>
              {items.map((rawItem, idx) => {
                const item = rawItem as WorksheetVocabItem
                const boxesCnt = Math.max(1, options.practice_boxes_count ?? 5)
                return (
                  <tr key={`${item.note_id}-${idx}`} className="border-b border-slate-300">
                    <td className="border border-slate-300 p-2 font-bold text-sm text-slate-900">
                      {item.word}
                    </td>
                    <td className="border border-slate-300 p-2 text-slate-700">
                      {item.reading}
                    </td>
                    <td className="border border-slate-300 p-2 text-slate-700">
                      {item.meaning}
                    </td>
                    <td className="border border-slate-300 p-1.5">
                      <div className="flex gap-1">
                        {Array.from({ length: boxesCnt }).map((_, bIdx) => (
                          <div
                            key={bIdx}
                            className="size-7 rounded border border-dashed border-slate-300 bg-white"
                          />
                        ))}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {/* Category: Recall Cloze Template */}
        {template.id === 'vocab_recall' && (
          <table className="w-full border-collapse text-xs border border-slate-300">
            <thead>
              <tr className="bg-slate-100 text-slate-800 text-left font-semibold">
                <th className="border border-slate-300 p-2 w-1/2">
                  Gợi ý (Ý nghĩa / Âm đọc)
                </th>
                <th className="border border-slate-300 p-2 w-1/2">
                  Từ vựng mục tiêu (Tự nhớ & Viết lại)
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((rawItem, idx) => {
                const item = rawItem as WorksheetRecallItem
                return (
                  <tr key={`${item.note_id}-${idx}`} className="border-b border-slate-300">
                    <td className="border border-slate-300 p-2.5">
                      <div className="font-semibold text-slate-900 text-sm">
                        {item.meaning}
                      </div>
                      {item.reading && options.show_reading_hint !== false && (
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          {item.reading}
                        </div>
                      )}
                    </td>
                    <td className="border border-slate-300 p-2.5">
                      <div className="w-full min-h-[26px] border-b border-dashed border-slate-400" />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {/* Category: Custom Deck Table Template */}
        {template.id === 'deck_table' && (
          <table className="w-full border-collapse text-xs border border-slate-300">
            <thead>
              <tr className="bg-slate-100 text-slate-800 text-left font-semibold">
                {(() => {
                  const rawCols = fieldMapping.custom_columns || []
                  const cols = Array.isArray(rawCols) ? rawCols : String(rawCols).split(',')
                  return cols.map((col, cIdx) => (
                    <th key={cIdx} className="border border-slate-300 p-2">
                      {col}
                    </th>
                  ))
                })()}
                {options.include_practice_column !== false && (
                  <th className="border border-slate-300 p-2">
                    {options.practice_column_label || 'Ghi chú / Luyện viết'}
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {items.map((rawItem, idx) => {
                const item = rawItem as WorksheetTableRowItem
                const rawCols = fieldMapping.custom_columns || []
                const cols = Array.isArray(rawCols) ? rawCols : String(rawCols).split(',')
                return (
                  <tr key={`${item.note_id}-${idx}`} className="border-b border-slate-300">
                    {cols.map((col, cIdx) => (
                      <td key={cIdx} className="border border-slate-300 p-2 text-slate-800">
                        {item.data[col] || ''}
                      </td>
                    ))}
                    {options.include_practice_column !== false && (
                      <td className="border border-slate-300 p-2">
                        <div className="w-full min-h-[22px] border-b border-dashed border-slate-300" />
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </main>

      {/* Footer Block */}
      <footer className="border-t border-slate-200 pt-1.5 mt-3.5 flex justify-between items-center text-[9px] text-slate-400 shrink-0">
        <span>Flama Worksheet Generator &bull; flama.app</span>
        <span>
          Trang {page_number} / {total_pages}
        </span>
      </footer>
    </div>
  )
})
