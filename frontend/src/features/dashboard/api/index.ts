import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from './dashboardApi'

export { dashboardApi } from './dashboardApi'
export type { NoteTypeOption } from './dashboardApi'

// The heatmap overview lives in @/entities/study-overview under its own key, so
// invalidating this one after create/rename/move refreshes only the deck tree.
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
