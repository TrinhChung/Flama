/**
 * Centralized Date & Relative Time formatting utilities for Flama.
 * Uses browser-native Intl.DateTimeFormat & Intl.RelativeTimeFormat.
 */

const LOCALE_MAP: Record<string, string> = {
  vi: 'vi-VN',
  ja: 'ja-JP',
  en: 'en-US',
}

export function resolveLocale(locale?: string): string {
  if (!locale) return 'vi-VN'
  return LOCALE_MAP[locale.toLowerCase()] || locale
}

export interface FormatDateOptions extends Intl.DateTimeFormatOptions {
  fallback?: string
}

/**
 * Formats a date into a localized string.
 */
export function formatDate(
  value: string | number | Date | null | undefined,
  options?: FormatDateOptions,
  locale?: string,
): string {
  const fallback = options?.fallback ?? '—'
  if (!value) return fallback

  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) {
    return typeof value === 'string' ? value : fallback
  }

  const { fallback: _, ...intlOptions } = options || {}
  const targetLocale = resolveLocale(locale)

  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    ...intlOptions,
  }

  try {
    return new Intl.DateTimeFormat(targetLocale, defaultOptions).format(date)
  } catch {
    return fallback
  }
}

/**
 * Formats a date into a human-readable relative time (e.g., "5 phút trước", "2 ngày trước").
 */
export function formatRelativeTime(
  value: string | number | Date | null | undefined,
  locale?: string,
  now = Date.now(),
): string {
  if (!value) return '—'

  const timestamp = value instanceof Date ? value.getTime() : new Date(value).getTime()
  if (Number.isNaN(timestamp)) return '—'

  const diffSeconds = Math.round((timestamp - now) / 1000)
  const absDiffSeconds = Math.abs(diffSeconds)

  const targetLocale = resolveLocale(locale)

  // Use Intl.RelativeTimeFormat if supported
  if (typeof Intl !== 'undefined' && Intl.RelativeTimeFormat) {
    try {
      const rtf = new Intl.RelativeTimeFormat(targetLocale, { numeric: 'auto' })

      if (absDiffSeconds < 60) {
        return rtf.format(diffSeconds, 'second')
      }
      const diffMinutes = Math.round(diffSeconds / 60)
      if (Math.abs(diffMinutes) < 60) {
        return rtf.format(diffMinutes, 'minute')
      }
      const diffHours = Math.round(diffMinutes / 60)
      if (Math.abs(diffHours) < 24) {
        return rtf.format(diffHours, 'hour')
      }
      const diffDays = Math.round(diffHours / 24)
      if (Math.abs(diffDays) < 30) {
        return rtf.format(diffDays, 'day')
      }
      const diffMonths = Math.round(diffDays / 30)
      if (Math.abs(diffMonths) < 12) {
        return rtf.format(diffMonths, 'month')
      }
      const diffYears = Math.round(diffDays / 365)
      return rtf.format(diffYears, 'year')
    } catch {
      // Fallback if rtf throws
    }
  }

  // Fallback simple string format
  return formatDate(value, { year: 'numeric', month: 'short', day: 'numeric' }, locale)
}

/**
 * Formats date string (YYYY-MM-DD) into DD/MM for chart labels.
 */
export function formatDateLabel(dateStr: string): string {
  if (!dateStr) return ''
  const parts = dateStr.split('-')
  if (
    parts.length === 3 &&
    parts[0].length === 4 &&
    !Number.isNaN(Number(parts[1])) &&
    !Number.isNaN(Number(parts[2]))
  ) {
    return `${parts[2]}/${parts[1]}`
  }
  return dateStr
}
