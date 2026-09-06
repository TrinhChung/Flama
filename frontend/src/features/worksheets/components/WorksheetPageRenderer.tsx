import { memo, useMemo } from 'react'
import QRCode from 'qrcode'
import { Table as TableIcon } from 'lucide-react'
import type {
  WorksheetKanjiItem,
  WorksheetKanjiCompoundItem,
  WorksheetKanjiStepItem,
  WorksheetLayoutOptions,
  WorksheetPageData,
  WorksheetRecallItem,
  WorksheetTableRowItem,
  WorksheetTemplate,
  WorksheetVocabItem,
  WorksheetEssayRowItem,
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

const staticKanjiSvgCache = new Map<string, string | null>()
const MAX_STATIC_SVG_CACHE_SIZE = 1200

function extractStaticKanjiSvgClient(
  svgContent: string | null | undefined,
  isTrace: boolean = false,
  charColor: string = '#0f172a',
  gridStyle: 'cross' | 'diagonal' | 'square' = 'cross',
  rounded: boolean = false,
  strokeColor: string = '#64748b',
): string | null {
  if (!svgContent || !svgContent.includes('<svg')) return null

  const cacheKey = `${svgContent.length}_${svgContent.slice(0, 32)}_${svgContent.slice(-32)}_${isTrace}_${charColor}_${gridStyle}_${rounded}_${strokeColor}`
  const cached = staticKanjiSvgCache.get(cacheKey)
  if (cached !== undefined) {
    return cached
  }

  const result = _parseStaticKanjiSvgClient(
    svgContent,
    isTrace,
    charColor,
    gridStyle,
    rounded,
    strokeColor,
  )

  if (staticKanjiSvgCache.size >= MAX_STATIC_SVG_CACHE_SIZE) {
    const keysToDelete = Array.from(staticKanjiSvgCache.keys()).slice(0, 250)
    for (const k of keysToDelete) staticKanjiSvgCache.delete(k)
  }
  staticKanjiSvgCache.set(cacheKey, result)
  return result
}

function _parseStaticKanjiSvgClient(
  svgContent: string,
  isTrace: boolean = false,
  charColor: string = '#0f172a',
  gridStyle: 'cross' | 'diagonal' | 'square' = 'cross',
  rounded: boolean = false,
  strokeColor: string = '#64748b',
): string | null {
  try {
    const parser = new DOMParser()
    const doc = parser.parseFromString(svgContent, 'image/svg+xml')
    const svgEl = doc.querySelector('svg')
    if (!svgEl) return null

    const viewBox = svgEl.getAttribute('viewBox') || '0 0 109 109'
    const isMmah = viewBox.includes('1024') || svgContent.includes('flama-grid-box')

    if (isMmah) {
      let paths = Array.from(doc.querySelectorAll('path[fill="lightgray"]'))
      if (!paths.length) {
        paths = Array.from(doc.querySelectorAll('path')).filter(
          (p) => p.getAttribute('fill') === 'lightgray'
        )
      }
      if (!paths.length) return null

      const rxVal = rounded ? 24 : 0
      const grid: string[] = [
        `<rect x="8" y="8" width="1008" height="1008" stroke="${strokeColor}" stroke-width="4" rx="${rxVal}" fill="#ffffff" />`,
      ]
      if (gridStyle === 'cross' || gridStyle === 'diagonal') {
        grid.push(
          '<line x1="512" y1="8" x2="512" y2="1016" stroke="#cbd5e1" stroke-width="4" stroke-dasharray="16,16" />' +
          '<line x1="8" y1="512" x2="1016" y2="512" stroke="#cbd5e1" stroke-width="4" stroke-dasharray="16,16" />'
        )
      }
      if (gridStyle === 'diagonal') {
        grid.push(
          '<line x1="8" y1="8" x2="1016" y2="1016" stroke="#e2e8f0" stroke-width="3" stroke-dasharray="16,16" />' +
          '<line x1="8" y1="1016" x2="1016" y2="8" stroke="#e2e8f0" stroke-width="3" stroke-dasharray="16,16" />'
        )
      }

      const pathsXml = paths.map((p) => {
        const d = p.getAttribute('d') || ''
        if (isTrace) {
          return `<path d="${d}" fill="#cbd5e1" stroke="#cbd5e1" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill-opacity="0.85" stroke-opacity="0.85" />`
        }
        const activeColor = charColor || '#0f172a'
        return `<path d="${d}" fill="${activeColor}" stroke="${activeColor}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />`
      })

      return (
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="100%" height="100%" class="flama-static-kanji-box" preserveAspectRatio="xMidYMid meet">` +
        grid.join('') +
        `<g transform="scale(1, -1) translate(0, -900)">${pathsXml.join('')}</g>` +
        `</svg>`
      )
    } else {
      let paths = Array.from(doc.querySelectorAll('path.flama-kvg-stroke'))
      if (!paths.length) {
        paths = Array.from(doc.querySelectorAll('path')).filter((p) => {
          const id = p.getAttribute('id') || ''
          const cls = p.getAttribute('class') || ''
          return id.includes('-s') || cls.includes('flama-kvg-stroke')
        })
      }
      if (!paths.length) return null

      const rxVal = rounded ? 3 : 0
      const grid: string[] = [
        `<rect x="0.5" y="0.5" width="108" height="108" stroke="${strokeColor}" stroke-width="1" rx="${rxVal}" fill="#ffffff" />`,
      ]
      if (gridStyle === 'cross' || gridStyle === 'diagonal') {
        grid.push(
          '<line x1="54.5" y1="1" x2="54.5" y2="108" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,2" />' +
          '<line x1="1" y1="54.5" x2="108" y2="54.5" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,2" />'
        )
      }
      if (gridStyle === 'diagonal') {
        grid.push(
          '<line x1="1" y1="1" x2="108" y2="108" stroke="#e2e8f0" stroke-width="0.6" stroke-dasharray="2,2" />' +
          '<line x1="1" y1="108" x2="108" y2="1" stroke="#e2e8f0" stroke-width="0.6" stroke-dasharray="2,2" />'
        )
      }

      const pathsXml = paths.map((p) => {
        const d = p.getAttribute('d') || ''
        if (isTrace) {
          return `<path d="${d}" fill="none" stroke="#cbd5e1" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />`
        }
        const activeColor = charColor || '#0f172a'
        return `<path d="${d}" fill="none" stroke="${activeColor}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round" />`
      })

      return (
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109" width="100%" height="100%" class="flama-static-kanji-box" preserveAspectRatio="xMidYMid meet">` +
        grid.join('') +
        pathsXml.join('') +
        `</svg>`
      )
    }
  } catch {
    return null
  }
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
  const boxSize = options.box_size || (isLandscape ? 38 : (template.id === 'kanji_compact' || template.id === 'kanji_stroke' ? 30 : 36))
  const traceCount = Math.max(0, options.trace_count ?? (template.id === 'kanji_compact' || template.id === 'kanji_stroke' ? 1 : 2))

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

  // Watermark options (Mandatory anti-theft protection)
  const watermarkText = (
    options.watermark_text ||
    (typeof window !== 'undefined' ? window.location.hostname : 'flama.app') ||
    'flama.app'
  ).toUpperCase()
  const watermarkOpacity = Math.max(0.015, Math.min(0.15, options.watermark_opacity ?? 0.04))
  const watermarkLayout = options.watermark_layout || 'diagonal_grid'

  const currentUrl =
    options.current_url ||
    (typeof window !== 'undefined' ? window.location.href : '')

  let currentDomain = 'flama.app'
  if (options.current_url) {
    try {
      const u = new URL(options.current_url)
      currentDomain = u.host || options.current_url
    } catch {
      currentDomain = options.current_url
    }
  } else if (typeof window !== 'undefined' && window.location.host) {
    currentDomain = window.location.host
  }

  const qrData = useMemo(() => {
    if (!currentUrl) return null
    try {
      const qr = QRCode.create(currentUrl, { errorCorrectionLevel: 'M' })
      const modSize = qr.modules.size
      const margin = 1
      const totalSize = modSize + margin * 2
      let path = ''
      for (let r = 0; r < modSize; r++) {
        for (let c = 0; c < modSize; c++) {
          if (qr.modules.get(r, c)) {
            path += `M${c + margin},${r + margin}h1v1h-1z `
          }
        }
      }
      return { path, totalSize }
    } catch {
      return null
    }
  }, [currentUrl])

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
      {/* Global CSS overrides for stroke diagram color modes */}
      <style>{`
        .stroke-box-wrap svg,
        .stroke-step-box svg,
        .stroke-static-box svg,
        .stroke-trace-box svg,
        .flama-static-kanji-box,
        .flama-stroke-char,
        svg.flama-stroke-char {
          width: 100% !important;
          height: 100% !important;
          max-width: 100% !important;
          max-height: 100% !important;
          display: block !important;
        }
        .flama-kvg-num {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
          font-size: 12px !important;
          font-weight: 800 !important;
          paint-order: stroke fill !important;
          stroke: #ffffff !important;
          stroke-width: 2px !important;
        }
        .flama-mmah-numbers text,
        .flama-stroke-num {
          font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
          font-size: 56px !important;
          font-weight: 900 !important;
          paint-order: stroke fill !important;
          stroke: #ffffff !important;
          stroke-width: 10px !important;
        }
        .stroke-box-wrap .flama-grid-box rect {
          stroke-width: 3 !important;
        }
        .stroke-box-wrap .flama-grid-box path {
          stroke-width: 2.5 !important;
          stroke-dasharray: 10,10 !important;
        }
        .flama-hide-stroke-numbers .flama-kvg-num,
        .flama-hide-stroke-numbers .flama-mmah-numbers,
        .flama-hide-stroke-numbers .flama-stroke-num {
          display: none !important;
        }
        .flama-stroke-monochrome .flama-stroke-char {
          --flama-stroke-c1: #0f172a !important;
          --flama-stroke-c2: #0f172a !important;
          --flama-stroke-c3: #0f172a !important;
          --flama-stroke-c4: #0f172a !important;
          --flama-stroke-c5: #0f172a !important;
          --flama-stroke-c6: #0f172a !important;
          --flama-stroke-c7: #0f172a !important;
          --flama-stroke-c8: #0f172a !important;
          --flama-stroke-c9: #0f172a !important;
          --flama-stroke-c10: #0f172a !important;
        }
        .flama-stroke-monochrome .flama-kvg-num,
        .flama-stroke-monochrome .flama-mmah-numbers text,
        .flama-stroke-monochrome .flama-stroke-num {
          fill: #0f172a !important;
          stroke: #ffffff !important;
        }
        .flama-stroke-monochrome .flama-kvg-stroke {
          stroke: #0f172a !important;
        }
        .flama-stroke-monochrome path[id^="make-me-a-hanzi-animation"] {
          stroke: #0f172a !important;
        }
        .flama-stroke-same-ref .flama-kvg-stroke {
          stroke: var(--ref-char-color, #e11d48) !important;
        }
        .flama-stroke-same-ref .flama-kvg-num,
        .flama-stroke-same-ref .flama-mmah-numbers text,
        .flama-stroke-same-ref .flama-stroke-num {
          fill: var(--ref-char-color, #e11d48) !important;
          stroke: #ffffff !important;
        }
        .flama-stroke-same-ref path[id^="make-me-a-hanzi-animation"] {
          stroke: var(--ref-char-color, #e11d48) !important;
        }
      `}</style>

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
      {template.id === 'genkouyoushi' ? (
        <header className="mb-2 shrink-0 relative z-10 w-full">
          {options.title_placement === 'header' && header.title && (
            <h1 className="text-center font-bold text-slate-900 text-base sm:text-lg mb-1.5">
              {header.title}
            </h1>
          )}
          {header.show_student_info && (
            <div className="flex justify-between items-center text-xs font-medium text-slate-800 px-1 py-0.5">
              {options.header_student_style === 'chinese' || !options.header_student_style ? (
                <>
                  <span>班级 ____________</span>
                  <span>姓名 ____________</span>
                  <span>学号 ____________</span>
                  <span>分数 ____________</span>
                </>
              ) : options.header_student_style === 'japanese' ? (
                <>
                  <span>クラス ____________</span>
                  <span>氏名 ____________</span>
                  <span>学籍番号 ____________</span>
                  <span>得点 ____________</span>
                </>
              ) : options.header_student_style === 'vietnamese' ? (
                <>
                  <span>Lớp: ____________</span>
                  <span>Họ tên: ____________</span>
                  <span>Mã số: ____________</span>
                  <span>Điểm: ____________</span>
                </>
              ) : (
                <>
                  <span>Lớp: ____________</span>
                  <span>Họ tên: ____________</span>
                  <span>Điểm: ____________</span>
                </>
              )}
            </div>
          )}
        </header>
      ) : (
        <header className="border-b-2 border-slate-900 pb-1.5 mb-2.5 flex justify-between items-end shrink-0 relative z-10">
          <div className="flex items-end gap-2.5">
            {qrData && (
              <div className="relative w-11 h-0 shrink-0">
                <a
                  href={currentUrl || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="absolute bottom-0 -left-2.5 w-[54px] h-[54px] p-1 bg-white border border-slate-300 rounded shadow-xs flex items-center justify-center hover:opacity-85 transition-opacity z-20"
                  title={`Quét mã QR để mở trang: ${currentUrl}`}
                  aria-label="Mã QR trang bài tập"
                >
                  <svg
                    viewBox={`0 0 ${qrData.totalSize} ${qrData.totalSize}`}
                    shapeRendering="crispEdges"
                    className="size-full block"
                  >
                    <rect width={qrData.totalSize} height={qrData.totalSize} fill="#ffffff" />
                    <path d={qrData.path} fill="#0f172a" />
                  </svg>
                </a>
              </div>
            )}
            <div>
              <h1 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight leading-tight">
                {header.title || 'Flama Worksheet'}
              </h1>
              {header.subtitle && (
                <p className="text-[10px] text-slate-500 mt-0.5">{header.subtitle}</p>
              )}
            </div>
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
      )}

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
          <div
            className={`flex-1 flex flex-col ${
              options.page_fill_mode === 'balanced_stretch'
                ? (items.length >= (isLandscape ? 4 : 5) ? 'justify-between' : 'justify-start gap-1 sm:gap-1.5')
                : (items.length >= (isLandscape ? 8 : 13) ? 'justify-between' : 'justify-start gap-1 sm:gap-1.5')
            }`}
          >
            {items.map((rawItem, idx) => {
              if (template.id === 'kanji_compound') {
                const compoundItem = (rawItem || {}) as WorksheetKanjiCompoundItem
                const isFiller = Boolean(compoundItem.is_blank_filler)
                const characters = compoundItem.characters || []
                const word = compoundItem.word || ''
                const extraBlanks = Math.max(0, Math.min(3, Number(compoundItem.extra_blank_rows ?? options.extra_blank_rows ?? 0)))
                const refCharColor = options.reference_char_color || '#e11d48'

                if (isFiller || characters.length === 0) {
                  return (
                    <div key={`blank-compound-${idx}`} className="flex flex-col gap-1 w-full">
                      <div className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden w-fit shadow-2xs">
                        {Array.from({ length: fullRowBoxesCount }).map((_, bIdx) => (
                          <KanjiGridBox key={`filler-box-${bIdx}`} char="" gridStyle={gridStyle} isBlank={true} size={boxSize} rounded={false} strokeColor="#cbd5e1" />
                        ))}
                      </div>
                    </div>
                  )
                }

                const charCount = characters.length
                const showReading = Boolean(compoundItem.reading && options.show_reading)
                const showMeaning = Boolean(compoundItem.meaning && options.show_meaning)
                const hasPill = showReading || showMeaning

                let pillWidth = 0
                if (hasPill) {
                  const readingLen = showReading ? String(compoundItem.reading).length * 8 : 0
                  const meaningLen = showMeaning ? String(compoundItem.meaning).length * 6 : 0
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
                  <div key={`${compoundItem.note_id || idx}-${word}-${idx}`} className="flex flex-col gap-0.5">
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
                          <div
                            className="flex flex-col justify-center px-1 leading-tight overflow-hidden shrink-0"
                            style={{ width: pillWidth, minWidth: pillWidth, maxWidth: pillWidth }}
                          >
                            {showReading && (
                              <span
                                className="font-semibold text-slate-900 truncate"
                                style={{ fontSize: `${Math.max(6, Math.min(11, Math.round(boxSize * 0.3)))}px`, lineHeight: 1.15 }}
                                title={compoundItem.reading}
                              >
                                {compoundItem.reading}
                              </span>
                            )}
                            {showMeaning && (
                              <span
                                className="text-slate-500 truncate"
                                style={{ fontSize: `${Math.max(5.5, Math.min(10, Math.round(boxSize * 0.25)))}px`, lineHeight: 1.15 }}
                                title={compoundItem.meaning}
                              >
                                {compoundItem.meaning}
                              </span>
                            )}
                          </div>
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
                    {extraBlanks > 0 && (
                      <div className="flex flex-col gap-1">
                        {Array.from({ length: extraBlanks }).map((_, eIdx) => (
                          <div key={`extra-${eIdx}`} className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden w-fit shadow-2xs">
                            {Array.from({ length: fullRowBoxesCount }).map((_, bIdx) => (
                              <KanjiGridBox key={`extra-box-${bIdx}`} char="" gridStyle={gridStyle} isBlank={true} size={boxSize} rounded={false} strokeColor="#cbd5e1" />
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              }

              if (template.id === 'kanji_step_by_step') {
                const stepItem = (rawItem || {}) as WorksheetKanjiStepItem
                const isFiller = Boolean(stepItem.is_blank_filler)
                const char = stepItem.char || ''
                const stepSvgs = stepItem.step_svgs || []
                const extraBlanks = Math.max(0, Math.min(3, Number(stepItem.extra_blank_rows ?? options.extra_blank_rows ?? 0)))
                const refCharColor = options.reference_char_color || '#e11d48'

                if (isFiller || !char) {
                  return (
                    <div key={`blank-step-${idx}`} className="flex flex-col gap-1 w-full">
                      <div className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden w-fit shadow-2xs">
                        {Array.from({ length: fullRowBoxesCount }).map((_, bIdx) => (
                          <KanjiGridBox key={`filler-box-${bIdx}`} char="" gridStyle={gridStyle} isBlank={true} size={boxSize} rounded={false} strokeColor="#cbd5e1" />
                        ))}
                      </div>
                    </div>
                  )
                }

                const numSteps = stepSvgs.length
                const requestedTrace = Math.max(1, options.trace_count ?? 2)
                const requestedPractice = Math.max(1, options.practice_count ?? 2)

                const showReading = Boolean(stepItem.reading && options.show_reading)
                const showMeaning = Boolean(stepItem.meaning && options.show_meaning)
                const showSourceWord = Boolean(stepItem.source_word && stepItem.source_word !== char && options.show_source_word)
                const hasMeta = showReading || showMeaning || showSourceWord
                const pillWidth = hasMeta
                  ? Math.max(40, Math.min(120, Math.round(boxSize * 2.5)))
                  : 0
                const infoWidth = boxSize + (pillWidth > 0 ? pillWidth + 6 : 0)
                const rowPaddingGap = 10 + 6 + 2
                const availableWidth = Math.max(0, topComponentWidthPx - infoWidth - rowPaddingGap)
                const boxSlotWidth = boxSize + 2
                const boxesPerLine = Math.max(1, Math.floor((availableWidth + 2) / boxSlotWidth))

                const availableInLine1 = boxesPerLine - numSteps - requestedTrace
                let actualPractice = requestedPractice
                if (availableInLine1 >= 1) {
                  actualPractice = availableInLine1
                } else {
                  actualPractice = requestedPractice
                }

                const staticSvg =
                  stepItem.static_svg ||
                  extractStaticKanjiSvgClient(stepItem.stroke_svg, false, refCharColor, gridStyle, true, '#0f172a')

                const traceSvg =
                  stepItem.trace_svg ||
                  extractStaticKanjiSvgClient(stepItem.stroke_svg, true, '#cbd5e1', gridStyle, false, '#cbd5e1')

                return (
                  <div key={`${stepItem.note_id || idx}-${char}-${idx}`} className="flex flex-col gap-0.5">
                    <div className="border border-slate-200 rounded-md p-1 bg-white flex items-start gap-1.5 overflow-hidden shadow-2xs">
                      {/* Left: Chữ mẫu to (Full SVG tĩnh không animation) + Reading/Meaning */}
                      <div className="flex items-center gap-1.5 shrink-0">
                        {staticSvg ? (
                          <div
                            className="shrink-0 rounded-[3px] bg-white flex items-center justify-center overflow-hidden stroke-static-box"
                            style={{
                              width: boxSize,
                              height: boxSize,
                              minWidth: boxSize,
                              minHeight: boxSize,
                              maxWidth: boxSize,
                              maxHeight: boxSize,
                            }}
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
                          <div
                            className="flex flex-col justify-center px-1 leading-tight overflow-hidden"
                            style={{ maxWidth: Math.max(40, Math.min(120, Math.round(boxSize * 2.5))) }}
                          >
                            {stepItem.reading && showReading && (
                              <span
                                className="font-semibold text-slate-900 truncate"
                                style={{ fontSize: `${Math.max(6, Math.min(11, Math.round(boxSize * 0.3)))}px`, lineHeight: 1.15 }}
                                title={stepItem.reading}
                              >
                                {stepItem.reading}
                              </span>
                            )}
                            {stepItem.meaning && showMeaning && (
                              <span
                                className="text-slate-500 truncate"
                                style={{ fontSize: `${Math.max(5.5, Math.min(10, Math.round(boxSize * 0.25)))}px`, lineHeight: 1.15 }}
                                title={stepItem.meaning}
                              >
                                {stepItem.meaning}
                              </span>
                            )}
                            {stepItem.source_word && showSourceWord && (
                              <span
                                className="text-slate-400 italic truncate"
                                style={{
                                  fontSize: `${Math.max(5, Math.min(9, Math.round(boxSize * 0.23)))}px`,
                                  lineHeight: 1.1,
                                }}
                              >
                                ({stepItem.source_word})
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Right: Dãy các ô bước nét (1..N) + Ô mờ (trace SVG) + Ô trống (practice) */}
                      <div className="flex items-center flex-1 flex-wrap gap-0.5">
                        {/* 1. Step-by-step stroke boxes */}
                        {stepSvgs.map((svg, sIdx) => (
                          <div
                            key={`step-${sIdx}`}
                            className="shrink-0 rounded-[2px] bg-white border border-slate-300 flex items-center justify-center overflow-hidden stroke-step-box"
                            style={{
                              width: boxSize,
                              height: boxSize,
                              minWidth: boxSize,
                              minHeight: boxSize,
                              maxWidth: boxSize,
                              maxHeight: boxSize,
                            }}
                            dangerouslySetInnerHTML={{ __html: svg }}
                          />
                        ))}

                        {/* 2. Tracing boxes (SVG in mờ) */}
                        {Array.from({ length: requestedTrace }).map((_, tIdx) => (
                          <div
                            key={`trace-${tIdx}`}
                            className="shrink-0 rounded-[2px] bg-white border border-slate-300 flex items-center justify-center overflow-hidden stroke-step-box stroke-trace-box"
                            style={{
                              width: boxSize,
                              height: boxSize,
                              minWidth: boxSize,
                              minHeight: boxSize,
                              maxWidth: boxSize,
                              maxHeight: boxSize,
                            }}
                          >
                            {traceSvg ? (
                              <div
                                className="w-full h-full flex items-center justify-center overflow-hidden"
                                dangerouslySetInnerHTML={{ __html: traceSvg }}
                              />
                            ) : (
                              <KanjiGridBox
                                key={`trace-box-${tIdx}`}
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
                            style={{
                              width: boxSize,
                              height: boxSize,
                              minWidth: boxSize,
                              minHeight: boxSize,
                              maxWidth: boxSize,
                              maxHeight: boxSize,
                            }}
                          >
                            <KanjiGridBox
                              key={`practice-box-${pIdx}`}
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
                    {extraBlanks > 0 && (
                      <div className="flex flex-col gap-1">
                        {Array.from({ length: extraBlanks }).map((_, eIdx) => (
                          <div key={`extra-${eIdx}`} className="flex -space-x-px border border-slate-700 bg-white rounded-[3px] overflow-hidden w-fit shadow-2xs">
                            {Array.from({ length: fullRowBoxesCount }).map((_, bIdx) => (
                              <KanjiGridBox key={`extra-box-${bIdx}`} char="" gridStyle={gridStyle} isBlank={true} size={boxSize} rounded={false} strokeColor="#cbd5e1" />
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              }

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

              const refCharColor = options.reference_char_color || '#e11d48'
              const strokeColorMode = options.stroke_color_mode || 'monochrome'
              const strokeWrapperClass = [
                strokeColorMode === 'monochrome'
                  ? 'flama-stroke-monochrome'
                  : strokeColorMode === 'same_as_reference'
                  ? 'flama-stroke-same-ref'
                  : 'flama-stroke-multicolor',
                options.show_stroke_numbers === false ? 'flama-hide-stroke-numbers' : '',
              ]
                .filter(Boolean)
                .join(' ')

              return (
                <div key={`${item.note_id || idx}-${char || 'blank'}-${idx}`} className="flex flex-col gap-0.5">
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
                      {options.show_stroke_diagram !== false && (
                        <div className="flex flex-col items-center">
                          {item.stroke_svg ? (
                            <div
                              className={`shrink-0 rounded-[3px] bg-white border border-slate-700 p-0.5 flex items-center justify-center overflow-hidden stroke-box-wrap ${strokeWrapperClass}`}
                              style={
                                {
                                  width: boxSize,
                                  height: boxSize,
                                  minWidth: boxSize,
                                  minHeight: boxSize,
                                  maxWidth: boxSize,
                                  maxHeight: boxSize,
                                  '--ref-char-color': refCharColor,
                                } as React.CSSProperties
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
                      {(() => {
                        const showReading = Boolean(options.show_reading)
                        const showMeaning = Boolean(options.show_meaning)
                        const showSourceWord = Boolean(options.show_source_word)
                        const hasReadingOrMeaning = Boolean(
                          (showReading && item.reading) ||
                          (showMeaning && item.meaning) ||
                          (showSourceWord && item.source_word && item.source_word !== char)
                        )

                        if (!hasReadingOrMeaning) return null

                        return (
                          <div
                            className="flex flex-col justify-center px-1 leading-tight overflow-hidden"
                            style={{
                              maxWidth: Math.max(40, Math.min(130, Math.round(boxSize * 2.8))),
                            }}
                          >
                            {item.reading && showReading && (
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
                            {item.meaning && showMeaning && (
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
                            {item.source_word && item.source_word !== char && showSourceWord && (
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
                        )
                      })()}
                    </div>

                    {/* Right Continuous Grid Strip: Tracing + Blank Boxes (Connected Seamlessly) */}
                    {(() => {
                      const showReading = Boolean(options.show_reading)
                      const showMeaning = Boolean(options.show_meaning)
                      const showSourceWord = Boolean(options.show_source_word)
                      const hasReadingOrMeaning = Boolean(
                        (showReading && item.reading) ||
                        (showMeaning && item.meaning) ||
                        (showSourceWord && item.source_word && item.source_word !== char)
                      )
                      const itemPillWidth = hasReadingOrMeaning
                        ? Math.max(40, Math.min(130, Math.round(boxSize * 2.8)))
                        : 0
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
                      )
                    })()}
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
          (() => {
            const showReading = options.show_reading !== false
            const showMeaning = options.show_meaning !== false
            const practiceType = options.practice_type || 'boxes'
            const boxesCnt = Math.max(1, options.practice_boxes_count ?? (isLandscape ? 10 : 6))

            let wWord = 'w-[22%]'
            let wRead = 'w-[20%]'
            let wMean = 'w-[28%]'
            let wPrac = 'w-[30%]'

            if (!showReading && !showMeaning) {
              wWord = 'w-[35%]'
              wPrac = 'w-[65%]'
            } else if (!showReading) {
              wWord = 'w-[28%]'
              wMean = 'w-[32%]'
              wPrac = 'w-[40%]'
            } else if (!showMeaning) {
              wWord = 'w-[28%]'
              wRead = 'w-[32%]'
              wPrac = 'w-[40%]'
            }

            return (
              <table className="w-full border-collapse text-xs border border-slate-400">
                <thead>
                  <tr className="bg-slate-100 text-slate-900 text-left font-semibold">
                    <th className={`border border-slate-400 px-2 py-1 ${wWord} text-xs`}>Từ vựng</th>
                    {showReading && <th className={`border border-slate-400 px-2 py-1 ${wRead} text-xs`}>Cách đọc</th>}
                    {showMeaning && <th className={`border border-slate-400 px-2 py-1 ${wMean} text-xs`}>Ý nghĩa</th>}
                    <th className={`border border-slate-400 px-2 py-1 ${wPrac} text-xs`}>Luyện viết</th>
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
          })()
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
                const wordLen = item.word_length || (item.word ? item.word.length : 4)
                const showBoxes = options.recall_answer_style === 'boxes' || options.show_word_length_hint

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
          <div
            className={`flex-1 flex flex-col ${
              options.page_fill_mode === 'balanced_stretch'
                ? (items.length >= (isLandscape ? 3 : 4) ? 'justify-between' : 'justify-start gap-1.5 sm:gap-2')
                : (items.length >= (isLandscape ? 4 : 6) ? 'justify-between' : 'justify-start gap-1.5 sm:gap-2')
            }`}
          >
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
          <div
            className={`flex-1 flex flex-col ${
              options.page_fill_mode === 'balanced_stretch'
                ? (items.length >= (isLandscape ? 3 : 4) ? 'justify-between' : 'justify-start gap-1.5 sm:gap-2')
                : (items.length >= (isLandscape ? 4 : 6) ? 'justify-between' : 'justify-start gap-1.5 sm:gap-2')
            }`}
          >
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

        {/* Category: Essay / Genkouyoushi Grid */}
        {(template.category === 'essay' || template.id === 'genkouyoushi') && (
          <div className="flex flex-col w-full my-auto">
            {items.map((rawItem, rIdx) => {
              const rowItem = rawItem as WorksheetEssayRowItem
              const cells = rowItem.cells || []
              const gridColor = options.grid_color || '#475569'
              const boxStyle = options.box_style || 'square'
              const hasSpacer = options.has_spacer_band !== false
              const spacerHeight = Math.max(4, Math.min(24, Number(options.spacer_height || 10)))

              return (
                <div key={rowItem.note_id || `essay-row-${rIdx}`} className="flex flex-col w-full">
                  {/* Row of square cells */}
                  <div className="flex w-full -space-x-px">
                    {cells.map((cell, cIdx) => {
                      const char = cell.char || ''
                      const isBlank = cell.is_blank || !char
                      const isTrace = Boolean(cell.is_trace)
                      const isTitle = Boolean(cell.is_title)

                      return (
                        <div
                          key={`cell-${rIdx}-${cIdx}`}
                          style={{
                            borderColor: gridColor,
                          }}
                          className="flex-1 aspect-square border relative flex items-center justify-center select-none overflow-hidden bg-white -mt-px first:-mt-0"
                        >
                          {/* Optional guideline lines */}
                          {boxStyle === 'cross' && (
                            <svg className="absolute inset-0 size-full pointer-events-none stroke-slate-300 stroke-dasharray-[2,2]">
                              <line x1="50%" y1="0" x2="50%" y2="100%" strokeWidth="0.75" />
                              <line x1="0" y1="50%" x2="100%" y2="50%" strokeWidth="0.75" />
                            </svg>
                          )}
                          {boxStyle === 'diagonal' && (
                            <svg className="absolute inset-0 size-full pointer-events-none stroke-slate-200 stroke-dasharray-[2,2]">
                              <line x1="50%" y1="0" x2="50%" y2="100%" strokeWidth="0.75" />
                              <line x1="0" y1="50%" x2="100%" y2="50%" strokeWidth="0.75" />
                              <line x1="0" y1="0" x2="100%" y2="100%" strokeWidth="0.5" stroke="#e2e8f0" />
                              <line x1="0" y1="100%" x2="100%" y2="0" strokeWidth="0.5" stroke="#e2e8f0" />
                            </svg>
                          )}
                          {/* Character content */}
                          {!isBlank && char && (
                            <span
                              className={`z-10 font-serif leading-none select-none ${
                                isTrace
                                  ? 'text-slate-300 font-light'
                                  : isTitle
                                  ? 'text-slate-900 font-bold'
                                  : 'text-slate-800 font-normal'
                              }`}
                              style={{
                                fontSize: 'clamp(10px, 1.4vw, 15px)',
                              }}
                            >
                              {char}
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>

                  {/* Spacer band between rows */}
                  {hasSpacer && rIdx < items.length - 1 && (
                    <div
                      style={{
                        height: `${spacerHeight}px`,
                        borderColor: gridColor,
                      }}
                      className="w-full border-x border-b -mt-px bg-white"
                    />
                  )}
                </div>
              )
            })}
          </div>
        )}
      </main>

      {/* Footer Block */}
      {template.id === 'genkouyoushi' ? (
        <footer className="pt-1 mt-2 flex justify-between items-center text-[10px] text-slate-500 shrink-0 relative z-10 px-1 font-serif">
          <span className="font-semibold text-slate-600">
            {options.footer_brand_label || 'Flama (400格)'}
          </span>
          <span className="text-[9px] text-slate-400 font-sans">
            Trang {page_number} / {total_pages}
          </span>
          <span className="tracking-widest">
            {options.footer_date_format === 'vietnamese'
              ? 'Ngày ...... Tháng ...... Năm 20......'
              : '年    月    日'}
          </span>
        </footer>
      ) : (
        <footer className="border-t border-slate-200 pt-1 mt-2 flex justify-between items-center text-[9px] text-slate-400 shrink-0 relative z-10">
          <span className="truncate max-w-[75%]">
            Flama Worksheet Generator &bull;{' '}
            {currentUrl ? (
              <a
                href={currentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline text-inherit"
              >
                {currentDomain}
              </a>
            ) : (
              currentDomain
            )}
          </span>
          <span className="shrink-0 ml-2">
            Trang {page_number} / {total_pages}
          </span>
        </footer>
      )}
    </div>
  )
})
