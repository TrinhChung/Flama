import { useQuery } from '@tanstack/react-query'
import { appApi } from '../../app/api'
import type {
  StatisticsConfig,
  StatisticsFilters,
  TodayFutureStats,
} from './types'

export function useStatisticsConfig() {
  return useQuery({
    queryKey: ['frontend', 'statistics', 'config'],
    queryFn: () => appApi.getStatisticsConfig() as Promise<StatisticsConfig>,
  })
}

export function useTodayFutureStats(filters: StatisticsFilters) {
  return useQuery({
    queryKey: ['stats', 'today-future', filters],
    queryFn: () =>
      appApi.getTodayFutureStats(filters) as Promise<TodayFutureStats>,
    enabled: filters.scope === 'collection' || filters.deckId !== null,
  })
}
