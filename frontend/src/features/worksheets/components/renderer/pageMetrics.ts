import type { CSSProperties } from 'react'
import type { WorksheetLayoutOptions, WorksheetTemplate } from '../../types'

export const MM_TO_PX = 3.7795

export type GridStyle = NonNullable<WorksheetLayoutOptions['grid_style']>

/** Geometry shared by every row of a rendered A4 page. */
export interface PageMetrics {
  isLandscape: boolean
  gridStyle: GridStyle
  boxSize: number
  traceCount: number
  paddingClass: string
  /** Exact width of a full-width row, from paper width minus margins. */
  topComponentWidthPx: number
  /** Blank boxes that fill one full-width row. */
  fullRowBoxesCount: number
}

function isCompactKanjiTemplate(templateId: string): boolean {
  return templateId === 'kanji_compact' || templateId === 'kanji_stroke'
}

export function getPageMetrics(template: WorksheetTemplate, options: WorksheetLayoutOptions): PageMetrics {
  const isLandscape = (options.orientation || 'portrait') === 'landscape'
  const gridStyle = options.grid_style || 'cross'
  const boxSize = options.box_size || (isLandscape ? 38 : (isCompactKanjiTemplate(template.id) ? 30 : 36))
  const traceCount = Math.max(0, options.trace_count ?? (isCompactKanjiTemplate(template.id) ? 1 : 2))

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
  const topComponentWidthPx = Math.floor(usableWidthMm * MM_TO_PX)

  return {
    isLandscape,
    gridStyle,
    boxSize,
    traceCount,
    paddingClass,
    topComponentWidthPx,
    fullRowBoxesCount: Math.max(1, Math.floor(topComponentWidthPx / (boxSize - 1))),
  }
}

/**
 * Vertical distribution of a row list: rows spread to fill the page once there
 * are enough of them, otherwise they stack from the top.
 */
export function stackJustifyClass(
  options: WorksheetLayoutOptions,
  itemCount: number,
  isLandscape: boolean,
  thresholds: { stretch: [landscape: number, portrait: number]; dense: [landscape: number, portrait: number] },
  stackedClass: string,
): string {
  const [landscape, portrait] = options.page_fill_mode === 'balanced_stretch' ? thresholds.stretch : thresholds.dense
  return itemCount >= (isLandscape ? landscape : portrait) ? 'justify-between' : stackedClass
}

/** Inline style pinning an element to an exact square. */
export function squareStyle(size: number): CSSProperties {
  return {
    width: size,
    height: size,
    minWidth: size,
    minHeight: size,
    maxWidth: size,
    maxHeight: size,
  }
}

/** Clamped number of extra blank rows (0–3) for an item, falling back to the page option. */
export function extraBlankRowsFor(itemRows: number | undefined, optionRows: number | undefined): number {
  return Math.max(0, Math.min(3, Number(itemRows ?? optionRows ?? 0)))
}
