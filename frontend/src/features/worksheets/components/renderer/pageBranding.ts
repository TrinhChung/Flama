import type { WorksheetLayoutOptions } from '../../types'

/** Watermark and source-link details printed on every page (anti-theft protection). */
export interface PageBranding {
  watermarkText: string
  watermarkOpacity: number
  watermarkLayout: NonNullable<WorksheetLayoutOptions['watermark_layout']>
  currentUrl: string
  currentDomain: string
}

export function getPageBranding(options: WorksheetLayoutOptions): PageBranding {
  const watermarkText = (
    options.watermark_text ||
    (typeof window !== 'undefined' ? window.location.hostname : 'flama.app') ||
    'flama.app'
  ).toUpperCase()

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

  return {
    watermarkText,
    watermarkOpacity: Math.max(0.015, Math.min(0.15, options.watermark_opacity ?? 0.04)),
    watermarkLayout: options.watermark_layout || 'diagonal_grid',
    currentUrl,
    currentDomain,
  }
}
