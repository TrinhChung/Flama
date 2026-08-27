export type StatsDeck = {
  id: number
  name: string
}

export type StatisticsConfig = {
  decks: StatsDeck[]
  initial_deck_id: number | null
}

export type FutureDuePoint = {
  date: string
  day_offset: number
  due_count: number
  cumulative: number
  breakdown?: {
    new: number
    learn: number
    review: number
    relearn: number
  }
}

export type TodayFutureStats = {
  scope: 'deck' | 'collection'
  deck_id: number | null
  history_range: '12m' | 'all'
  future_range: '30' | '90' | '365' | 'all'
  backlog: boolean
  timezone: string
  today: {
    cards: number
    minutes: number
    sec_per_card: number
    has_studied: boolean
    message: string
  }
  future_due: {
    series: FutureDuePoint[]
    window_days: number
  }
  totals: {
    total_reviews: number
    avg_reviews_per_day: number
    due_tomorrow: number
    daily_load: number
  }
}

export type StatisticsFilters = {
  scope: 'deck' | 'collection'
  deckId: number | null
  historyRange: '12m' | 'all'
  futureRange: '30' | '90' | '365' | 'all'
  backlog: boolean
}

export type UserStudyTimePreset = 'today' | '7d' | '30d' | '90d' | '12m' | 'all' | 'custom'

export type UserDailyStudyTimeItem = {
  date: string
  total_reviews: number
  total_duration_minutes: number
  total_duration_hours: number
  avg_study_minutes_per_user: number
  retention_pass_rate: number
}

export type UserStudyTimeSummary = {
  total_study_minutes: number
  total_study_hours: number
  total_reviews: number
  avg_daily_minutes_system: number
  avg_daily_minutes: number
  avg_study_minutes_active_day: number
  active_days_count: number
  retention_pass_rate: number
}

export type UserStudyTimeResponse = {
  range_preset: string
  start_date: string
  end_date: string
  scope: 'deck' | 'collection'
  deck_id: number | null
  timezone: string
  summary: UserStudyTimeSummary
  daily_time_series: UserDailyStudyTimeItem[]
}

export type UserStudyTimeFilters = {
  scope: 'deck' | 'collection'
  deckId: number | null
  range: UserStudyTimePreset
  startDate?: string
  endDate?: string
}
