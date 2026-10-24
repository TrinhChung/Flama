import { API_BASE_URL } from '@/config/env'
import { apiRequest, getBrowserTimezone } from '@/shared/api/client'
import type { HeatmapOverviewData } from '@/shared/types/heatmap'

// Dashboard and Statistics share one cache entry per year. Deck-tree changes do
// not touch it; study, import and timezone changes refresh it via
// ['frontend', 'statistics'], and deck delete/reset via studyOverviewBaseKey.
export const studyOverviewBaseKey = ['frontend', 'statistics', 'overview'] as const

export function studyOverviewQueryKey(year: number) {
  return [...studyOverviewBaseKey, year] as const
}

export async function fetchStudyOverview(year: number): Promise<HeatmapOverviewData> {
  const query = new URLSearchParams({ year: String(year) })
  const tz = getBrowserTimezone()
  if (tz) query.set('timezone', tz)
  return apiRequest<HeatmapOverviewData>(
    `${API_BASE_URL}/statistics/overview?${query}`,
    { includeTimezone: false },
  )
}
