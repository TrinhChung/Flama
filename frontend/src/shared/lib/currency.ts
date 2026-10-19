/**
 * Centralized Currency & Numeric formatting utilities for Flama.
 * Uses browser-native Intl.NumberFormat to avoid manual string concatenation.
 */

import { resolveLocale } from './date'

export interface FormatCurrencyOptions {
  currency?: string
  locale?: string
  fallback?: string
  maximumFractionDigits?: number
  minimumFractionDigits?: number
}

/**
 * Formats a numeric value into a localized currency string.
 * Example: formatCurrency(50000, { currency: 'VND', locale: 'vi' }) => "50.000 ₫"
 */
export function formatCurrency(
  amount: number | string | null | undefined,
  options?: FormatCurrencyOptions,
): string {
  const fallback = options?.fallback ?? '0 ₫'
  if (amount === null || amount === undefined || amount === '') {
    return fallback
  }

  const num = typeof amount === 'number' ? amount : Number(amount)
  if (Number.isNaN(num)) {
    return fallback
  }

  const currency = options?.currency || 'VND'
  const targetLocale = resolveLocale(options?.locale)
  try {
    const isVND = currency === 'VND'
    return new Intl.NumberFormat(targetLocale, {
      style: 'currency',
      currency,
      maximumFractionDigits: options?.maximumFractionDigits ?? (isVND ? 0 : 2),
      minimumFractionDigits: options?.minimumFractionDigits ?? (isVND ? 0 : 2),
    }).format(num)
  } catch {
    return `${num.toLocaleString(targetLocale)} ${currency}`
  }
}

/**
 * Convenience helper specifically for Vietnamese Dong (VND).
 * Returns cleanly formatted numbers like "50.000 VND" or "50.000 ₫".
 */
export function formatVND(
  amount: number | string | null | undefined,
  suffix = '₫',
): string {
  if (amount === null || amount === undefined || amount === '') {
    return `0 ${suffix}`
  }

  const num = typeof amount === 'number' ? amount : Number(amount)
  if (Number.isNaN(num)) {
    return `0 ${suffix}`
  }

  const formattedNum = new Intl.NumberFormat('vi-VN', {
    maximumFractionDigits: 0,
  }).format(num)

  return `${formattedNum} ${suffix}`
}

/**
 * Parses raw text input (e.g. from user input "50.000 VND" or "50,000") into a clean integer amount.
 */
export function parseCurrency(text: string | null | undefined): number {
  if (!text) return 0
  const cleaned = String(text).replace(/\D/g, '')
  if (!cleaned) return 0
  const parsed = parseInt(cleaned, 10)
  return Number.isNaN(parsed) ? 0 : parsed
}
