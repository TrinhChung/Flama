import { describe, expect, it } from 'vitest'
import {
  formatDate,
  formatDateLabel,
  formatRelativeTime,
  resolveLocale,
} from './date'

describe('date utilities', () => {
  describe('resolveLocale', () => {
    it('resolves standard locales to BCP-47 tags', () => {
      expect(resolveLocale('vi')).toBe('vi-VN')
      expect(resolveLocale('ja')).toBe('ja-JP')
      expect(resolveLocale('en')).toBe('en-US')
      expect(resolveLocale()).toBe('vi-VN')
    })
  })

  describe('formatDate', () => {
    const testDate = '2026-10-19T14:30:00.000Z'

    it('formats ISO string correctly', () => {
      const formatted = formatDate(testDate, {}, 'en')
      expect(formatted).toContain('2026')
    })

    it('returns custom fallback for null or undefined', () => {
      expect(formatDate(null)).toBe('—')
      expect(formatDate(undefined, { fallback: 'Chưa có' })).toBe('Chưa có')
    })

    it('returns raw string for invalid date strings', () => {
      expect(formatDate('invalid-date')).toBe('invalid-date')
    })
  })

  describe('formatRelativeTime', () => {
    const now = 1760884800000 // Fixed timestamp

    it('formats past minutes', () => {
      const fiveMinutesAgo = now - 5 * 60 * 1000
      const resEn = formatRelativeTime(fiveMinutesAgo, 'en', now)
      expect(resEn).toMatch(/5 minutes? ago/)
    })

    it('formats past days', () => {
      const twoDaysAgo = now - 2 * 24 * 60 * 60 * 1000
      const resEn = formatRelativeTime(twoDaysAgo, 'en', now)
      expect(resEn).toMatch(/2 days? ago/)
    })

    it('returns fallback for invalid or null value', () => {
      expect(formatRelativeTime(null)).toBe('—')
      expect(formatRelativeTime('invalid-date')).toBe('—')
    })
  })

  describe('formatDateLabel', () => {
    it('converts YYYY-MM-DD to DD/MM', () => {
      expect(formatDateLabel('2026-10-19')).toBe('19/10')
      expect(formatDateLabel('2026-01-05')).toBe('05/01')
    })

    it('handles invalid or non-split strings gracefully', () => {
      expect(formatDateLabel('')).toBe('')
      expect(formatDateLabel('not-a-date')).toBe('not-a-date')
    })
  })
})
