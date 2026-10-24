export type HeatmapDay = {
  date: string
  cards: number
  minutes: number
  is_future: boolean
}

export type HeatmapToday = {
  date?: string
  cards: number
  minutes: number
}

export type HeatmapMetrics = {
  daily_average_cards: number
  days_learned_percent: number
  longest_streak_days: number
  current_streak_days: number
}

export type HeatmapOverviewData = {
  year: number
  timezone?: string
  today?: HeatmapToday
  heatmap: HeatmapDay[]
  metrics?: HeatmapMetrics
}
