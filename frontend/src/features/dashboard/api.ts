import { useQuery } from '@tanstack/react-query'
import { appApi } from '../../app/api'

export const dashboardQueryKey = ['frontend', 'dashboard'] as const

export function fetchDashboard() {
  return appApi.getDashboard()
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
    queryFn: () => appApi.getDashboardOverview(year),
    enabled: options?.enabled,
  })
}
