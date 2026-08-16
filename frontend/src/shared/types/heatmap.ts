export type HeatmapDay = {
  day: string
  date: string
  cards: number
  study_time: number
  minutes: number
  sec_per_card: number
  is_future: boolean
  source: 'reviewed' | 'due'
}

export type HeatmapToday = {
  date?: string
  cards: number
  minutes: number
  sec_per_card: number
}

export type HeatmapMetrics = {
  daily_average_cards: number
  days_learned_percent: number
  longest_streak_days: number
  current_streak_days: number
  days_counted?: number
}

export type HeatmapOverviewData = {
  year: number
  timezone?: string
  today?: HeatmapToday
  heatmap: HeatmapDay[]
  metrics?: HeatmapMetrics
}
