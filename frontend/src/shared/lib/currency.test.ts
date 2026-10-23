import { describe, expect, it } from 'vitest'
import {
  formatCurrency,
  formatVND,
  parseCurrency,
} from './currency'

describe('currency utilities', () => {
  describe('formatCurrency', () => {
    it('formats VND currency with default locale', () => {
      const formatted = formatCurrency(50000)
      // Node/browser Intl output for VND in vi-VN: "50.000 ₫" or "50.000\u00a0₫"
      expect(formatted).toMatch(/50[.,]000/)
      expect(formatted).toContain('₫')
    })

    it('formats USD currency correctly', () => {
      const formatted = formatCurrency(12.5, { currency: 'USD', locale: 'en' })
      expect(formatted).toBe('$12.50')
    })

    it('returns custom fallback when given null or undefined', () => {
      expect(formatCurrency(null, { fallback: 'Miễn phí' })).toBe('Miễn phí')
      expect(formatCurrency(undefined)).toBe('0 ₫')
      expect(formatCurrency('invalid-number')).toBe('0 ₫')
    })
  })

  describe('formatVND', () => {
    it('formats numbers with custom suffix', () => {
      expect(formatVND(100000, 'VND')).toMatch(/100[.,]000 VND/)
      expect(formatVND(0, 'VND')).toBe('0 VND')
    })

    it('handles null and invalid inputs gracefully', () => {
      expect(formatVND(null)).toBe('0 ₫')
      expect(formatVND('abc')).toBe('0 ₫')
    })
  })

  describe('parseCurrency', () => {
    it('strips non-numeric characters and parses integer', () => {
      expect(parseCurrency('50.000 VND')).toBe(50000)
      expect(parseCurrency('1,234,567 đ')).toBe(1234567)
      expect(parseCurrency('  $99.00  ')).toBe(9900)
    })

    it('returns 0 for empty or invalid inputs', () => {
      expect(parseCurrency('')).toBe(0)
      expect(parseCurrency(null)).toBe(0)
      expect(parseCurrency(undefined)).toBe(0)
      expect(parseCurrency('abc')).toBe(0)
    })
  })
})
