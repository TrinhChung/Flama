import { useQuery } from '@tanstack/react-query'
import { appApi } from '@/app/api'
import { dashboardApi } from './dashboardApi'

export { dashboardApi } from './dashboardApi'
export type { NoteTypeOption } from './dashboardApi'

export const dashboardQueryKey = ['frontend', 'dashboard'] as const

export function fetchDashboard() {
  return dashboardApi.getDashboard()
}

export function useDashboard() {
  return useQuery({
    queryKey: dashboardQueryKey,
    queryFn: fetchDashboard,
  })
}

export function useDashboardOverview(year: number, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['frontend', 'dashboard', 'overview', year],
    // Still on the legacy facade: StatisticsPage shares this request.
    queryFn: () => appApi.getDashboardOverview(year),
    enabled: options?.enabled,
  })
}
