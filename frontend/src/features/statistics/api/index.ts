import { useQuery } from '@tanstack/react-query'
import type { StatisticsFilters, UserStudyTimeFilters } from '../types'
import { statisticsApi } from './statisticsApi'

export { statisticsApi } from './statisticsApi'

export function useStatisticsConfig() {
  return useQuery({
    queryKey: ['frontend', 'statistics', 'config'],
    queryFn: () => statisticsApi.getStatisticsConfig(),
  })
}

export function useTodayFutureStats(filters: StatisticsFilters) {
  return useQuery({
    queryKey: ['stats', 'today-future', filters],
    queryFn: () => statisticsApi.getTodayFutureStats(filters),
    enabled: filters.scope === 'collection' || filters.deckId !== null,
  })
}

export function useUserStudyTimeStats(filters: UserStudyTimeFilters) {
  return useQuery({
    queryKey: ['stats', 'study-time', filters],
    queryFn: () => statisticsApi.getUserStudyTimeStats(filters),
    enabled: filters.scope === 'collection' || filters.deckId !== null,
  })
}
