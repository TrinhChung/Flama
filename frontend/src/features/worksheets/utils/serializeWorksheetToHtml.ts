/**
 * Serialize the React WorksheetPageRenderer into a standalone, self-contained
 * HTML document suitable for printing, downloading, and opening in new tabs.
 *
 * This replaces the backend `render_printable_html()` Python renderer so that
 * there is a single source of truth for worksheet layout (the React component).
 */

import { createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { flushSync } from 'react-dom'
import { WorksheetPageRenderer } from '../components/WorksheetPageRenderer'
import type { WorksheetPreviewResponse } from '../types'

// ---------------------------------------------------------------------------
// Inline computed styles with compact consolidation
// ---------------------------------------------------------------------------

/**
 * Walk every element in `root` and inline its computed styles so that the
 * HTML string is fully self-contained (no external Tailwind stylesheet needed).
 */
function inlineComputedStyles(root: Element): void {
  const all = Array.from(root.querySelectorAll('*'))
  // Include root itself
  const elements = [root, ...all]

  // Create a baseline element to compare defaults
  const baseline = document.createElement('div')
  baseline.style.cssText = 'position:absolute;visibility:hidden;pointer-events:none;'
  document.body.appendChild(baseline)
  const baselineStyles = window.getComputedStyle(baseline)

  for (const el of elements) {
    if (!(el instanceof Element)) continue
    const tag = el.tagName.toUpperCase()
    if (tag === 'STYLE' || tag === 'SCRIPT' || tag === 'DEFS') continue
    inlineElementStyles(el, baselineStyles)
  }

  document.body.removeChild(baseline)
}

function inlineElementStyles(el: Element, baselineStyles: CSSStyleDeclaration): void {
  const comp = window.getComputedStyle(el)
  const rules: string[] = []

  // 1. Layout & Positioning
  const display = comp.getPropertyValue('display')
  if (display && display !== 'inline' && display !== baselineStyles.getPropertyValue('display')) {
    rules.push(`display:${display}`)
  }

  const position = comp.getPropertyValue('position')
  if (position && position !== 'static') {
    rules.push(`position:${position}`)
    for (const side of ['top', 'right', 'bottom', 'left'] as const) {
      const v = comp.getPropertyValue(side)
      if (v && v !== 'auto') rules.push(`${side}:${v}`)
    }
  }

  const zIndex = comp.getPropertyValue('z-index')
  if (zIndex && zIndex !== 'auto') rules.push(`z-index:${zIndex}`)

  const boxSizing = comp.getPropertyValue('box-sizing')
  if (boxSizing && boxSizing !== 'content-box') rules.push(`box-sizing:${boxSizing}`)

  // 2. Dimensions
  for (const dim of ['width', 'min-width', 'max-width', 'height', 'min-height', 'max-height'] as const) {
    const v = comp.getPropertyValue(dim)
    if (v && v !== 'none' && v !== 'auto') {
      rules.push(`${dim}:${v}`)
    }
  }

  // 3. Flexbox & Grid
  if (display.includes('flex') || display.includes('grid')) {
    const fDir = comp.getPropertyValue('flex-direction')
    if (fDir && fDir !== 'row') rules.push(`flex-direction:${fDir}`)

    const fWrap = comp.getPropertyValue('flex-wrap')
    if (fWrap && fWrap !== 'nowrap') rules.push(`flex-wrap:${fWrap}`)

    const ai = comp.getPropertyValue('align-items')
    if (ai && ai !== 'normal' && ai !== 'stretch') rules.push(`align-items:${ai}`)

    const jc = comp.getPropertyValue('justify-content')
    if (jc && jc !== 'normal' && jc !== 'start') rules.push(`justify-content:${jc}`)

    const rGap = comp.getPropertyValue('row-gap')
    const cGap = comp.getPropertyValue('column-gap')
    if (rGap && rGap !== 'normal' && rGap !== '0px') {
      if (rGap === cGap) {
        rules.push(`gap:${rGap}`)
      } else {
        rules.push(`row-gap:${rGap};column-gap:${cGap}`)
      }
    }
  }

  const fGrow = comp.getPropertyValue('flex-grow')
  if (fGrow && fGrow !== '0') rules.push(`flex-grow:${fGrow}`)

  const fShrink = comp.getPropertyValue('flex-shrink')
  if (fShrink && fShrink !== '1') rules.push(`flex-shrink:${fShrink}`)

  const alignSelf = comp.getPropertyValue('align-self')
  if (alignSelf && alignSelf !== 'auto') rules.push(`align-self:${alignSelf}`)

  // 4. Padding (consolidated)
  const pt = comp.getPropertyValue('padding-top')
  const pr = comp.getPropertyValue('padding-right')
  const pb = comp.getPropertyValue('padding-bottom')
  const pl = comp.getPropertyValue('padding-left')
  if (pt !== '0px' || pr !== '0px' || pb !== '0px' || pl !== '0px') {
    if (pt === pr && pr === pb && pb === pl) {
      rules.push(`padding:${pt}`)
    } else if (pt === pb && pr === pl) {
      rules.push(`padding:${pt} ${pr}`)
    } else {
      rules.push(`padding:${pt} ${pr} ${pb} ${pl}`)
    }
  }

  // 5. Margin (consolidated)
  const mt = comp.getPropertyValue('margin-top')
  const mr = comp.getPropertyValue('margin-right')
  const mb = comp.getPropertyValue('margin-bottom')
  const ml = comp.getPropertyValue('margin-left')
  if (mt !== '0px' || mr !== '0px' || mb !== '0px' || ml !== '0px') {
    if (mt === mr && mr === mb && mb === ml) {
      rules.push(`margin:${mt}`)
    } else if (mt === mb && mr === ml) {
      rules.push(`margin:${mt} ${mr}`)
    } else {
      rules.push(`margin:${mt} ${mr} ${mb} ${ml}`)
    }
  }

  // 6. Borders (consolidated)
  const btw = comp.getPropertyValue('border-top-width')
  const bts = comp.getPropertyValue('border-top-style')
  const btc = comp.getPropertyValue('border-top-color')
  const brw = comp.getPropertyValue('border-right-width')
  const brs = comp.getPropertyValue('border-right-style')
  const brc = comp.getPropertyValue('border-right-color')
  const bbw = comp.getPropertyValue('border-bottom-width')
  const bbs = comp.getPropertyValue('border-bottom-style')
  const bbc = comp.getPropertyValue('border-bottom-color')
  const blw = comp.getPropertyValue('border-left-width')
  const bls = comp.getPropertyValue('border-left-style')
  const blc = comp.getPropertyValue('border-left-color')

  const hasTopBorder = bts !== 'none' && btw !== '0px'
  const hasRightBorder = brs !== 'none' && brw !== '0px'
  const hasBottomBorder = bbs !== 'none' && bbw !== '0px'
  const hasLeftBorder = bls !== 'none' && blw !== '0px'

  if (hasTopBorder && hasRightBorder && hasBottomBorder && hasLeftBorder &&
      btw === brw && brw === bbw && bbw === blw &&
      bts === brs && brs === bbs && bbs === bls &&
      btc === brc && brc === bbc && bbc === blc) {
    rules.push(`border:${btw} ${bts} ${btc}`)
  } else {
    if (hasTopBorder) rules.push(`border-top:${btw} ${bts} ${btc}`)
    if (hasRightBorder) rules.push(`border-right:${brw} ${brs} ${brc}`)
    if (hasBottomBorder) rules.push(`border-bottom:${bbw} ${bbs} ${bbc}`)
    if (hasLeftBorder) rules.push(`border-left:${blw} ${bls} ${blc}`)
  }

  // Border radius
  const rtl = comp.getPropertyValue('border-top-left-radius')
  const rtr = comp.getPropertyValue('border-top-right-radius')
  const rbr = comp.getPropertyValue('border-bottom-right-radius')
  const rbl = comp.getPropertyValue('border-bottom-left-radius')
  if (rtl !== '0px' || rtr !== '0px' || rbr !== '0px' || rbl !== '0px') {
    if (rtl === rtr && rtr === rbr && rbr === rbl) {
      rules.push(`border-radius:${rtl}`)
    } else {
      rules.push(`border-radius:${rtl} ${rtr} ${rbr} ${rbl}`)
    }
  }

  const bCollapse = comp.getPropertyValue('border-collapse')
  if (bCollapse && bCollapse === 'collapse') rules.push('border-collapse:collapse')

  // 7. Overflow
  const ox = comp.getPropertyValue('overflow-x')
  const oy = comp.getPropertyValue('overflow-y')
  if (ox !== 'visible' || oy !== 'visible') {
    if (ox === oy) {
      rules.push(`overflow:${ox}`)
    } else {
      rules.push(`overflow-x:${ox};overflow-y:${oy}`)
    }
  }

  // 8. Typography & Color
  const color = comp.getPropertyValue('color')
  if (color && color !== baselineStyles.getPropertyValue('color')) {
    rules.push(`color:${color}`)
  }

  const bgColor = comp.getPropertyValue('background-color')
  if (bgColor && bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent') {
    rules.push(`background-color:${bgColor}`)
  }

  const fSize = comp.getPropertyValue('font-size')
  if (fSize && fSize !== baselineStyles.getPropertyValue('font-size')) {
    rules.push(`font-size:${fSize}`)
  }

  const fWeight = comp.getPropertyValue('font-weight')
  if (fWeight && fWeight !== '400' && fWeight !== baselineStyles.getPropertyValue('font-weight')) {
    rules.push(`font-weight:${fWeight}`)
  }

  const fStyle = comp.getPropertyValue('font-style')
  if (fStyle && fStyle !== 'normal') rules.push(`font-style:${fStyle}`)

  const lHeight = comp.getPropertyValue('line-height')
  if (lHeight && lHeight !== 'normal' && lHeight !== baselineStyles.getPropertyValue('line-height')) {
    rules.push(`line-height:${lHeight}`)
  }

  const lSpacing = comp.getPropertyValue('letter-spacing')
  if (lSpacing && lSpacing !== 'normal') rules.push(`letter-spacing:${lSpacing}`)

  const tAlign = comp.getPropertyValue('text-align')
  if (tAlign && tAlign !== 'start') rules.push(`text-align:${tAlign}`)

  const wSpace = comp.getPropertyValue('white-space')
  if (wSpace && wSpace !== 'normal') rules.push(`white-space:${wSpace}`)

  const tOverflow = comp.getPropertyValue('text-overflow')
  if (tOverflow && tOverflow !== 'clip') rules.push(`text-overflow:${tOverflow}`)

  const wBreak = comp.getPropertyValue('word-break')
  if (wBreak && wBreak !== 'normal') rules.push(`word-break:${wBreak}`)

  // 9. Opacity, Transforms & Visuals
  const opacity = comp.getPropertyValue('opacity')
  if (opacity && opacity !== '1') rules.push(`opacity:${opacity}`)

  const transform = comp.getPropertyValue('transform')
  if (transform && transform !== 'none') rules.push(`transform:${transform}`)

  const transformOrigin = comp.getPropertyValue('transform-origin')
  if (transformOrigin && transform !== 'none') rules.push(`transform-origin:${transformOrigin}`)

  const bShadow = comp.getPropertyValue('box-shadow')
  if (bShadow && bShadow !== 'none') rules.push(`box-shadow:${bShadow}`)

  const wMode = comp.getPropertyValue('writing-mode')
  if (wMode && wMode !== 'horizontal-tb') rules.push(`writing-mode:${wMode}`)

  const vAlign = comp.getPropertyValue('vertical-align')
  if (vAlign && vAlign !== 'baseline') rules.push(`vertical-align:${vAlign}`)

  // Merge with existing style attribute (preserving CSS variables like --ref-char-color)
  const existing = el.getAttribute('style') || ''
  const merged = existing ? `${existing};${rules.join(';')}` : rules.join(';')
  if (merged) {
    el.setAttribute('style', merged)
  }
}

// ---------------------------------------------------------------------------
// Build standalone HTML document
// ---------------------------------------------------------------------------

function buildStandaloneDocument(
  pagesHtml: string[],
  options: WorksheetPreviewResponse['options'],
): string {
  const orientation = options.orientation || 'portrait'
  const isLandscape = orientation === 'landscape'
  const pageW = isLandscape ? '297mm' : '210mm'
  const pageH = isLandscape ? '210mm' : '297mm'

  const joinedPages = pagesHtml.join('\n')

  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Flama Worksheet</title>
<style>
@page {
  size: ${pageW} ${pageH};
  margin: 0;
}
html, body {
  margin: 0;
  padding: 0;
  font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, "Noto Sans", "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", sans-serif;
  color: #0f172a;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* Screen preview layout */
@media screen {
  body {
    padding: 24px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24px;
    background: #f8fafc;
  }
  .sheet-page {
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
    margin-bottom: 24px;
  }
  .screen-toolbar {
    position: sticky;
    top: 12px;
    z-index: 100;
    display: flex;
    gap: 12px;
    background: #1e293b;
    color: #ffffff;
    padding: 10px 20px;
    border-radius: 9999px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
  }
  .screen-btn {
    background: #ea580c;
    color: #ffffff;
    border: none;
    padding: 6px 16px;
    border-radius: 9999px;
    font-weight: 600;
    cursor: pointer;
    font-size: 13px;
  }
  .screen-btn:hover {
    background: #c2410c;
  }
}

/* Print layout */
@media print {
  * {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
    color-adjust: exact !important;
  }
  html, body {
    width: ${pageW};
    height: ${pageH};
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
  }
  .screen-toolbar {
    display: none !important;
  }
  .sheet-page {
    background: #ffffff !important;
    width: ${pageW} !important;
    min-height: ${pageH} !important;
    max-height: ${pageH} !important;
    height: ${pageH} !important;
    box-sizing: border-box !important;
    box-shadow: none !important;
    border: none !important;
    margin: 0 !important;
    page-break-after: always !important;
    break-after: page !important;
    overflow: hidden !important;
    position: relative !important;
  }
  .sheet-page:last-child {
    page-break-after: auto !important;
    break-after: auto !important;
  }
}

/* SVG sizing overrides */
svg {
  display: block;
}
</style>
</head>
<body>
<div class="screen-toolbar">
  <span style="font-weight:600;font-size:14px;">Flama Worksheet</span>
  <button class="screen-btn" onclick="window.print()">🖨️ In ngay</button>
</div>
${joinedPages}
</body>
</html>`
}

// ---------------------------------------------------------------------------
// Main serialization function
// ---------------------------------------------------------------------------

/**
 * Render the same React WorksheetPageRenderer components used for preview,
 * capture their DOM output, inline all computed styles, and produce a
 * standalone HTML document string identical to what the user sees on screen.
 */
export async function serializeWorksheetToHtml(
  previewData: WorksheetPreviewResponse,
): Promise<string> {
  const { template, options, pages } = previewData
  if (!pages || pages.length === 0) {
    throw new Error('No pages to serialize')
  }

  const pagesHtml: string[] = []

  for (const page of pages) {
    // 1. Create an off-screen container to render the page
    const container = document.createElement('div')
    container.style.cssText =
      'position:fixed;left:-9999px;top:0;visibility:hidden;pointer-events:none;' +
      `width:${options.orientation === 'landscape' ? '297mm' : '210mm'};` +
      `height:${options.orientation === 'landscape' ? '210mm' : '297mm'};`
    document.body.appendChild(container)

    // 2. Render WorksheetPageRenderer synchronously into the container
    const root = createRoot(container)
    flushSync(() => {
      root.render(
        createElement(WorksheetPageRenderer, {
          page,
          template,
          options,
          zoom: 1,
          isPrintMode: true,
        }),
      )
    })

    // 3. Wait a tick for browser layout to settle (needed for getComputedStyle)
    await new Promise((resolve) => setTimeout(resolve, 50))

    // 4. Get the rendered page element (first child of the container)
    const pageEl = container.firstElementChild as HTMLElement | null
    if (!pageEl) {
      root.unmount()
      document.body.removeChild(container)
      continue
    }

    // 5. Add .sheet-page class to the root page element
    pageEl.classList.add('sheet-page')

    // 6. Inline computed styles directly on pageEl and its descendants
    inlineComputedStyles(pageEl)

    // 7. Extract the serialized HTML string
    pagesHtml.push(pageEl.outerHTML)

    // 8. Cleanup
    root.unmount()
    document.body.removeChild(container)
  }

  return buildStandaloneDocument(pagesHtml, options)
}
