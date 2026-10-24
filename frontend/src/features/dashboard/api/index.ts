import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { dashboardApi } from './dashboardApi'

export { dashboardApi } from './dashboardApi'
export type { NoteTypeOption } from './dashboardApi'

export const dashboardQueryKey = ['frontend', 'dashboard'] as const

// The heatmap overview is keyed like StatisticsPage's so both screens share one
// cache entry. It deliberately sits outside dashboardQueryKey: creating, renaming
// or moving a deck only reshapes the tree and must not refetch the overview.
// Study, import and timezone changes refresh it via ['frontend', 'statistics'].
export const studyOverviewBaseKey = ['frontend', 'statistics', 'overview'] as const

export function studyOverviewQueryKey(year: number) {
  return [...studyOverviewBaseKey, year] as const
}

export function fetchDashboard() {
  return dashboardApi.getDashboard()
}

export function useDashboard() {
  return useQuery({
    queryKey: dashboardQueryKey,
    queryFn: fetchDashboard,
  })
}

export function useDashboardOverview(year: number) {
  return useQuery({
    queryKey: studyOverviewQueryKey(year),
    // Still on the legacy facade: StatisticsPage shares this request.
    queryFn: () => appApi.getDashboardOverview(year),
    // Switching year keeps the previous grid on screen instead of collapsing to a skeleton.
    placeholderData: keepPreviousData,
  })
}
