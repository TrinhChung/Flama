import { API_BASE_URL } from '@/config/env'
import { apiRequest } from '@/shared/api/client'
import type {
  StatisticsConfig,
  StatisticsFilters,
  TodayFutureStats,
  UserStudyTimeFilters,
  UserStudyTimeResponse,
} from '../types'

const API_BASE = API_BASE_URL

type StatisticsResponse = {
  decks: Array<{ id: number; name: string; parent_id?: number | null }>
  selected_deck_id: number | null
}

function browserTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
}

export const statisticsApi = {
  async getStatisticsConfig(): Promise<StatisticsConfig> {
    const payload = await apiRequest<StatisticsResponse>(
      `${API_BASE}/statistics`,
    )
    return {
      decks: payload.decks.map(({ id, name }) => ({ id, name })),
      initial_deck_id: payload.selected_deck_id,
    }
  },

  async getTodayFutureStats(
    filters: StatisticsFilters,
  ): Promise<TodayFutureStats> {
    const params = new URLSearchParams({
      scope: filters.scope,
      history_range: filters.historyRange,
      future_range: filters.futureRange,
      backlog: String(filters.backlog),
      timezone: browserTimezone(),
    })
    if (filters.deckId !== null) {
      params.set('deck_id', String(filters.deckId))
    }
    return apiRequest<TodayFutureStats>(
      `${API_BASE}/statistics/today-future?${params.toString()}`,
    )
  },

  async getUserStudyTimeStats(
    filters: UserStudyTimeFilters,
  ): Promise<UserStudyTimeResponse> {
    const params = new URLSearchParams({
      scope: filters.scope,
      range: filters.range,
      timezone: browserTimezone(),
    })
    if (filters.deckId !== null) {
      params.set('deck_id', String(filters.deckId))
    }
    if (filters.startDate) {
      params.set('start_date', filters.startDate)
    }
    if (filters.endDate) {
      params.set('end_date', filters.endDate)
    }
    return apiRequest<UserStudyTimeResponse>(
      `${API_BASE}/statistics/study-time?${params.toString()}`,
    )
  },
}
