import type { WorksheetKanjiStepItem, WorksheetLayoutOptions } from '../../../types'
import { extractStaticKanjiSvgClient } from '../../../utils/staticKanjiSvg'
import { KanjiGridBox } from '../../KanjiGridBox'
import { BlankFillerRow, ExtraBlankRows } from '../BlankBoxStrip'
import { KanjiItemMeta } from '../KanjiItemMeta'
import { extraBlankRowsFor, squareStyle, type PageMetrics } from '../pageMetrics'

/** Stroke-by-stroke practice: static model, one box per stroke step, traced and blank boxes. */
export function KanjiStepRow({
  item,
  options,
  metrics,
}: {
  item: WorksheetKanjiStepItem
  options: WorksheetLayoutOptions
  metrics: PageMetrics
}) {
  const { boxSize, gridStyle, topComponentWidthPx, fullRowBoxesCount } = metrics
  const char = item.char || ''
  const stepSvgs = item.step_svgs || []
  const extraBlanks = extraBlankRowsFor(item.extra_blank_rows, options.extra_blank_rows)
  const refCharColor = options.reference_char_color || '#e11d48'

  if (item.is_blank_filler || !char) {
    return <BlankFillerRow count={fullRowBoxesCount} boxSize={boxSize} gridStyle={gridStyle} />
  }

  const numSteps = stepSvgs.length
  const requestedTrace = Math.max(1, options.trace_count ?? 2)
  const requestedPractice = Math.max(1, options.practice_count ?? 2)

  const showReading = Boolean(item.reading && options.show_reading)
  const showMeaning = Boolean(item.meaning && options.show_meaning)
  const showSourceWord = Boolean(item.source_word && item.source_word !== char && options.show_source_word)
  const hasMeta = showReading || showMeaning || showSourceWord
  const pillWidth = hasMeta
    ? Math.max(40, Math.min(120, Math.round(boxSize * 2.5)))
    : 0
  const infoWidth = boxSize + (pillWidth > 0 ? pillWidth + 6 : 0)
  const rowPaddingGap = 10 + 6 + 2
  const availableWidth = Math.max(0, topComponentWidthPx - infoWidth - rowPaddingGap)
  const boxSlotWidth = boxSize + 2
  const boxesPerLine = Math.max(1, Math.floor((availableWidth + 2) / boxSlotWidth))

  // Spare room on the first line goes to blank practice boxes.
  const availableInLine1 = boxesPerLine - numSteps - requestedTrace
  const actualPractice = availableInLine1 >= 1 ? availableInLine1 : requestedPractice

  const staticSvg =
    item.static_svg ||
    extractStaticKanjiSvgClient(item.stroke_svg, false, refCharColor, gridStyle, true, '#0f172a')

  const traceSvg =
    item.trace_svg ||
    extractStaticKanjiSvgClient(item.stroke_svg, true, '#cbd5e1', gridStyle, false, '#cbd5e1')

  return (
    <div className="flex flex-col gap-0.5">
      <div className="border border-slate-200 rounded-md p-1 bg-white flex items-start gap-1.5 overflow-hidden shadow-2xs">
        {/* Left: Chữ mẫu to (Full SVG tĩnh không animation) + Reading/Meaning */}
        <div className="flex items-center gap-1.5 shrink-0">
          {staticSvg ? (
            <div
              className="shrink-0 rounded-[3px] bg-white flex items-center justify-center overflow-hidden stroke-static-box"
              style={squareStyle(boxSize)}
              dangerouslySetInnerHTML={{ __html: staticSvg }}
            />
          ) : (
            <KanjiGridBox
              char={char}
              gridStyle={gridStyle}
              isTrace={false}
              size={boxSize}
              rounded={true}
              strokeColor="#0f172a"
              charColor={refCharColor}
            />
          )}

          {hasMeta && (
            <KanjiItemMeta
              className="flex flex-col justify-center px-1 leading-tight overflow-hidden"
              style={{ maxWidth: Math.max(40, Math.min(120, Math.round(boxSize * 2.5))) }}
              boxSize={boxSize}
              reading={showReading && item.reading}
              meaning={showMeaning && item.meaning}
              sourceWord={showSourceWord && item.source_word}
            />
          )}
        </div>

        {/* Right: Dãy các ô bước nét (1..N) + Ô mờ (trace SVG) + Ô trống (practice) */}
        <div className="flex items-center flex-1 flex-wrap gap-0.5">
          {/* 1. Step-by-step stroke boxes */}
          {stepSvgs.map((svg, sIdx) => (
            <div
              key={`step-${sIdx}`}
              className="shrink-0 rounded-[2px] bg-white border border-slate-300 flex items-center justify-center overflow-hidden stroke-step-box"
              style={squareStyle(boxSize)}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
          ))}

          {/* 2. Tracing boxes (SVG in mờ) */}
          {Array.from({ length: requestedTrace }).map((_, tIdx) => (
            <div
              key={`trace-${tIdx}`}
              className="shrink-0 rounded-[2px] bg-white border border-slate-300 flex items-center justify-center overflow-hidden stroke-step-box stroke-trace-box"
              style={squareStyle(boxSize)}
            >
              {traceSvg ? (
                <div
                  className="w-full h-full flex items-center justify-center overflow-hidden"
                  dangerouslySetInnerHTML={{ __html: traceSvg }}
                />
              ) : (
                <KanjiGridBox
                  char={char}
                  gridStyle={gridStyle}
                  isTrace={true}
                  size={boxSize}
                  rounded={false}
                  strokeColor="#cbd5e1"
                />
              )}
            </div>
          ))}

          {/* 3. Blank Practice boxes */}
          {Array.from({ length: actualPractice }).map((_, pIdx) => (
            <div
              key={`practice-${pIdx}`}
              className="shrink-0 rounded-[2px] bg-white border border-slate-300 flex items-center justify-center overflow-hidden stroke-step-box"
              style={squareStyle(boxSize)}
            >
              <KanjiGridBox
                char=""
                gridStyle={gridStyle}
                isBlank={true}
                size={boxSize}
                rounded={false}
                strokeColor="#cbd5e1"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Extra Blank Practice Rows */}
      <ExtraBlankRows rows={extraBlanks} count={fullRowBoxesCount} boxSize={boxSize} gridStyle={gridStyle} />
    </div>
  )
}
