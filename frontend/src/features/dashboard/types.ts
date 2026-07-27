export type DeckNode = {
  id: number
  parent_id: number | null
  name: string
  depth: number
  study_url: string
  counts: {
    new: number
    learning: number
    due: number
  }
  move: {
    alias: string
    token: string
    parent_alias: string | null
    parent_token: string | null
  }
  actions: {
    rename: string
    move: string
    delete: string
    reset: string
    share: string
  }
  children: DeckNode[]
}

export type DashboardPayload = {
  decks: DeckNode[]
  totals: {
    new: number
    learning: number
    due: number
  }
  admin_mode: boolean
  stats_initial_year: number
  actions: {
    create: string
    move: string
  }
}

export type DashboardHeatmapDay = {
  day: string
  date: string
  cards: number
  study_time: number
  minutes: number
  sec_per_card: number
  is_future: boolean
  source: 'reviewed' | 'due'
}

export type DashboardOverview = {
  year: number
  timezone: string
  today: {
    cards: number
    minutes: number
    sec_per_card: number
  }
  heatmap: DashboardHeatmapDay[]
  metrics: {
    daily_average_cards: number
    days_learned_percent: number
    longest_streak_days: number
    current_streak_days: number
    days_counted: number
  }
}

export type DeckAction = 'rename' | 'move' | 'reset' | 'delete'

export type SelectedDeckAction = {
  type: DeckAction
  deck: DeckNode
}
