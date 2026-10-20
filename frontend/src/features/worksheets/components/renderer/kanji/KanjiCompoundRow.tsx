import type { WorksheetKanjiCompoundItem, WorksheetLayoutOptions } from '../../../types'
import { KanjiGridBox } from '../../KanjiGridBox'
import { BlankFillerRow, ExtraBlankRows } from '../BlankBoxStrip'
import { KanjiItemMeta } from '../KanjiItemMeta'
import { extraBlankRowsFor, type PageMetrics } from '../pageMetrics'

/** Whole-word practice: reference word, then traced/blank copies of the word, then fill boxes. */
export function KanjiCompoundRow({
  item,
  options,
  metrics,
}: {
  item: WorksheetKanjiCompoundItem
  options: WorksheetLayoutOptions
  metrics: PageMetrics
}) {
  const { boxSize, gridStyle, topComponentWidthPx, fullRowBoxesCount } = metrics
  const characters = item.characters || []
  const extraBlanks = extraBlankRowsFor(item.extra_blank_rows, options.extra_blank_rows)
  const refCharColor = options.reference_char_color || '#e11d48'

  if (item.is_blank_filler || characters.length === 0) {
    return <BlankFillerRow count={fullRowBoxesCount} boxSize={boxSize} gridStyle={gridStyle} />
  }

  const charCount = characters.length
  const showReading = Boolean(item.reading && options.show_reading)
  const showMeaning = Boolean(item.meaning && options.show_meaning)
  const hasPill = showReading || showMeaning

  let pillWidth = 0
  if (hasPill) {
    const readingLen = showReading ? String(item.reading).length * 8 : 0
    const meaningLen = showMeaning ? String(item.meaning).length * 6 : 0
    const maxTextWidth = Math.max(readingLen, meaningLen)
    const maxPillWidth = Math.max(45, Math.min(120, Math.round(boxSize * 2.6)))
    pillWidth = Math.max(38, Math.min(maxPillWidth, Math.round(maxTextWidth + 10)))
  }

  // Reference characters: boxes with 2px gap (gap-0.5)
  const refBoxesWidth = charCount * boxSize + (charCount > 1 ? (charCount - 1) * 2 : 0)
  const pillGap = hasPill ? 8 : 0
  const leftColWidth = refBoxesWidth + pillGap + pillWidth
  const gapBetweenCols = 8
  const rowOverhead = 14 // 12px padding + 2px border

  const rightAvailableWidth = Math.max(0, topComponentWidthPx - rowOverhead - leftColWidth - gapBetweenCols)
  const unitGap = 4 // gap-1
  const singleUnitWidth = charCount * (boxSize - 1) + 3 // boxes with -space-x-px + 2px border
  const maxUnits = singleUnitWidth > 0
    ? Math.max(0, Math.floor((rightAvailableWidth + unitGap) / (singleUnitWidth + unitGap)))
    : 0

  const requestedTrace = Math.max(1, options.trace_count ?? 2)
  const requestedPractice = Math.max(1, options.practice_count ?? 4)
  const totalRequested = requestedTrace + requestedPractice

  let actualTrace = requestedTrace
  let actualPractice = requestedPractice
  if (maxUnits >= totalRequested) {
    actualTrace = requestedTrace
    actualPractice = maxUnits - actualTrace
  } else if (maxUnits >= requestedTrace + 1) {
    actualTrace = requestedTrace
    actualPractice = maxUnits - actualTrace
  } else {
    actualTrace = Math.max(1, Math.min(requestedTrace, maxUnits - 1))
    actualPractice = Math.max(0, maxUnits - actualTrace)
  }

  const totalUnits = actualTrace + actualPractice
  const unitsUsedWidth = totalUnits > 0 ? (totalUnits * singleUnitWidth + (totalUnits - 1) * unitGap) : 0
  const remainingAfterUnits = Math.max(0, rightAvailableWidth - unitsUsedWidth)
  const availableForFill = remainingAfterUnits - (totalUnits > 0 ? unitGap : 0)
  const fillCount = Math.max(0, Math.floor((availableForFill - 3) / (boxSize - 1)))

  return (
    <div className="flex flex-col gap-0.5">
      <div className="border border-slate-200 rounded-md p-1 bg-white flex items-center gap-2 overflow-hidden shadow-2xs">
        {/* Left: Compound Reference + Mini Strokes + Word Reading/Meaning */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Reference Characters */}
          <div className="flex items-center gap-0.5">
            {characters.map((c, cIdx) => (
              <KanjiGridBox
                key={`ref-${cIdx}-${c.char}`}
                char={c.char}
                gridStyle={gridStyle}
                isTrace={false}
                size={boxSize}
                rounded={true}
                strokeColor="#0f172a"
                charColor={refCharColor}
              />
            ))}
          </div>

          {/* Compound Reading & Meaning */}
          {hasPill && (
            <KanjiItemMeta
              className="flex flex-col justify-center px-1 leading-tight overflow-hidden shrink-0"
              style={{ width: pillWidth, minWidth: pillWidth, maxWidth: pillWidth }}
              boxSize={boxSize}
              reading={showReading && item.reading}
              meaning={showMeaning && item.meaning}
            />
          )}
        </div>

        {/* Right: Tracing in compound units + Practice in compound units + Fill boxes */}
        <div className="flex items-center gap-1 flex-1 overflow-hidden">
          {/* Tracing Units */}
          {Array.from({ length: actualTrace }).map((_, uIdx) => (
            <div key={`trace-unit-${uIdx}`} className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden shrink-0">
              {characters.map((c, cIdx) => (
                <KanjiGridBox
                  key={`trace-${uIdx}-${cIdx}`}
                  char={c.char}
                  gridStyle={gridStyle}
                  isTrace={true}
                  size={boxSize}
                  rounded={false}
                  strokeColor="#cbd5e1"
                />
              ))}
            </div>
          ))}

          {/* Practice Units */}
          {Array.from({ length: actualPractice }).map((_, uIdx) => (
            <div key={`practice-unit-${uIdx}`} className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden shrink-0">
              {characters.map((_, cIdx) => (
                <KanjiGridBox
                  key={`practice-${uIdx}-${cIdx}`}
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

          {/* Fill single boxes to seamlessly cover remaining line space */}
          {fillCount > 0 && (
            <div className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden shrink-0">
              {Array.from({ length: fillCount }).map((_, fIdx) => (
                <KanjiGridBox
                  key={`fill-${fIdx}`}
                  char=""
                  gridStyle={gridStyle}
                  isBlank={true}
                  size={boxSize}
                  rounded={false}
                  strokeColor="#cbd5e1"
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Extra Blank Practice Rows */}
      <ExtraBlankRows rows={extraBlanks} count={fullRowBoxesCount} boxSize={boxSize} gridStyle={gridStyle} />
    </div>
  )
}
