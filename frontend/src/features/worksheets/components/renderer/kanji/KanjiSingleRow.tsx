import type { CSSProperties } from 'react'
import type { WorksheetKanjiItem, WorksheetLayoutOptions } from '../../../types'
import { KanjiGridBox } from '../../KanjiGridBox'
import { BlankFillerRow, ExtraBlankRows } from '../BlankBoxStrip'
import { KanjiItemMeta } from '../KanjiItemMeta'
import { extraBlankRowsFor, squareStyle, type PageMetrics } from '../pageMetrics'

function strokeWrapperClassFor(options: WorksheetLayoutOptions): string {
  const strokeColorMode = options.stroke_color_mode || 'monochrome'
  return [
    strokeColorMode === 'monochrome'
      ? 'flama-stroke-monochrome'
      : strokeColorMode === 'same_as_reference'
      ? 'flama-stroke-same-ref'
      : 'flama-stroke-multicolor',
    options.show_stroke_numbers === false ? 'flama-hide-stroke-numbers' : '',
  ]
    .filter(Boolean)
    .join(' ')
}

/** Single-character practice: reference, stroke order, optional meta pill, then traced and blank boxes. */
export function KanjiSingleRow({
  item,
  options,
  metrics,
}: {
  item: WorksheetKanjiItem
  options: WorksheetLayoutOptions
  metrics: PageMetrics
}) {
  const { boxSize, gridStyle, traceCount, topComponentWidthPx, fullRowBoxesCount } = metrics
  const char = item.char || (typeof item === 'object' && 'word' in item ? (item as any).word : '')
  const extraBlanks = extraBlankRowsFor(item.extra_blank_rows, options.extra_blank_rows)

  // Blank filler row: direct continuous guideline grid strip!
  if (item.is_blank_filler || (!char && !item.reading && !item.meaning)) {
    return (
      <BlankFillerRow
        count={fullRowBoxesCount}
        boxSize={boxSize}
        gridStyle={gridStyle}
        extraRows={extraBlanks}
      />
    )
  }

  const refCharColor = options.reference_char_color || '#e11d48'
  const strokeColorMode = options.stroke_color_mode || 'monochrome'
  const showReading = Boolean(options.show_reading)
  const showMeaning = Boolean(options.show_meaning)
  const showSourceWord = Boolean(options.show_source_word)
  const hasReadingOrMeaning = Boolean(
    (showReading && item.reading) ||
    (showMeaning && item.meaning) ||
    (showSourceWord && item.source_word && item.source_word !== char)
  )
  const pillMaxWidth = Math.max(40, Math.min(130, Math.round(boxSize * 2.8)))

  // Right strip: trace boxes, then blank boxes filling the rest of the line.
  const itemPillWidth = hasReadingOrMeaning ? pillMaxWidth : 0
  const hasStrokeBox = options.show_stroke_diagram !== false
  const itemStrokeWidth = hasStrokeBox ? boxSize : 0
  const itemInfoWidth = boxSize + itemStrokeWidth + itemPillWidth + (itemStrokeWidth > 0 ? 6 : 0) + (itemPillWidth > 0 ? 6 : 0)
  const itemRemainingWidth = Math.max(40, topComponentWidthPx - itemInfoWidth - 28)
  const itemBoxesFit = Math.max(1, Math.floor(itemRemainingWidth / (boxSize - 1)))
  const userPractice = options.practice_count
  let itemPracticeCount = userPractice ? userPractice : Math.max(1, itemBoxesFit - traceCount)
  if (traceCount + itemPracticeCount < itemBoxesFit) {
    itemPracticeCount = Math.max(itemPracticeCount, itemBoxesFit - traceCount)
  }

  return (
    <div className="flex flex-col gap-0.5">
      <div className="border border-slate-200 rounded-md p-1 bg-white flex items-center justify-between gap-2 overflow-hidden">
        {/* Left Info Column: Mẫu + Thứ tự nét + Âm/Nghĩa */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* 1. Reference Kanji (Chữ mẫu đầu tiên có màu) */}
          <div className="flex flex-col items-center">
            <KanjiGridBox
              char={char}
              gridStyle={gridStyle}
              isTrace={false}
              size={boxSize}
              rounded={true}
              strokeColor="#0f172a"
              charColor={refCharColor}
            />
          </div>

          {/* 2. Stroke Order Box (Chữ thứ 2: Nét vẽ) */}
          {hasStrokeBox && (
            <div className="flex flex-col items-center">
              {item.stroke_svg ? (
                <div
                  className={`shrink-0 rounded-[3px] bg-white border border-slate-700 p-0.5 flex items-center justify-center overflow-hidden stroke-box-wrap ${strokeWrapperClassFor(options)}`}
                  style={
                    {
                      ...squareStyle(boxSize),
                      '--ref-char-color': refCharColor,
                    } as CSSProperties
                  }
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
                  charColor={strokeColorMode === 'same_as_reference' ? refCharColor : '#0f172a'}
                />
              )}
            </div>
          )}

          {/* Metadata Pill: Scales proportionally with boxSize */}
          {hasReadingOrMeaning && (
            <KanjiItemMeta
              className="flex flex-col justify-center px-1 leading-tight overflow-hidden"
              style={{ maxWidth: pillMaxWidth }}
              boxSize={boxSize}
              reading={showReading && item.reading}
              meaning={showMeaning && item.meaning}
              sourceWord={showSourceWord && item.source_word !== char && item.source_word}
            />
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
          {Array.from({ length: itemPracticeCount }).map((_, pIdx) => (
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
      <ExtraBlankRows rows={extraBlanks} count={fullRowBoxesCount} boxSize={boxSize} gridStyle={gridStyle} />
    </div>
  )
}
