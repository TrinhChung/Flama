const staticKanjiSvgCache = new Map<string, string | null>()
const MAX_STATIC_SVG_CACHE_SIZE = 1200

/** Static (non-animated) kanji SVG on a practice grid, memoized per input. */
export function extractStaticKanjiSvgClient(
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
