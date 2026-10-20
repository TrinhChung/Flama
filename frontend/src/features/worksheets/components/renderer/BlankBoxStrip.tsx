import { KanjiGridBox } from '../KanjiGridBox'
import type { GridStyle } from './pageMetrics'

interface StripProps {
  count: number
  boxSize: number
  gridStyle: GridStyle
}

/** Continuous strip of blank practice boxes. */
export function BlankBoxStrip({ count, boxSize, gridStyle }: StripProps) {
  return (
    <div className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden w-fit shadow-2xs">
      {Array.from({ length: count }).map((_, bIdx) => (
        <KanjiGridBox
          key={`blank-box-${bIdx}`}
          char=""
          gridStyle={gridStyle}
          isBlank={true}
          size={boxSize}
          rounded={false}
          strokeColor="#cbd5e1"
        />
      ))}
    </div>
  )
}

/** Extra full-width blank rows printed under a practice row. */
export function ExtraBlankRows({ rows, ...strip }: StripProps & { rows: number }) {
  if (rows <= 0) return null
  return (
    <div className="flex flex-col gap-1">
      {Array.from({ length: rows }).map((_, eIdx) => (
        <BlankBoxStrip key={`extra-${eIdx}`} {...strip} />
      ))}
    </div>
  )
}

/** Filler row used to pad a page: one blank strip plus optional extra strips. */
export function BlankFillerRow({ extraRows = 0, ...strip }: StripProps & { extraRows?: number }) {
  return (
    <div className="flex flex-col gap-1 w-full">
      <BlankBoxStrip {...strip} />
      {extraRows > 0 &&
        Array.from({ length: extraRows }).map((_, eIdx) => (
          <BlankBoxStrip key={`filler-extra-${eIdx}`} {...strip} />
        ))}
    </div>
  )
}
