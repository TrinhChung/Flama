import { memo } from 'react'
import { Table as TableIcon } from 'lucide-react'
import type {
  WorksheetGrammarItem,
  WorksheetKanjiItem,
  WorksheetLayoutOptions,
  WorksheetPageData,
  WorksheetRecallItem,
  WorksheetSentenceItem,
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
  const boxSize = options.box_size || (isLandscape ? 38 : (template.id === 'kanji_compact' ? 30 : 36))
  const traceCount = Math.max(0, options.trace_count ?? (template.id === 'kanji_compact' ? 1 : 2))

  // Exact width of the top row component based on paper width and margins
  const marginType = options.margin || 'compact'
  const marginMm =
    marginType === 'minimal' || marginType === 'ultra_compact'
      ? 8
      : marginType === 'compact'
      ? 12
      : marginType === 'wide'
      ? 28
      : 20
  const paddingClass =
    marginType === 'minimal' || marginType === 'ultra_compact'
      ? 'p-[4mm]'
      : marginType === 'compact'
      ? 'p-[6mm]'
      : marginType === 'wide'
      ? 'p-[14mm]'
      : 'p-[10mm]'
  const usableWidthMm = (isLandscape ? 297 : 210) - marginMm
  const topComponentWidthPx = Math.floor(usableWidthMm * 3.7795)

  // Divide top component width by box size for the optimal number of boxes
  const fullRowBoxesCount = Math.max(1, Math.floor(topComponentWidthPx / (boxSize - 1)))

  // Practice boxes count for top row practice strip
  const strokeBoxWidth = options.show_stroke_diagram !== false ? boxSize : 0
  const pillMaxWidth = Math.max(40, Math.min(130, Math.round(boxSize * 2.8)))
  const leftInfoWidth = boxSize + strokeBoxWidth + pillMaxWidth + 28
  const remainingWidth = Math.max(80, topComponentWidthPx - leftInfoWidth)
  const autoPracticeCount = Math.max(
    1,
    Math.floor(remainingWidth / (boxSize - 1)) - traceCount,
  )
  const practiceCount = options.practice_count ?? autoPracticeCount

  // Watermark options (Mandatory anti-theft protection)
  const watermarkText = (
    options.watermark_text ||
    (typeof window !== 'undefined' ? window.location.hostname : 'flama.app') ||
    'flama.app'
  ).toUpperCase()
  const watermarkOpacity = Math.max(0.015, Math.min(0.15, options.watermark_opacity ?? 0.04))
  const watermarkLayout = options.watermark_layout || 'diagonal_grid'

  return (
    <div
      style={{
        transform: isPrintMode || zoom === 1 ? undefined : `scale(${zoom})`,
        transformOrigin: 'top left',
      }}
      className={`bg-white text-slate-900 mx-auto shadow-2xl border border-slate-300/80 flex flex-col justify-between select-none box-border shrink-0 print:shadow-none print:border-none print:m-0 font-['Segoe_UI',-apple-system,BlinkMacSystemFont,Roboto,'Noto_Sans','Noto_Sans_JP','Hiragino_Kaku_Gothic_ProN','Yu_Gothic','Meiryo',sans-serif] relative overflow-hidden ${
        isLandscape
          ? 'w-[297mm] min-h-[210mm] max-h-[210mm]'
          : 'w-[210mm] min-h-[297mm] max-h-[297mm]'
      } ${paddingClass}`}
    >
      {/* Watermark: Refined Non-Distracting Overlays (Mandatory Protection) */}
      {watermarkLayout === 'diagonal_grid' && (
        <div
          aria-hidden="true"
          className="absolute -top-[25%] -left-[25%] w-[150%] h-[150%] pointer-events-none select-none z-30 flex flex-col justify-between overflow-hidden py-4"
          style={{ opacity: watermarkOpacity }}
        >
          {Array.from({ length: 8 }).map((_, rIdx) => (
            <div
              key={`wm-row-${rIdx}`}
              className="flex justify-around whitespace-nowrap font-medium text-[12px] sm:text-[13px] tracking-[6px] text-slate-700"
              style={{
                transform: `rotate(-28deg) translateX(${rIdx % 2 === 0 ? '0px' : '-70px'})`,
              }}
            >
              {Array.from({ length: 6 }).map((_, cIdx) => (
                <span key={`wm-token-${cIdx}`} className="px-8">
                  {watermarkText} &bull;
                </span>
              ))}
            </div>
          ))}
        </div>
      )}

      {watermarkLayout === 'margin_bounds' && (
        <div
          aria-hidden="true"
          className="absolute inset-0 pointer-events-none select-none z-30 flex justify-between overflow-hidden p-1"
          style={{ opacity: watermarkOpacity * 1.5 }}
        >
          {/* Left margin vertical stripe */}
          <div className="flex flex-col justify-around text-[10px] tracking-[3px] font-semibold text-slate-700 [writing-mode:vertical-rl] rotate-180 select-none">
            <span>{watermarkText} &bull; FLAMA WORKSHEET &bull; {watermarkText}</span>
            <span>{watermarkText} &bull; FLAMA WORKSHEET &bull; {watermarkText}</span>
          </div>

          {/* Right margin vertical stripe */}
          <div className="flex flex-col justify-around text-[10px] tracking-[3px] font-semibold text-slate-700 [writing-mode:vertical-rl] select-none">
            <span>{watermarkText} &bull; FLAMA WORKSHEET &bull; {watermarkText}</span>
            <span>{watermarkText} &bull; FLAMA WORKSHEET &bull; {watermarkText}</span>
          </div>
        </div>
      )}

      {/* Header Block */}
      <header className="border-b-2 border-slate-900 pb-1.5 mb-2.5 flex justify-between items-end shrink-0 relative z-10">
        <div>
          <h1 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight leading-tight">
            {header.title || 'Flama Worksheet'}
          </h1>
          {header.subtitle && (
            <p className="text-[10px] text-slate-500 mt-0.5">{header.subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-3 text-[10px] text-slate-700 font-medium shrink-0">
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
      <main className="flex-1 flex flex-col justify-start relative z-10">
        {/* Top Exercise Prompt Banner for Grammar and Sentence Worksheets */}
        {options.exercise_prompt &&
          (template.id === 'grammar_practice' || template.id === 'sentence_writing') && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 flex items-start gap-2.5 text-xs text-amber-950 mb-2.5 shadow-2xs">
              <span className="text-base font-bold leading-none select-none">📝</span>
              <div className="flex-1">
                <span className="font-bold uppercase tracking-wider text-[9.5px] text-amber-800 block mb-0.5">
                  Đề bài / Yêu cầu bài tập:
                </span>
                <span className="font-semibold text-xs leading-relaxed text-slate-800">
                  {options.exercise_prompt}
                </span>
              </div>
            </div>
          )}

        {/* Category: Kanji Templates */}
        {template.category === 'kanji' && (
          <div className="flex flex-col gap-1.5">
            {items.map((rawItem, idx) => {
              const item = (rawItem || {}) as WorksheetKanjiItem
              const isFiller = Boolean(item.is_blank_filler)
              const char = item.char || (typeof item === 'object' && 'word' in item ? (item as any).word : '')
              const extraBlanks = Math.max(
                0,
                Math.min(3, Number(item.extra_blank_rows ?? options.extra_blank_rows ?? 0)),
              )

              // Blank filler row: direct continuous guideline grid strip!
              if (isFiller || (!char && !item.reading && !item.meaning)) {
                return (
                  <div key={`blank-filler-${idx}`} className="flex flex-col gap-1 w-full">
                    <div className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden w-fit shadow-2xs">
                      {Array.from({ length: fullRowBoxesCount }).map((_, bIdx) => (
                        <KanjiGridBox
                          key={`filler-box-${bIdx}`}
                          char=""
                          gridStyle={gridStyle}
                          isBlank={true}
                          size={boxSize}
                          rounded={false}
                          strokeColor="#cbd5e1"
                        />
                      ))}
                    </div>
                    {extraBlanks > 0 &&
                      Array.from({ length: extraBlanks }).map((_, eIdx) => (
                        <div
                          key={`filler-extra-${eIdx}`}
                          className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden w-fit shadow-2xs"
                        >
                          {Array.from({ length: fullRowBoxesCount }).map((_, bIdx) => (
                            <KanjiGridBox
                              key={`filler-extra-box-${bIdx}`}
                              char=""
                              gridStyle={gridStyle}
                              isBlank={true}
                              size={boxSize}
                              rounded={false}
                              strokeColor="#cbd5e1"
                            />
                          ))}
                        </div>
                      ))}
                  </div>
                )
              }

              return (
                <div key={`${item.note_id || idx}-${char || 'blank'}-${idx}`} className="flex flex-col gap-1">
                  <div className="border border-slate-200 rounded-md p-1.5 bg-white flex items-center justify-between gap-2 overflow-hidden">
                    {/* Left Info Column: Mẫu + Thứ tự nét + Âm/Nghĩa */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      {/* 1. Reference Kanji */}
                      <div className="flex flex-col items-center">
                        <KanjiGridBox
                          char={char}
                          gridStyle={gridStyle}
                          isTrace={false}
                          size={boxSize}
                          rounded={true}
                          strokeColor="#0f172a"
                        />
                      </div>

                      {/* 2. Stroke Order Box */}
                      {options.show_stroke_diagram !== false && (
                        <div className="flex flex-col items-center">
                          {item.stroke_svg ? (
                            <div
                              className="shrink-0 rounded-[3px] bg-white border border-slate-700 p-0.5 flex items-center justify-center"
                              style={{ width: boxSize, height: boxSize }}
                              dangerouslySetInnerHTML={{ __html: item.stroke_svg }}
                            />
                          ) : (
                            <KanjiGridBox
                              char={char}
                              gridStyle={gridStyle}
                              isTrace={false}
                              size={boxSize}
                              rounded={true}
                              strokeColor="#475569"
                            />
                          )}
                        </div>
                      )}

                      {/* Metadata Pill: Scales proportionally with boxSize */}
                      {(item.reading || item.meaning) && (
                        <div
                          className="flex flex-col justify-center px-1 leading-tight overflow-hidden"
                          style={{
                            maxWidth: Math.max(40, Math.min(130, Math.round(boxSize * 2.8))),
                          }}
                        >
                          {item.reading && options.show_reading !== false && (
                            <span
                              className="font-semibold text-slate-900 truncate"
                              style={{
                                fontSize: `${Math.max(6, Math.min(11, Math.round(boxSize * 0.3)))}px`,
                                lineHeight: 1.15,
                              }}
                              title={item.reading}
                            >
                              {item.reading}
                            </span>
                          )}
                          {item.meaning && options.show_meaning !== false && (
                            <span
                              className="text-slate-500 truncate"
                              style={{
                                fontSize: `${Math.max(5.5, Math.min(10, Math.round(boxSize * 0.25)))}px`,
                                lineHeight: 1.15,
                              }}
                              title={item.meaning}
                            >
                              {item.meaning}
                            </span>
                          )}
                          {item.source_word && item.source_word !== char && (
                            <span
                              className="text-slate-400 italic truncate"
                              style={{
                                fontSize: `${Math.max(5, Math.min(9, Math.round(boxSize * 0.23)))}px`,
                                lineHeight: 1.1,
                              }}
                            >
                              ({item.source_word})
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Right Continuous Grid Strip: Tracing + Blank Boxes (Connected Seamlessly) */}
                    <div className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden shrink-0">
                      {/* 3. Tracing Boxes */}
                      {Array.from({ length: traceCount }).map((_, tIdx) => (
                        <KanjiGridBox
                          key={`trace-${tIdx}`}
                          char={char}
                          gridStyle={gridStyle}
                          isTrace={true}
                          size={boxSize}
                          rounded={false}
                          strokeColor="#cbd5e1"
                        />
                      ))}

                      {/* 4. Blank Practice Boxes */}
                      {Array.from({ length: practiceCount }).map((_, pIdx) => (
                        <KanjiGridBox
                          key={`practice-${pIdx}`}
                          char=""
                          gridStyle={gridStyle}
                          isBlank={true}
                          size={boxSize}
                          rounded={false}
                          strokeColor="#cbd5e1"
                        />
                      ))}
                    </div>
                  </div>

                  {/* Extra Blank Practice Rows Underneath (Direct continuous strip) */}
                  {extraBlanks > 0 && (
                    <div className="flex flex-col gap-1">
                      {Array.from({ length: extraBlanks }).map((_, eIdx) => (
                        <div
                          key={`extra-blank-${eIdx}`}
                          className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden w-fit shadow-2xs"
                        >
                          {Array.from({ length: fullRowBoxesCount }).map((_, bIdx) => (
                            <KanjiGridBox
                              key={`extra-b-${bIdx}`}
                              char=""
                              gridStyle={gridStyle}
                              isBlank={true}
                              size={boxSize}
                              rounded={false}
                              strokeColor="#cbd5e1"
                            />
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Category: Vocabulary Writing Template */}
        {template.id === 'vocab_writing' && (
          <table className="w-full border-collapse text-xs border border-slate-400">
            <thead>
              <tr className="bg-slate-100 text-slate-900 text-left font-semibold">
                <th className="border border-slate-400 px-2 py-1 w-[22%] text-xs">Từ vựng</th>
                <th className="border border-slate-400 px-2 py-1 w-[20%] text-xs">Cách đọc</th>
                <th className="border border-slate-400 px-2 py-1 w-[24%] text-xs">Ý nghĩa</th>
                <th className="border border-slate-400 px-2 py-1 text-xs">Ô luyện viết liên tiếp</th>
              </tr>
            </thead>
            <tbody>
              {items.map((rawItem, idx) => {
                const item = (rawItem || {}) as WorksheetVocabItem
                const word = item.word || (typeof item === 'object' && 'char' in item ? (item as any).char : '')
                const boxesCnt = Math.max(1, options.practice_boxes_count ?? (isLandscape ? 10 : 6))

                return (
                  <tr key={`${item.note_id || idx}-${idx}`} className="border-b border-slate-300">
                    <td className="border border-slate-300 px-2 py-1 font-bold text-sm text-slate-900">
                      {word}
                    </td>
                    <td className="border border-slate-300 px-2 py-1 text-slate-700 text-xs">
                      {item.reading || ''}
                    </td>
                    <td className="border border-slate-300 px-2 py-1 text-slate-700 text-xs">
                      {item.meaning || ''}
                    </td>
                    <td className="border border-slate-300 p-1">
                      <div className="flex -space-x-px border border-slate-400 rounded-xs overflow-hidden w-fit">
                        {Array.from({ length: boxesCnt }).map((_, bIdx) => (
                          <div
                            key={bIdx}
                            className="size-6 sm:size-6.5 border-r border-slate-300 bg-white"
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
          <table className="w-full border-collapse text-xs border border-slate-400">
            <thead>
              <tr className="bg-slate-100 text-slate-900 text-left font-semibold">
                <th className="border border-slate-400 px-2 py-1.5 w-1/2 text-xs">
                  Gợi ý (Ý nghĩa / Âm đọc)
                </th>
                <th className="border border-slate-400 px-2 py-1.5 w-1/2 text-xs">
                  Từ vựng mục tiêu (Tự nhớ & Viết lại)
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((rawItem, idx) => {
                const item = (rawItem || {}) as WorksheetRecallItem
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
                      <div className="w-full min-h-[22px] border-b border-dashed border-slate-400" />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {/* Category: Custom Deck Table Template */}
        {template.id === 'deck_table' && (
          (() => {
            const rawCols = fieldMapping.custom_columns || []
            const cols = Array.isArray(rawCols)
              ? rawCols
              : String(rawCols).split(',').map((s) => s.trim()).filter(Boolean)

            if (cols.length === 0) {
              return (
                <div className="w-full border-2 border-dashed border-slate-300 rounded-xl p-8 flex flex-col items-center justify-center text-center gap-2 bg-slate-50/60 my-6">
                  <div className="size-10 rounded-full bg-slate-200 flex items-center justify-center text-slate-500">
                    <TableIcon className="size-5" />
                  </div>
                  <div className="text-sm font-bold text-slate-700">Chưa chọn cột nào để hiển thị</div>
                  <p className="text-xs text-slate-500 max-w-sm">
                    Vui lòng mở tab <strong>&ldquo;Dữ liệu &amp; Trường&rdquo;</strong> ở bảng điều khiển bên trái và tích chọn các trường bạn muốn xuất bảng.
                  </p>
                </div>
              )
            }

            const colWidths = options.column_widths || {}
            const hasAuxCol =
              options.auxiliary_column_enabled !== undefined
                ? options.auxiliary_column_enabled
                : options.include_practice_column !== false
            const auxTitle =
              options.auxiliary_column_title ||
              options.practice_column_label ||
              'Ghi chú / Luyện viết'
            const auxType = options.auxiliary_column_type || 'dashed_line'
            const auxWidth = options.auxiliary_column_width
            const auxBoxesCount = options.auxiliary_column_boxes_count || 4

            const renderAuxiliaryCell = () => {
              if (auxType === 'grid_boxes') {
                return (
                  <div className="flex items-center justify-center -space-x-px border border-slate-600 bg-white rounded-[2px] overflow-hidden w-fit mx-auto shadow-2xs">
                    {Array.from({ length: auxBoxesCount }).map((_, bIdx) => (
                      <KanjiGridBox
                        key={`aux-b-${bIdx}`}
                        char=""
                        gridStyle={gridStyle}
                        isBlank={true}
                        size={22}
                        rounded={false}
                        strokeColor="#cbd5e1"
                      />
                    ))}
                  </div>
                )
              }
              if (auxType === 'checkboxes') {
                return (
                  <div className="flex items-center justify-around gap-1 text-[10px] text-slate-500 font-medium px-1">
                    <span className="flex items-center gap-1">
                      <span className="inline-block size-3.5 rounded-[2px] border border-slate-400 bg-white" /> 1
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="inline-block size-3.5 rounded-[2px] border border-slate-400 bg-white" /> 2
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="inline-block size-3.5 rounded-[2px] border border-slate-400 bg-white" /> 3
                    </span>
                  </div>
                )
              }
              if (auxType === 'double_line') {
                return (
                  <div className="flex flex-col justify-between min-h-[22px] py-1 gap-1.5 w-full">
                    <div className="w-full border-b border-slate-300" />
                    <div className="w-full border-b border-slate-300" />
                  </div>
                )
              }
              if (auxType === 'blank') {
                return <div className="w-full min-h-[20px]" />
              }
              // Default: dashed line
              return <div className="w-full min-h-[20px] border-b border-dashed border-slate-300" />
            }

            return (
              <table className="w-full border-collapse text-xs border border-slate-400 table-fixed">
                <thead>
                  <tr className="bg-slate-100 text-slate-900 text-left font-semibold">
                    {cols.map((col, cIdx) => {
                      const customW = colWidths[col]
                      const wStyle = customW
                        ? typeof customW === 'number'
                          ? `${customW}%`
                          : customW
                        : undefined
                      return (
                        <th
                          key={cIdx}
                          className="border border-slate-400 px-2 py-1.5 text-xs truncate"
                          style={{ width: wStyle }}
                        >
                          {col}
                        </th>
                      )
                    })}
                    {hasAuxCol && (
                      <th
                        className="border border-slate-400 px-2 py-1.5 text-xs text-center truncate"
                        style={{
                          width: auxWidth
                            ? typeof auxWidth === 'number'
                              ? `${auxWidth}%`
                              : auxWidth
                            : undefined,
                        }}
                      >
                        {auxTitle}
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {items.map((rawItem, idx) => {
                    const item = (rawItem || {}) as WorksheetTableRowItem
                    const rowData =
                      item && typeof item === 'object' && 'data' in item && item.data
                        ? item.data
                        : {}

                    return (
                      <tr key={`${item.note_id || idx}-${idx}`} className="border-b border-slate-300">
                        {cols.map((col, cIdx) => (
                          <td
                            key={cIdx}
                            className="border border-slate-300 px-2 py-1.5 text-slate-800 text-xs overflow-hidden break-words"
                          >
                            {rowData[col] ??
                              (typeof item === 'object' && 'word' in item
                                ? (item as any).word
                                : typeof item === 'object' && 'char' in item
                                ? (item as any).char
                                : '')}
                          </td>
                        ))}
                        {hasAuxCol && (
                          <td className="border border-slate-300 px-2 py-1.5 align-middle">
                            {renderAuxiliaryCell()}
                          </td>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )
          })()
        )}

        {/* Category: Sentence Practice & Translation */}
        {template.id === 'sentence_writing' && (
          <div className="flex flex-col gap-2.5">
            {items.map((rawItem, idx) => {
              const item = rawItem as any
              const linesCnt = Math.max(1, Math.min(10, Number(options.writing_lines_count ?? 3)))
              const lineStyle = options.writing_line_style || 'dashed'
              const borderStyleClass = lineStyle === 'solid' ? 'border-solid' : 'border-dashed'

              return (
                <div
                  key={`${item.note_id || idx}-${idx}`}
                  className="border border-slate-300 rounded-lg p-2.5 bg-white flex flex-col gap-1.5 shadow-2xs"
                >
                  <div className="flex items-start gap-2">
                    <span className="text-[10px] font-bold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200 shrink-0">
                      #{idx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
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
                    </div>
                  </div>

                  {/* Ruled / dashed writing lines for student */}
                  <div className="flex flex-col gap-2 pt-1">
                    {Array.from({ length: linesCnt }).map((_, lIdx) => (
                      <div
                        key={`line-${lIdx}`}
                        className={`w-full min-h-[20px] border-b border-slate-400 ${borderStyleClass}`}
                      />
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Category: Grammar Practice & Prompts */}
        {template.id === 'grammar_practice' && (
          <div className="flex flex-col gap-2.5">
            {items.map((rawItem, idx) => {
              const item = rawItem as any
              const linesCnt = Math.max(1, Math.min(10, Number(options.writing_lines_count ?? 3)))
              const lineStyle = options.writing_line_style || 'dashed'
              const borderStyleClass = lineStyle === 'solid' ? 'border-solid' : 'border-dashed'

              return (
                <div
                  key={`${item.note_id || idx}-${idx}`}
                  className="border border-slate-300 rounded-lg p-2.5 bg-white flex flex-col gap-1.5 shadow-2xs"
                >
                  <div className="flex items-start gap-2">
                    <span className="text-[10px] font-bold text-amber-800 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 shrink-0">
                      Cấu trúc #{idx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
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
                          <span className="font-semibold text-slate-700">Ví dụ: </span>
                          {item.example}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Ruled / dashed writing lines for student */}
                  <div className="flex flex-col gap-2 pt-0.5">
                    {Array.from({ length: linesCnt }).map((_, lIdx) => (
                      <div
                        key={`line-${lIdx}`}
                        className={`w-full min-h-[20px] border-b border-slate-400 ${borderStyleClass}`}
                      />
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>

      {/* Footer Block */}
      <footer className="border-t border-slate-200 pt-1 mt-2 flex justify-between items-center text-[9px] text-slate-400 shrink-0 relative z-10">
        <span>Flama Worksheet Generator &bull; flama.app</span>
        <span>
          Trang {page_number} / {total_pages}
        </span>
      </footer>
    </div>
  )
})
