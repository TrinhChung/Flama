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
