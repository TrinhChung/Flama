type Orientation = 'portrait' | 'landscape'

export const MIN_ZOOM = 0.25
export const MAX_ZOOM = 1.5
const MOBILE_BREAKPOINT = 768

export function isMobileViewport(): boolean {
  return typeof window !== 'undefined' && window.innerWidth < MOBILE_BREAKPOINT
}

/** Zoom that fits one A4 page beside the studio sidebar (or full width on mobile). */
export function getFitZoom(orientation?: Orientation, customWidth?: number): number {
  const isLandscape = orientation === 'landscape'
  const a4WidthPx = (isLandscape ? 297 : 210) * 3.7795
  const winWidth = typeof window !== 'undefined' ? (customWidth || window.innerWidth) : 360
  const padding = winWidth < 640 ? 24 : winWidth < 1024 ? 40 : 64
  const availableWidth = Math.max(220, (winWidth < MOBILE_BREAKPOINT ? winWidth : winWidth - 420) - padding)
  const fit = Math.floor((availableWidth / a4WidthPx) * 100) / 100
  return Math.min(1.4, Math.max(MIN_ZOOM, fit))
}

/** Zoom applied when the first preview of a session arrives. */
export function getFirstPreviewZoom(orientation?: Orientation): number {
  if (isMobileViewport()) return getFitZoom(orientation, window.innerWidth)
  return orientation === 'landscape' ? 0.72 : 0.8
}

export function stepZoom(zoom: number, delta: number): number {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number((zoom + delta).toFixed(2))))
}
