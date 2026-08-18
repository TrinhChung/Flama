export type AnalyticsRangePreset = 'today' | '7d' | '30d' | '90d' | '12m' | 'all' | 'custom'

export type AnalyticsKpiTotals = {
  users: number
  decks: number
  notes: number
  cards: number
  dau: number
  mau: number
  stickiness_ratio: number
}

export type AnalyticsPeriodMetrics = {
  new_users: number
  active_users: number
  total_reviews: number
  total_duration_minutes: number
  total_duration_hours: number
  avg_study_minutes_per_active_user: number
  retention_pass_rate: number
  paid_orders: number
  revenue_minor: number
  new_cards: number
}

export type AnalyticsDeltas = {
  new_users_delta_pct: number | null
  active_users_delta_pct: number | null
  total_reviews_delta_pct: number | null
  total_duration_delta_pct: number | null
  avg_study_time_delta_pct: number | null
  revenue_delta_pct: number | null
}

export type TopLearner = {
  user_id: number
  username: string
  email: string
  reviews_count: number
  total_study_minutes: number
  last_active_at: string | null
}

export type AnalyticsOverviewResponse = {
  range_preset: string
  start_date: string
  end_date: string
  totals: AnalyticsKpiTotals
  period_metrics: AnalyticsPeriodMetrics
  deltas: AnalyticsDeltas
  top_learners: TopLearner[]
}

export type DailyUserGrowthItem = {
  date: string
  new_users: number
  cumulative_users: number
  active_users: number
  reviews_count: number
}

export type UserGrowthResponse = {
  range_preset: string
  start_date: string
  end_date: string
  data: DailyUserGrowthItem[]
}

export type DailyStudyTimeItem = {
  date: string
  active_users: number
  total_reviews: number
  total_duration_minutes: number
  total_duration_hours: number
  avg_study_minutes_per_user: number
  retention_pass_rate: number
  cards_per_user: number
}

export type HourlyDistributionItem = {
  hour: number
  hour_label: string
  reviews_count: number
  unique_users: number
  duration_minutes: number
}

export type BreakdownItem = {
  mode?: string
  rating?: string
  scheduler?: string
  count: number
}

export type StudyTimeResponse = {
  range_preset: string
  start_date: string
  end_date: string
  summary: {
    total_study_minutes: number
    total_study_hours: number
    total_reviews: number
    avg_daily_minutes_system: number
  }
  daily_time_series: DailyStudyTimeItem[]
  hourly_distribution: HourlyDistributionItem[]
  modes_breakdown: BreakdownItem[]
  ratings_breakdown: BreakdownItem[]
  schedulers_breakdown: BreakdownItem[]
}

export type DailyContentGrowthItem = {
  date: string
  new_decks: number
  new_notes: number
  new_cards: number
  deck_installs: number
  connect_imports: number
}

export type ContentGrowthResponse = {
  range_preset: string
  start_date: string
  end_date: string
  data: DailyContentGrowthItem[]
}

export type RetentionCohortItem = {
  cohort: string
  cohort_size: number
  d1_retained: number
  d1_rate: number
  d7_retained: number
  d7_rate: number
  d14_retained: number
  d14_rate: number
  d30_retained: number
  d30_rate: number
}

export type RetentionCohortsResponse = {
  cohorts: RetentionCohortItem[]
  intervals: string[]
}
